"""Build and reconcile the three top-level engines for all submitted metrics."""

from __future__ import annotations

from datetime import date

from forecast.fundamental import enrich_with_drivers, source_families
from forecast.meta import meta_forecast
from forecast.metrics import submitted_specs
from forecast.polymarket import market_estimate
from forecast.schema import (
    Company,
    ContributionStatus,
    Engine,
    EngineContribution,
    Estimate,
    MetricForecast,
)
from forecast.street import street_contribution


def _fundamental_contribution(
    company: Company, metric: MetricForecast
) -> EngineContribution:
    estimate = Estimate(
        estimator="fundamental_engine",
        value=metric.value,
        sigma=metric.sigma or max(abs(metric.value) * 0.08, 0.05),
        n_observations=sum(item.n_observations for item in metric.estimates),
        reasoning=metric.reasoning,
        citations=metric.citations,
    )
    return EngineContribution(
        engine=Engine.FUNDAMENTAL,
        status=ContributionStatus.AVAILABLE,
        estimate=estimate,
        reliability=0.85 if not metric.needs_review else 0.60,
        source_families=source_families(company, metric),
        note="deterministic company model with compatible driver nowcasts",
    )


def _prediction_contribution(
    company: Company, metric_key: str, *, as_of: date | None
) -> EngineContribution:
    estimate = market_estimate(company, metric_key, as_of)
    if estimate is None:
        return EngineContribution(
            engine=Engine.PREDICTION_MARKET,
            status=ContributionStatus.ABSTAINED,
            note="no direct, point-in-time market with a defensible metric mapping",
        )
    return EngineContribution(
        engine=Engine.PREDICTION_MARKET,
        status=ContributionStatus.AVAILABLE,
        estimate=estimate,
        # One binary quantile is useful but not as well calibrated as a complete
        # earnings distribution. The consensus strike is also shared with Street.
        reliability=0.03,
        source_families=["prediction_market", "public_consensus"],
        note=(
            "direct beat market interpreted as one quantile, not a point observation; "
            "low top-level reliability prevents false precision from dominating"
        ),
    )


def orchestrate(
    company: Company,
    fundamental_metrics: list[MetricForecast],
    *,
    as_of: date | None = None,
) -> list[MetricForecast]:
    """Return final metrics after all three engines and the meta-forecaster."""
    enriched = enrich_with_drivers(company, fundamental_metrics, as_of=as_of)
    by_label = {metric.label: metric for metric in enriched}
    final: list[MetricForecast] = []
    for metric_spec in submitted_specs(company):
        metric = by_label[metric_spec.label or ""]
        contributions = [
            street_contribution(company, metric_spec, as_of=as_of),
            _fundamental_contribution(company, metric),
            _prediction_contribution(company, metric_spec.key, as_of=as_of),
        ]
        combined = meta_forecast(
            metric_spec.label or "", metric_spec.units, contributions
        )
        combined.needs_review = combined.needs_review or metric.needs_review
        for warning in metric.warnings:
            if warning not in combined.warnings:
                combined.warnings.append(warning)
        final.append(combined)
    return final
