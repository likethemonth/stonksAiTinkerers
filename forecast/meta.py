"""Overlap-aware reconciliation for numeric engines and research critics.

The top-level contract is deliberately stricter than the estimator reconciler:
every configured engine must be represented, even when it abstains. This keeps
missing market/forecaster coverage visible and prevents a copied consensus value
from being mistaken for independent evidence.
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

PROBABILITY_DISAGREEMENT = 0.25


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
    """Combine numeric contributions while preserving unweighted critics.

    Base precision is ``1 / sigma^2``. Engine reliability and a source-overlap
    penalty scale that precision. Abstentions and unvalidated research signals
    receive no numeric weight but stay in the audit record.
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
    warnings.extend(
        f"{c.engine.value} signal only (0% weight): {c.note}"
        for c in contributions
        if c.status is ContributionStatus.SIGNAL_ONLY
    )
    needs_review = False
    signals = [
        contribution
        for contribution in contributions
        if contribution.status is ContributionStatus.SIGNAL_ONLY
        and contribution.signal is not None
    ]
    for index, left in enumerate(signals):
        assert left.signal is not None
        for right in signals[index + 1 :]:
            assert right.signal is not None
            comparable = (
                left.signal.relation == right.signal.relation
                and math.isclose(
                    left.signal.threshold, right.signal.threshold, abs_tol=0.005
                )
            )
            gap = abs(left.signal.probability - right.signal.probability)
            if comparable and gap > PROBABILITY_DISAGREEMENT:
                needs_review = True
                warnings.append(
                    f"{left.engine.value} and {right.engine.value} probabilities "
                    f"disagree by {gap:.1%} at threshold {left.signal.threshold:g}"
                )

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
