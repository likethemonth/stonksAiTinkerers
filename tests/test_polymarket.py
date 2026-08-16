from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from forecast import polymarket
from forecast.schema import Company


def _write_history(path: Path) -> None:
    rows = []
    for index, (event_date, error) in enumerate(
        [
            ("2026-01-02", 0.0),
            ("2026-02-02", 1.0),
            ("2026-03-02", 2.0),
            ("2026-05-02", 3.0),
        ]
    ):
        rows.append(
            {
                "source_id": "public_consensus",
                "company": "Home Depot",
                "metric": "Adjusted diluted EPS",
                "forecast_date": f"2026-0{index + 1}-01",
                "event_date": event_date,
                "forecast": "10",
                "actual": str(10 + error),
            }
        )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_surprise_sigma_excludes_outcomes_after_cutoff(tmp_path: Path) -> None:
    history = tmp_path / "history.csv"
    _write_history(history)

    early, early_n = polymarket.surprise_sigma(
        Company.HD, "adj_eps", date(2026, 4, 1), history_path=history
    )
    late, late_n = polymarket.surprise_sigma(
        Company.HD, "adj_eps", date(2026, 6, 1), history_path=history
    )

    assert early_n == 3
    assert early[1] == polymarket.FALLBACK_SURPRISE_SIGMA[(Company.HD, "adj_eps")]
    assert late_n == 4
    assert late[1] == pytest.approx(1.290994, abs=1e-6)


def test_surprise_sigma_excludes_outcomes_on_date_granular_cutoff(tmp_path: Path) -> None:
    history = tmp_path / "history.csv"
    _write_history(history)

    _, before_result_n = polymarket.surprise_sigma(
        Company.HD, "adj_eps", date(2026, 5, 2), history_path=history
    )

    assert before_result_n == 3


def test_mid_price_maps_the_yes_outcome_by_label() -> None:
    market = {
        "outcomes": '["No", "Yes"]',
        "outcomePrices": '["0.2", "0.8"]',
    }
    assert polymarket._mid_price(market) == pytest.approx(0.8)


def test_wide_spread_uses_last_trade_like_polymarket_display() -> None:
    market = {
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.7", "0.3"]',
        "bestBid": 0.5,
        "bestAsk": 0.8,
        "lastTradePrice": 0.66,
    }
    assert polymarket._mid_price(market) == pytest.approx(0.66)


def test_snapshot_lookup_is_per_slug_across_partial_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "snapshots"
    old = root / "2026-08-15" / "120000.000000Z"
    new = root / "2026-08-16" / "120000.000000Z"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / "kept.json").write_text("[]", encoding="utf-8")
    (new / "other.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(polymarket, "SNAPSHOT_ROOT", root)

    assert polymarket.snapshot_dir(date(2026, 8, 16)) == new
    assert polymarket.snapshot_file("kept", date(2026, 8, 16)) == old / "kept.json"


def test_direct_market_validates_resolution_basis_and_strike(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "hd-quarterly-earnings-nongaap-eps-08-18-2026-4pt73"
    root = tmp_path / "forecast" / "data" / "polymarket"
    run = root / "2026-08-16" / "120000.000000Z"
    run.mkdir(parents=True)
    event = {
        "slug": slug,
        "closed": False,
        "description": (
            "The Street consensus estimate for Home Depot's non-GAAP EPS "
            "for the relevant quarter is $4.73 as of market creation."
        ),
        "markets": [
            {
                "closed": False,
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.75", "0.25"]',
                "bestBid": 0.70,
                "bestAsk": 0.80,
                "volumeNum": 1000,
            }
        ],
    }
    path = run / f"{slug}.json"
    path.write_text(json.dumps([event]), encoding="utf-8")
    monkeypatch.setattr(polymarket, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(polymarket, "SNAPSHOT_ROOT", root)
    monkeypatch.setattr(
        polymarket, "surprise_sigma", lambda *args, **kwargs: ((0.1, 0.2, 0.3), 4)
    )

    signal = polymarket.parse_beat_market(
        Company.HD, "adj_eps", slug, date(2026, 8, 16)
    )
    assert signal is not None
    assert signal.strike == pytest.approx(4.73)
    assert signal.p_beat == pytest.approx(0.75)
    assert signal.fetched_from.endswith(f"{slug}.json")

    event["description"] = event["description"].replace("$4.73", "$4.72")
    path.write_text(json.dumps([event]), encoding="utf-8")
    assert polymarket.parse_beat_market(
        Company.HD, "adj_eps", slug, date(2026, 8, 16)
    ) is None


def test_resolved_direct_market_is_never_reused_as_a_forecast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "hd-quarterly-earnings-nongaap-eps-08-18-2026-4pt73"
    root = tmp_path / "forecast" / "data" / "polymarket"
    run = root / "2026-08-16"
    run.mkdir(parents=True)
    (run / f"{slug}.json").write_text(
        json.dumps([{"slug": slug, "closed": True, "markets": []}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(polymarket, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(polymarket, "SNAPSHOT_ROOT", root)
    assert polymarket.parse_beat_market(
        Company.HD, "adj_eps", slug, date(2026, 8, 16)
    ) is None
