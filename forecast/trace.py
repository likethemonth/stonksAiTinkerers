"""Follow one number end to end: source documents to scored outcome.

    npm run trace
    .venv/bin/python -m forecast.trace --company analog-devices --metric revenue
    .venv/bin/python -m forecast.trace --company home-depot --metric net_sales

This exists for the question a judge asks out loud: *show me one number being
made*. Everything else in the repository reports aggregates. This prints a
single metric's whole chain in the order it actually happens:

    1. the point-in-time cutoff, and how it is chosen
    2. the documents the corpus hands over at that cutoff
    3. the observations the extractor pulls out of them, with dates and excerpts
    4. each estimator inside the fundamental engine, with its arithmetic
    5. each of the three top-level engines: value, sigma, reliability,
       source families, or an explicit abstention and its reason
    6. the meta-forecaster's precision weighting, overlap penalty and output
    7. the reported actual, the error, the benchmark's error, and the score

By default it traces a *closed* period, so step 7 is a real comparison against
a figure the company has since reported rather than a forecast nobody can check
yet. Pass --submitted to trace the live submitted period instead, where step 7
is necessarily absent because the actual does not exist.
"""

from __future__ import annotations

import argparse
import textwrap
from datetime import date, timedelta

from forecast.corpus import load
from forecast.historical_backtest import (
    _actual_observations,
    _forecast as _baseline_forecast,
    _resolve_actual,
)
from forecast.metrics import display_name, submitted_specs, target_period, ticker
from forecast.orchestrate import orchestrate
from forecast.run import EXTRACTORS, FORECASTERS
from forecast.schema import Company, Period, Unit
from forecast.system_backtest import ABSTENTIONS, _Silent, _floor_for, _score, _slots

RULE = "─" * 78

#: A closed period per company that exercises the whole chain. These are the
#: most recent slots the system backtest scores, so the trace and the backtest
#: agree by construction.
DEFAULT_METRIC = {
    Company.HD: "net_sales",
    Company.ADI: "revenue",
    Company.HAS: "net_fees",
    Company.DE: "worldwide_net_sales_revenues",
}


def heading(text: str) -> None:
    print(f"\n{RULE}\n{text}\n{RULE}")


def wrap(text: str, indent: str = "      ") -> str:
    return textwrap.fill(
        " ".join(text.split()), width=78, initial_indent=indent, subsequent_indent=indent
    )


def _latest_scored_slot(company: Company, as_of: date, metric_key: str):
    """The most recent period where this metric has a filing-derived actual."""
    actuals = _actual_observations(company, as_of)
    for slot in reversed(_slots(company, actuals, 20)):
        actual, match, _ = _resolve_actual(company, metric_key, slot, actuals)
        if actual is not None and match != "unavailable":
            return slot, actual, actuals
    return None, None, actuals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trace one number end to end.")
    parser.add_argument(
        "--company",
        default="analog-devices",
        choices=[c.value for c in Company],
    )
    parser.add_argument("--metric", default=None, help="metric key; default per company")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 8, 16))
    parser.add_argument(
        "--submitted",
        action="store_true",
        help="trace the live submitted period instead of a closed one",
    )
    args = parser.parse_args(argv)

    company = Company(args.company)
    metric_key = args.metric or DEFAULT_METRIC[company]
    spec = next((s for s in submitted_specs(company) if s.key == metric_key), None)
    if spec is None:
        keys = ", ".join(s.key for s in submitted_specs(company))
        print(f"unknown metric {metric_key!r}; choose one of: {keys}")
        return 2

    # The system backtest refuses to score some companies on history. The trace
    # has to refuse for the same reason, or it would quietly present a score for
    # a path the backtest excluded — the fallback baseline is anchored to the
    # submitted period, so replaying it against an older actual is meaningless.
    if not args.submitted and company in ABSTENTIONS:
        heading(f"{display_name(company)} ({ticker(company)}) · {spec.label}")
        print("\nTHIS COMPANY IS NOT REPLAYABLE ON HISTORY")
        print(wrap(ABSTENTIONS[company]))
        print(wrap(
            "Tracing it against a closed period would exercise the provisional "
            "baseline fallback, not the engine that produces the submitted "
            "number, and any score printed would be an artefact of that "
            "substitution. Use --submitted to trace the live period instead."
        ))
        return 0

    if args.submitted:
        period, actual, actuals = target_period(company), None, {}
        cutoff = args.as_of
    else:
        period, actual, actuals = _latest_scored_slot(company, args.as_of, metric_key)
        if actual is None:
            print(f"no closed actual for {company.value} {metric_key}; try --submitted")
            return 2
        cutoff = actual.as_of - timedelta(days=1)
        if company is Company.HAS:
            period = Period(year=period.year, quarter=None)

    heading(
        f"{display_name(company)} ({ticker(company)}) · {spec.label} · {period.key}"
    )

    # --- 1. the cutoff -------------------------------------------------------
    print("\n1. POINT-IN-TIME CUTOFF")
    if actual is not None:
        print(f"      the company reported this period on {actual.as_of.isoformat()}")
        print(f"      so the world is rebuilt as of {cutoff.isoformat()} — one day earlier")
        print(wrap(
            "Look-ahead is structural rather than promised: the corpus is loaded "
            "with as_of=cutoff, so a leak would require a filing to travel "
            "backwards in time."
        ))
    else:
        print(f"      live submitted period; evidence cutoff {cutoff.isoformat()}")

    # --- 2. the documents ----------------------------------------------------
    docs = load(company, as_of=cutoff)
    print(f"\n2. DOCUMENTS AT THE CUTOFF — {len(docs)} available")
    for doc in sorted(docs, key=lambda d: d.published_at, reverse=True)[:4]:
        print(f"      {doc.published_at.isoformat()}  {doc.doc_type.value:16s} {doc.rel_path}")
    if len(docs) > 4:
        print(f"      … and {len(docs) - 4} older documents")

    # --- 3. the observations -------------------------------------------------
    rejected: list[str] = []
    observations = EXTRACTORS[company](docs, rejected)
    relevant = sorted(
        (o for o in observations if o.metric_key == metric_key),
        key=lambda o: (o.period.sort_key, o.as_of),
        reverse=True,
    )
    print(f"\n3. EXTRACTED OBSERVATIONS — {len(observations)} total, "
          f"{len(relevant)} for {metric_key}, {len(rejected)} rejected")
    for row in relevant[:5]:
        print(f"      {row.period.key:10s} {row.value:>12,.4g} {row.units.value:<12} "
              f"{row.kind.value:<10} {row.as_of.isoformat()}  {row.extractor}")
        if row.excerpt:
            print(wrap(f"“{row.excerpt[:150]}”", indent="        "))
    for reason in rejected[:3]:
        print(f"      REJECTED {reason}")

    # --- 4 & 5. engines ------------------------------------------------------
    metrics = FORECASTERS[company](cutoff, _Silent(), period=period)
    fundamental = next((m for m in metrics if m.label == spec.label), None)

    print("\n4. ESTIMATORS INSIDE THE FUNDAMENTAL ENGINE")
    if fundamental is None:
        print("      the engine produced no estimate for this metric")
    else:
        for est in fundamental.estimates:
            print(f"      {est.estimator}: {est.value:,.4g} (sigma {est.sigma:,.4g}, "
                  f"n={est.n_observations})")
            print(wrap(est.reasoning))
            for citation in est.citations[:3]:
                print(f"        cite: {citation}")

    final_metrics = orchestrate(company, metrics, as_of=cutoff)
    final = next((m for m in final_metrics if m.label == spec.label), None)
    if final is None:
        print("\n   the pipeline produced no final value for this metric")
        return 1

    print("\n5. THE THREE TOP-LEVEL ENGINES")
    for contribution in final.engine_contributions:
        name = contribution.engine.value
        if contribution.status.value != "available" or contribution.estimate is None:
            print(f"      {name:18s} ABSTAINED")
            print(wrap(contribution.note or "no reason recorded"))
            continue
        est = contribution.estimate
        print(f"      {name:18s} {est.value:>12,.4g}  sigma {est.sigma:<10,.4g} "
              f"reliability {contribution.reliability:.0%}")
        print(f"        families: {', '.join(contribution.source_families) or '—'}")

    # --- 6. the aggregation --------------------------------------------------
    print("\n6. META-FORECASTER — precision weighting with an overlap penalty")
    print(wrap(
        "Each engine contributes 1/sigma^2, scaled by its reliability and by a "
        "penalty for evidence it shares with another engine. An engine that "
        "abstains contributes nothing rather than a default."
    ))
    print()
    print(wrap(final.reasoning, indent="      "))
    print(f"\n      → {spec.label} = {final.value:,.4g} {spec.units.value}"
          + (f"  (sigma {final.sigma:,.4g})" if final.sigma else ""))
    for warning in final.warnings:
        print(f"      WARNING {warning}")
    if final.needs_review:
        print("      WARNING flagged for review; reliability reduced accordingly")

    # --- 7. the outcome ------------------------------------------------------
    if actual is None:
        print("\n7. OUTCOME")
        print("      this period has not been reported yet; nothing to score against")
        return 0

    baseline = _baseline_forecast(actual, cutoff, actuals, spec.units)
    system_error = abs(final.value - actual.value)
    print("\n7. COMPARED TO WHAT THE COMPANY ACTUALLY REPORTED")
    print(f"      system forecast   {final.value:>14,.4g} {spec.units.value}")
    print(f"      reported actual   {actual.value:>14,.4g} {spec.units.value}"
          f"   ({actual.source_file})")
    print(f"      absolute error    {system_error:>14,.4g}")
    if baseline is None:
        print("      no benchmark available for this period")
        return 0
    baseline_error = abs(baseline["value"] - actual.value)
    score = _score(system_error, baseline_error, spec.units, actual.value)
    floor = _floor_for(spec.units, actual.value)
    print(f"      benchmark         {baseline['value']:>14,.4g}   "
          f"(seasonal median year-over-year replay)")
    print(f"      benchmark error   {baseline_error:>14,.4g}")
    print(f"      denominator floor {floor:>14,.4g}")
    print(f"\n      SCORE = {system_error:,.4g} / max({baseline_error:,.4g}, "
          f"{floor:,.4g}) = {score:.2f}")
    print(wrap(
        "This is the competition's own formula, with the seasonal baseline "
        "standing in for the Wall Street benchmark teams are never shown. "
        "Below 1.00 means the system beat it on this metric.",
        indent="      ",
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
