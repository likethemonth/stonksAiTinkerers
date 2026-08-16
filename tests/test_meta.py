from __future__ import annotations

import pytest
from pydantic import ValidationError

from forecast.meta import meta_forecast
from forecast.schema import (
    ContributionStatus,
    Engine,
    EngineContribution,
    Estimate,
    Unit,
)


def contribution(
    engine: Engine,
    value: float | None,
    *,
    sigma: float = 1.0,
    reliability: float = 1.0,
    families: list[str] | None = None,
) -> EngineContribution:
    if value is None:
        return EngineContribution(
            engine=engine,
            status=ContributionStatus.ABSTAINED,
            note="no economically relevant market",
        )
    return EngineContribution(
        engine=engine,
        status=ContributionStatus.AVAILABLE,
        estimate=Estimate(
            estimator=f"{engine.value}_test",
            value=value,
            sigma=sigma,
            n_observations=4,
            reasoning="test estimate",
            citations=[f"{engine.value}.md"],
        ),
        reliability=reliability,
        source_families=families or [engine.value],
        note="available in test",
    )


def test_requires_every_engine_to_be_explicit() -> None:
    with pytest.raises(ValueError, match="missing explicit"):
        meta_forecast(
            "Revenue",
            Unit.USD_M,
            [
                contribution(Engine.STREET, 100.0),
                contribution(Engine.FUNDAMENTAL, 110.0),
            ],
        )


def test_abstention_is_visible_and_has_no_weight() -> None:
    forecast = meta_forecast(
        "Revenue",
        Unit.USD_M,
        [
            contribution(Engine.STREET, 100.0),
            contribution(Engine.FUNDAMENTAL, 110.0),
            contribution(Engine.PREDICTION_MARKET, None),
        ],
    )
    assert forecast.value == pytest.approx(105.0)
    assert {weight.engine for weight in forecast.meta_weights} == {
        Engine.STREET,
        Engine.FUNDAMENTAL,
    }
    assert any("prediction_market abstained" in warning for warning in forecast.warnings)


def test_lower_sigma_and_higher_reliability_earn_more_weight() -> None:
    forecast = meta_forecast(
        "Revenue",
        Unit.USD_M,
        [
            contribution(Engine.STREET, 100.0, sigma=10.0, reliability=1.0),
            contribution(Engine.FUNDAMENTAL, 120.0, sigma=5.0, reliability=0.8),
            contribution(Engine.PREDICTION_MARKET, None),
        ],
    )
    weights = {weight.engine: weight.normalized_weight for weight in forecast.meta_weights}
    assert weights[Engine.FUNDAMENTAL] > weights[Engine.STREET]
    assert 110.0 < forecast.value < 120.0


def test_shared_source_families_reduce_precision() -> None:
    independent = meta_forecast(
        "Revenue",
        Unit.USD_M,
        [
            contribution(Engine.STREET, 100.0, families=["analysts"]),
            contribution(Engine.FUNDAMENTAL, 100.0, families=["filings"]),
            contribution(Engine.PREDICTION_MARKET, 100.0, families=["markets"]),
        ],
    )
    overlapping = meta_forecast(
        "Revenue",
        Unit.USD_M,
        [
            contribution(Engine.STREET, 100.0, families=["consensus"]),
            contribution(Engine.FUNDAMENTAL, 100.0, families=["filings"]),
            contribution(Engine.PREDICTION_MARKET, 100.0, families=["consensus"]),
        ],
    )
    assert overlapping.sigma > independent.sigma


def test_available_contribution_requires_an_estimate() -> None:
    with pytest.raises(ValidationError):
        EngineContribution(
            engine=Engine.STREET,
            status=ContributionStatus.AVAILABLE,
            note="broken",
        )
