"""Point-in-time replay with filing-sourced actuals and full traces.

This is deliberately separate from ``forecasting.backtest``. That module ranks
individual Street sources. This module defines the product backtest denominator:
every recoverable filing period per company, three challenge metrics per period,
and an explicit outcome for every resulting metric slot.

The replay model is a transparent seasonal/trend baseline. It is not presented
as a historical replay of Street or prediction-market engines because those
point-in-time inputs do not exist for every historical cutoff. Its purpose is to
make the infrastructure honest and auditable while leaving a stable contract for
additional historical engines.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
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
STREET_ARCHIVE = REPO_ROOT / "forecasting" / "data" / "historical_forecasts.csv"
ANALYST_ARCHIVE = REPO_ROOT / "analyst_knowledge" / "dataset" / "backtest.json"
MARKET_ARCHIVE = REPO_ROOT / "forecast" / "data" / "polymarket" / "historical-signals.json"
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


COMPANY_FROM_NAME = {
    "Home Depot": Company.HD,
    "Analog Devices": Company.ADI,
    "Hays plc": Company.HAS,
    "Deere & Company": Company.DE,
}
COMPANY_FROM_TICKER = {
    "HD": Company.HD,
    "ADI": Company.ADI,
    "HAS.L": Company.HAS,
    "LSE:HAS": Company.HAS,
    "DE": Company.DE,
}
CSV_METRIC_KEYS = {
    (Company.HD, "Net sales"): "net_sales",
    (Company.HD, "Adjusted diluted EPS"): "adj_eps",
    (Company.HD, "Comparable sales, total company"): "comp_sales_pct",
    (Company.ADI, "Revenue"): "revenue",
    (Company.ADI, "Adjusted diluted EPS"): "adj_eps",
    (Company.ADI, "Adjusted gross margin"): "adj_gross_margin_pct",
    (Company.HAS, "Net fees"): "net_fees",
    (Company.HAS, "Pre-exceptional basic EPS"): "pre_exc_basic_eps",
    (Company.HAS, "Pre-exceptional operating profit"): "pre_exc_operating_profit",
    (Company.DE, "Worldwide net sales and revenues"): "worldwide_net_sales_revenues",
    (Company.DE, "Diluted EPS (GAAP)"): "diluted_eps_gaap",
    (Company.DE, "Production & Precision Ag operating profit"): "ppa_operating_profit",
}
ANALYST_METRIC_KEYS = {
    (Company.HD, "net_sales"): "net_sales",
    (Company.HD, "adjusted_diluted_eps"): "adj_eps",
    (Company.HD, "comparable_sales_growth"): "comp_sales_pct",
    (Company.ADI, "revenue"): "revenue",
    (Company.ADI, "adjusted EPS"): "adj_eps",
    (Company.HAS, "net_fees"): "net_fees",
    (Company.HAS, "basic_eps_pre_exceptional"): "pre_exc_basic_eps",
    (Company.HAS, "pre_exceptional_operating_profit"): "pre_exc_operating_profit",
    (Company.DE, "worldwide net sales and revenues"): "worldwide_net_sales_revenues",
    (Company.DE, "diluted EPS"): "diluted_eps_gaap",
    (Company.DE, "EPS"): "diluted_eps_gaap",
}


def _normalise_period(raw: str, company: Company) -> str | None:
    if "guidance issued" in raw.lower():
        return None
    compact = raw.upper().replace(" ", "")
    match = re.fullmatch(r"FY(\d{4})Q([1-4])", compact)
    if match:
        return f"FY{match.group(1)}Q{match.group(2)}"
    match = re.fullmatch(r"Q([1-4])FY(\d{4})", compact)
    if match:
        return f"FY{match.group(2)}Q{match.group(1)}"
    match = re.fullmatch(r"FY(\d{4})", compact)
    if match and company is Company.HAS:
        return f"FY{match.group(1)}Q4"
    return None


def _convert_analyst_value(value: Any, source_units: str, target_units: Unit) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    numeric = float(value)
    if source_units == "USD billions" and target_units is Unit.USD_M:
        return numeric * 1000.0
    compatible = {
        ("USD/share", Unit.USD_PER_SHARE),
        ("USD per diluted share", Unit.USD_PER_SHARE),
        ("GBP millions", Unit.GBP_M),
        ("GBP pence/share", Unit.GBP_PENCE),
        ("percent", Unit.PERCENT),
        ("percentage points", Unit.PERCENT),
    }
    return numeric if (source_units, target_units) in compatible else None


def _load_source_archive() -> list[dict[str, Any]]:
    """Load only pre-outcome numeric forecasts with explicit metric joins."""
    rows: list[dict[str, Any]] = []
    if STREET_ARCHIVE.is_file():
        with STREET_ARCHIVE.open(newline="", encoding="utf-8") as handle:
            for raw in csv.DictReader(handle):
                company = COMPANY_FROM_NAME.get(raw["company"])
                if company is None:
                    continue
                metric_key = CSV_METRIC_KEYS.get((company, raw["metric"]))
                period = _normalise_period(raw["period"], company)
                if metric_key is None or period is None:
                    continue
                source_type = raw["source_type"]
                lane = "street" if source_type == "consensus" else (
                    "fundamental" if source_type == "company_guidance" else None
                )
                if lane is None:
                    continue
                rows.append(
                    {
                        "lane": lane,
                        "company": company,
                        "metricKey": metric_key,
                        "period": period,
                        "value": float(raw["forecast"]),
                        "units": raw["units"],
                        "publishedAt": raw["forecast_date"],
                        "eventDate": raw["event_date"],
                        "sourceId": raw["source_id"],
                        "sourceName": raw["source_name"],
                        "sourceRole": source_type,
                        "sourceUrl": raw["source_url"],
                        "quality": float(raw["quality"]),
                        "claimId": None,
                        "provenanceTier": "curated_archive",
                        "archive": str(STREET_ARCHIVE.relative_to(REPO_ROOT)),
                    }
                )

    if ANALYST_ARCHIVE.is_file():
        analyst = json.loads(ANALYST_ARCHIVE.read_text(encoding="utf-8"))
        for raw in analyst.get("evaluations", []):
            company = COMPANY_FROM_TICKER.get(str(raw.get("ticker")))
            if company is None:
                continue
            metric_key = ANALYST_METRIC_KEYS.get((company, str(raw.get("metric"))))
            period = _normalise_period(str(raw.get("target_period", "")), company)
            if metric_key is None or period is None:
                continue
            role = raw.get("source_role")
            lane = "street" if role == "consensus" else (
                "expert" if role in {"individual", "firm_team"} else None
            )
            if lane is None:
                continue
            target_units = spec(company, metric_key).units
            value = _convert_analyst_value(raw.get("prediction"), str(raw.get("units")), target_units)
            if value is None:
                continue
            rows.append(
                {
                    "lane": lane,
                    "company": company,
                    "metricKey": metric_key,
                    "period": period,
                    "value": value,
                    "units": target_units.value,
                    "publishedAt": str(raw["published_at"])[:10],
                    "eventDate": str(raw["reported_at"])[:10],
                    "sourceId": raw["author_id"],
                    "sourceName": raw["author_display"],
                    "sourceRole": role,
                    "sourceUrl": raw["source_url"],
                    "quality": None,
                    "claimId": raw["claim_id"],
                    "provenanceTier": raw.get("provenance_tier"),
                    "archive": str(ANALYST_ARCHIVE.relative_to(REPO_ROOT)),
                }
            )
    return rows


def _load_market_archive() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not MARKET_ARCHIVE.is_file():
        return ({"retrievedAt": None, "cutoffPolicy": None}, [])
    payload = json.loads(MARKET_ARCHIVE.read_text(encoding="utf-8"))
    return payload, payload.get("records", [])


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


def _earliest_resolved_quarter(
    company: Company,
    actuals: dict[tuple[str, str], MetricObservation],
) -> Period:
    """Earliest filing-derived period for any routed challenge metric."""
    if company is Company.HAS:
        years = [
            row.period.year
            for row in actuals.values()
            if row.metric_key in {"net_fees", "pre_exc_basic_eps", "pre_exc_operating_profit"}
            and row.period.is_full_year
        ]
        if not years:
            raise ValueError("hays: no resolved annual actuals")
        return Period(year=min(years), quarter=4)

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
    return min(periods, key=lambda period: period.sort_key)


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
    company: Company,
    submitted_metric_key: str,
    actual: MetricObservation,
    cutoff: date,
    actuals: dict[tuple[str, str], MetricObservation],
) -> list[MetricObservation]:
    route = ACTUAL_ROUTES[(company, submitted_metric_key)]
    route_keys = (*route.exact_keys, *route.proxy_keys)
    candidates = [
        row
        for row in actuals.values()
        if row.metric_key in route_keys
        and row.as_of <= cutoff
        and row.period.sort_key < actual.period.sort_key
        and row.period.is_full_year == actual.period.is_full_year
    ]
    # One fiscal period may have both the submitted metric and a labelled proxy.
    # Prefer the exact route, then the earliest contemporaneous disclosure.
    exact_rank = {key: index for index, key in enumerate(route_keys)}
    selected: dict[str, MetricObservation] = {}
    for row in candidates:
        prior = selected.get(row.period.key)
        if prior is None or (
            exact_rank[row.metric_key], row.as_of, row.source_file
        ) < (
            exact_rank[prior.metric_key], prior.as_of, prior.source_file
        ):
            selected[row.period.key] = row
    return sorted(selected.values(), key=lambda row: row.period.sort_key)


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
    company: Company,
    submitted_metric_key: str,
    actual: MetricObservation,
    cutoff: date,
    actuals: dict[tuple[str, str], MetricObservation],
    submitted_units: Unit,
) -> dict[str, Any] | None:
    history = _eligible_history(company, submitted_metric_key, actual, cutoff, actuals)
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


def _external_components(
    archive: list[dict[str, Any]],
    *,
    lane: str,
    company: Company,
    metric_key: str,
    period: Period,
    units: Unit,
    cutoff: date,
) -> list[dict[str, Any]]:
    matches = [
        row
        for row in archive
        if row["lane"] == lane
        and row["company"] is company
        and row["metricKey"] == metric_key
        and row["period"] == period.key
        and row["units"] == units.value
        and date.fromisoformat(row["publishedAt"]) <= cutoff
    ]
    # The curated CSV is the primary consensus panel. The analyst ledger fills
    # periods absent from that panel but never double-counts the same consensus.
    if lane == "street" and any(row["archive"].endswith("historical_forecasts.csv") for row in matches):
        matches = [row for row in matches if row["archive"].endswith("historical_forecasts.csv")]
    unique: dict[tuple[str, str, float], dict[str, Any]] = {}
    for row in matches:
        unique[(row["sourceId"], row["publishedAt"], row["value"])] = row
    return [
        {
            key: value
            for key, value in row.items()
            if key not in {"company", "metricKey", "period", "lane"}
        }
        for row in sorted(unique.values(), key=lambda item: (item["publishedAt"], item["sourceId"]))
    ]


def _component_error(value: float, actual: float, units: Unit) -> dict[str, Any]:
    signed = value - actual
    return {
        "signed": signed,
        "absolute": abs(signed),
        "relativePct": abs(signed) / max(abs(actual), 1e-9) * 100.0,
        "mode": "percentage_points" if units is Unit.PERCENT else "reported_units",
    }


def _numeric_lane(
    lane_id: str,
    label: str,
    components: list[dict[str, Any]],
    units: Unit,
    actual: float,
    missing_reason: str,
) -> dict[str, Any]:
    if not components:
        return {
            "id": lane_id,
            "label": label,
            "status": "abstained",
            "estimate": None,
            "units": units.value,
            "sourceCount": 0,
            "components": [],
            "aggregation": None,
            "numericWeight": 0,
            "reason": missing_reason,
        }
    for component in components:
        component["error"] = _component_error(component["value"], actual, units)
    values = [component["value"] for component in components]
    estimate = statistics.median(values)
    return {
        "id": lane_id,
        "label": label,
        "status": "available",
        "estimate": estimate,
        "units": units.value,
        "sourceCount": len(components),
        "components": components,
        "aggregation": "single source" if len(values) == 1 else f"median of {len(values)} compatible inputs",
        "numericWeight": 1,
        "reason": None,
        "error": _component_error(estimate, actual, units),
    }


def _market_lane(
    market_rows: list[dict[str, Any]],
    *,
    company: Company,
    period: Period,
    metric_key: str,
    actual: float,
) -> dict[str, Any]:
    matches = [
        row
        for row in market_rows
        if row["ticker"] == ticker(company)
        and row["period"] == period.key
        and row["metricKey"] == metric_key
    ]
    if not matches:
        return {
            "id": "market",
            "label": "Prediction market",
            "status": "abstained",
            "estimate": None,
            "sourceCount": 0,
            "components": [],
            "numericWeight": 0,
            "signal": None,
            "reason": "No compatible pre-result prediction market was found for this metric and fiscal period.",
        }
    row = matches[0]
    realised = 1 if actual > row["strike"] else 0
    signal = {
        **row,
        "realisedFromFilingActual": realised,
        "outcomeConsistent": realised == row["binaryOutcome"],
    }
    return {
        "id": "market",
        "label": "Prediction market",
        "status": "signal_only",
        "estimate": None,
        "sourceCount": 1,
        "components": [],
        "numericWeight": 0,
        "signal": signal,
        "reason": (
            "Binary probability is evaluated with Brier score and receives zero numeric weight; "
            "it is not converted into an EPS point estimate."
        ),
    }


def _assemble_lanes(
    *,
    company: Company,
    metric_key: str,
    period: Period,
    units: Unit,
    actual: float,
    cutoff: date,
    baseline: dict[str, Any],
    source_archive: list[dict[str, Any]],
    market_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline_component = {
        "value": baseline["value"],
        "units": units.value,
        "publishedAt": cutoff.isoformat(),
        "sourceId": "filing-seasonal-baseline",
        "sourceName": "Filing-only seasonal baseline",
        "sourceRole": "model",
        "sourceUrl": None,
        "quality": None,
        "claimId": None,
        "provenanceTier": "company_filings",
        "archive": "challenge/offline-data",
        "modelMethod": baseline["method"],
        "modelTrace": baseline["trace"],
    }
    guidance = _external_components(
        source_archive,
        lane="fundamental",
        company=company,
        metric_key=metric_key,
        period=period,
        units=units,
        cutoff=cutoff,
    )
    fundamental = _numeric_lane(
        "fundamental",
        "Fundamental / filing model",
        [baseline_component, *guidance],
        units,
        actual,
        "No prior filing history or compatible management guidance was available.",
    )
    street = _numeric_lane(
        "street",
        "Street consensus",
        _external_components(
            source_archive,
            lane="street",
            company=company,
            metric_key=metric_key,
            period=period,
            units=units,
            cutoff=cutoff,
        ),
        units,
        actual,
        "No exact metric-period consensus forecast was archived before the cutoff.",
    )
    expert = _numeric_lane(
        "expert",
        "Named expert / research team",
        _external_components(
            source_archive,
            lane="expert",
            company=company,
            metric_key=metric_key,
            period=period,
            units=units,
            cutoff=cutoff,
        ),
        units,
        actual,
        "No named expert published an exact numeric forecast for this metric-period before the cutoff.",
    )
    market = _market_lane(
        market_rows,
        company=company,
        period=period,
        metric_key=metric_key,
        actual=actual,
    )
    lanes = [fundamental, street, expert, market]
    numeric = [lane for lane in lanes if lane["status"] == "available" and lane["estimate"] is not None]
    values = [lane["estimate"] for lane in numeric]
    value = statistics.median(values)
    calculation = "median(" + ", ".join(f"{lane['id']}={lane['estimate']:.4f}" for lane in numeric) + f") = {value:.4f}"
    meta = {
        "value": value,
        "units": units.value,
        "method": "median_of_available_numeric_lanes",
        "modelVersion": "period-engine-replay-v2",
        "cutoff": cutoff.isoformat(),
        "eligibleLanes": [lane["id"] for lane in numeric],
        "numericLaneCount": len(numeric),
        "calculation": calculation,
        "marketWeight": 0,
        "reasoning": (
            "Take the median of the available independent numeric lanes. Missing lanes abstain; "
            "binary market probabilities remain signal-only."
        ),
        "warning": (
            "Case-study meta-forecast: fewer than three independent numeric lanes."
            if len(numeric) < 3
            else "Three independent numeric lanes available; source histories may still be sparse."
        ),
        "error": _component_error(value, actual, units),
        "trace": {
            "cutoff": cutoff.isoformat(),
            "lookAheadPolicy": "Every numeric source predates or equals the cutoff; the target filing actual was published later.",
            "steps": [
                {
                    "label": "Freeze eligible evidence",
                    "calculation": f"metric={metric_key}; period={period.key}; cutoff={cutoff.isoformat()}",
                    "result": f"{sum(lane['sourceCount'] for lane in numeric)} numeric components",
                },
                {
                    "label": "Aggregate each lane",
                    "calculation": "; ".join(
                        f"{lane['id']}: {lane['aggregation']}" for lane in numeric
                    ),
                    "result": ", ".join(f"{lane['id']}={lane['estimate']:.4f}" for lane in numeric),
                },
                {
                    "label": "Form meta-forecast",
                    "calculation": calculation,
                    "result": f"{value:.4f} {units.value}",
                },
            ],
            "inputs": baseline["trace"]["inputs"],
            "trendObservations": baseline["trace"]["trendObservations"],
            "trendDispersion": baseline["trace"]["trendDispersion"],
        },
    }
    return lanes, meta


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
    source_archive: list[dict[str, Any]],
    market_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    actual, match, gap = _resolve_actual(company, metric_key, slot, actuals)
    base: dict[str, Any] = {
        "ticker": ticker(company),
        "metricKey": metric_key,
        "label": label,
        "units": units.value,
        "status": "unavailable" if actual is None else "resolved",
        "actualMatch": match,
        "availabilityReason": gap,
        "forecast": None,
        "baselineForecast": None,
        "metaForecast": None,
        "lanes": [],
        "actual": None,
        "delta": None,
    }
    if actual is None:
        return base

    cutoff = actual.as_of - timedelta(days=1)
    baseline = _forecast(company, metric_key, actual, cutoff, actuals, units)
    base["actual"] = _actual_payload(actual, match, gap)
    if baseline is None:
        base["status"] = "unforecastable"
        base["availabilityReason"] = "Actual exists, but no prior-year seasonal anchor was available before the cutoff."
        return base

    lanes, forecast = _assemble_lanes(
        company=company,
        metric_key=metric_key,
        period=slot,
        units=units,
        actual=actual.value,
        cutoff=cutoff,
        baseline=baseline,
        source_archive=source_archive,
        market_rows=market_rows,
    )
    base["baselineForecast"] = baseline
    base["metaForecast"] = forecast
    base["lanes"] = lanes
    base["forecast"] = forecast

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
    lane_ids = ("fundamental", "street", "expert", "market")
    lane_coverage = {
        lane_id: {
            "available": sum(
                any(
                    lane["id"] == lane_id and lane["status"] in {"available", "signal_only"}
                    for lane in row.get("lanes", [])
                )
                for row in rows
            ),
            "requested": len(rows),
        }
        for lane_id in lane_ids
    }
    market_scores = [
        lane["signal"]["brierScore"]
        for row in rows
        for lane in row.get("lanes", [])
        if lane["id"] == "market" and lane["status"] == "signal_only"
    ]
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
        "laneCoverage": lane_coverage,
        "marketMeanBrierScore": statistics.fmean(market_scores) if market_scores else None,
    }


def _source_scorecards(rows: list[dict[str, Any]], minimum_n: int = 3) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    labels: dict[tuple[str, str, str, str], str] = {}
    for row in rows:
        if row.get("actual") is None:
            continue
        for lane in row.get("lanes", []):
            if lane["id"] not in {"street", "expert"}:
                continue
            for component in lane["components"]:
                key = (lane["id"], component["sourceId"], row["ticker"], row["metricKey"])
                labels[key] = component["sourceName"]
                grouped[key].append(component["error"])
    scorecards = []
    for (lane_id, source_id, source_ticker, metric_key), errors in grouped.items():
        n = len(errors)
        scorecards.append(
            {
                "lane": lane_id,
                "sourceId": source_id,
                "sourceName": labels[(lane_id, source_id, source_ticker, metric_key)],
                "ticker": source_ticker,
                "metricKey": metric_key,
                "n": n,
                "meanAbsoluteScaledErrorPct": statistics.fmean(error["relativePct"] for error in errors),
                "meanAbsoluteDelta": statistics.fmean(error["absolute"] for error in errors),
                "status": "rankable" if n >= minimum_n else "case_study",
                "rank": None,
            }
        )
    rankable = sorted(
        (row for row in scorecards if row["status"] == "rankable"),
        key=lambda row: row["meanAbsoluteScaledErrorPct"],
    )
    for rank, row in enumerate(rankable, 1):
        row["rank"] = rank
    return sorted(
        scorecards,
        key=lambda row: (row["status"] != "rankable", row["rank"] or 10_000, row["sourceName"]),
    )


def build_backtest(*, as_of: date, quarters: int | None = None) -> dict[str, Any]:
    companies: list[dict[str, Any]] = []
    all_metric_rows: list[dict[str, Any]] = []
    source_archive = _load_source_archive()
    market_meta, market_rows = _load_market_archive()

    for company in COMPANY_ORDER:
        actuals = _actual_observations(company, as_of)
        end = _latest_resolved_quarter(company, actuals)
        if quarters is None:
            start = _earliest_resolved_quarter(company, actuals)
            slot_count = _quarter_index(end) - _quarter_index(start) + 1
        else:
            slot_count = quarters
        slots = _quarter_window(end, slot_count)
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
                    source_archive,
                    market_rows,
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
            "requestedPeriods": len(slots),
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
            "requestedCompanyPeriods": sum(len(company["periods"]) for company in companies),
            "companies": len(COMPANY_ORDER),
            "metricsPerPeriod": 3,
        }
    )
    return {
        "meta": {
            "title": "Full filing-history point-in-time forecast replay",
            "asOf": as_of.isoformat(),
            "quartersPerCompany": quarters,
            "windowMode": "full_filing_history" if quarters is None else "fixed_quarters",
            "modelVersion": "period-engine-replay-v2",
            "modelScope": (
                "Period-engine replay: filing/fundamental baseline, exact-metric Street consensus, "
                "named numeric expert calls, and binary prediction markets frozen before each result. "
                "Missing lanes abstain; the numeric meta-forecast is the median of available numeric lanes."
            ),
            "actualSource": "Frozen company filings in challenge/offline-data",
            "sourceCutoffPolicy": "Source publication date must be on or before the day preceding the filing result date.",
            "aggregationPolicy": "Median within each numeric lane, then median across available numeric lanes.",
            "marketPolicy": "Binary probabilities are signal-only, scored by Brier score, and receive zero numeric weight.",
            "rankingPolicy": "Source rankings require at least three matured exact metric forecasts; smaller histories are case studies.",
            "marketRetrievedAt": market_meta.get("retrievedAt"),
        },
        "summary": overall,
        "sourceScorecards": _source_scorecards(all_metric_rows),
        "companies": companies,
    }


def write_backtest(payload: dict[str, Any], output: Path = DEFAULT_OUTPUT) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument(
        "--quarters",
        type=int,
        default=None,
        help="Optional trailing-quarter limit; omitted replays all recoverable filing periods.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.quarters is not None and args.quarters < 1:
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
