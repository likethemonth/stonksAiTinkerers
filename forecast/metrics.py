"""Canonical metric registry.

Two naming systems meet here and must never be confused:

    metric_key   internal, stable, snake_case ('adj_gross_margin_pct'). What the
                 observation table, estimators and calibration all speak.
    label        the EXACT string in challenge/companies.json and in the workbook
                 template's column A. Renaming one fails the submission check.

Only the twelve SUBMITTED specs carry a label. The rest are supporting metrics —
things we extract because an estimator needs them (ADI guides adjusted operating
margin but we must submit adjusted *gross* margin, so we bridge between them).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from forecast.schema import Company, Period, Unit

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPANIES_JSON = REPO_ROOT / "challenge" / "companies.json"


@dataclass(frozen=True)
class MetricSpec:
    """One metric we track, submitted or supporting."""

    key: str
    company: Company
    units: Unit
    label: str | None = None  # set only for the twelve submitted metrics
    description: str = ""

    @property
    def submitted(self) -> bool:
        return self.label is not None


# --------------------------------------------------------------------------- #
# The registry
# --------------------------------------------------------------------------- #

_SPECS: tuple[MetricSpec, ...] = (
    # ---- Home Depot · FY2026Q2 -------------------------------------------- #
    MetricSpec("net_sales", Company.HD, Unit.USD_M, "Net sales"),
    MetricSpec("adj_eps", Company.HD, Unit.USD_PER_SHARE, "Adjusted diluted EPS"),
    MetricSpec(
        "comp_sales_pct", Company.HD, Unit.PERCENT, "Comparable sales, total company"
    ),
    MetricSpec("diluted_eps_gaap", Company.HD, Unit.USD_PER_SHARE,
               description="GAAP EPS; bridges to adjusted via disclosed add-backs."),
    MetricSpec("comp_sales_us_pct", Company.HD, Unit.PERCENT,
               description="US comps; the total-company figure's largest component."),
    MetricSpec("operating_margin_pct", Company.HD, Unit.PERCENT),

    # ---- Analog Devices · FY2026Q3 ---------------------------------------- #
    MetricSpec("revenue", Company.ADI, Unit.USD_M, "Revenue"),
    MetricSpec("adj_eps", Company.ADI, Unit.USD_PER_SHARE, "Adjusted diluted EPS"),
    MetricSpec(
        "adj_gross_margin_pct", Company.ADI, Unit.PERCENT, "Adjusted gross margin"
    ),
    # ADI guides adjusted OPERATING margin but we submit adjusted GROSS margin, so
    # the operating figure is the anchor the spread-bridge estimator works from.
    MetricSpec("adj_operating_margin_pct", Company.ADI, Unit.PERCENT,
               description="Guided every quarter; the bridge anchor for gross margin."),
    MetricSpec("gross_margin_pct", Company.ADI, Unit.PERCENT),
    MetricSpec("diluted_eps_gaap", Company.ADI, Unit.USD_PER_SHARE),

    # ---- Hays plc · FY2026 ------------------------------------------------- #
    MetricSpec("net_fees", Company.HAS, Unit.GBP_M, "Net fees"),
    MetricSpec(
        "pre_exc_basic_eps", Company.HAS, Unit.GBP_PENCE, "Pre-exceptional basic EPS"
    ),
    MetricSpec(
        "pre_exc_operating_profit",
        Company.HAS,
        Unit.GBP_M,
        "Pre-exceptional operating profit",
    ),
    MetricSpec("net_fees_growth_lfl_pct", Company.HAS, Unit.PERCENT,
               description="Like-for-like YoY; the quarterly trading statements' headline."),
    MetricSpec("net_fees_growth_actual_pct", Company.HAS, Unit.PERCENT,
               description="Actual (reported) YoY growth — what converts FY25 to FY26."),

    # ---- Deere & Company · FY2026Q3 ---------------------------------------- #
    MetricSpec(
        "worldwide_net_sales_revenues",
        Company.DE,
        Unit.USD_M,
        "Worldwide net sales and revenues",
    ),
    MetricSpec("diluted_eps_gaap", Company.DE, Unit.USD_PER_SHARE, "Diluted EPS (GAAP)"),
    MetricSpec(
        "ppa_operating_profit",
        Company.DE,
        Unit.USD_M,
        "Production & Precision Ag operating profit",
    ),
    # The regressor for the only fitted model in the system.
    MetricSpec("ppa_net_sales", Company.DE, Unit.USD_M,
               description="P&PA segment sales; OLS regressor for segment op profit."),
    MetricSpec("net_income", Company.DE, Unit.USD_M,
               description="FY guidance is given as net income, not EPS."),
    MetricSpec("diluted_shares", Company.DE, Unit.COUNT_M),
)

_BY_COMPANY_KEY: dict[tuple[Company, str], MetricSpec] = {
    (s.company, s.key): s for s in _SPECS
}


def spec(company: Company, key: str) -> MetricSpec:
    """Look up a metric spec, failing loudly on a typo'd key."""
    try:
        return _BY_COMPANY_KEY[(company, key)]
    except KeyError:
        raise KeyError(f"no metric {key!r} registered for {company.value}") from None


def submitted_specs(company: Company) -> list[MetricSpec]:
    """The three submitted metrics for a company, in companies.json order."""
    order = [m["label"] for m in _company_config(company)["metrics"]]
    specs = [s for s in _SPECS if s.company is company and s.submitted]
    by_label = {s.label: s for s in specs}
    missing = [lbl for lbl in order if lbl not in by_label]
    if missing:
        raise KeyError(f"{company.value}: no spec registered for labels {missing}")
    return [by_label[lbl] for lbl in order]


# --------------------------------------------------------------------------- #
# challenge/companies.json — parsed, never hardcoded
# --------------------------------------------------------------------------- #

_TICKER_TO_COMPANY = {
    "HD": Company.HD,
    "ADI": Company.ADI,
    "LSE:HAS": Company.HAS,
    "DE": Company.DE,
}


@lru_cache(maxsize=1)
def _config() -> dict[Company, dict]:
    raw = json.loads(COMPANIES_JSON.read_text(encoding="utf-8"))
    return {_TICKER_TO_COMPANY[c["ticker"]]: c for c in raw["companies"]}


def _company_config(company: Company) -> dict:
    return _config()[company]


def ticker(company: Company) -> str:
    return _company_config(company)["ticker"]


def display_name(company: Company) -> str:
    return _company_config(company)["company"]


def output_file(company: Company) -> str:
    return _company_config(company)["outputFile"]


def target_period(company: Company) -> Period:
    return Period.parse(_company_config(company)["period"])


def verify_registry() -> None:
    """Assert the registry agrees with companies.json on labels and units.

    Called at the start of every run: a mismatch here means the workbook would be
    written with a wrong label or unit, which fails the structural check.
    """
    for company, cfg in _config().items():
        expected = [(m["label"], m["units"]) for m in cfg["metrics"]]
        actual = [(s.label, s.units.value) for s in submitted_specs(company)]
        if expected != actual:
            raise ValueError(
                f"{company.value}: registry disagrees with companies.json\n"
                f"  companies.json: {expected}\n"
                f"  registry:       {actual}"
            )
