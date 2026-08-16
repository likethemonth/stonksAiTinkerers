"""The final command. One invocation, four workbooks, one timestamped log.

    .venv/bin/python -m forecast.run

Processes all four companies sequentially, writes submission/*.xlsx and a log
under logs/. A failure on one company is caught and reported rather than aborting
the run: a missing forecast scores 5.0 under the accuracy rubric, so three
workbooks beats none, and the exit code still reflects that something went wrong.

Companies with an extractor are forecast from calibrated guidance. Those without
fall back to the cited provisional baselines in baselines.py, flagged for review
so the log never lets a provisional number pass as a calibrated one.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

from forecast.baselines import BASELINES
from forecast.calibrate import calibrate
from forecast.corpus import load
from forecast.estimators import guidance_realisation, reconcile, regression_bridge
from forecast.extract import adi
from forecast.metrics import (
    display_name,
    output_file,
    submitted_specs,
    target_period,
    ticker,
    verify_registry,
)
from forecast.schema import Company, CompanyForecast, MetricForecast
from forecast.store import write_calibration_report, write_observations
from forecast.writer import write_workbook

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"

EXTRACTORS = {Company.ADI: adi.extract}


class Log:
    """Writes to stdout and a timestamped file at once.

    The run log is submitted evidence, so it records failures and retries as
    faithfully as successes.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lines: list[str] = []

    def __call__(self, message: str = "") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}" if message else ""
        print(line)
        self.lines.append(line)

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def _forecast_adi(as_of: date | None, log: Log) -> list[MetricForecast]:
    """Calibrated forecast from extracted guidance."""
    docs = load(Company.ADI, as_of=as_of)
    rejected: list[str] = []
    observations = adi.extract(docs, rejected)
    write_observations(
        Company.ADI, observations, as_of=as_of, rejected=rejected
    )
    corrections = calibrate(observations)
    write_calibration_report(Company.ADI, corrections, as_of=as_of)

    log(f"  {len(docs)} docs -> {len(observations)} observations, "
        f"{len(rejected)} rejected, {len(corrections)} calibrated metrics")
    for reason in rejected:
        log(f"  REJECTED {reason}")

    period = target_period(Company.ADI)
    specs = submitted_specs(Company.ADI)
    metrics: list[MetricForecast] = []

    # Revenue and adjusted EPS are guided directly.
    direct = {"Revenue": "revenue", "Adjusted diluted EPS": "adj_eps"}
    operating_margin: object = None

    for spec in specs:
        key = direct.get(spec.label)
        if key is None:
            continue
        est = guidance_realisation(
            observations,
            corrections.get((Company.ADI, key)),
            company=Company.ADI,
            metric_key=key,
            period=period,
        )
        if est is None:
            raise RuntimeError(f"ADI: no guidance found for {spec.label}")
        metrics.append(reconcile(spec.label, spec.units, [est]))

    # Adjusted gross margin is NOT guided; bridge from adjusted operating margin.
    operating_margin = guidance_realisation(
        observations,
        corrections.get((Company.ADI, "adj_operating_margin_pct")),
        company=Company.ADI,
        metric_key="adj_operating_margin_pct",
        period=period,
    )
    if operating_margin is None:
        raise RuntimeError("ADI: no adjusted operating margin guidance to bridge from")
    bridged = regression_bridge(
        observations,
        company=Company.ADI,
        target_key="adj_gross_margin_pct",
        source_key="adj_operating_margin_pct",
        source_estimate=operating_margin,
    )
    if bridged is None:
        raise RuntimeError("ADI: not enough paired history for the margin bridge")
    gross_spec = next(s for s in specs if s.label == "Adjusted gross margin")
    metrics.append(reconcile(gross_spec.label, gross_spec.units, [bridged]))

    order = {s.label: i for i, s in enumerate(specs)}
    return sorted(metrics, key=lambda m: order[m.label])


def _forecast_baseline(company: Company, log: Log) -> list[MetricForecast]:
    """Provisional, cited baselines for a company without an extractor."""
    log("  PROVISIONAL: no extractor yet, using cited baselines")
    metrics = []
    for spec in submitted_specs(company):
        est = BASELINES[company][spec.label]
        forecast = reconcile(spec.label, spec.units, [est])
        forecast.needs_review = True
        forecast.warnings.append("provisional baseline; not calibrated")
        metrics.append(forecast)
    return metrics


def run_company(company: Company, as_of: date | None, log: Log) -> Path:
    log(f"=== {display_name(company)} ({ticker(company)}) "
        f"{target_period(company).key} ===")

    if company in EXTRACTORS:
        metrics = _forecast_adi(as_of, log)
    else:
        metrics = _forecast_baseline(company, log)

    forecast = CompanyForecast(
        ticker=ticker(company),
        company=company,
        period=target_period(company),
        output_file=output_file(company),
        as_of=as_of or date.today(),
        metrics=metrics,
    )

    for m in forecast.metrics:
        flag = "  [REVIEW]" if m.needs_review else ""
        log(f"  {m.label}: {m.value:,.2f} {m.units.value}{flag}")
        log(f"      {m.reasoning}")
        for w in m.warnings:
            log(f"      WARNING {w}")
        log(f"      sources: {', '.join(m.citations[:3])}")

    path = write_workbook(forecast)
    log(f"  wrote {path.relative_to(REPO_ROOT)}")
    log()
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Point-in-time cutoff (YYYY-MM-DD). Omit for the full frozen corpus.",
    )
    args = parser.parse_args()

    started = datetime.now()
    log = Log(LOG_DIR / f"run-{started.strftime('%Y%m%dT%H%M%S')}.log")
    log(f"Agents vs Wall Street — forecast run started {started.isoformat(timespec='seconds')}")
    log(f"as_of: {args.as_of.isoformat() if args.as_of else 'full frozen corpus'}")
    log()

    verify_registry()
    log("registry verified against challenge/companies.json")
    log()

    failures: list[str] = []
    for company in Company:
        try:
            run_company(company, args.as_of, log)
        except Exception as exc:  # noqa: BLE001 - one company must not kill the run
            failures.append(company.value)
            log(f"  FAILED {company.value}: {exc}")
            for line in traceback.format_exc().splitlines():
                log(f"    {line}")
            log()

    elapsed = (datetime.now() - started).total_seconds()
    if failures:
        log(f"COMPLETED WITH FAILURES in {elapsed:.1f}s: {', '.join(failures)}")
    else:
        log(f"OK — 4 workbooks written in {elapsed:.1f}s")
    log.flush()
    print(f"\nlog: {log.path.relative_to(REPO_ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
