"""Five-year point-in-time replay with filing-sourced actuals and full traces.

This is deliberately separate from ``forecasting.backtest``. That module ranks
individual Street sources. This module defines the product backtest denominator:
20 requested fiscal quarters per company, three challenge metrics per period,
and an explicit outcome for every one of the resulting 240 metric slots.

The replay model is a transparent seasonal/trend baseline. It is not presented
as a historical replay of Street or prediction-market engines because those
point-in-time inputs do not exist for every historical cutoff. Its purpose is to
make the infrastructure honest and auditable while leaving a stable contract for
additional historical engines.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from forecast.corpus import CORPUS_ROOT, load
from forecast.extract import adi, deere, hays, home_depot
from forecast.metrics import display_name, spec, submitted_specs, ticker
from forecast.schema import Company, Kind, MetricObservation, Period, Unit


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "research" / "five-year-backtest.json"
COMPANY_ORDER = (Company.HD, Company.ADI, Company.HAS, Company.DE)
EXTRACTORS = {
    Company.HD: home_depot.extract,
    Company.ADI: adi.extract,
    Company.HAS: hays.extract,
    Company.DE: deere.extract,
}


@dataclass(frozen=True)
class ActualRoute:
    """How a submitted metric resolves to a historical filing actual."""

    exact_keys: tuple[str, ...]
    proxy_keys: tuple[str, ...] = ()
    cadence: str = "quarterly"


ACTUAL_ROUTES: dict[tuple[Company, str], ActualRoute] = {
    (Company.HD, "net_sales"): ActualRoute(("net_sales",)),
    # HD only began publishing a separate adjusted quarterly figure recently.
    # Earlier quarters use GAAP diluted EPS as a visible, labelled proxy.
    (Company.HD, "adj_eps"): ActualRoute(("adj_eps",), ("diluted_eps_gaap",)),
    (Company.HD, "comp_sales_pct"): ActualRoute(("comp_sales_pct",)),
    (Company.ADI, "revenue"): ActualRoute(("revenue",)),
    (Company.ADI, "adj_eps"): ActualRoute(("adj_eps",)),
    (Company.ADI, "adj_gross_margin_pct"): ActualRoute(("adj_gross_margin_pct",)),
    (Company.HAS, "net_fees"): ActualRoute(("net_fees",), cadence="annual"),
    (Company.HAS, "pre_exc_basic_eps"): ActualRoute(
        ("pre_exc_basic_eps",), cadence="annual"
    ),
    (Company.HAS, "pre_exc_operating_profit"): ActualRoute(
        ("pre_exc_operating_profit",), cadence="annual"
    ),
    (Company.DE, "worldwide_net_sales_revenues"): ActualRoute(
        ("worldwide_net_sales_revenues",)
    ),
    (Company.DE, "diluted_eps_gaap"): ActualRoute(("diluted_eps_gaap",)),
    (Company.DE, "ppa_operating_profit"): ActualRoute(("ppa_operating_profit",)),
}


def _quarter_index(period: Period) -> int:
    if period.quarter is None:
        raise ValueError(f"quarter required: {period.key}")
    return period.year * 4 + period.quarter - 1


def _period_from_index(value: int) -> Period:
    year, offset = divmod(value, 4)
    return Period(year=year, quarter=offset + 1)


def _quarter_window(end: Period, quarters: int) -> list[Period]:
    last = _quarter_index(end)
    return [_period_from_index(index) for index in range(last - quarters + 1, last + 1)]


def _observation_rank(row: MetricObservation) -> tuple[date, bool, str]:
    """Prefer the earliest direct disclosure over a later comparative repeat."""
    comparative = row.note == "prior-year comparative"
    return row.as_of, comparative, row.source_file


def _actual_observations(
    company: Company, as_of: date
) -> dict[tuple[str, str], MetricObservation]:
    rejected: list[str] = []
    # corpus.load() is newest-first for interactive research. Extractors that
    # deduplicate repeated releases must see the original disclosure first or a
    # later comparative table can incorrectly become the observation's as-of.
    docs = sorted(load(company, as_of=as_of), key=lambda doc: (doc.published_at, doc.path.name))
    rows = EXTRACTORS[company](docs, rejected)
    selected: dict[tuple[str, str], MetricObservation] = {}
    for row in rows:
        if row.kind is not Kind.ACTUAL or row.as_of > as_of:
            continue
        identity = (row.metric_key, row.period.key)
        prior = selected.get(identity)
        if prior is None or _observation_rank(row) < _observation_rank(prior):
            selected[identity] = row
    return selected


def _latest_resolved_quarter(
    company: Company,
    actuals: dict[tuple[str, str], MetricObservation],
) -> Period:
    if company is Company.HAS:
        years = [
            row.period.year
            for row in actuals.values()
            if row.metric_key in {"net_fees", "pre_exc_basic_eps", "pre_exc_operating_profit"}
            and row.period.is_full_year
        ]
        if not years:
            raise ValueError("hays: no resolved annual actuals")
        return Period(year=max(years), quarter=4)

    route_keys = {
        key
        for metric in submitted_specs(company)
        for key in (
            *ACTUAL_ROUTES[(company, metric.key)].exact_keys,
            *ACTUAL_ROUTES[(company, metric.key)].proxy_keys,
        )
    }
    periods = [
        row.period
        for row in actuals.values()
        if row.metric_key in route_keys and row.period.quarter is not None
    ]
    if not periods:
        raise ValueError(f"{company.value}: no resolved quarterly actuals")
    return max(periods, key=lambda period: period.sort_key)


def _resolve_actual(
    company: Company,
    metric_key: str,
    slot: Period,
    actuals: dict[tuple[str, str], MetricObservation],
) -> tuple[MetricObservation | None, str, str | None]:
    route = ACTUAL_ROUTES[(company, metric_key)]
    if route.cadence == "annual" and slot.quarter != 4:
        return (
            None,
            "unavailable",
            "Hays publishes these challenge metrics annually; no quarterly actual is invented.",
        )
    actual_period = Period(year=slot.year, quarter=None) if route.cadence == "annual" else slot
    candidates: list[tuple[MetricObservation, str]] = []
    for key in route.exact_keys:
        row = actuals.get((key, actual_period.key))
        if row is not None:
            candidates.append((row, "exact"))
    for key in route.proxy_keys:
        row = actuals.get((key, actual_period.key))
        if row is not None:
            candidates.append((row, "proxy"))
    if candidates:
        # An exact comparative disclosed a year later is less useful as a
        # historical outcome boundary than a labelled proxy disclosed on the
        # original results date. Earliest publication wins; exact wins ties.
        row, match = min(
            candidates,
            key=lambda item: (item[0].as_of, item[1] != "exact", item[0].source_file),
        )
        note = None
        if match == "proxy":
            note = (
                f"Exact {metric_key} actual was not published on the original results date; "
                f"{row.metric_key} is used as a labelled proxy."
            )
        return row, match, note
    return (
        None,
        "unavailable",
        f"No filing-derived {metric_key} actual was recovered for {actual_period.key}.",
    )


def _eligible_history(
    actual: MetricObservation,
    cutoff: date,
    actuals: dict[tuple[str, str], MetricObservation],
) -> list[MetricObservation]:
    return sorted(
        (
            row
            for row in actuals.values()
            if row.metric_key == actual.metric_key
            and row.as_of <= cutoff
            and row.period.sort_key < actual.period.sort_key
        ),
        key=lambda row: row.period.sort_key,
    )


def _trace_input(row: MetricObservation, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "period": row.period.key,
        "value": row.value,
        "units": row.units.value,
        "publishedAt": row.as_of.isoformat(),
        "sourceFile": row.source_file,
        "excerpt": row.excerpt,
        "extractor": row.extractor,
        "note": row.note,
    }


def _history_changes(
    history: list[MetricObservation], units: Unit
) -> list[tuple[MetricObservation, MetricObservation, float]]:
    by_period = {row.period.key: row for row in history}
    changes: list[tuple[MetricObservation, MetricObservation, float]] = []
    for current in history:
        prior = by_period.get(current.period.prior_year().key)
        if prior is None:
            continue
        if units is Unit.PERCENT:
            change = current.value - prior.value
        elif abs(prior.value) > 1e-9:
            change = current.value / prior.value - 1.0
        else:
            continue
        changes.append((current, prior, change))
    return changes[-8:]


def _forecast(
    actual: MetricObservation,
    cutoff: date,
    actuals: dict[tuple[str, str], MetricObservation],
    submitted_units: Unit,
) -> dict[str, Any] | None:
    history = _eligible_history(actual, cutoff, actuals)
    by_period = {row.period.key: row for row in history}
    anchor = by_period.get(actual.period.prior_year().key)
    if anchor is None and history:
        anchor = history[-1]
    if anchor is None:
        return None
    seasonal_anchor = anchor.period.key == actual.period.prior_year().key
    changes = _history_changes(history, submitted_units)
    trend_values = [change for _, _, change in changes]
    trend = statistics.median(trend_values) if trend_values else 0.0

    if submitted_units is Unit.PERCENT:
        value = anchor.value + trend
        formula = f"{anchor.value:.4f} + {trend:.4f}pp = {value:.4f}"
        trend_label = "median trailing year-over-year change"
    else:
        # Keep one extraordinary historical transition from exploding a replay.
        trend = min(max(trend, -0.75), 1.50)
        value = anchor.value * (1.0 + trend)
        formula = f"{anchor.value:.4f} × (1 + {trend:.4%}) = {value:.4f}"
        trend_label = "median trailing year-over-year growth"

    dispersion = (
        statistics.median(abs(item - trend) for item in trend_values)
        if trend_values
        else 0.0
    )
    input_rows: dict[tuple[str, str], MetricObservation] = {
        (anchor.metric_key, anchor.period.key): anchor
    }
    for current, prior, _ in changes:
        input_rows[(current.metric_key, current.period.key)] = current
        input_rows[(prior.metric_key, prior.period.key)] = prior
    inputs = [
        _trace_input(row, "seasonal anchor" if row is anchor else "trend history")
        for row in sorted(input_rows.values(), key=lambda item: item.period.sort_key)[-12:]
    ]
    return {
        "value": value,
        "method": (
            "seasonal_median_yoy_replay"
            if seasonal_anchor
            else "latest_actual_median_yoy_fallback"
        ),
        "modelVersion": "five-year-replay-v1",
        "reasoning": (
            f"Use {'the same fiscal period one year earlier' if seasonal_anchor else 'the latest published actual'} "
            f"as the anchor, then apply the {trend_label} available before {cutoff.isoformat()}."
        ),
        "trace": {
            "cutoff": cutoff.isoformat(),
            "lookAheadPolicy": "Every forecast input was published on or before the cutoff; the target actual was published later.",
            "steps": [
                {
                    "label": "Lock the replay cutoff",
                    "calculation": f"actual publication {actual.as_of.isoformat()} − 1 day",
                    "result": cutoff.isoformat(),
                },
                {
                    "label": "Select the seasonal anchor",
                    "calculation": (
                        f"same fiscal period: {actual.period.prior_year().key}"
                        if seasonal_anchor
                        else f"seasonal anchor unavailable; latest published actual: {anchor.period.key}"
                    ),
                    "result": f"{anchor.value:.4f} {anchor.units.value}",
                },
                {
                    "label": trend_label.capitalize(),
                    "calculation": (
                        ", ".join(f"{item:.4f}" for item in trend_values)
                        if trend_values
                        else "no prior transitions; neutral trend"
                    ),
                    "result": f"{trend:.4f}",
                },
                {
                    "label": "Calculate the replay forecast",
                    "calculation": formula,
                    "result": f"{value:.4f} {submitted_units.value}",
                },
            ],
            "inputs": inputs,
            "trendObservations": len(changes),
            "trendDispersion": dispersion,
        },
    }


def _actual_payload(
    row: MetricObservation, match: str, note: str | None
) -> dict[str, Any]:
    return {
        "value": row.value,
        "units": row.units.value,
        "period": row.period.key,
        "publishedAt": row.as_of.isoformat(),
        "sourceFile": row.source_file,
        "sourceExists": (CORPUS_ROOT / row.source_file).is_file(),
        "excerpt": row.excerpt,
        "extractor": row.extractor,
        "metricKey": row.metric_key,
        "match": match,
        "note": note or row.note,
    }


def _metric_result(
    company: Company,
    metric_key: str,
    label: str,
    units: Unit,
    slot: Period,
    actuals: dict[tuple[str, str], MetricObservation],
) -> dict[str, Any]:
    actual, match, gap = _resolve_actual(company, metric_key, slot, actuals)
    base: dict[str, Any] = {
        "metricKey": metric_key,
        "label": label,
        "units": units.value,
        "status": "unavailable" if actual is None else "resolved",
        "actualMatch": match,
        "availabilityReason": gap,
        "forecast": None,
        "actual": None,
        "delta": None,
    }
    if actual is None:
        return base

    cutoff = actual.as_of - timedelta(days=1)
    forecast = _forecast(actual, cutoff, actuals, units)
    base["actual"] = _actual_payload(actual, match, gap)
    if forecast is None:
        base["status"] = "unforecastable"
        base["availabilityReason"] = "Actual exists, but no prior-year seasonal anchor was available before the cutoff."
        return base

    signed = forecast["value"] - actual.value
    absolute = abs(signed)
    relative = absolute / max(abs(actual.value), 1e-9) * 100.0
    base["forecast"] = forecast
    base["delta"] = {
        "signed": signed,
        "absolute": absolute,
        "relativePct": relative,
        "mode": "percentage_points" if units is Unit.PERCENT else "reported_units",
        "formula": f"{forecast['value']:.4f} − {actual.value:.4f} = {signed:+.4f}",
    }
    return base


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    resolved = [row for row in rows if row["actual"] is not None]
    evaluated = [row for row in rows if row["delta"] is not None]
    exact = sum(row["actualMatch"] == "exact" for row in resolved)
    proxy = sum(row["actualMatch"] == "proxy" for row in resolved)
    absolute = [row["delta"]["absolute"] for row in evaluated]
    signed = [row["delta"]["signed"] for row in evaluated]
    relative = [row["delta"]["relativePct"] for row in evaluated]
    units = {row["units"] for row in evaluated}
    comparable_raw_units = len(units) == 1
    return {
        "requestedMetricSlots": len(rows),
        "actualAvailable": len(resolved),
        "exactActuals": exact,
        "proxyActuals": proxy,
        "unavailable": len(rows) - len(resolved),
        "evaluated": len(evaluated),
        "actualCoveragePct": len(resolved) / len(rows) * 100.0 if rows else 0.0,
        "exactCoveragePct": exact / len(rows) * 100.0 if rows else 0.0,
        "meanAbsoluteDelta": (
            statistics.fmean(absolute) if absolute and comparable_raw_units else None
        ),
        "meanSignedDelta": (
            statistics.fmean(signed) if signed and comparable_raw_units else None
        ),
        "meanAbsoluteScaledErrorPct": (
            statistics.fmean(relative) if relative else None
        ),
        "rootMeanSquaredDelta": (
            math.sqrt(statistics.fmean(value * value for value in signed))
            if signed and comparable_raw_units
            else None
        ),
        "rawDeltaAggregation": (
            "single_unit" if comparable_raw_units else "not_comparable_across_units"
        ),
    }


def build_backtest(*, as_of: date, quarters: int = 20) -> dict[str, Any]:
    companies: list[dict[str, Any]] = []
    all_metric_rows: list[dict[str, Any]] = []

    for company in COMPANY_ORDER:
        actuals = _actual_observations(company, as_of)
        end = _latest_resolved_quarter(company, actuals)
        slots = _quarter_window(end, quarters)
        period_rows: list[dict[str, Any]] = []
        company_metric_rows: list[dict[str, Any]] = []
        specs = submitted_specs(company)
        for slot in slots:
            metrics = [
                _metric_result(
                    company,
                    metric.key,
                    metric.label or metric.key,
                    metric.units,
                    slot,
                    actuals,
                )
                for metric in specs
            ]
            company_metric_rows.extend(metrics)
            period_rows.append({"period": slot.key, "metrics": metrics})

        metric_summaries = []
        for metric in specs:
            rows = [row for row in company_metric_rows if row["metricKey"] == metric.key]
            metric_summaries.append(
                {
                    "metricKey": metric.key,
                    "label": metric.label,
                    "units": metric.units.value,
                    **_summary(rows),
                }
            )
        company_payload = {
            "company": company.value,
            "ticker": ticker(company),
            "name": display_name(company),
            "cadence": "annual challenge metrics" if company is Company.HAS else "quarterly",
            "requestedPeriods": quarters,
            "windowStart": slots[0].key,
            "windowEnd": slots[-1].key,
            "periods": period_rows,
            "metricSummaries": metric_summaries,
            "summary": _summary(company_metric_rows),
        }
        companies.append(company_payload)
        all_metric_rows.extend(company_metric_rows)

    overall = _summary(all_metric_rows)
    overall.update(
        {
            "requestedCompanyPeriods": len(COMPANY_ORDER) * quarters,
            "companies": len(COMPANY_ORDER),
            "metricsPerPeriod": 3,
        }
    )
    return {
        "meta": {
            "title": "Five-year point-in-time forecast replay",
            "asOf": as_of.isoformat(),
            "quartersPerCompany": quarters,
            "modelVersion": "five-year-replay-v1",
            "modelScope": (
                "Transparent seasonal median-YoY replay using only filing actuals "
                "published before each cutoff. Historical Street and prediction-market "
                "inputs are not fabricated."
            ),
            "actualSource": "Frozen company filings in challenge/offline-data",
        },
        "summary": overall,
        "companies": companies,
    }


def write_backtest(payload: dict[str, Any], output: Path = DEFAULT_OUTPUT) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--quarters", type=int, default=20)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.quarters < 1:
        parser.error("--quarters must be positive")
    payload = build_backtest(as_of=date.fromisoformat(args.as_of), quarters=args.quarters)
    write_backtest(payload, args.output)
    print(
        f"Wrote {args.output}: {payload['summary']['requestedCompanyPeriods']} company-periods, "
        f"{payload['summary']['requestedMetricSlots']} metric slots, "
        f"{payload['summary']['actualAvailable']} actuals"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
