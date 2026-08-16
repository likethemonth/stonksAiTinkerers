"""Leakage-safe walk-forward backtest for binary earnings prediction markets.

The production ensemble treats a beat contract as a probability constraint,
not a point observation.  This module evaluates the existing research-only
conversion::

    implied actual = strike + pre-event surprise sigma * normal_ppf(P(beat))

Each surprise sigma is recomputed at that event's cutoff, so later earnings
results cannot leak into an earlier estimate.  A promotion gate is emitted, but
the current live estimates remain shadow-only and receive zero numeric weight.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

from forecast.metrics import ticker
from forecast.polymarket import market_signal, norm_ppf, surprise_sigma
from forecast.schema import Company

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVE = REPO_ROOT / "forecast" / "data" / "polymarket" / "historical-signals.json"
DEFAULT_JSON_OUTPUT = REPO_ROOT / "research" / "prediction-market-backtest.json"
DEFAULT_MD_OUTPUT = REPO_ROOT / "research" / "prediction-market-backtest.md"

MIN_RESOLVED = 12
MAX_MEAN_BRIER = 0.10
MIN_MAE_IMPROVEMENT = 0.10
MAX_SIGN_TEST_P = 0.05

_COMPANY_BY_TICKER = {
    "HD": Company.HD,
    "ADI": Company.ADI,
    "DE": Company.DE,
}
_MODEL_METRIC = {
    "adj_eps": "adj_eps",
    "diluted_eps_gaap": "gaap_eps",
}
_EXPECTED_BASIS = {
    "adj_eps": "non_gaap_adjusted_diluted_eps",
    "diluted_eps_gaap": "gaap_diluted_eps",
}


def _timestamp(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty market backtest")
    return sum(values) / len(values)


def _one_sided_sign_test(wins: int, losses: int) -> float:
    """Exact P(X >= wins) for X ~ Binomial(wins + losses, 0.5)."""
    trials = wins + losses
    if trials == 0:
        return 1.0
    return sum(math.comb(trials, k) for k in range(wins, trials + 1)) / (2**trials)


def _load_records(archive_path: Path, as_of: date) -> list[dict[str, Any]]:
    payload = json.loads(archive_path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "historical-market-signals-v1":
        raise ValueError("unsupported historical market archive schema")
    records = [
        row
        for row in payload.get("records", [])
        if date.fromisoformat(row["actualReportedAt"]) <= as_of
    ]
    if not records:
        raise ValueError(f"no resolved market records at {as_of.isoformat()}")
    return records


def _score_row(row: dict[str, Any]) -> dict[str, Any]:
    company = _COMPANY_BY_TICKER.get(row.get("ticker"))
    metric_key = row.get("metricKey")
    if company is None or metric_key not in _MODEL_METRIC:
        raise ValueError(f"unsupported market row: {row.get('ticker')} {metric_key}")
    if row.get("relation") != "greater_than":
        raise ValueError("only strict greater-than contracts are supported")
    if row.get("actualMatch") != "exact":
        raise ValueError(f"{row['ticker']} {row['period']}: actual must be exact")
    if row.get("actualBasis") != _EXPECTED_BASIS[metric_key]:
        raise ValueError(f"{row['ticker']} {row['period']}: actual basis mismatch")
    if not str(row.get("actualSourceUrl", "")).startswith("https://"):
        raise ValueError(f"{row['ticker']} {row['period']}: missing actual source")

    cutoff = _timestamp(row["cutoff"])
    last_trade = _timestamp(row["lastTradeAt"])
    if last_trade >= cutoff:
        raise ValueError(f"{row['ticker']} {row['period']}: post-cutoff price")
    report_date = date.fromisoformat(row["actualReportedAt"])
    if cutoff.date() != report_date:
        raise ValueError(f"{row['ticker']} {row['period']}: cutoff/report mismatch")

    probability = float(row["probability"])
    strike = float(row["strike"])
    actual = float(row["actualValue"])
    outcome = int(actual > strike)
    if outcome != int(row["binaryOutcome"]):
        raise ValueError(f"{row['ticker']} {row['period']}: binary outcome mismatch")

    point_probability = min(0.98, max(0.02, probability))
    scenarios, calibration_n = surprise_sigma(
        company,
        _MODEL_METRIC[metric_key],
        as_of=cutoff.date(),
    )
    low_sigma, mid_sigma, high_sigma = scenarios
    z_score = norm_ppf(point_probability)
    shadow = strike + mid_sigma * z_score
    market_error = abs(shadow - actual)
    strike_error = abs(strike - actual)
    delta = strike_error - market_error

    return {
        "ticker": row["ticker"],
        "period": row["period"],
        "metricKey": metric_key,
        "units": row["units"],
        "cutoff": row["cutoff"],
        "lastTradeAt": row["lastTradeAt"],
        "pointInTime": True,
        "probability": probability,
        "pointProbability": point_probability,
        "strike": strike,
        "actual": actual,
        "actualBasis": row["actualBasis"],
        "actualMatch": row["actualMatch"],
        "actualSourceUrl": row["actualSourceUrl"],
        "binaryOutcome": outcome,
        "binaryHit": int(probability >= 0.5) == outcome,
        "brierScore": (probability - outcome) ** 2,
        "surpriseSigma": {
            "low": low_sigma,
            "mid": mid_sigma,
            "high": high_sigma,
            "calibrationN": calibration_n,
            "calibrationCutoffExclusive": cutoff.date().isoformat(),
        },
        "zScore": z_score,
        "shadowEstimate": shadow,
        "shadowAbsoluteError": market_error,
        "strikeAbsoluteError": strike_error,
        "absoluteErrorImprovement": delta,
        "rowResult": "win" if delta > 1e-12 else "loss" if delta < -1e-12 else "tie",
        "marketSourceUrl": row["sourceUrl"],
        "marketSourceContentSha256": row["sourceContentSha256"],
        "numericWeight": 0,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(row["rowResult"] == "win" for row in rows)
    losses = sum(row["rowResult"] == "loss" for row in rows)
    ties = len(rows) - wins - losses
    market_mae = _mean([row["shadowAbsoluteError"] for row in rows])
    strike_mae = _mean([row["strikeAbsoluteError"] for row in rows])
    return {
        "resolved": len(rows),
        "binaryHits": sum(row["binaryHit"] for row in rows),
        "binaryHitRate": _mean([float(row["binaryHit"]) for row in rows]),
        "meanBrierScore": _mean([row["brierScore"] for row in rows]),
        "shadowMae": market_mae,
        "strikeBaselineMae": strike_mae,
        "maeImprovement": strike_mae - market_mae,
        "maeImprovementPct": (strike_mae - market_mae) / strike_mae,
        "rowWins": wins,
        "rowLosses": losses,
        "rowTies": ties,
        "oneSidedSignTestP": _one_sided_sign_test(wins, losses),
        "allPointInTime": all(row["pointInTime"] for row in rows),
        "allActualsExact": all(row["actualMatch"] == "exact" for row in rows),
    }


def _promotion(summary: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "minimumResolved": {
            "pass": summary["resolved"] >= MIN_RESOLVED,
            "observed": summary["resolved"],
            "required": MIN_RESOLVED,
        },
        "pointInTime": {
            "pass": summary["allPointInTime"],
            "observed": summary["allPointInTime"],
            "required": True,
        },
        "exactActualBasis": {
            "pass": summary["allActualsExact"],
            "observed": summary["allActualsExact"],
            "required": True,
        },
        "meanBrier": {
            "pass": summary["meanBrierScore"] <= MAX_MEAN_BRIER,
            "observed": summary["meanBrierScore"],
            "requiredMaximum": MAX_MEAN_BRIER,
        },
        "maeImprovement": {
            "pass": summary["maeImprovementPct"] >= MIN_MAE_IMPROVEMENT,
            "observed": summary["maeImprovementPct"],
            "requiredMinimum": MIN_MAE_IMPROVEMENT,
        },
        "moreWinsThanLosses": {
            "pass": summary["rowWins"] > summary["rowLosses"],
            "observed": f"{summary['rowWins']}-{summary['rowLosses']}",
            "required": "wins > losses",
        },
        "signTest": {
            "pass": summary["oneSidedSignTestP"] <= MAX_SIGN_TEST_P,
            "observed": summary["oneSidedSignTestP"],
            "requiredMaximum": MAX_SIGN_TEST_P,
        },
    }
    failed = [name for name, check in checks.items() if not check["pass"]]
    return {
        "eligible": not failed,
        "numericWeight": 0,
        "decision": "eligible_for_review" if not failed else "shadow_only",
        "failedChecks": failed,
        "checks": checks,
        "policy": (
            "Passing makes the market conversion eligible for human review; it does "
            "not silently assign ensemble weight. Until then numeric weight is zero."
        ),
    }


def promotion_decision(
    *, as_of: date, archive_path: Path = DEFAULT_ARCHIVE
) -> dict[str, Any]:
    """Compute the promotion decision without loading current live markets."""
    rows = [_score_row(row) for row in _load_records(archive_path, as_of)]
    return _promotion(_summary(rows))


def promotion_note(*, as_of: date) -> str:
    """Compact, computed audit note for the ensemble contribution."""
    rows = [_score_row(row) for row in _load_records(DEFAULT_ARCHIVE, as_of)]
    summary = _summary(rows)
    decision = _promotion(summary)
    failed = ", ".join(decision["failedChecks"]) or "none"
    return (
        f"walk-forward market backtest: n={summary['resolved']}, Brier="
        f"{summary['meanBrierScore']:.4f}, shadow MAE improves on strike by "
        f"{summary['maeImprovementPct']:.1%}, sign-test p="
        f"{summary['oneSidedSignTestP']:.4f}; promotion={decision['decision']} "
        f"(failed: {failed})"
    )


def _live_shadows(as_of: date) -> list[dict[str, Any]]:
    targets = (
        (Company.HD, "adj_eps"),
        (Company.ADI, "adj_eps"),
        (Company.DE, "diluted_eps_gaap"),
    )
    rows: list[dict[str, Any]] = []
    for company, canonical_metric in targets:
        signal = market_signal(company, canonical_metric, as_of)
        if signal is None:
            continue
        rows.append(
            {
                "ticker": ticker(company),
                "metricKey": canonical_metric,
                "asOf": as_of.isoformat(),
                "probability": signal.p_beat,
                "strike": signal.strike,
                "shadowEstimate": signal.implied["mid"],
                "surpriseSigma": {
                    "low": signal.surprise_sigma[0],
                    "mid": signal.surprise_sigma[1],
                    "high": signal.surprise_sigma[2],
                    "calibrationN": signal.calibration_n,
                },
                "status": "signal_only",
                "numericWeight": 0,
                "sourceSnapshot": signal.fetched_from,
                "sourceUrl": signal.url,
            }
        )
    return rows


def build_market_backtest(
    *, as_of: date, archive_path: Path = DEFAULT_ARCHIVE
) -> dict[str, Any]:
    rows = [_score_row(row) for row in _load_records(archive_path, as_of)]
    summary = _summary(rows)
    return {
        "schemaVersion": "prediction-market-backtest-v1",
        "meta": {
            "title": "Prediction-market earnings walk-forward backtest",
            "asOf": as_of.isoformat(),
            "method": "strike + pre-event surprise sigma * normal_ppf(P(beat))",
            "probabilityClipForPointEstimate": [0.02, 0.98],
            "evaluationUnit": "one resolved direct EPS beat contract",
            "actualPolicy": "exact reported EPS on the market's GAAP/non-GAAP basis",
        },
        "summary": summary,
        "promotion": _promotion(summary),
        "rows": rows,
        "liveShadowEstimates": _live_shadows(as_of),
    }


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    promotion = payload["promotion"]
    lines = [
        "# Prediction-market earnings backtest",
        "",
        f"As of: {payload['meta']['asOf']}",
        "",
        (
            f"The shadow conversion scored **{summary['shadowMae']:.4f} MAE** versus "
            f"**{summary['strikeBaselineMae']:.4f}** for the strike baseline "
            f"({summary['maeImprovementPct']:.1%} improvement). It won "
            f"{summary['rowWins']} of {summary['rowWins'] + summary['rowLosses']} "
            f"non-tied comparisons; exact one-sided sign-test p="
            f"{summary['oneSidedSignTestP']:.4f}."
        ),
        "",
        f"Promotion decision: **{promotion['decision']}**. Numeric weight: **0**.",
        "",
        "| Company | Period | P(beat) | Strike | Shadow | Actual | Shadow error | Strike error | Result |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['ticker']} | {row['period']} | {row['probability']:.1%} | "
            f"{row['strike']:.2f} | {row['shadowEstimate']:.3f} | {row['actual']:.2f} | "
            f"{row['shadowAbsoluteError']:.3f} | {row['strikeAbsoluteError']:.3f} | "
            f"{row['rowResult']} |"
        )
    lines.extend(["", "## Promotion checks", ""])
    for name, check in promotion["checks"].items():
        lines.append(f"- {'PASS' if check['pass'] else 'FAIL'} — `{name}`: {check['observed']}")
    lines.extend(
        [
            "",
            "All market prices are pre-resolution and every actual is an exact-basis, first-party reported figure. Passing the gate would make the method eligible for review, not automatically assign weight.",
            "",
        ]
    )
    return "\n".join(lines)


def write_market_backtest(
    payload: dict[str, Any],
    *,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    markdown_output: Path = DEFAULT_MD_OUTPUT,
) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown_output.write_text(_markdown(payload), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD_OUTPUT)
    args = parser.parse_args(argv)
    payload = build_market_backtest(
        as_of=date.fromisoformat(args.as_of), archive_path=args.archive
    )
    write_market_backtest(
        payload, json_output=args.json_output, markdown_output=args.markdown_output
    )
    print(
        f"wrote {args.json_output} and {args.markdown_output}; "
        f"promotion={payload['promotion']['decision']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
