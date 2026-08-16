#!/usr/bin/env python3
"""Backtest forecast sources and blend their current, point-in-time estimates."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path


PERCENT_UNITS = {"%"}
PRIOR_ERROR = 0.08
PRIOR_OBSERVATIONS = 3.0
HALF_LIFE_DAYS = 730.0
STREET_SOURCE_TYPES = frozenset(
    {"consensus", "company_consensus", "analyst", "social_explicit"}
)


@dataclass(frozen=True)
class Observation:
    source_id: str
    source_name: str
    source_type: str
    company: str
    metric: str
    period: str
    forecast_date: date
    event_date: date
    forecast: float
    actual: float | None
    units: str
    source_url: str
    quality: float


@dataclass(frozen=True)
class SourceScore:
    source_id: str
    source_name: str
    company: str
    metric: str
    observations: int
    weighted_error: float
    shrunk_error: float
    signed_bias: float
    within_one_percent_rate: float
    last_forecast_date: str


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_observations(path: Path) -> list[Observation]:
    rows: list[Observation] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            actual = float(raw["actual"]) if raw.get("actual", "").strip() else None
            event_date = parse_date(raw["event_date"])
            observation = Observation(
                source_id=raw["source_id"],
                source_name=raw["source_name"],
                source_type=raw["source_type"],
                company=raw["company"],
                metric=raw["metric"],
                period=raw["period"],
                forecast_date=parse_date(raw["forecast_date"]),
                event_date=event_date,
                forecast=float(raw["forecast"]),
                actual=actual,
                units=raw["units"],
                source_url=raw["source_url"],
                quality=float(raw.get("quality") or 1.0),
            )
            if observation.forecast_date >= observation.event_date:
                raise ValueError(
                    f"look-ahead row rejected: {observation.source_id} "
                    f"{observation.company} {observation.period}"
                )
            rows.append(observation)
    return rows


def signed_scaled_error(row: Observation) -> float:
    if row.actual is None:
        raise ValueError("closed observation required")
    difference = row.forecast - row.actual
    if row.units in PERCENT_UNITS:
        return difference / max(abs(row.actual), 1.0)
    return difference / max(abs(row.actual), 1e-9)


def recency_weight(row: Observation, as_of: date) -> float:
    age = max((as_of - row.forecast_date).days, 0)
    return 0.5 ** (age / HALF_LIFE_DAYS)


def score_sources(rows: list[Observation], as_of: date) -> list[SourceScore]:
    groups: dict[tuple[str, str, str], list[Observation]] = defaultdict(list)
    for row in rows:
        # A replay may only score outcomes that had actually resolved by the
        # cutoff. Filtering on forecast_date alone leaks future actuals.
        if row.actual is not None and row.event_date <= as_of:
            groups[(row.source_id, row.company, row.metric)].append(row)

    scores: list[SourceScore] = []
    for (source_id, company, metric), observations in groups.items():
        weights = [recency_weight(row, as_of) for row in observations]
        signed = [signed_scaled_error(row) for row in observations]
        total_weight = sum(weights)
        weighted_error = sum(w * abs(error) for w, error in zip(weights, signed)) / total_weight
        bias = sum(w * error for w, error in zip(weights, signed)) / total_weight
        # Shrink sparse histories toward an 8% prior error so one lucky call cannot dominate.
        shrunk = (
            total_weight * weighted_error + PRIOR_OBSERVATIONS * PRIOR_ERROR
        ) / (total_weight + PRIOR_OBSERVATIONS)
        within_one_percent = sum(1 for error in signed if abs(error) <= 0.01) / len(signed)
        scores.append(
            SourceScore(
                source_id=source_id,
                source_name=observations[0].source_name,
                company=company,
                metric=metric,
                observations=len(observations),
                weighted_error=weighted_error,
                shrunk_error=shrunk,
                signed_bias=bias,
                within_one_percent_rate=within_one_percent,
                last_forecast_date=max(row.forecast_date for row in observations).isoformat(),
            )
        )
    return sorted(scores, key=lambda score: (score.shrunk_error, -score.observations))


def score_lookup(scores: list[SourceScore]) -> dict[tuple[str, str, str], SourceScore]:
    return {(score.source_id, score.company, score.metric): score for score in scores}


def bias_adjust(row: Observation, score: SourceScore | None) -> float:
    if score is None:
        return row.forecast
    if row.units in PERCENT_UNITS:
        scale = max(abs(row.forecast), 1.0)
        return row.forecast - score.signed_bias * scale
    denominator = 1.0 + score.signed_bias
    return row.forecast if abs(denominator) < 0.25 else row.forecast / denominator


def reporting_precision(units: str) -> int:
    return {"USDm": 0, "GBPm": 1, "USD / share": 2, "GBp": 2, "%": 2}.get(units, 4)


def blend_current(
    current: list[Observation],
    scores: list[SourceScore],
    *,
    as_of: date | None = None,
    source_types: frozenset[str] | None = None,
) -> list[dict[str, object]]:
    lookup = score_lookup(scores)
    groups: dict[tuple[str, str, str, str], list[Observation]] = defaultdict(list)
    for row in current:
        if as_of is not None and row.forecast_date > as_of:
            continue
        if source_types is not None and row.source_type not in source_types:
            continue
        groups[(row.company, row.metric, row.period, row.units)].append(row)

    results: list[dict[str, object]] = []
    for (company, metric, period, units), rows in groups.items():
        components = []
        weighted_sum = 0.0
        total_weight = 0.0
        for row in rows:
            score = lookup.get((row.source_id, company, metric))
            estimated_error = score.shrunk_error if score else PRIOR_ERROR
            adjusted = bias_adjust(row, score)
            history_factor = min((score.observations if score else 0) / 4.0, 1.0)
            confidence_factor = 0.35 + 0.65 * history_factor
            weight = row.quality * confidence_factor / max(estimated_error, 0.01)
            weighted_sum += adjusted * weight
            total_weight += weight
            components.append(
                {
                    "source_id": row.source_id,
                    "source_name": row.source_name,
                    "source_type": row.source_type,
                    "raw_forecast": row.forecast,
                    "bias_adjusted_forecast": adjusted,
                    "observations": score.observations if score else 0,
                    "shrunk_error": score.shrunk_error if score else None,
                    "weight": weight,
                    "source_url": row.source_url,
                }
            )
        unrounded_forecast = weighted_sum / total_weight
        forecast = round(unrounded_forecast, reporting_precision(units))
        results.append(
            {
                "company": company,
                "metric": metric,
                "period": period,
                "units": units,
                "forecast": forecast,
                "unrounded_forecast": unrounded_forecast,
                "components": components,
            }
        )
    return sorted(results, key=lambda item: (str(item["company"]), str(item["metric"])))


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Point-in-time forecast source backtest",
        "",
        f"**As of:** {payload['as_of']}  ",
        f"**Closed observations:** {payload['closed_observations']}  ",
        "",
        "Look-ahead rows are rejected. Errors are recency weighted and sparse histories are shrunk toward an 8% prior.",
        "",
        "## Ranked source × company × metric histories",
        "",
        "| Rank | Source | Company | Metric | N | Weighted error | Shrunk error | Bias |",
        "|---:|---|---|---|---:|---:|---:|---:|",
    ]
    for rank, score in enumerate(payload["source_scores"], start=1):
        lines.append(
            f"| {rank} | {score['source_name']} | {score['company']} | {score['metric']} | "
            f"{score['observations']} | {score['weighted_error']:.2%} | "
            f"{score['shrunk_error']:.2%} | {score['signed_bias']:+.2%} |"
        )
    lines.extend(
        [
            "",
            "## Current forecasts",
            "",
            "| Company | Period | Metric | Forecast | Units | Inputs |",
            "|---|---|---|---:|---|---:|",
        ]
    )
    for forecast in payload["forecasts"]:
        lines.append(
            f"| {forecast['company']} | {forecast['period']} | {forecast['metric']} | "
            f"{forecast['forecast']:.4f} | {forecast['units']} | {len(forecast['components'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A low error with a tiny sample remains heavily shrunk. Sources without closed historical calls can contribute only at reduced confidence. Social posts with no explicit numeric, timestamped forecast are preserved as research evidence but are excluded from the numeric ensemble.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", type=Path, default=Path("forecasting/data/historical_forecasts.csv"))
    parser.add_argument("--current", type=Path, default=Path("forecasting/data/current_forecasts.csv"))
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--output", type=Path, default=Path("research/backtest-results.json"))
    parser.add_argument("--markdown", type=Path, default=Path("research/backtest-results.md"))
    parser.add_argument(
        "--street-only",
        action="store_true",
        help="Exclude company guidance and internal models from the current blend.",
    )
    args = parser.parse_args(argv)

    as_of = parse_date(args.as_of)
    historical = load_observations(args.historical)
    current = load_observations(args.current)
    scores = score_sources(historical, as_of)
    forecasts = blend_current(
        current,
        scores,
        as_of=as_of,
        source_types=STREET_SOURCE_TYPES if args.street_only else None,
    )
    payload = {
        "as_of": as_of.isoformat(),
        "closed_observations": sum(row.actual is not None for row in historical),
        "source_scores": [asdict(score) for score in scores],
        "forecasts": forecasts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(render_markdown(payload), encoding="utf-8")
    print(f"Wrote {args.output} and {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
