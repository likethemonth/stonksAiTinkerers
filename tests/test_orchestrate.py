from __future__ import annotations

from datetime import date

import pytest

from forecast.baselines import BASELINES
from forecast.estimators import reconcile
from forecast.metrics import submitted_specs
from forecast.orchestrate import orchestrate
from forecast.schema import Company, ContributionStatus, Engine


def baseline_metrics(company: Company):
    return [
        reconcile(spec.label or "", spec.units, [BASELINES[company][spec.label or ""]])
        for spec in submitted_specs(company)
    ]


def test_orchestrator_records_every_engine_for_every_metric() -> None:
    for company in (Company.HD, Company.HAS, Company.DE):
        metrics = orchestrate(
            company,
            baseline_metrics(company),
            as_of=date(2026, 8, 16),
        )
        assert len(metrics) == 3
        for metric in metrics:
            assert {item.engine for item in metric.engine_contributions} == set(Engine)
            assert sum(
                weight.normalized_weight for weight in metric.meta_weights
            ) == pytest.approx(1.0)


def test_driver_nowcast_is_nested_in_fundamental_not_a_fourth_engine() -> None:
    metrics = orchestrate(
        Company.HD,
        baseline_metrics(Company.HD),
        as_of=date(2026, 8, 16),
    )
    comps = next(metric for metric in metrics if metric.label.startswith("Comparable"))
    fundamental = next(
        item for item in comps.engine_contributions if item.engine is Engine.FUNDAMENTAL
    )
    assert "external_drivers" in fundamental.source_families
    assert len(comps.engine_contributions) == 4


def test_missing_prediction_market_is_explicit_abstention() -> None:
    metrics = orchestrate(
        Company.HAS,
        baseline_metrics(Company.HAS),
        as_of=date(2026, 8, 16),
    )
    for metric in metrics:
        market = next(
            item
            for item in metric.engine_contributions
            if item.engine is Engine.PREDICTION_MARKET
        )
        assert market.status is ContributionStatus.ABSTAINED


def test_deere_registry_key_maps_to_direct_eps_market() -> None:
    metrics = orchestrate(
        Company.DE,
        baseline_metrics(Company.DE),
        as_of=date(2026, 8, 16),
    )
    eps = next(metric for metric in metrics if metric.label == "Diluted EPS (GAAP)")
    market = next(
        item
        for item in eps.engine_contributions
        if item.engine is Engine.PREDICTION_MARKET
    )
    assert market.status is ContributionStatus.SIGNAL_ONLY
    assert market.estimate is None
    assert market.signal is not None
    assert market.signal.threshold == pytest.approx(4.72)
    numinous = next(
        item for item in eps.engine_contributions if item.engine is Engine.NUMINOUS
    )
    assert numinous.status is ContributionStatus.SIGNAL_ONLY
    assert numinous.signal is not None
    assert numinous.signal.probability == pytest.approx(0.2912)


def test_unvalidated_binary_market_proxy_has_zero_final_weight() -> None:
    metrics = orchestrate(
        Company.HD,
        baseline_metrics(Company.HD),
        as_of=date(2026, 8, 16),
    )
    eps = next(metric for metric in metrics if metric.label == "Adjusted diluted EPS")
    market = next(
        item
        for item in eps.engine_contributions
        if item.engine is Engine.PREDICTION_MARKET
    )
    assert market.status is ContributionStatus.SIGNAL_ONLY
    assert market.estimate is None
    assert market.signal is not None
    assert market.signal.probability == pytest.approx(0.785)
    assert all(
        item.engine is not Engine.PREDICTION_MARKET for item in eps.meta_weights
    )
    assert any("signal only (0% weight)" in warning for warning in eps.warnings)


def test_numinous_is_a_separate_zero_weight_critic() -> None:
    metrics = orchestrate(
        Company.HD,
        baseline_metrics(Company.HD),
        as_of=date(2026, 8, 16),
    )
    eps = next(metric for metric in metrics if metric.label == "Adjusted diluted EPS")
    numinous = next(
        item for item in eps.engine_contributions if item.engine is Engine.NUMINOUS
    )
    assert numinous.status is ContributionStatus.SIGNAL_ONLY
    assert numinous.estimate is None
    assert numinous.signal is not None
    assert numinous.signal.provider == "numinous"
    assert numinous.signal.threshold == pytest.approx(4.73)
    assert numinous.signal.probability == pytest.approx(0.2931)
    assert all(item.engine is not Engine.NUMINOUS for item in eps.meta_weights)
    assert eps.needs_review
    assert any(
        "prediction_market and numinous probabilities disagree" in warning
        for warning in eps.warnings
    )
