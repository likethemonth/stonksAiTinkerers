"""Overlap-aware reconciliation for the three independent forecast engines.

The top-level contract is deliberately stricter than the estimator reconciler:
all three engines must be represented, even when an engine abstains. This keeps
missing market coverage visible and prevents a copied consensus value from being
mistaken for independent evidence.
"""

from __future__ import annotations

import math

from forecast.estimators import BAND_SIGMAS, DISAGREEMENT_SIGMAS
from forecast.schema import (
    ContributionStatus,
    Engine,
    EngineContribution,
    EngineWeight,
    MetricForecast,
    Unit,
)


def _overlap(a: EngineContribution, b: EngineContribution) -> float:
    left, right = set(a.source_families), set(b.source_families)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _overlap_penalty(
    contribution: EngineContribution, available: list[EngineContribution]
) -> float:
    """Penalize shared evidence without throwing a useful lens away entirely."""
    maximum = max(
        (_overlap(contribution, other) for other in available if other is not contribution),
        default=0.0,
    )
    # Full source overlap halves precision; no overlap leaves it unchanged.
    return 1.0 - 0.5 * maximum


def meta_forecast(
    label: str,
    units: Unit,
    contributions: list[EngineContribution],
) -> MetricForecast:
    """Combine Street, fundamental and market contributions into one forecast.

    Base precision is ``1 / sigma^2``. Engine reliability and a source-overlap
    penalty scale that precision. Abstentions receive no numeric weight but stay
    in the audit record.
    """
    engines = [c.engine for c in contributions]
    if len(engines) != len(set(engines)):
        raise ValueError(f"{label}: duplicate engine contribution")
    missing = set(Engine) - set(engines)
    if missing:
        names = ", ".join(sorted(engine.value for engine in missing))
        raise ValueError(f"{label}: missing explicit contribution/abstention for {names}")

    available = [
        c
        for c in contributions
        if c.status is ContributionStatus.AVAILABLE and c.estimate is not None
    ]
    if not available:
        raise ValueError(f"{label}: every engine abstained")

    weighted: list[tuple[EngineContribution, float, float]] = []
    for contribution in available:
        assert contribution.estimate is not None
        penalty = _overlap_penalty(contribution, available)
        raw_weight = (
            contribution.reliability * penalty / contribution.estimate.sigma**2
        )
        weighted.append((contribution, raw_weight, penalty))

    total_weight = sum(raw for _, raw, _ in weighted)
    value = sum(
        contribution.estimate.value * raw
        for contribution, raw, _ in weighted
        if contribution.estimate is not None
    ) / total_weight
    sigma = total_weight**-0.5

    weights = [
        EngineWeight(
            engine=contribution.engine,
            raw_weight=raw,
            overlap_penalty=penalty,
            normalized_weight=raw / total_weight,
        )
        for contribution, raw, penalty in weighted
    ]
    weight_by_engine = {weight.engine: weight for weight in weights}
    reasoning = "Meta-forecast: " + "; ".join(
        f"{contribution.engine.value} {contribution.estimate.value:,.2f} "
        f"(sigma {contribution.estimate.sigma:,.2f}, "
        f"reliability {contribution.reliability:.0%}, "
        f"overlap penalty {weight_by_engine[contribution.engine].overlap_penalty:.0%}, "
        f"weight {weight_by_engine[contribution.engine].normalized_weight:.0%})"
        for contribution in available
        if contribution.estimate is not None
    ) + f" -> {value:,.2f}."

    warnings = [
        f"{c.engine.value} abstained: {c.note}"
        for c in contributions
        if c.status is ContributionStatus.ABSTAINED
    ]
    needs_review = False
    for index, left in enumerate(available):
        assert left.estimate is not None
        for right in available[index + 1 :]:
            assert right.estimate is not None
            pair_sigma = math.hypot(left.estimate.sigma, right.estimate.sigma)
            z = abs(left.estimate.value - right.estimate.value) / pair_sigma
            if z > DISAGREEMENT_SIGMAS:
                needs_review = True
                warnings.append(
                    f"{left.engine.value} and {right.engine.value} disagree by "
                    f"{z:.2f} combined sigmas"
                )

    citations: list[str] = []
    estimates = []
    for contribution in available:
        assert contribution.estimate is not None
        estimates.append(contribution.estimate)
        for citation in contribution.estimate.citations:
            if citation not in citations:
                citations.append(citation)

    forecast = MetricForecast(
        label=label,
        units=units,
        value=value,
        sigma=sigma,
        reasoning=reasoning,
        estimates=estimates,
        engine_contributions=contributions,
        meta_weights=weights,
        citations=citations,
        plausible_low=value - BAND_SIGMAS * sigma,
        plausible_high=value + BAND_SIGMAS * sigma,
        warnings=warnings,
        needs_review=needs_review,
    )
    return forecast.finalise()
