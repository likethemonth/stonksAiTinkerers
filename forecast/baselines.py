"""Provisional baselines for companies without an extractor yet.

Why this module exists. Under the accuracy rubric a MISSING forecast scores 5.0,
the worst outcome available, while a merely rough one scores around 1.5. So the
first priority is a defensible number in all twelve cells; refinement is upside.
Every baseline here is therefore built from a figure a company actually disclosed,
carries its source document, and states its arithmetic in full.

These are deliberately simple: an anchor the company published, moved by a
disclosed growth rate or a share of the fiscal year. No calibration, because
without an extractor there is no observation history to calibrate against. Each
one is flagged `needs_review` so it is visibly provisional in the run log, and
each is a direct upgrade target once its extractor lands.

ADI is absent from this module: it has a real extractor and is forecast from
calibrated guidance in estimators.py.
"""

from __future__ import annotations

from forecast.schema import Company, Estimate

# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #

HD_Q1_8K = "home-depot/filings/2026-05-19__hd-us-20260519-q1-8k__1038584.md"
HD_Q2_FY25_8K = "home-depot/filings/2025-08-19__hd-us-20250819-q2-8k__101812.md"
HAS_Q4_TRADING = "hays/filings/2026-07-10__has-ln-20260710-q4-8k__1572805.md"
HAS_FY25_RESULTS = "hays/filings/2025-08-21__has-ln-20250821-fy-8k__155999.md"
DE_Q2_8K = "deere/filings/2026-05-21__de-us-20260521-q2-8k__1042167.md"
DE_Q3_FY25_8K = "deere/filings/2025-08-15__de-us-20250815-q3-8k__143410.md"


def _estimate(
    name: str,
    value: float,
    sigma: float,
    reasoning: str,
    citations: list[str],
    anchor: float | None = None,
) -> Estimate:
    return Estimate(
        estimator=name,
        value=value,
        sigma=sigma,
        n_observations=0,  # no calibration history: this is an uncalibrated anchor
        anchor=anchor,
        reasoning=reasoning,
        citations=citations,
    )


# --------------------------------------------------------------------------- #
# Home Depot · FY2026Q2
# --------------------------------------------------------------------------- #
# FY2026 guidance reaffirmed 19 May 2026: total sales growth ~2.5% to 4.5%,
# comparable sales ~flat to 2.0%, adjusted diluted EPS ~flat to +4.0% from
# $14.69 in fiscal 2025. Q2 FY2025 actuals: net sales $45.3bn, adjusted diluted
# EPS $4.68.

HD_BASELINES: dict[str, Estimate] = {
    "Net sales": _estimate(
        "fy_growth_applied_to_prior_quarter",
        45_300.0 * 1.035,
        sigma=45_300.0 * 0.02,
        anchor=45_300.0,
        reasoning=(
            "Q2 FY2025 net sales of $45.3bn grown by the midpoint of the "
            "reaffirmed FY2026 total sales growth guidance of 2.5%-4.5% (3.5%). "
            "Assumes Q2 grows in line with the full year; the acquisitions "
            "contributing to FY26 growth were present for part of Q2 FY25, so "
            "this may understate slightly."
        ),
        citations=[HD_Q1_8K, HD_Q2_FY25_8K],
    ),
    "Adjusted diluted EPS": _estimate(
        "fy_guide_by_seasonal_share",
        14.69 * 1.02 * (4.68 / 14.69),
        sigma=0.20,
        anchor=14.69 * 1.02,
        reasoning=(
            "FY2026 adjusted diluted EPS guided to grow ~flat to +4.0% from "
            "$14.69, midpoint +2.0% giving $14.98 for the year. Q2 FY2025 "
            "adjusted EPS of $4.68 was 31.9% of FY2025's $14.69; applying that "
            "same seasonal share to the FY2026 midpoint gives the quarter."
        ),
        citations=[HD_Q1_8K, HD_Q2_FY25_8K],
    ),
    "Comparable sales, total company": _estimate(
        "fy_guide_midpoint",
        1.0,
        sigma=0.8,
        anchor=1.0,
        reasoning=(
            "FY2026 comparable sales guided ~flat to 2.0%, midpoint 1.0%. Q1 "
            "FY2026 printed +0.6%, below that midpoint, which implies management "
            "expects stronger comps later in the year; taking the FY midpoint "
            "for Q2 is the neutral read between the two."
        ),
        citations=[HD_Q1_8K],
    ),
}


# --------------------------------------------------------------------------- #
# Hays plc · FY2026
# --------------------------------------------------------------------------- #
# The strongest-evidenced company in the set. The Q4 FY2026 trading statement
# (10 July 2026) reports the year's net fee growth and discloses company-compiled
# consensus for operating profit, together with management's own steer on where
# in that range the year will land.

HAS_BASELINES: dict[str, Estimate] = {
    "Net fees": _estimate(
        "disclosed_growth_on_prior_year",
        972.4 * 0.96,
        sigma=972.4 * 0.01,
        anchor=972.4,
        reasoning=(
            "FY2025 net fees of GBP 972.4m reduced by the 4% actual (reported "
            "basis) decline given in the Q4 FY2026 trading statement. The "
            "statement's headline 5% decline is like-for-like; the actual basis "
            "is the one that reconciles to reported net fees, and is what the "
            "workbook asks for."
        ),
        citations=[HAS_Q4_TRADING, HAS_FY25_RESULTS],
    ),
    "Pre-exceptional operating profit": _estimate(
        "consensus_plus_management_steer",
        45.5,
        sigma=1.2,
        anchor=43.5,
        reasoning=(
            "Company-compiled consensus for FY2026 pre-exceptional operating "
            "profit was GBP 43.5m across a 37.0-46.0m range from 10 analysts as "
            "at 9 July 2026. Management stated they expect to land at the TOP of "
            "that range. We take 45.5m: just below the 46.0m ceiling, since "
            "'top of the range' is a directional steer rather than a point "
            "commitment. This is a deliberate, evidenced deviation above "
            "consensus rather than a matching of it."
        ),
        citations=[HAS_Q4_TRADING],
    ),
    "Pre-exceptional basic EPS": _estimate(
        "profit_ratio_on_prior_year_eps",
        1.31 * (45.5 / 45.6),
        sigma=0.12,
        anchor=1.31,
        reasoning=(
            "FY2025 pre-exceptional basic EPS was 1.31p on pre-exceptional "
            "operating profit of GBP 45.6m. FY2026 operating profit is forecast "
            "at 45.5m, essentially flat, so EPS is scaled by the profit ratio. "
            "The completed buyback reduces the share count, which is upside not "
            "captured here; the higher net finance charge noted in FY2025 is a "
            "partial offset. Entered in PENCE."
        ),
        citations=[HAS_Q4_TRADING, HAS_FY25_RESULTS],
    ),
}


# --------------------------------------------------------------------------- #
# Deere & Company · FY2026Q3
# --------------------------------------------------------------------------- #
# FY2026 net income guided to $4.5-5.0bn (maintained at Q2). H1 FY2026 net income
# was $2.429bn on $8.97 per share, implying ~270.8m diluted shares. Q3 FY2025
# actuals: total net sales and revenues $12,018m, net income $1.289bn ($4.75 per
# share), P&PA net sales $4,273m and operating profit $580m (13.6% margin).

_DE_H2_NET_INCOME = 4_750.0 - 2_429.0  # FY guide midpoint less reported H1
_DE_Q3_SHARE_OF_H2 = 0.55  # Q3 runs ahead of Q4 in Deere's seasonal pattern
_DE_DILUTED_SHARES = 270.8

DE_BASELINES: dict[str, Estimate] = {
    "Worldwide net sales and revenues": _estimate(
        "prior_year_quarter_with_fy_decline",
        12_018.0 * 0.95,
        sigma=12_018.0 * 0.04,
        anchor=12_018.0,
        reasoning=(
            "Q3 FY2025 worldwide net sales and revenues of $12,018m reduced 5%. "
            "The FY2026 segment outlook has Production & Precision Ag down 5-10% "
            "with Small Ag & Turf and Construction & Forestry holding up better, "
            "so a group decline at the shallower end of the P&PA range is the "
            "neutral read."
        ),
        citations=[DE_Q2_8K, DE_Q3_FY25_8K],
    ),
    "Diluted EPS (GAAP)": _estimate(
        "fy_guide_residual_by_seasonal_share",
        (_DE_H2_NET_INCOME * _DE_Q3_SHARE_OF_H2) / _DE_DILUTED_SHARES,
        sigma=0.55,
        anchor=_DE_H2_NET_INCOME / _DE_DILUTED_SHARES,
        reasoning=(
            "FY2026 net income guided to $4.5-5.0bn, midpoint $4.75bn. H1 FY2026 "
            "delivered $2.429bn, leaving $2.321bn for H2. Q3 takes 55% of that "
            "on Deere's usual seasonal split, giving $1.277bn. Divided by the "
            "270.8m diluted shares implied by H1's $2.429bn at $8.97 per share."
        ),
        citations=[DE_Q2_8K],
    ),
    "Production & Precision Ag operating profit": _estimate(
        "segment_sales_times_margin",
        4_273.0 * 0.925 * 0.150,
        sigma=90.0,
        anchor=4_273.0 * 0.925,
        reasoning=(
            "Q3 FY2025 P&PA net sales of $4,273m reduced 7.5%, the midpoint of "
            "the FY2026 guidance of down 5-10%, giving ~$3,952m. Applying a 15.0% "
            "operating margin: above Q3 FY2025's 13.6% because FY2026 guidance "
            "carries ~3.0% positive price realisation, but below the 15.7% Q2 "
            "FY2026 achieved ($706m on $4,503m), since Q3 carries lower volume. "
            "This is the least-constrained of the twelve and the first to "
            "replace with a fitted segment model."
        ),
        citations=[DE_Q2_8K, DE_Q3_FY25_8K],
    ),
}


BASELINES: dict[Company, dict[str, Estimate]] = {
    Company.HD: HD_BASELINES,
    Company.HAS: HAS_BASELINES,
    Company.DE: DE_BASELINES,
}
