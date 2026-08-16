"""Fast, DB-free tests for the forecast ontology and point-in-time corpus access.

These run in milliseconds and catch the two classes of mistake that would silently
cost real points: unit-entry errors (a percentage entered as 0.045 instead of 4.5)
and look-ahead leakage in the backtest.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from forecast.corpus import CALENDARS, TARGET_PERIOD, load
from forecast.schema import (
    Company,
    DocType,
    Estimate,
    Kind,
    MetricForecast,
    MetricObservation,
    Period,
    Unit,
)

# --------------------------------------------------------------------------- #
# Periods and fiscal calendars
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw,year,quarter",
    [("FY2026Q2", 2026, 2), ("FY2026", 2026, None), ("fy2026q4", 2026, 4)],
)
def test_period_parse(raw: str, year: int, quarter: int | None) -> None:
    p = Period.parse(raw)
    assert (p.year, p.quarter) == (year, quarter)


@pytest.mark.parametrize("raw", ["Q2 2026", "FY26Q2", "2026", "", "FY2026Q5"])
def test_period_parse_rejects_junk(raw: str) -> None:
    with pytest.raises(ValueError):
        Period.parse(raw)


def test_full_year_sorts_after_q4() -> None:
    assert Period.parse("FY2026").sort_key > Period.parse("FY2026Q4").sort_key


@pytest.mark.parametrize(
    "company,day,expected",
    [
        # Anchors taken from actual results in the corpus. All four run different
        # fiscal years and two label them in opposite directions, so these pin down
        # the exact off-by-one-year and off-by-one-quarter traps.
        (Company.ADI, date(2026, 5, 2), "FY2026Q2"),  # Q2 FY26 ended 2 May 2026
        (Company.ADI, date(2026, 8, 1), "FY2026Q3"),  # the target quarter
        (Company.ADI, date(2026, 1, 31), "FY2026Q1"),
        (Company.HD, date(2026, 5, 3), "FY2026Q1"),  # Q1 FY26 ended 3 May 2026
        (Company.HD, date(2026, 8, 2), "FY2026Q2"),  # the target quarter
        (Company.DE, date(2026, 5, 3), "FY2026Q2"),  # Q2 FY26 ended 3 May 2026
        (Company.DE, date(2025, 11, 2), "FY2026Q1"),
        (Company.HAS, date(2026, 6, 30), "FY2026Q4"),  # Hays FY ends 30 June
    ],
)
def test_fiscal_calendar_anchors(company: Company, day: date, expected: str) -> None:
    assert CALENDARS[company].period_of(day).key == expected


def test_target_periods_match_companies_json() -> None:
    assert TARGET_PERIOD[Company.HD].key == "FY2026Q2"
    assert TARGET_PERIOD[Company.ADI].key == "FY2026Q3"
    assert TARGET_PERIOD[Company.HAS].key == "FY2026"
    assert TARGET_PERIOD[Company.DE].key == "FY2026Q3"


# --------------------------------------------------------------------------- #
# Point-in-time integrity
# --------------------------------------------------------------------------- #


def test_corpus_loads_and_is_newest_first() -> None:
    docs = load(Company.ADI)
    assert len(docs) > 200
    assert all(
        a.published_at >= b.published_at for a, b in zip(docs, docs[1:])
    ), "corpus must be sorted newest first"


def test_as_of_never_leaks_the_future() -> None:
    """The one invariant the backtest depends on."""
    cutoff = date(2026, 2, 17)
    for company in Company:
        docs = load(company, as_of=cutoff)
        assert docs, f"{company} has no documents before {cutoff}"
        assert max(d.published_at for d in docs) <= cutoff


def test_as_of_is_strictly_narrowing() -> None:
    full = load(Company.HAS)
    cut = load(Company.HAS, as_of=date(2026, 2, 17))
    assert 0 < len(cut) < len(full)


def test_frontmatter_null_sentinel_resolved() -> None:
    """`source_url: null` must never reach downstream code as the string 'null'."""
    for doc in load(Company.HD)[:50]:
        assert doc.period_hint != "null"


# --------------------------------------------------------------------------- #
# Observations
# --------------------------------------------------------------------------- #


def _observation(**overrides: object) -> MetricObservation:
    base = dict(
        company=Company.ADI,
        metric_key="revenue",
        period=Period.parse("FY2026Q3"),
        value=3900.0,
        units=Unit.USD_M,
        kind=Kind.GUIDE_MID,
        as_of=date(2026, 5, 20),
        source_file="analog-devices/filings/example.md",
        doc_type=DocType.FILING,
        excerpt="forecasting revenue of $3.9 billion",
        extractor="test",
    )
    return MetricObservation(**{**base, **overrides})


def test_observation_collapses_ragged_pdf_whitespace() -> None:
    obs = _observation(excerpt="revenue  of\n  $3.9   billion ")
    assert obs.excerpt == "revenue of $3.9 billion"


def test_observation_rejects_fractional_percentage() -> None:
    """0.045 for 4.5% is the single most expensive unit slip available."""
    with pytest.raises(ValidationError):
        _observation(metric_key="adj_gross_margin_pct", value=730.0, units=Unit.PERCENT)


def test_observation_rejects_pounds_where_pence_expected() -> None:
    with pytest.raises(ValidationError):
        _observation(metric_key="pre_exc_basic_eps", value=0.062, units=Unit.GBP_PENCE)


def test_observation_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        _observation(sneaky_extra="nope")


# --------------------------------------------------------------------------- #
# Forecasts — failure policy
# --------------------------------------------------------------------------- #


def _forecast(**overrides: object) -> MetricForecast:
    base = dict(
        label="Revenue",
        units=Unit.USD_M,
        value=3980.0,
        reasoning="guidance midpoint 3900 lifted by the shrunk realisation ratio",
        citations=["analog-devices/filings/example.md"],
    )
    return MetricForecast(**{**base, **overrides})


def test_forecast_clamps_rather_than_raising() -> None:
    """A missing forecast scores 5.0, the worst possible. Never refuse a number."""
    f = _forecast(value=9999.0, plausible_low=3400.0, plausible_high=4300.0).finalise()
    assert f.value == 4300.0
    assert any("clamped" in w for w in f.warnings)


def test_forecast_inside_band_is_untouched() -> None:
    f = _forecast(value=3980.0, plausible_low=3400.0, plausible_high=4300.0).finalise()
    assert f.value == 3980.0
    assert not f.warnings


def test_forecast_survives_an_inverted_band() -> None:
    f = _forecast(plausible_low=4300.0, plausible_high=3400.0).finalise()
    assert f.value == 3980.0  # band ignored, number still ships
    assert any("inverted" in w for w in f.warnings)


def test_forecast_hard_fails_on_unit_error() -> None:
    """Unit errors are always bugs, so these stay fatal."""
    with pytest.raises(ValidationError):
        _forecast(label="Adjusted gross margin", units=Unit.PERCENT, value=0.73 * 1000)


def test_forecast_refuses_silent_uncited_number() -> None:
    with pytest.raises(ValidationError):
        _forecast(citations=[])


def test_forecast_allows_uncited_number_if_warned() -> None:
    """Degrade loudly, but still ship a value."""
    f = _forecast(citations=[], warnings=["no citation: fell back to seasonal naive"])
    assert f.value == 3980.0


def test_estimate_requires_positive_sigma() -> None:
    """Inverse-variance weighting divides by sigma^2, so zero is not allowed."""
    with pytest.raises(ValidationError):
        Estimate(
            estimator="guidance_realisation",
            value=3980.0,
            sigma=0.0,
            n_observations=8,
            reasoning="x",
        )
