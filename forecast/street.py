"""Reconstruct the hidden Street benchmark from point-in-time source histories."""

from __future__ import annotations

import csv
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from forecast.metrics import MetricSpec, display_name, output_file
from forecast.schema import (
    Company,
    ContributionStatus,
    Engine,
    EngineContribution,
    Estimate,
    Period,
    Unit,
)
from forecasting.backtest import (
    PRIOR_ERROR,
    STREET_SOURCE_TYPES,
    blend_current,
    load_observations,
    score_sources,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORICAL = REPO_ROOT / "forecasting" / "data" / "historical_forecasts.csv"
CURRENT = REPO_ROOT / "forecasting" / "data" / "current_forecasts.csv"
RESEARCH_FALLBACK = REPO_ROOT / "agent" / "fable-research-forecast.json"

_SIGMA_FLOORS = {
    Unit.USD_M: 25.0,
    Unit.GBP_M: 1.0,
    Unit.USD_PER_SHARE: 0.05,
    Unit.GBP_PENCE: 0.05,
    Unit.PERCENT: 0.30,
}


@lru_cache(maxsize=8)
def _street_rows(cutoff: date) -> dict[tuple[str, str], dict[str, object]]:
    historical = load_observations(HISTORICAL)
    current = load_observations(CURRENT)
    scores = score_sources(historical, cutoff)
    rows = blend_current(
        current,
        scores,
        as_of=cutoff,
        source_types=STREET_SOURCE_TYPES,
    )
    return {(str(row["company"]), str(row["metric"])): row for row in rows}


@lru_cache(maxsize=8)
def _fallback_rows(cutoff: date) -> dict[tuple[str, str], dict]:
    if not RESEARCH_FALLBACK.exists():
        return {}
    payload = json.loads(RESEARCH_FALLBACK.read_text(encoding="utf-8"))
    if date.fromisoformat(payload["asOf"]) > cutoff:
        return {}
    rows: dict[tuple[str, str], dict] = {}
    for block in payload["forecasts"].values():
        for metric in block["metrics"]:
            rows[(block["company"], metric["label"])] = metric
    return rows


@lru_cache(maxsize=8)
def _historical_rows(cutoff: date) -> dict[tuple[str, str, str], dict]:
    """Point-in-time Street forecasts for *closed* periods, keyed by period.

    ``_street_rows`` is period-blind: it keys on (company, metric) because the
    current panel only ever describes the one period being submitted. That is
    why the Street engine abstained on every historical cell of the system
    backtest — not because no archive exists, but because nothing could address
    it by period.

    ``forecasting/data/historical_forecasts.csv`` is that archive: 39 consensus
    rows, each stamped with the date it was published, one day before the
    company reported. Every row targets a period that has since closed, so this
    map can never serve a submitted period and cannot move a submitted number.
    """
    rows: dict[tuple[str, str, str], list[dict]] = {}
    with HISTORICAL.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("source_type") not in STREET_SOURCE_TYPES:
                continue
            forecast_date = row.get("forecast_date")
            if not forecast_date or date.fromisoformat(forecast_date) > cutoff:
                continue
            if not row.get("forecast"):
                continue
            key = (row["company"], row["metric"], row["period"])
            rows.setdefault(key, []).append(row)

    blended: dict[tuple[str, str, str], dict] = {}
    for key, group in rows.items():
        weights = [max(float(item.get("quality") or 0.5), 0.01) for item in group]
        total = sum(weights)
        value = sum(
            float(item["forecast"]) * weight for item, weight in zip(group, weights)
        ) / total
        blended[key] = {
            "value": value,
            "n_sources": len(group),
            "sources": sorted({item["source_name"] for item in group}),
            "urls": sorted({item["source_url"] for item in group if item.get("source_url")}),
            "as_of": max(item["forecast_date"] for item in group),
        }
    return blended


def _sigma(value: float, units: Unit, components: list[dict]) -> float:
    if components:
        total = sum(float(component["weight"]) for component in components)
        relative_error = sum(
            float(component["weight"])
            * float(component["shrunk_error"] or PRIOR_ERROR)
            for component in components
        ) / total
    else:
        relative_error = PRIOR_ERROR
    scale = max(abs(value), 1.0) if units is Unit.PERCENT else abs(value)
    return max(scale * relative_error, _SIGMA_FLOORS[units])


def street_contribution(
    company: Company,
    metric: MetricSpec,
    *,
    as_of: date | None = None,
    period: Period | None = None,
) -> EngineContribution:
    """Return the exact-metric Street estimate, or an explicit abstention.

    ``period`` is supplied only by the historical replay. Omitting it reproduces
    the submitted run exactly, because the archive it unlocks contains no row
    for any period still open.
    """
    cutoff = as_of or date.today()
    key = (display_name(company), metric.label or "")

    if period is not None:
        archived = _historical_rows(cutoff).get(
            (display_name(company), metric.label or "", period.key)
        )
        if archived is not None:
            value = float(archived["value"])
            return EngineContribution(
                engine=Engine.STREET,
                status=ContributionStatus.AVAILABLE,
                estimate=Estimate(
                    estimator="street_archived_consensus",
                    value=value,
                    sigma=_sigma(value, metric.units, []),
                    n_observations=int(archived["n_sources"]),
                    reasoning=(
                        f"Archived point-in-time consensus for {period.key} from "
                        f"{archived['n_sources']} source(s), published "
                        f"{archived['as_of']}, quality-weighted."
                    ),
                    citations=list(archived["urls"]),
                ),
                reliability=min(0.9, 0.6 + 0.1 * int(archived["n_sources"])),
                source_families=["public_consensus"],
                note="archived exact-metric Street consensus for a closed period",
            )

    row = _street_rows(cutoff).get(key)
    if row is not None:
        components = list(row.get("components", []))
        value = float(row["unrounded_forecast"])
        families = sorted(
            {
                "company_consensus"
                if component.get("source_type") == "company_consensus"
                else "analyst_research"
                if component.get("source_type") in {"analyst", "social_explicit"}
                else "public_consensus"
                for component in components
            }
        )
        estimate = Estimate(
            estimator="street_reliability_blend",
            value=value,
            sigma=_sigma(value, metric.units, components),
            n_observations=sum(int(component.get("observations", 0)) for component in components),
            reasoning=(
                f"Point-in-time Street reconstruction from {len(components)} current "
                "source(s), bias-corrected and weighted by shrunk historical error."
            ),
            citations=[str(component["source_url"]) for component in components],
        )
        return EngineContribution(
            engine=Engine.STREET,
            status=ContributionStatus.AVAILABLE,
            estimate=estimate,
            reliability=min(0.9, 0.6 + 0.1 * len(components)),
            source_families=families,
            note="numeric exact-metric Street panel",
        )

    fallback = _fallback_rows(cutoff).get(key)
    if fallback is not None:
        value = float(fallback["street"])
        return EngineContribution(
            engine=Engine.STREET,
            status=ContributionStatus.AVAILABLE,
            estimate=Estimate(
                estimator="street_research_reconstruction",
                value=value,
                sigma=_sigma(value, metric.units, []),
                n_observations=0,
                reasoning=(
                    "Research-run reconstruction used because the numeric exact-metric "
                    f"panel has no eligible row. {fallback['rationale']}"
                ),
                citations=["agent/FableResearchRun1.md"],
            ),
            reliability=0.45,
            source_families=["reconstructed_street_artifact"],
            note=f"fallback Street reconstruction for {output_file(company)}",
        )

    return EngineContribution(
        engine=Engine.STREET,
        status=ContributionStatus.ABSTAINED,
        reliability=1.0,
        source_families=[],
        note="no point-in-time exact-metric Street source available",
    )
