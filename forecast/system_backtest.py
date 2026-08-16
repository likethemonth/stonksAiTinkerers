"""Replay the real three-engine system at historical cutoffs and score it.

    npm run backtest:system
    .venv/bin/python -m forecast.system_backtest --as-of 2026-08-16 --jobs 4

The question this answers is the one the other backtests do not. ``forecasting.
backtest`` ranks Street *sources*. ``forecast.backtest`` tests one calibration
step on one company. ``forecast.historical_backtest`` owns an excellent
point-in-time harness but drives a seasonal baseline through it, and says so.

None of them replay the pipeline that writes the twelve submitted numbers. This
module does: for every historical period with a filing-derived actual, it
rebuilds the world as it stood the day before that actual was published, runs
the *same* extractors, calibration, estimators, ``reconcile`` and
``orchestrate`` the final command runs, and scores the number that comes out.

Method
------
For each company and each closed period P:

1.  ``cutoff`` = earliest publication date of P's actuals, minus one day.
2.  The corpus is loaded ``as_of=cutoff``. Look-ahead is structural, not a
    convention: a leak would require a filing to travel backwards in time.
3.  ``FORECASTERS[company](cutoff, silent, period=P)`` produces the fundamental
    engine exactly as the final command does.
4.  ``orchestrate(company, metrics, as_of=cutoff)`` runs all three top-level
    engines and the meta-forecaster. Street and prediction-market engines
    abstain wherever no point-in-time input existed at the cutoff; the meta
    forecaster already handles abstention, so the replay degrades honestly
    rather than inventing a benchmark.
5.  The result is scored against the actual with the competition's own formula:
    error divided by the benchmark's error, floored and capped at 5.0.

The benchmark is the seasonal median-YoY replay from ``historical_backtest``.
It stands in for the Wall Street consensus we are never shown. A score below
1.00 means the system earned its complexity against a model you could write in
twenty lines; above 1.00 means it did not.

Deere abstains from the whole replay. Its engine is a driver chain anchored to
dated AEM snapshots rather than to a fiscal period, so no historical cutoff has
the inputs it needs. Scoring it would mean scoring a model that could not have
existed at the time, so it is recorded as an explicit abstention instead.

Fan-out
-------
Cells are independent, so the grid is evaluated in parallel over companies with
``ProcessPoolExecutor``. Parallelism is deliberately deterministic: results are
re-sorted into a fixed order before writing, so repeated runs are byte
identical. No agent, model call or network request is involved.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from forecast.historical_backtest import (
    _actual_observations,
    _forecast as _baseline_forecast,
    _latest_resolved_quarter,
    _quarter_window,
    _resolve_actual,
)
from forecast.metrics import display_name, submitted_specs, ticker
from forecast.orchestrate import orchestrate
from forecast.schema import Company, MetricObservation, Period, Unit

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON = REPO_ROOT / "research" / "system-backtest.json"
DEFAULT_MARKDOWN = REPO_ROOT / "research" / "system-backtest.md"

#: Competition denominator floors. Percentage metrics use half a percentage
#: point; money and EPS use half a percent of the reported result.
PERCENT_FLOOR = 0.5
RELATIVE_FLOOR = 0.005
ZERO_FALLBACK = 1e-6

#: Companies whose engine is period-addressable and can therefore be replayed.
REPLAYABLE = (Company.HD, Company.ADI, Company.HAS)

#: Why a company is excluded, recorded in the report rather than hidden.
ABSTENTIONS = {
    Company.DE: (
        "The Deere engine is an AEM units-to-dollars driver chain anchored to a "
        "dated snapshot, not to a fiscal period. No historical cutoff carries the "
        "driver observations it consumes, so replaying it would score a model that "
        "did not exist at the time."
    ),
}


class _Silent:
    """Forecasters log through a callable; the replay discards that output."""

    def __call__(self, *args: object, **kwargs: object) -> None:
        return None


@dataclass
class Cell:
    """One scored (company, period, metric) outcome."""

    company: str
    ticker: str
    period: str
    metric_key: str
    metric_label: str
    units: str
    actual: float
    actual_published: str
    cutoff: str
    system: float | None = None
    baseline: float | None = None
    system_error: float | None = None
    baseline_error: float | None = None
    score: float | None = None
    beat_baseline: bool | None = None
    system_engines: list[str] = field(default_factory=list)
    system_reasoning: str = ""
    #: Each top-level engine scored on its own against the same actual, so the
    #: aggregate can be compared with the parts it was built from.
    engine_values: dict[str, float] = field(default_factory=dict)
    engine_errors: dict[str, float] = field(default_factory=dict)
    engine_scores: dict[str, float] = field(default_factory=dict)
    status: str = "scored"
    note: str | None = None


def _floor_for(units: Unit, actual: float) -> float:
    if units is Unit.PERCENT:
        return PERCENT_FLOOR
    return max(abs(actual) * RELATIVE_FLOOR, ZERO_FALLBACK)


def _score(system_error: float, baseline_error: float, units: Unit, actual: float) -> float:
    denominator = max(baseline_error, _floor_for(units, actual))
    return min(system_error / denominator, 5.0)


def _forecast_period(company: Company, slot: Period) -> Period:
    """The period the engine is asked to forecast for this slot."""
    if company is Company.HAS:
        return Period(year=slot.year, quarter=None)
    return slot


def _slots(company: Company, actuals: dict[tuple[str, str], MetricObservation],
           quarters: int) -> list[Period]:
    latest = _latest_resolved_quarter(company, actuals)
    window = _quarter_window(latest, quarters)
    if company is Company.HAS:
        # Hays reports these metrics annually. One slot per fiscal year, using
        # Q4 as the resolution key so the annual route in _resolve_actual fires.
        years = sorted({period.year for period in window})
        return [Period(year=year, quarter=4) for year in years]
    return window


def _run_company(company: Company, as_of: date, quarters: int) -> list[dict[str, Any]]:
    """Replay every eligible period for one company. Runs inside a worker."""
    # Point-in-time replay writes nothing: the store would otherwise emit one
    # observation file per cutoff and race across workers.
    from forecast import run as run_module

    run_module.write_observations = lambda *a, **k: None  # type: ignore[assignment]
    run_module.write_calibration_report = lambda *a, **k: None  # type: ignore[assignment]

    actuals = _actual_observations(company, as_of)
    specs = submitted_specs(company)
    silent = _Silent()
    forecaster = run_module.FORECASTERS[company]
    cells: list[Cell] = []

    for slot in _slots(company, actuals, quarters):
        resolved: list[tuple[Any, MetricObservation]] = []
        for spec in specs:
            actual, match, note = _resolve_actual(company, spec.key, slot, actuals)
            if actual is None or match == "unavailable":
                continue
            resolved.append((spec, actual))
        if not resolved:
            continue

        # One cutoff per slot, taken from the earliest actual in it. Using the
        # earliest is the most blinded choice available.
        published = min(actual.as_of for _, actual in resolved)
        cutoff = published - timedelta(days=1)
        period = _forecast_period(company, slot)

        try:
            metrics = forecaster(cutoff, silent, period=period)
            final = orchestrate(company, metrics, as_of=cutoff)
        except Exception as exc:  # noqa: BLE001 - one slot must not kill the grid
            for spec, actual in resolved:
                cells.append(
                    Cell(
                        company=display_name(company),
                        ticker=ticker(company),
                        period=period.key,
                        metric_key=spec.key,
                        metric_label=spec.label or spec.key,
                        units=spec.units.value,
                        actual=actual.value,
                        actual_published=actual.as_of.isoformat(),
                        cutoff=cutoff.isoformat(),
                        status="engine_failed",
                        note=f"{type(exc).__name__}: {exc}",
                    )
                )
            continue

        by_label = {metric.label: metric for metric in final}
        for spec, actual in resolved:
            produced = by_label.get(spec.label or "")
            cell = Cell(
                company=display_name(company),
                ticker=ticker(company),
                period=period.key,
                metric_key=spec.key,
                metric_label=spec.label or spec.key,
                units=spec.units.value,
                actual=actual.value,
                actual_published=actual.as_of.isoformat(),
                cutoff=cutoff.isoformat(),
            )
            if produced is None:
                cell.status = "no_output"
                cell.note = "engine returned no estimate for this metric"
                cells.append(cell)
                continue

            baseline = _baseline_forecast(actual, cutoff, actuals, spec.units)
            if baseline is None:
                cell.status = "no_benchmark"
                cell.note = "no prior-year anchor available for the benchmark"
                cell.system = produced.value
                cells.append(cell)
                continue

            cell.system = produced.value
            cell.baseline = baseline["value"]
            cell.system_error = abs(produced.value - actual.value)
            cell.baseline_error = abs(baseline["value"] - actual.value)
            cell.score = _score(
                cell.system_error, cell.baseline_error, spec.units, actual.value
            )
            cell.beat_baseline = cell.system_error < cell.baseline_error
            cell.system_engines = [
                contribution.engine.value
                for contribution in produced.engine_contributions
                if contribution.status.value == "available"
            ]
            cell.system_reasoning = produced.reasoning
            # Score every engine that spoke, on its own, against the same actual
            # and the same benchmark. Without this the aggregate can only be
            # asserted to be worth building, never shown to be.
            for contribution in produced.engine_contributions:
                if contribution.status.value != "available" or contribution.estimate is None:
                    continue
                name = contribution.engine.value
                error = abs(contribution.estimate.value - actual.value)
                cell.engine_values[name] = contribution.estimate.value
                cell.engine_errors[name] = error
                cell.engine_scores[name] = _score(
                    error, cell.baseline_error, spec.units, actual.value
                )
            cells.append(cell)

    return [asdict(cell) for cell in cells]


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row["status"] == "scored"]
    by_metric: dict[str, list[dict[str, Any]]] = {}
    for row in scored:
        by_metric.setdefault(f"{row['ticker']} · {row['metric_label']}", []).append(row)

    def block(items: list[dict[str, Any]]) -> dict[str, Any]:
        scores = [item["score"] for item in items]
        return {
            "n": len(items),
            "meanScore": statistics.fmean(scores),
            "medianScore": statistics.median(scores),
            "beat": sum(1 for item in items if item["beat_baseline"]),
            "meanSystemError": statistics.fmean(item["system_error"] for item in items),
            "meanBaselineError": statistics.fmean(
                item["baseline_error"] for item in items
            ),
        }

    # Each engine judged only on the cells where it actually spoke, plus the
    # aggregate restricted to those same cells so the comparison is like for
    # like: an engine that abstains 60 times must not look good on the 3 it took.
    engines: dict[str, dict[str, Any]] = {}
    for name in sorted({key for row in scored for key in row["engine_scores"]}):
        spoke = [row for row in scored if name in row["engine_scores"]]
        alone = [row["engine_scores"][name] for row in spoke]
        together = [row["score"] for row in spoke]
        engines[name] = {
            "n": len(spoke),
            "meanScoreAlone": statistics.fmean(alone),
            "medianScoreAlone": statistics.median(alone),
            "beatBenchmarkAlone": sum(1 for value in alone if value < 1.0),
            "meanScoreOfAggregateOnSameCells": statistics.fmean(together),
            "aggregateBetterOnCells": sum(
                1 for row in spoke if row["score"] < row["engine_scores"][name]
            ),
        }

    return {
        "overall": block(scored) if scored else None,
        "byEngine": engines,
        "byMetric": {key: block(items) for key, items in sorted(by_metric.items())},
        "counts": {
            status: sum(1 for row in rows if row["status"] == status)
            for status in sorted({row["status"] for row in rows})
        },
    }


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# System backtest — the real pipeline replayed on history",
        "",
        f"**As of:** {payload['asOf']}  ",
        f"**Cells scored:** {summary['overall']['n'] if summary['overall'] else 0}  ",
        "",
        "Each cell rebuilds the corpus as of the day before the actual was published, "
        "runs the same extractors, calibration, estimators and three-engine "
        "meta-forecaster the final command runs, and scores the result against a "
        "seasonal median-YoY benchmark using the competition's own formula "
        "(error ÷ benchmark error, floored, capped at 5.0). Below 1.00 is better.",
        "",
    ]

    if summary["overall"]:
        overall = summary["overall"]
        lines += [
            "## Headline",
            "",
            f"- **Mean score {overall['meanScore']:.2f}**, median "
            f"**{overall['medianScore']:.2f}** across {overall['n']} held-out cells.",
            f"- Beat the benchmark on **{overall['beat']} of {overall['n']}** "
            f"({overall['beat'] / overall['n']:.0%}).",
            f"- Mean absolute error {overall['meanSystemError']:.4g} versus benchmark "
            f"{overall['meanBaselineError']:.4g}.",
            "",
        ]

    if summary.get("byEngine"):
        lines += [
            "## Each engine alone, against the aggregate",
            "",
            "An engine is judged only on the cells where it actually produced a "
            "value, and the aggregate is shown on those same cells so the "
            "comparison is like for like. `Aggregate better` counts the cells "
            "where the meta-forecast beat that engine on its own.",
            "",
            "| Engine | Cells it spoke on | Mean score alone | Median alone | "
            "Beat benchmark alone | Aggregate on same cells | Aggregate better |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for name, item in summary["byEngine"].items():
            lines.append(
                f"| {name} | {item['n']} | **{item['meanScoreAlone']:.2f}** | "
                f"{item['medianScoreAlone']:.2f} | "
                f"{item['beatBenchmarkAlone']}/{item['n']} | "
                f"{item['meanScoreOfAggregateOnSameCells']:.2f} | "
                f"{item['aggregateBetterOnCells']}/{item['n']} |"
            )
        lines.append("")

    lines += [
        "## By metric",
        "",
        "| Company · Metric | n | Mean score | Median | Beat | Mean err | Benchmark err |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, item in summary["byMetric"].items():
        lines.append(
            f"| {key} | {item['n']} | **{item['meanScore']:.2f}** | "
            f"{item['medianScore']:.2f} | {item['beat']}/{item['n']} | "
            f"{item['meanSystemError']:.4g} | {item['meanBaselineError']:.4g} |"
        )

    lines += ["", "## Coverage and abstentions", ""]
    for status, count in payload["summary"]["counts"].items():
        lines.append(f"- `{status}`: {count} cells")
    for company, reason in payload["abstentions"].items():
        lines.append(f"- **{company} excluded.** {reason}")

    lines += [
        "",
        "## Per-cell results",
        "",
        "| Company | Period | Metric | Cutoff | Actual | System | Benchmark | Score |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["cells"]:
        if row["status"] != "scored":
            continue
        lines.append(
            f"| {row['ticker']} | {row['period']} | {row['metric_label']} | "
            f"{row['cutoff']} | {row['actual']:,.4g} | {row['system']:,.4g} | "
            f"{row['baseline']:,.4g} | {row['score']:.2f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay the real system on history.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--quarters", type=int, default=20)
    parser.add_argument("--jobs", type=int, default=len(REPLAYABLE))
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args(argv)

    print(
        f"system backtest — replaying {len(REPLAYABLE)} companies "
        f"as of {args.as_of.isoformat()} over {args.quarters} quarters"
    )

    rows: list[dict[str, Any]] = []
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(_run_company, company, args.as_of, args.quarters): company
                for company in REPLAYABLE
            }
            for future, company in futures.items():
                try:
                    rows.extend(future.result())
                except Exception as exc:  # noqa: BLE001
                    print(f"  FAILED {company.value}: {exc}", file=sys.stderr)
    else:
        for company in REPLAYABLE:
            rows.extend(_run_company(company, args.as_of, args.quarters))

    # Deterministic order regardless of worker completion order.
    rows.sort(key=lambda row: (row["ticker"], row["period"], row["metric_key"]))

    payload = {
        "generatedBy": "forecast/system_backtest.py — real pipeline, point-in-time replay",
        "asOf": args.as_of.isoformat(),
        "quarters": args.quarters,
        "benchmark": "seasonal median year-over-year replay (historical_backtest)",
        "scoring": (
            "error / max(benchmark error, floor), capped at 5.0; floor is 0.5pp for "
            "percentage metrics and 0.5% of the reported result otherwise"
        ),
        "abstentions": {display_name(c): reason for c, reason in ABSTENTIONS.items()},
        "summary": _summarise(rows),
        "cells": rows,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(_markdown(payload), encoding="utf-8")

    overall = payload["summary"]["overall"]
    if overall:
        print(
            f"  {overall['n']} cells scored — mean {overall['meanScore']:.2f}, "
            f"median {overall['medianScore']:.2f}, "
            f"beat benchmark {overall['beat']}/{overall['n']}"
        )
    else:
        print("  no cells scored")
    for status, count in payload["summary"]["counts"].items():
        if status != "scored":
            print(f"  {status}: {count}")
    print(f"  wrote {args.output.relative_to(REPO_ROOT)}")
    print(f"  wrote {args.markdown.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
