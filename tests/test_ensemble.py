"""Invariants for the four-lens error-weighted ensemble artifact."""

import json
import math
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).resolve().parent.parent / "research" / "lens-ensemble.json"

pytestmark = pytest.mark.skipif(not ARTIFACT.exists(), reason="ensemble not built")


def _rows():
    return json.loads(ARTIFACT.read_text())["rows"]


def test_covers_all_twelve_metrics():
    rows = _rows()
    assert len(rows) == 12
    assert {r["ticker"] for r in rows} == {"HD", "ADI", "Hays", "DE"}


def test_weights_are_inverse_error_and_normalized():
    for row in _rows():
        total = sum(1.0 / lens["err"] for lens in row["lenses"])
        assert math.isclose(sum(lens["weight"] for lens in row["lenses"]), 1.0,
                            abs_tol=0.005), row["label"]
        for lens in row["lenses"]:
            expected = (1.0 / lens["err"]) / total
            assert math.isclose(lens["weight"], expected, abs_tol=0.001), (
                f"{row['ticker']} {row['label']} {lens['lens']}")


def test_final_is_weighted_mean_inside_lens_range():
    for row in _rows():
        mean = sum(lens["weight"] * lens["value"] for lens in row["lenses"])
        assert math.isclose(row["final"], mean, abs_tol=max(0.02, abs(mean) * 1e-3))
        values = [lens["value"] for lens in row["lenses"]]
        assert min(values) - 0.01 <= row["final"] <= max(values) + 0.01


def test_hays_driver_is_excluded_as_a_carry():
    for row in _rows():
        if row["ticker"] == "Hays":
            assert all(lens["lens"] != "driver" for lens in row["lenses"]), (
                "the Hays driver lens declares itself a carry and must not vote")


def test_error_bases_are_declared():
    allowed = ("validated", "market-implied", "assumed-at-gate")
    for row in _rows():
        for lens in row["lenses"]:
            assert lens["errBasis"].startswith(allowed), lens
            assert lens["err"] > 0
