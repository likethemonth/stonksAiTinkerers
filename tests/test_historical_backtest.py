from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest

from forecast.historical_backtest import build_backtest


@pytest.fixture(scope="module")
def replay() -> dict:
    return build_backtest(as_of=date(2026, 8, 16), quarters=20)


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
