from __future__ import annotations

from datetime import date

from forecast.corpus import load
from forecast.estimators import hays_full_year_net_fees
from forecast.extract import hays
from forecast.schema import Company, Period


def test_hays_fy_reconstruction_uses_h1_q3_q4_and_disposals() -> None:
    observations = hays.extract(load(Company.HAS, as_of=date(2026, 8, 16)))
    estimate = hays_full_year_net_fees(observations, period=Period.parse("FY2026"))
    assert estimate is not None
    assert 885.0 < estimate.value < 892.0
    assert len(estimate.citations) == 5
