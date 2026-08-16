"""Persist the observation table and the calibration report.

Two audiences. The JSON is the machine handoff: extraction runs once, writes the
table, and every downstream estimator reads from that frozen artefact rather than
re-parsing 1,139 documents. The Markdown is the human/judge handoff — the research
record showing which disclosures the system found and how each one historically
landed, with a citation on every row.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from forecast.calibrate import Correction
from forecast.schema import Company, MetricObservation

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data"
OBSERVATIONS_DIR = DATA_ROOT / "observations"
CALIBRATION_DIR = DATA_ROOT / "calibration"


def _observation_payload(obs: MetricObservation) -> dict[str, object]:
    return {
        "company": obs.company.value,
        "metric_key": obs.metric_key,
        "period": obs.period.key,
        "value": obs.value,
        "units": obs.units.value,
        "kind": obs.kind.value,
        "as_of": obs.as_of.isoformat(),
        "source_file": obs.source_file,
        "doc_type": obs.doc_type.value,
        "excerpt": obs.excerpt,
        "extractor": obs.extractor,
        "note": obs.note,
    }


def _stem(company: Company, as_of: date | None) -> str:
    """Artefact name, suffixed when point-in-time restricted.

    A replay must never overwrite the production table: they describe different
    information sets, and silently clobbering the real one with a deliberately
    blinded version is exactly the sort of mistake that survives to submission.
    """
    return company.value if as_of is None else f"{company.value}@{as_of.isoformat()}"


def write_observations(
    company: Company,
    observations: list[MetricObservation],
    *,
    as_of: date | None,
    rejected: list[str] | None = None,
) -> Path:
    """Write one company's observation table to data/observations/<company>.json."""
    OBSERVATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = OBSERVATIONS_DIR / f"{_stem(company, as_of)}.json"
    payload = {
        "company": company.value,
        "as_of": as_of.isoformat() if as_of else None,
        "observation_count": len(observations),
        "rejected": rejected or [],
        "observations": [
            _observation_payload(o)
            for o in sorted(
                observations, key=lambda o: (o.period.sort_key, o.metric_key, o.kind)
            )
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_observations(company: Company) -> list[dict[str, object]]:
    """Read back a persisted table. Used by the estimators and the fan-out."""
    path = OBSERVATIONS_DIR / f"{company.value}.json"
    return json.loads(path.read_text(encoding="utf-8"))["observations"]


def write_calibration_report(
    company: Company,
    corrections: dict[tuple[Company, str], Correction],
    *,
    as_of: date | None,
) -> Path:
    """Write the human-readable backtest for one company.

    Every pairing is listed with both source files, so a judge can open the
    guidance document and the reporting document and check the arithmetic.
    """
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    path = CALIBRATION_DIR / f"{_stem(company, as_of)}.md"

    lines: list[str] = [
        f"# Calibration — {company.value}",
        "",
        f"Point-in-time cutoff: **{as_of.isoformat() if as_of else 'full frozen corpus'}**",
        "",
        "Each row pairs a guidance figure published *before* a period with the",
        "actual reported *after* it. The bias is shrunk toward zero by",
        "`n / (n + 5)` so a short history cannot swing a forecast far off its",
        "anchor. Sigma is the dispersion about the shrunk mean — the error an",
        "estimator using this correction would actually have made — and is what",
        "the reconciler weights by.",
        "",
    ]

    for (_, metric_key), cor in sorted(corrections.items()):
        unit_suffix = "pp" if cor.additive else "%"
        lines += [
            f"## `{metric_key}` ({cor.units.value})",
            "",
            f"- observations: **{cor.n}**",
            f"- raw bias: **{cor.raw_mean if cor.additive else (cor.raw_mean - 1) * 100:+.2f}{unit_suffix}**",
            f"- shrunk bias: **{cor.shrunk_mean if cor.additive else (cor.shrunk_mean - 1) * 100:+.2f}{unit_suffix}**",
            f"- sigma: **{cor.sigma if cor.additive else cor.sigma * 100:.2f}{unit_suffix}**",
            "",
            "| Period | Guided | Actual | Miss | Guidance source | Result source |",
            "|---|---:|---:|---:|---|---|",
        ]
        for p in cor.pairings:
            miss = p.delta if cor.additive else (p.ratio - 1) * 100
            lines.append(
                f"| {p.period.key} | {p.guided:,.2f} | {p.actual:,.2f} | "
                f"{miss:+.2f}{unit_suffix} | `{p.guided_source}` | `{p.actual_source}` |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
