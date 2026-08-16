from __future__ import annotations

from datetime import date

from forecast.baselines import BASELINES
from forecast.estimators import reconcile
from forecast.metrics import submitted_specs
from forecast.ml import hd_estimates
from forecast.orchestrate import orchestrate
from forecast.schema import Company, Engine


def _hd_baselines():
    return [
        reconcile(spec.label or "", spec.units, [BASELINES[Company.HD][spec.label or ""]])
        for spec in submitted_specs(Company.HD)
    ]


def test_only_gate_passing_ml_outputs_are_loaded() -> None:
    estimates = hd_estimates(date(2026, 8, 16))
    assert {key for company, key in estimates if company is Company.HD} == {
        "net_sales",
        "adj_eps",
        "comp_sales_pct",
    }
    assert all(estimate.sigma > 0 for estimate in estimates.values())


def test_ml_artifact_respects_point_in_time_cutoff() -> None:
    assert hd_estimates(date(2026, 8, 15)) == {}


def test_ml_is_nested_inside_fundamental_engine() -> None:
    metrics = orchestrate(
        Company.HD,
        _hd_baselines(),
        as_of=date(2026, 8, 16),
    )
    assert all(len(metric.engine_contributions) == 4 for metric in metrics)
    for metric in metrics:
        fundamental = next(
            item
            for item in metric.engine_contributions
            if item.engine is Engine.FUNDAMENTAL
        )
        assert "historical_actuals_ml" in fundamental.source_families
