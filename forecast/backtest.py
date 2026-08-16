"""Walk-forward backtest: does calibrating the anchor actually beat the anchor?

    python -m forecast.backtest
    python -m forecast.backtest --company analog-devices

The question this answers is the one a judge should ask about the whole system:
you claim guidance is biased and you correct for it — show that the correction
helps out of sample, on quarters the calibration had not seen.

Method. For each closed period P with both a guidance figure and a reported
actual, we rebuild the world as it stood the day before that guidance was issued.
The calibration is fitted on that restricted history only, then applied to P's
guidance. Two forecasts are compared against the actual:

    naive       submit management's midpoint unchanged
    calibrated  midpoint corrected by the shrunk historical bias

`skill` is the ratio of calibrated error to naive error. Below 1.0 means the
correction earned its place; above 1.0 means we are adding noise and should ship
the raw guidance instead.

The blinding is structural, not a convention: the calibration is fitted from a
corpus loaded with `as_of=<day before the guidance>`, so a leak would require
documents to travel backwards in time.
"""

from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass
from datetime import date, timedelta

from forecast.calibrate import ADDITIVE_UNITS, calibrate
from forecast.corpus import load
from forecast.extract import adi
from forecast.schema import Company, Kind, MetricObservation, Period, Unit

EXTRACTORS = {
    Company.ADI: adi.extract,
}

#: A correction fitted on fewer than this many pairs is too thin to evaluate.
MIN_HISTORY = 3

#: Scoring mirrors the competition's accuracy rubric so the backtest reports the
#: same statistic the prize is decided on:
#:     score = min(CAP, our_error / max(benchmark_error, floor))
#: The floor stops a benchmark that happened to be almost exactly right from
#: producing a meaningless ratio; the cap stops one outlier dominating the mean.
#: Here the benchmark is management's own guidance rather than Wall Street.
SCORE_CAP = 5.0
PERCENT_FLOOR_PP = 0.5  # percentage-point metrics
RELATIVE_FLOOR = 0.005  # money and EPS: 0.5% of the reported result


def denominator_floor(actual: float, units: Unit) -> float:
    """Smallest benchmark error the score is allowed to divide by."""
    if units in ADDITIVE_UNITS:
        return PERCENT_FLOOR_PP
    return max(abs(actual) * RELATIVE_FLOOR, 1e-9)


@dataclass(frozen=True)
class Result:
    """One held-out period's outcome for one metric."""

    company: Company
    metric_key: str
    period: Period
    units: Unit
    guided: float
    actual: float
    calibrated: float
    n_history: int

    @property
    def naive_error(self) -> float:
        return abs(self.guided - self.actual)

    @property
    def calibrated_error(self) -> float:
        return abs(self.calibrated - self.actual)

    @property
    def skill(self) -> float:
        """Competition-style score against the guidance benchmark.

        Floored and capped exactly as the accuracy rubric does, so this is
        directly comparable to the number the prize is decided on. Below 1.0
        means the calibration beat parroting the guidance.
        """
        floor = denominator_floor(self.actual, self.units)
        return min(SCORE_CAP, self.calibrated_error / max(self.naive_error, floor))


def _targets(observations: list[MetricObservation]) -> list[tuple[str, Period]]:
    """(metric, period) pairs that have both a guidance and a later actual."""
    guided = {
        (o.metric_key, o.period.key): o
        for o in observations
        if o.kind is Kind.GUIDE_MID
    }
    actual = {
        (o.metric_key, o.period.key): o for o in observations if o.kind is Kind.ACTUAL
    }
    out = []
    for key, g in guided.items():
        a = actual.get(key)
        if a is not None and a.as_of > g.as_of:
            out.append((g.metric_key, g.period))
    return sorted(out, key=lambda t: (t[1].sort_key, t[0]))


def run(company: Company) -> list[Result]:
    """Walk forward through every held-out period for one company."""
    extractor = EXTRACTORS[company]
    full = extractor(load(company))

    guided_by = {
        (o.metric_key, o.period.key): o for o in full if o.kind is Kind.GUIDE_MID
    }
    actual_by = {(o.metric_key, o.period.key): o for o in full if o.kind is Kind.ACTUAL}

    results: list[Result] = []
    for metric_key, period in _targets(full):
        g = guided_by[(metric_key, period.key)]
        a = actual_by[(metric_key, period.key)]

        # Rebuild the world as of the day before this guidance was published, so
        # neither this period's guidance nor its result can inform the correction.
        cutoff = g.as_of - timedelta(days=1)
        history = extractor(load(company, as_of=cutoff))
        corrections = calibrate(history)
        cor = corrections.get((company, metric_key))
        if cor is None or cor.n < MIN_HISTORY:
            continue

        results.append(
            Result(
                company=company,
                metric_key=metric_key,
                period=period,
                units=g.units,
                guided=g.value,
                actual=a.value,
                calibrated=cor.apply(g.value),
                n_history=cor.n,
            )
        )
    return results


def report(results: list[Result]) -> str:
    """Human-readable walk-forward table plus the headline skill numbers."""
    if not results:
        return "no evaluable periods"

    lines = [
        "| Period | Metric | Guided | Actual | Naive err | Calib | Calib err | Skill |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.period.key} | `{r.metric_key}` | {r.guided:,.2f} | {r.actual:,.2f} "
            f"| {r.naive_error:,.2f} | {r.calibrated:,.2f} | {r.calibrated_error:,.2f} "
            f"| {r.skill:.2f} |"
        )

    lines.append("")
    by_metric: dict[str, list[Result]] = {}
    for r in results:
        by_metric.setdefault(r.metric_key, []).append(r)

    lines.append(
        "| Metric | n | Mean naive err | Mean calib err | Err ratio | Mean score | Beat |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for metric_key, rows in sorted(by_metric.items()):
        naive = statistics.fmean(r.naive_error for r in rows)
        calib = statistics.fmean(r.calibrated_error for r in rows)
        beat = sum(1 for r in rows if r.calibrated_error < r.naive_error)
        ratio = calib / naive if naive else float("nan")
        score = statistics.fmean(r.skill for r in rows)
        lines.append(
            f"| `{metric_key}` | {len(rows)} | {naive:,.3f} | {calib:,.3f} "
            f"| **{ratio:.2f}** | {score:.2f} | {beat}/{len(rows)} |"
        )

    beat = sum(1 for r in results if r.calibrated_error < r.naive_error)
    # Errors live in different units, so the pooled headline is the mean of the
    # floored-and-capped per-period scores, not a mean of raw errors.
    mean_score = statistics.fmean(r.skill for r in results)
    median_score = statistics.median(r.skill for r in results)
    lines += [
        "",
        f"**{len(results)} held-out periods.** "
        f"Calibration improved {beat} of them ({beat / len(results):.0%}). "
        f"Mean score **{mean_score:.2f}**, median **{median_score:.2f}** "
        "(1.00 = no better than parroting the guidance; lower is better).",
        "",
        "Scores use the competition's own formula — error divided by the "
        "benchmark's, floored and capped at 5.0 — with management guidance "
        "standing in for the Wall Street benchmark we are never shown.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--company",
        choices=[c.value for c in EXTRACTORS],
        default=None,
        help="Restrict to one company. Omit for every company with an extractor.",
    )
    args = parser.parse_args()

    wanted = [Company(args.company)] if args.company else list(EXTRACTORS)
    all_results: list[Result] = []
    for company in wanted:
        results = run(company)
        all_results.extend(results)
        print(f"\n## {company.value}\n")
        print(report(results))


if __name__ == "__main__":
    main()
