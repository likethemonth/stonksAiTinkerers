"""Point-in-time Numinous probability forecasts.

Numinous is an external AI forecaster, not a traded prediction market. Its
binary probabilities are therefore kept as native constraints and never
converted into EPS points or assigned meta-forecast weight without a held-out
earnings calibration.

CLI:
    python3 -m forecast.numinous --refresh
    python3 -m forecast.numinous --as-of 2026-08-16

``--refresh`` requires ``NUMINOUS_API_KEY`` and writes append-only, sanitized
API responses. The key is used only in the request header and is never stored.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from forecast.schema import Company, ProbabilityConstraint

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_ROOT = REPO_ROOT / "forecast" / "data" / "numinous"
API_BASE = "https://api.numinouslabs.io/api/v1"
API_DOCS = (
    "https://truth-alpha.notion.site/"
    "Numinous-Forecasts-API-30b8237a2fad80c18b2df8f888676cc9"
)


@dataclass(frozen=True)
class SignalDefinition:
    company: Company
    metric_key: str
    slug: str
    threshold: float
    basis: str
    report_date: date
    query: str


SIGNALS: dict[tuple[Company, str], SignalDefinition] = {
    (Company.HD, "adj_eps"): SignalDefinition(
        Company.HD,
        "adj_eps",
        "hd-fy2026q2-adjusted-eps-above-4pt73",
        4.73,
        "non_gaap",
        date(2026, 8, 18),
        "Will Home Depot report non-GAAP adjusted diluted earnings per share "
        "strictly above $4.73 for fiscal Q2 2026 in its official earnings "
        "release scheduled for August 18, 2026? Resolve YES only from the "
        "company reported non-GAAP adjusted diluted EPS.",
    ),
    (Company.ADI, "adj_eps"): SignalDefinition(
        Company.ADI,
        "adj_eps",
        "adi-fy2026q3-adjusted-eps-above-3pt33",
        3.33,
        "non_gaap",
        date(2026, 8, 19),
        "Will Analog Devices report non-GAAP adjusted diluted earnings per "
        "share strictly above $3.33 for fiscal Q3 2026 in its official earnings "
        "release scheduled for August 19, 2026? Resolve YES only from the "
        "company reported non-GAAP adjusted diluted EPS.",
    ),
    (Company.DE, "gaap_eps"): SignalDefinition(
        Company.DE,
        "gaap_eps",
        "de-fy2026q3-gaap-eps-above-4pt72",
        4.72,
        "gaap",
        date(2026, 8, 20),
        "Will Deere & Company report diluted earnings per share under GAAP "
        "strictly above $4.72 for fiscal Q3 2026 in its official earnings "
        "release scheduled for August 20, 2026? Resolve YES only from the "
        "company reported GAAP diluted EPS.",
    ),
}


def _snapshot_runs(as_of: date | None = None) -> list[Path]:
    if not SNAPSHOT_ROOT.is_dir():
        return []
    cutoff = (as_of or date.today()).isoformat()
    day_dirs = sorted(
        (
            path
            for path in SNAPSHOT_ROOT.iterdir()
            if path.is_dir()
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name)
            and path.name <= cutoff
        ),
        reverse=True,
    )
    runs: list[Path] = []
    for day_dir in day_dirs:
        runs.extend(
            sorted((path for path in day_dir.iterdir() if path.is_dir()), reverse=True)
        )
        if any(day_dir.glob("*.json")):
            runs.append(day_dir)
    return runs


def snapshot_file(slug: str, as_of: date | None = None) -> Path | None:
    for run in _snapshot_runs(as_of):
        path = run / f"{slug}.json"
        if path.is_file():
            return path
    return None


def parse_snapshot(
    definition: SignalDefinition, payload: dict, source_snapshot: str
) -> ProbabilityConstraint | None:
    """Validate a completed response against the exact earnings contract."""
    response = payload.get("api_response", payload)
    if not isinstance(response, dict) or response.get("status") != "COMPLETED":
        return None
    result = response.get("result")
    if not isinstance(result, dict):
        return None
    try:
        probability = float(result["prediction"])
    except (KeyError, TypeError, ValueError):
        return None
    if not 0.0 <= probability <= 1.0:
        return None

    parsed = result.get("parsed_fields")
    if not isinstance(parsed, dict):
        return None
    title = str(parsed.get("title") or "")
    folded = title.casefold()
    threshold_pattern = rf"\$?{re.escape(f'{definition.threshold:.2f}')}(?!\d)"
    if not re.search(threshold_pattern, title) or "strictly above" not in folded:
        return None
    if definition.basis == "non_gaap" and (
        "non-gaap" not in folded or "adjusted" not in folded
    ):
        return None
    if definition.basis == "gaap" and (
        "gaap" not in folded or "non-gaap" in folded
    ):
        return None
    cutoff = str(parsed.get("cutoff") or "")
    if not cutoff.startswith(definition.report_date.isoformat()):
        return None

    return ProbabilityConstraint(
        provider="numinous",
        threshold=definition.threshold,
        probability=probability,
        volume=None,
        source_snapshot=source_snapshot,
        citation=API_DOCS,
    )


def numinous_constraint(
    company: Company, metric_key: str, as_of: date | None = None
) -> ProbabilityConstraint | None:
    signal_key = "gaap_eps" if metric_key == "diluted_eps_gaap" else metric_key
    definition = SIGNALS.get((company, signal_key))
    if definition is None:
        return None
    path = snapshot_file(definition.slug, as_of)
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_snapshot(definition, payload, str(path.relative_to(REPO_ROOT)))


def _request_json(
    url: str, api_key: str, *, payload: dict | None = None
) -> tuple[int, dict]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method="POST" if payload is not None else "GET",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "User-Agent": "avws-forecast/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.load(exc)
        except (json.JSONDecodeError, UnicodeDecodeError):
            detail = {"detail": exc.reason}
        return exc.code, detail


def snapshot_now(*, poll_seconds: float = 5.0, timeout_seconds: float = 180.0) -> Path:
    """Run every registered question and write an append-only sanitized snapshot."""
    api_key = os.environ.get("NUMINOUS_API_KEY", "")
    if not api_key:
        raise RuntimeError("NUMINOUS_API_KEY is required for refresh")
    api_base = os.environ.get("NUMINOUS_API_BASE", API_BASE).rstrip("/")
    now = datetime.now(timezone.utc)
    output = SNAPSHOT_ROOT / now.date().isoformat() / now.strftime("%H%M%S.%fZ")
    output.mkdir(parents=True, exist_ok=False)

    signal_names: list[str] = []
    manifest: dict[str, object] = {
        "fetched_at": now.isoformat(),
        "signals": signal_names,
    }
    for definition in SIGNALS.values():
        status, submitted = _request_json(
            f"{api_base}/forecasters/prediction-jobs",
            api_key,
            payload={"query": definition.query},
        )
        if status != 202 or not submitted.get("prediction_id"):
            raise RuntimeError(f"Numinous submission failed for {definition.slug}: HTTP {status}")
        prediction_id = str(submitted["prediction_id"])
        deadline = time.monotonic() + timeout_seconds
        completed: dict = submitted
        while time.monotonic() < deadline:
            _, completed = _request_json(
                f"{api_base}/forecasters/prediction-jobs/{prediction_id}", api_key
            )
            if completed.get("status") in {"COMPLETED", "FAILED"}:
                break
            time.sleep(poll_seconds)
        if completed.get("status") != "COMPLETED":
            raise RuntimeError(f"Numinous job did not complete for {definition.slug}")
        snapshot = {
            "query": definition.query,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "api_response": completed,
        }
        (output / f"{definition.slug}.json").write_text(
            json.dumps(snapshot, indent=2) + "\n", encoding="utf-8"
        )
        signal_names.append(definition.slug)

    (output / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    if args.refresh:
        print(snapshot_now())
    for definition in SIGNALS.values():
        signal = numinous_constraint(definition.company, definition.metric_key, args.as_of)
        state = "ABSTAIN" if signal is None else f"{signal.probability:.2%} > {signal.threshold:g}"
        print(f"{definition.company.value} {definition.metric_key}: {state}")


if __name__ == "__main__":
    main()
