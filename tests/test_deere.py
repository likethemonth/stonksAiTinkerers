from __future__ import annotations

from datetime import date

import pytest

from forecast.corpus import load
from forecast.extract import deere
from forecast.schema import Company, Kind, Period


@pytest.fixture(scope="module")
def observations():
    return deere.extract(load(Company.DE, as_of=date(2025, 8, 15)))


@pytest.mark.parametrize(
    "metric,value",
    [
        ("worldwide_net_sales_revenues", 12_018.0),
        ("diluted_eps_gaap", 4.75),
        ("ppa_net_sales", 4_273.0),
        ("ppa_operating_profit", 580.0),
    ],
)
def test_q3_fy25_actuals_are_extracted(observations, metric, value) -> None:
    row = next(
        item
        for item in observations
        if item.period == Period.parse("FY2025Q3")
        and item.metric_key == metric
        and item.kind is Kind.ACTUAL
    )
    assert row.value == value


def test_cutoff_contains_no_target_quarter_actual(observations) -> None:
    assert not any(item.period == Period.parse("FY2026Q3") for item in observations)
