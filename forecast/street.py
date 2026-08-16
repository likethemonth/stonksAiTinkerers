"""Reconstruct the hidden Street benchmark from point-in-time source histories."""

from __future__ import annotations

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
) -> EngineContribution:
    """Return the exact-metric Street estimate, or an explicit abstention."""
    cutoff = as_of or date.today()
    key = (display_name(company), metric.label or "")
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
