from __future__ import annotations

from datetime import date

from forecast.corpus import load
from forecast.estimators import hays_full_year_net_fees
from forecast.extract import hays
from forecast.schema import Company, Period


def test_hays_fy_reconstruction_uses_h1_and_h2_growth() -> None:
    """FY2026 net fees = reported H1 + a grown FY25 H2 base.

    The expected band moved from 885-892 to 900-907, and the citation count from
    5 to 4, when the disposed-country subtraction was removed. That subtraction
    was wrong twice over: the GBP15m figure comes from the Q4 statement's FY27
    outlook section and describes what will be absent NEXT year, while those
    countries were owned for essentially all of FY26 and are already inside
    reported FY26 net fees; and the actual-basis growth rates applied here
    already reflect the divestments. The Street engine independently produces
    902.40, which corroborates the corrected figure rather than the old one.
    """
    observations = hays.extract(load(Company.HAS, as_of=date(2026, 8, 16)))
    estimate = hays_full_year_net_fees(observations, period=Period.parse("FY2026"))
    assert estimate is not None
    assert 900.0 < estimate.value < 907.0
    # H1 actual, FY25 full year, Q3 statement, Q4 statement.
    assert len(estimate.citations) == 4


def test_hays_reconstruction_does_not_subtract_disposals() -> None:
    """Guard the specific regression: the disposal figure must not be netted off.

    Subtracting it produces ~888.5. Anything at or below 895 means the
    subtraction has come back.
    """
    observations = hays.extract(load(Company.HAS, as_of=date(2026, 8, 16)))
    estimate = hays_full_year_net_fees(observations, period=Period.parse("FY2026"))
    assert estimate is not None
    assert estimate.value > 895.0, (
        f"got {estimate.value:.2f}: the ~15m disposed-country figure appears to "
        "have been subtracted again"
    )
