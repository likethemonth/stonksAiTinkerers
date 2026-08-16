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
from forecast.estimators import (
    consensus_anchor,
    growth_on_prior_actual,
    guidance_realisation,
    quarter_vs_year_offset,
    ratio_on_prior_actual,
    reconcile,
    seasonal_share,
    regression_bridge,
)
from forecast.extract import adi, hays, home_depot
from forecast.metrics import (
    display_name,
    output_file,
    submitted_specs,
    target_period,
    ticker,
    verify_registry,
)
from forecast.schema import Company, CompanyForecast, Estimate, Kind, MetricForecast, Period
from forecast.store import write_calibration_report, write_observations
from forecast.writer import write_workbook

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"


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


#: How far from consensus toward the top of its disclosed range to sit for Hays'
#: operating profit. Management said they expect the TOP of the range, so this is
#: high; not 1.0 because "top of the range" is a directional steer, not a point
#: commitment, and the ceiling is the most optimistic analyst rather than a target.
_HAYS_CONSENSUS_POSITION = 0.8


def _forecast_hays(as_of: date | None, log: Log) -> list[MetricForecast]:
    """Hays: the only company where a real analyst benchmark exists in the corpus."""
    docs = load(Company.HAS, as_of=as_of)
    rejected: list[str] = []
    observations = hays.extract(docs, rejected)
    write_observations(Company.HAS, observations, as_of=as_of, rejected=rejected)

    log(f"  {len(docs)} docs -> {len(observations)} observations, "
        f"{len(rejected)} conflicts/rejections")
    for reason in rejected:
        log(f"  RESOLVED {reason}")

    period = target_period(Company.HAS)
    specs = {s.label: s for s in submitted_specs(Company.HAS)}
    metrics: list[MetricForecast] = []

    # Net fees: prior-year actual moved by the disclosed reported-basis growth.
    fees = growth_on_prior_actual(
        observations,
        company=Company.HAS,
        metric_key="net_fees",
        growth_key="net_fees_growth_actual_pct",
        period=period,
    )
    if fees is None:
        raise RuntimeError("Hays: no net fee growth or prior-year base found")
    spec = specs["Net fees"]
    metrics.append(reconcile(spec.label, spec.units, [fees]))

    # Operating profit: consensus, positioned by management's own steer.
    profit = consensus_anchor(
        observations,
        company=Company.HAS,
        metric_key="pre_exc_operating_profit",
        period=period,
        position=_HAYS_CONSENSUS_POSITION,
    )
    if profit is None:
        raise RuntimeError("Hays: no company-compiled consensus found")
    spec = specs["Pre-exceptional operating profit"]
    profit_forecast = reconcile(spec.label, spec.units, [profit])
    metrics.append(profit_forecast)

    # EPS: two independent routes, reconciled by inverse variance rather than
    # chosen between here. The regression spans operating profit from 45 to 249
    # and is dominated by the high-profit years, so it carries a wide sigma and
    # little weight; the ratio estimator anchors on FY2025, whose profit is
    # within 0.1 of the FY2026 forecast, and carries most of it.
    eps = regression_bridge(
        observations,
        company=Company.HAS,
        target_key="pre_exc_basic_eps",
        source_key="pre_exc_operating_profit",
        source_estimate=profit,
    )
    scaled = ratio_on_prior_actual(
        observations,
        company=Company.HAS,
        metric_key="pre_exc_basic_eps",
        driver_key="pre_exc_operating_profit",
        driver_estimate=profit,
        period=period,
    )
    eps_estimates = [e for e in (eps, scaled) if e is not None]
    if not eps_estimates:
        raise RuntimeError("Hays: no usable EPS estimate")
    spec = specs["Pre-exceptional basic EPS"]
    metrics.append(reconcile(spec.label, spec.units, eps_estimates))

    order = {s.label: i for i, s in enumerate(submitted_specs(Company.HAS))}
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


def _forecast_hd(as_of: date | None, log: Log) -> list[MetricForecast]:
    """Home Depot: full-year guidance divided into a quarter by seasonal history."""
    docs = load(Company.HD, as_of=as_of)
    rejected: list[str] = []
    observations = home_depot.extract(docs, rejected)
    write_observations(Company.HD, observations, as_of=as_of, rejected=rejected)

    log(f"  {len(docs)} docs -> {len(observations)} observations, "
        f"{len(rejected)} rejected")
    for reason in rejected:
        log(f"  REJECTED {reason}")

    period = target_period(Company.HD)
    fy = Period(year=period.year, quarter=None)
    specs = {s.label: s for s in submitted_specs(Company.HD)}
    metrics: list[MetricForecast] = []

    def _guide(metric_key: str) -> Estimate | None:
        """The guided full-year rate, as a plain estimate over its own range."""
        rows = [
            o for o in observations
            if o.company is Company.HD and o.metric_key == metric_key
            and o.period == fy
        ]
        mid = max((o for o in rows if o.kind is Kind.GUIDE_MID),
                  key=lambda o: o.as_of, default=None)
        if mid is None:
            return None
        low = max((o for o in rows if o.kind is Kind.GUIDE_LOW),
                  key=lambda o: o.as_of, default=None)
        high = max((o for o in rows if o.kind is Kind.GUIDE_HIGH),
                   key=lambda o: o.as_of, default=None)
        # Half the guided range is a fair statement of management's own uncertainty.
        sigma = (high.value - low.value) / 2.0 if low and high else abs(mid.value) * 0.5
        return Estimate(
            estimator="fy_guidance_midpoint",
            value=mid.value,
            sigma=max(sigma, 0.05),
            n_observations=1,
            anchor=mid.value,
            reasoning=(
                f"FY{fy.year} {metric_key} guided to a midpoint of {mid.value:+.2f}%"
                + (f" across {low.value:+.2f}% to {high.value:+.2f}%" if low and high else "")
                + f", as of {mid.as_of.isoformat()}."
            ),
            citations=[mid.source_file],
        )

    sales_growth = _guide("total_sales_growth_pct")
    eps_growth = _guide("adj_eps_growth_pct")
    comp_guide = _guide("comp_sales_pct")
    if sales_growth is None or eps_growth is None or comp_guide is None:
        raise RuntimeError("HD: full-year guidance not found")

    net_sales = seasonal_share(
        observations, company=Company.HD, metric_key="net_sales",
        period=period, growth_estimate=sales_growth,
    )
    if net_sales is None:
        raise RuntimeError("HD: not enough quarterly history for the net sales share")
    spec = specs["Net sales"]
    metrics.append(reconcile(spec.label, spec.units, [net_sales]))

    # Adjusted EPS has no quarterly history — HD only began reporting it recently
    # — so the seasonal shape comes from GAAP EPS, which has years of it.
    eps = seasonal_share(
        observations, company=Company.HD, metric_key="adj_eps",
        period=period, growth_estimate=eps_growth, shape_key="diluted_eps_gaap",
    )
    if eps is None:
        raise RuntimeError("HD: not enough EPS history for the seasonal share")
    spec = specs["Adjusted diluted EPS"]
    metrics.append(reconcile(spec.label, spec.units, [eps]))

    comps = quarter_vs_year_offset(
        observations, company=Company.HD, metric_key="comp_sales_pct",
        period=period, year_estimate=comp_guide,
    )
    spec = specs["Comparable sales, total company"]
    metrics.append(reconcile(spec.label, spec.units, [e for e in (comps, comp_guide) if e]))

    order = {s.label: i for i, s in enumerate(submitted_specs(Company.HD))}
    return sorted(metrics, key=lambda m: order[m.label])


#: Companies with a real extractor and estimators. Anything absent falls back to
#: the cited provisional baselines. Defined after the functions it references.
FORECASTERS = {
    Company.HD: _forecast_hd,
    Company.ADI: _forecast_adi,
    Company.HAS: _forecast_hays,
}


def run_company(company: Company, as_of: date | None, log: Log) -> Path:
    log(f"=== {display_name(company)} ({ticker(company)}) "
        f"{target_period(company).key} ===")

    forecaster = FORECASTERS.get(company)
    if forecaster is not None:
        metrics = forecaster(as_of, log)
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
