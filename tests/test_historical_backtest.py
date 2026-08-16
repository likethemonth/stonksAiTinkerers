from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest

from forecast.historical_backtest import build_backtest


@pytest.fixture(scope="module")
def replay() -> dict:
    return build_backtest(as_of=date(2026, 8, 16), quarters=20)


@pytest.fixture(scope="module")
def full_replay() -> dict:
    return build_backtest(as_of=date(2026, 8, 16))


def metric_rows(replay: dict) -> list[dict]:
    return [
        metric
        for company in replay["companies"]
        for period in company["periods"]
        for metric in period["metrics"]
    ]


def test_five_year_denominator_and_actual_coverage(replay: dict) -> None:
    assert replay["summary"]["requestedCompanyPeriods"] == 80
    assert replay["summary"]["requestedMetricSlots"] == 240
    assert replay["summary"]["actualAvailable"] == 195
    assert replay["summary"]["unavailable"] == 45
    assert replay["summary"]["evaluated"] == 195
    assert len(replay["companies"]) == 4
    assert all(len(company["periods"]) == 20 for company in replay["companies"])
    assert all(
        len(period["metrics"]) == 3
        for company in replay["companies"]
        for period in company["periods"]
    )


def test_full_replay_uses_every_recoverable_filing_period(full_replay: dict) -> None:
    assert full_replay["meta"]["windowMode"] == "full_filing_history"
    assert full_replay["meta"]["quartersPerCompany"] is None
    assert full_replay["summary"]["requestedCompanyPeriods"] == 139
    assert full_replay["summary"]["requestedMetricSlots"] == 417
    assert full_replay["summary"]["actualAvailable"] == 305
    assert full_replay["summary"]["unavailable"] == 112
    assert full_replay["summary"]["evaluated"] == 285

    spans = {
        company["ticker"]: (
            company["windowStart"],
            company["windowEnd"],
            company["requestedPeriods"],
        )
        for company in full_replay["companies"]
    }
    assert spans == {
        "HD": ("FY2013Q1", "FY2026Q1", 53),
        "ADI": ("FY2020Q4", "FY2026Q2", 23),
        "LSE:HAS": ("FY2018Q4", "FY2025Q4", 29),
        "DE": ("FY2018Q1", "FY2026Q2", 34),
    }


def test_full_replay_evaluated_rows_remain_point_in_time(full_replay: dict) -> None:
    corpus = Path("challenge/offline-data")
    evaluated = [row for row in metric_rows(full_replay) if row["delta"] is not None]
    assert len(evaluated) == 285
    for row in evaluated:
        cutoff = date.fromisoformat(row["forecast"]["trace"]["cutoff"])
        actual_date = date.fromisoformat(row["actual"]["publishedAt"])
        assert cutoff < actual_date
        assert (corpus / row["actual"]["sourceFile"]).is_file()
        assert row["forecast"]["trace"]["inputs"]
        assert all(
            date.fromisoformat(item["publishedAt"]) <= cutoff
            for item in row["forecast"]["trace"]["inputs"]
        )


def test_every_evaluated_row_is_point_in_time_and_sourced(replay: dict) -> None:
    corpus = Path("challenge/offline-data")
    for row in metric_rows(replay):
        if row["actual"] is None:
            continue
        assert row["forecast"] is not None
        cutoff = date.fromisoformat(row["forecast"]["trace"]["cutoff"])
        actual_date = date.fromisoformat(row["actual"]["publishedAt"])
        assert cutoff < actual_date
        assert row["actual"]["sourceExists"] is True
        assert (corpus / row["actual"]["sourceFile"]).is_file()
        assert row["actual"]["excerpt"]
        assert row["forecast"]["trace"]["steps"]
        assert row["forecast"]["trace"]["inputs"]
        for item in row["forecast"]["trace"]["inputs"]:
            assert date.fromisoformat(item["publishedAt"]) <= cutoff
            assert (corpus / item["sourceFile"]).is_file()


def test_delta_arithmetic_is_exact(replay: dict) -> None:
    for row in metric_rows(replay):
        if row["delta"] is None:
            continue
        expected = row["forecast"]["value"] - row["actual"]["value"]
        assert math.isclose(row["delta"]["signed"], expected, rel_tol=0, abs_tol=1e-9)
        assert math.isclose(
            row["delta"]["absolute"], abs(expected), rel_tol=0, abs_tol=1e-9
        )
        assert row["delta"]["formula"]


def test_hays_annual_cadence_is_not_fabricated_as_quarterly(replay: dict) -> None:
    hays = next(company for company in replay["companies"] if company["ticker"] == "LSE:HAS")
    assert hays["summary"]["actualAvailable"] == 15
    assert hays["summary"]["unavailable"] == 45
    for period in hays["periods"]:
        if period["period"].endswith("Q4"):
            assert all(metric["status"] == "resolved" for metric in period["metrics"])
        else:
            assert all(metric["status"] == "unavailable" for metric in period["metrics"])
            assert all("annually" in metric["availabilityReason"] for metric in period["metrics"])


def test_home_depot_adjusted_eps_proxy_is_explicit(replay: dict) -> None:
    home_depot = next(company for company in replay["companies"] if company["ticker"] == "HD")
    eps = next(
        metric
        for metric in home_depot["metricSummaries"]
        if metric["metricKey"] == "adj_eps"
    )
    assert eps["actualAvailable"] == 20
    assert eps["exactActuals"] == 1
    assert eps["proxyActuals"] == 19
    proxy_rows = [
        metric
        for period in home_depot["periods"]
        for metric in period["metrics"]
        if metric["metricKey"] == "adj_eps" and metric["actualMatch"] == "proxy"
    ]
    assert all("labelled proxy" in row["actual"]["note"] for row in proxy_rows)


def test_home_depot_adjusted_eps_baseline_never_uses_full_year_eps_as_quarterly_anchor(replay: dict) -> None:
    home_depot = next(company for company in replay["companies"] if company["ticker"] == "HD")
    period = next(period for period in home_depot["periods"] if period["period"] == "FY2026Q1")
    eps = next(metric for metric in period["metrics"] if metric["metricKey"] == "adj_eps")
    baseline = next(lane for lane in eps["lanes"] if lane["id"] == "fundamental")
    assert baseline["estimate"] == pytest.approx(3.3631128108305264)
    inputs = eps["baselineForecast"]["trace"]["inputs"]
    assert inputs
    assert all("Q" in item["period"] for item in inputs)
    assert eps["forecast"]["value"] == pytest.approx(3.3865564054152633)


def test_cross_unit_summaries_do_not_average_raw_deltas(replay: dict) -> None:
    assert replay["summary"]["meanAbsoluteDelta"] is None
    assert replay["summary"]["rawDeltaAggregation"] == "not_comparable_across_units"
    assert all(company["summary"]["meanAbsoluteDelta"] is None for company in replay["companies"])
    assert all(
        metric["rawDeltaAggregation"] == "single_unit"
        for company in replay["companies"]
        for metric in company["metricSummaries"]
    )


def test_replay_is_deterministic(replay: dict) -> None:
    assert build_backtest(as_of=date(2026, 8, 16), quarters=20) == replay


def test_period_engine_lane_denominators_are_explicit(replay: dict) -> None:
    coverage = replay["summary"]["laneCoverage"]
    assert coverage == {
        "fundamental": {"available": 195, "requested": 240},
        "street": {"available": 50, "requested": 240},
        "expert": {"available": 5, "requested": 240},
        "market": {"available": 9, "requested": 240},
    }
    assert replay["meta"]["modelVersion"] == "period-engine-replay-v2"
    assert "Missing lanes abstain" in replay["meta"]["modelScope"]


def test_2025_q1_replays_real_street_data_without_inventing_other_lanes(replay: dict) -> None:
    home_depot = next(company for company in replay["companies"] if company["ticker"] == "HD")
    period = next(period for period in home_depot["periods"] if period["period"] == "FY2025Q1")
    eps = next(metric for metric in period["metrics"] if metric["metricKey"] == "adj_eps")
    lanes = {lane["id"]: lane for lane in eps["lanes"]}
    assert lanes["street"]["status"] == "available"
    assert lanes["street"]["estimate"] == 3.59
    assert lanes["street"]["components"][0]["publishedAt"] == "2025-05-19"
    assert lanes["expert"]["status"] == "abstained"
    assert lanes["market"]["status"] == "abstained"
    assert eps["metaForecast"]["eligibleLanes"] == ["fundamental", "street"]


def test_exact_named_expert_call_enters_only_its_matching_period_and_metric(replay: dict) -> None:
    adi = next(company for company in replay["companies"] if company["ticker"] == "ADI")
    period = next(period for period in adi["periods"] if period["period"] == "FY2023Q4")
    revenue = next(metric for metric in period["metrics"] if metric["metricKey"] == "revenue")
    expert = next(lane for lane in revenue["lanes"] if lane["id"] == "expert")
    assert expert["status"] == "available"
    assert expert["estimate"] == 3000.0
    assert expert["components"][0]["sourceName"] == "Brian Colello"
    assert expert["components"][0]["publishedAt"] == "2023-08-23"


def test_external_numeric_sources_obey_cutoffs_and_exact_units(replay: dict) -> None:
    for row in metric_rows(replay):
        if row["forecast"] is None:
            continue
        cutoff = date.fromisoformat(row["forecast"]["cutoff"])
        for lane in row["lanes"]:
            for component in lane["components"]:
                assert component["units"] == row["units"]
                assert date.fromisoformat(component["publishedAt"]) <= cutoff
                assert "guidance issued" not in str(component.get("claimId", "")).lower()
                assert component["sourceRole"] != "anonymous"


def test_market_lane_is_binary_signal_only_and_point_in_time(replay: dict) -> None:
    signals = [
        lane
        for row in metric_rows(replay)
        for lane in row["lanes"]
        if lane["id"] == "market" and lane["status"] == "signal_only"
    ]
    assert len(signals) == 9
    assert replay["summary"]["marketMeanBrierScore"] == pytest.approx(0.049843221765333366)
    for lane in signals:
        signal = lane["signal"]
        assert lane["estimate"] is None
        assert lane["numericWeight"] == 0
        assert 0 <= signal["probability"] <= 1
        assert signal["outcomeConsistent"] is True
        assert signal["lastTradeAt"] < signal["cutoff"]
        assert signal["sourceContentSha256"]


def test_sources_below_three_matured_calls_are_not_ranked(replay: dict) -> None:
    for scorecard in replay["sourceScorecards"]:
        if scorecard["n"] < 3:
            assert scorecard["status"] == "case_study"
            assert scorecard["rank"] is None
        else:
            assert scorecard["status"] == "rankable"
            assert scorecard["rank"] is not None
