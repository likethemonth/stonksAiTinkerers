"""Guards for the blinded LLM replay: blinding, cutoff isolation, scoring.

These tests run against the emitted packets and the scored artifact, because
those files are what the predictor sessions and the page actually consume. If
either is regenerated with a leak, this is where it should fail first.
"""

import json
import math
import re
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKETS = ROOT / "research" / "llm-replay" / "packets"
ARTIFACT = ROOT / "research" / "llm-replay" / "llm-driver-backtest.json"

#: Any of these appearing in a packet prompt is an identity or timeline leak.
FORBIDDEN = re.compile(
    r"home depot|deere|analog devices|hays|maxim|polymarket"      # names
    r"|\bFY20\d\d\b"                                              # fiscal labels
    r"|\b20[12]\d-[01]\d-[0-3]\d\b"                               # ISO dates
    r"|\bppa\b|precision ag",                                     # DE segment vocab
    re.IGNORECASE,
)

packet_files = sorted(PACKETS.glob("*.json")) if PACKETS.is_dir() else []


@pytest.mark.skipif(not packet_files, reason="packets not emitted")
def test_prompts_are_blinded():
    for path in packet_files:
        prompt = json.loads(path.read_text())["prompt"]
        leak = FORBIDDEN.search(prompt)
        assert leak is None, f"{path.name}: leaked {leak.group(0)!r}"


@pytest.mark.skipif(not packet_files, reason="packets not emitted")
def test_sources_respect_cutoff():
    for path in packet_files:
        private = json.loads(path.read_text())["private"]
        cutoff = date.fromisoformat(private["cutoff"])
        for src in private["sources"]:
            if src["source"].startswith("polymarket strike"):
                continue  # strike frozen at creation; its ref date is the print
            try:
                published = date.fromisoformat(src["published"])
            except ValueError:
                continue  # census series entry carries a lag note, not a date
            assert published <= cutoff, (
                f"{path.name}: {src['source']} published {published} "
                f"after cutoff {cutoff}")


@pytest.mark.skipif(not ARTIFACT.exists(), reason="replay not scored")
def test_scored_errors_recompute():
    data = json.loads(ARTIFACT.read_text())
    checked = 0
    for block in data["companies"].values():
        for key, metric in block["metrics"].items():
            for row in metric["rows"]:
                if key.endswith("_pct"):
                    expected = abs(row["predicted"] - row["actual"])
                else:
                    expected = (abs(row["predicted"] - row["actual"])
                                / abs(row["actual"]) * 100.0)
                assert math.isclose(row["err"], expected, abs_tol=0.011), (
                    f"{key} {row['period']}: err {row['err']} != {expected:.3f}")
                checked += 1
    assert checked >= 50


@pytest.mark.skipif(not ARTIFACT.exists(), reason="replay not scored")
def test_pbeat_brier_recompute():
    data = json.loads(ARTIFACT.read_text())
    for block in data["companies"].values():
        for row in block["pBeat"]["rows"]:
            if row["brierLLM"] is None:
                continue
            assert math.isclose(
                row["brierLLM"], (row["pLLM"] - row["outcome"]) ** 2, abs_tol=1e-3)
