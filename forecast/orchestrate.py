"""Build and reconcile numeric engines plus zero-weight research critics."""

from __future__ import annotations

from datetime import date

from forecast.fundamental import enrich_with_drivers, source_families
from forecast.market_backtest import promotion_note
from forecast.meta import meta_forecast
from forecast.metrics import submitted_specs
from forecast.numinous import numinous_constraint
from forecast.polymarket import market_constraint
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
    signal = market_constraint(company, metric_key, as_of)
    if signal is None:
        return EngineContribution(
            engine=Engine.PREDICTION_MARKET,
            status=ContributionStatus.ABSTAINED,
            note="no direct, point-in-time market with a defensible metric mapping",
        )
    return EngineContribution(
        engine=Engine.PREDICTION_MARKET,
        status=ContributionStatus.SIGNAL_ONLY,
        signal=signal,
        # SIGNAL_ONLY entries receive zero numeric weight. Promotion to AVAILABLE
        # requires a passing pre-resolution walk-forward ablation.
        reliability=0.03,
        source_families=["prediction_market", "public_consensus"],
        note=(
            "binary beat price retained as a one-quantile research signal and "
            f"adversarial critic; {promotion_note(as_of=as_of or date.today())}"
        ),
    )


def _numinous_contribution(
    company: Company, metric_key: str, *, as_of: date | None
) -> EngineContribution:
    signal = numinous_constraint(company, metric_key, as_of)
    if signal is None:
        return EngineContribution(
            engine=Engine.NUMINOUS,
            status=ContributionStatus.ABSTAINED,
            note="no point-in-time Numinous forecast for this exact metric and basis",
        )
    return EngineContribution(
        engine=Engine.NUMINOUS,
        status=ContributionStatus.SIGNAL_ONLY,
        signal=signal,
        reliability=0.01,
        source_families=["external_ai_forecaster", "public_information"],
        note=(
            "Numinous agent-pool probability retained as an independent critic; "
            "it is not a traded price and has no held-out earnings calibration, "
            "so it receives zero numeric weight"
        ),
    )


def orchestrate(
    company: Company,
    fundamental_metrics: list[MetricForecast],
    *,
    as_of: date | None = None,
) -> list[MetricForecast]:
    """Return final metrics after numeric engines and all explicit critics."""
    enriched = enrich_with_drivers(company, fundamental_metrics, as_of=as_of)
    by_label = {metric.label: metric for metric in enriched}
    final: list[MetricForecast] = []
    for metric_spec in submitted_specs(company):
        metric = by_label[metric_spec.label or ""]
        contributions = [
            street_contribution(company, metric_spec, as_of=as_of),
            _fundamental_contribution(company, metric),
            _prediction_contribution(company, metric_spec.key, as_of=as_of),
            _numinous_contribution(company, metric_spec.key, as_of=as_of),
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
