"""Build the observation table and calibration report for every company.

    python -m forecast.build_table
    python -m forecast.build_table --as-of 2026-02-17

The `--as-of` flag is the whole backtest apparatus. Passing a date before a
quarter's results makes the pipeline blind to them, so the table it builds is
exactly what the system would have had that morning — which is how the
calibration is validated rather than merely asserted.

Extraction is decoupled from inference on purpose: this command writes frozen
JSON per company, and the estimators read only that. It means the expensive parse
happens once and the inference layer can fan out across companies.
"""

from __future__ import annotations

import argparse
from datetime import date

from forecast.calibrate import calibrate
from forecast.corpus import load
from forecast.extract import adi, deere, hays, home_depot
from forecast.metrics import verify_registry
from forecast.schema import Company, Kind, MetricObservation
from forecast.store import write_calibration_report, write_observations

#: Company -> extractor. Companies without one yet are reported as pending rather
#: than silently skipped, so a partial run is never mistaken for a complete one.
EXTRACTORS = {
    Company.HD: home_depot.extract,
    Company.ADI: adi.extract,
    Company.HAS: hays.extract,
    Company.DE: deere.extract,
}


def build(company: Company, as_of: date | None) -> list[MetricObservation]:
    """Extract, persist and calibrate one company."""
    extractor = EXTRACTORS[company]
    docs = load(company, as_of=as_of)
    rejected: list[str] = []
    observations = extractor(docs, rejected)

    obs_path = write_observations(
        company, observations, as_of=as_of, rejected=rejected
    )
    corrections = calibrate(observations)
    cal_path = write_calibration_report(company, corrections, as_of=as_of)

    kinds = {k.value: 0 for k in Kind}
    for o in observations:
        kinds[o.kind.value] += 1
    counted = {k: v for k, v in kinds.items() if v}

    print(f"[{company.value}] {len(docs)} docs -> {len(observations)} observations {counted}")
    if rejected:
        print(f"  rejected {len(rejected)} row(s):")
        for reason in rejected:
            print(f"    - {reason}")
    for (_, metric_key), cor in sorted(corrections.items()):
        print(f"  calibrated {metric_key:28s} {cor.summary}")
    print(f"  wrote {obs_path.relative_to(obs_path.parents[2])}")
    print(f"  wrote {cal_path.relative_to(cal_path.parents[2])}")
    return observations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Point-in-time cutoff (YYYY-MM-DD). Omit to use the full frozen corpus.",
    )
    parser.add_argument(
        "--company",
        choices=[c.value for c in Company],
        default=None,
        help="Restrict to one company. Omit for all.",
    )
    args = parser.parse_args()

    verify_registry()
    wanted = [Company(args.company)] if args.company else list(Company)

    for company in wanted:
        if company not in EXTRACTORS:
            print(f"[{company.value}] no extractor yet — PENDING")
            continue
        build(company, args.as_of)


if __name__ == "__main__":
    main()
