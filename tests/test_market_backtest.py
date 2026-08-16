from __future__ import annotations

import json
from datetime import date

import pytest

from forecast.market_backtest import (
    DEFAULT_ARCHIVE,
    build_market_backtest,
    promotion_note,
)


@pytest.fixture(scope="module")
def market_replay() -> dict:
    return build_market_backtest(as_of=date(2026, 8, 16))


def test_market_backtest_replays_exact_pre_resolution_events(market_replay: dict) -> None:
    assert len(market_replay["rows"]) == 9
    assert market_replay["summary"]["allPointInTime"] is True
    assert market_replay["summary"]["allActualsExact"] is True
    for row in market_replay["rows"]:
        assert row["lastTradeAt"] < row["cutoff"]
        assert row["actualMatch"] == "exact"
        assert row["actualSourceUrl"].startswith("https://")
        assert row["surpriseSigma"]["calibrationCutoffExclusive"] == row["cutoff"][:10]
        assert row["numericWeight"] == 0


def test_market_backtest_scores_probability_and_point_conversion(market_replay: dict) -> None:
    summary = market_replay["summary"]
    assert summary["binaryHits"] == 9
    assert summary["meanBrierScore"] == pytest.approx(0.049843221765333366)
    assert summary["shadowMae"] == pytest.approx(0.10845773642059021)
    assert summary["strikeBaselineMae"] == pytest.approx(0.21111111111111105)
    assert summary["maeImprovementPct"] == pytest.approx(0.48625282748036205)
    assert (summary["rowWins"], summary["rowLosses"], summary["rowTies"]) == (7, 2, 0)
    assert summary["oneSidedSignTestP"] == pytest.approx(0.08984375)


def test_promotion_gate_refuses_small_non_significant_archive(market_replay: dict) -> None:
    promotion = market_replay["promotion"]
    assert promotion["eligible"] is False
    assert promotion["decision"] == "shadow_only"
    assert promotion["numericWeight"] == 0
    assert promotion["failedChecks"] == ["minimumResolved", "signTest"]
    assert "n=9" in promotion_note(as_of=date(2026, 8, 16))
    assert "p=0.0898" in promotion_note(as_of=date(2026, 8, 16))


def test_current_market_outputs_are_shadow_only(market_replay: dict) -> None:
    shadows = {row["ticker"]: row for row in market_replay["liveShadowEstimates"]}
    assert set(shadows) == {"HD", "ADI", "DE"}
    assert shadows["HD"]["shadowEstimate"] == pytest.approx(4.823)
    assert shadows["ADI"]["shadowEstimate"] == pytest.approx(3.421)
    assert shadows["DE"]["shadowEstimate"] == pytest.approx(5.246)
    assert all(row["status"] == "signal_only" for row in shadows.values())
    assert all(row["numericWeight"] == 0 for row in shadows.values())


def test_metric_basis_mismatch_fails_closed(tmp_path) -> None:
    archive = json.loads(DEFAULT_ARCHIVE.read_text(encoding="utf-8"))
    archive["records"][0]["actualBasis"] = "gaap_diluted_eps"
    bad_archive = tmp_path / "bad-market-history.json"
    bad_archive.write_text(json.dumps(archive), encoding="utf-8")
    with pytest.raises(ValueError, match="actual basis mismatch"):
        build_market_backtest(as_of=date(2026, 8, 16), archive_path=bad_archive)


def test_post_cutoff_trade_fails_closed(tmp_path) -> None:
    archive = json.loads(DEFAULT_ARCHIVE.read_text(encoding="utf-8"))
    archive["records"][0]["lastTradeAt"] = archive["records"][0]["cutoff"]
    bad_archive = tmp_path / "bad-market-history.json"
    bad_archive.write_text(json.dumps(archive), encoding="utf-8")
    with pytest.raises(ValueError, match="post-cutoff price"):
        build_market_backtest(as_of=date(2026, 8, 16), archive_path=bad_archive)


def test_market_replay_is_deterministic(market_replay: dict) -> None:
    assert build_market_backtest(as_of=date(2026, 8, 16)) == market_replay
