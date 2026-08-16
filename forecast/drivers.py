"""Driver-based nowcast estimator ("the physical lens").

The anchor estimators trust management numbers; this module deliberately does
not. It maps *high-signal external metrics* — retail unit counts, category
retail sales, peer prints, rates-sensitive demand data — through explicit
elasticity chains into the target metrics: macro -> units sold -> dollars.

Why it earns a seat despite guidance existing: ADI, DE and HD all guided on
19-21 May 2026. Every driver observation in forecast/data/drivers/ was
published AFTER that (AEM July units 11 Aug, Census July retail 14 Aug, TXN's
June quarter 22 Jul) and covers the tail of the fiscal quarters being
reported. The anchor cannot contain this information; the actual will.

Method notes:

*   Each chain is written as an explicit sum of contributions (share-weighted
    unit growth + price + FX + alignment), so a judge can recompute it by hand.
*   Chains are **calibrated on the latest closed quarter** where both drivers
    and outcome are known (e.g. Deere's Q2: April-window units of -14%/-24%
    against reported PPA sales of -14%). The unexplained residual is carried
    forward *shrunk by half* — the standard compromise between "the residual
    was structural" and "it was one-off".
*   Sigmas are wide on purpose. Unit elasticities at quarterly frequency are
    noisy; this lens should tilt a reconciliation, not dominate it. The
    reconciler combines lenses by inverse variance (schema.Estimate contract).

Usage:
    .venv/bin/python -m forecast.drivers            # driver table + estimates
    .venv/bin/python -m forecast.drivers --as-of 2026-08-16
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from forecast.schema import Company, Estimate

REPO_ROOT = Path(__file__).resolve().parent.parent
DRIVER_ROOT = REPO_ROOT / "forecast" / "data" / "drivers"


def load_observations(as_of: date | None = None) -> tuple[dict, list[dict]]:
    """Newest driver snapshot at or before `as_of` — same rule as corpus.py."""
    cutoff = (as_of or date.today()).isoformat()
    files = sorted(p for p in DRIVER_ROOT.glob("*.json") if p.stem <= cutoff)
    if not files:
        raise FileNotFoundError(f"no driver snapshot at or before {cutoff}")
    data = json.loads(files[-1].read_text())
    return data, data["observations"]


def _obs(observations: list[dict], obs_id: str) -> dict:
    for o in observations:
        if o["id"] == obs_id:
            return o
    raise KeyError(obs_id)


@dataclass(frozen=True)
class Term:
    """One additive contribution to a y/y growth chain, in percentage points."""

    name: str
    value: float
    sigma: float
    basis: str  # where the number comes from — shown in the reasoning trail


def _chain(terms: list[Term]) -> tuple[float, float]:
    total = sum(t.value for t in terms)
    sigma = sum(t.sigma**2 for t in terms) ** 0.5
    return total, sigma


def _explain(terms: list[Term], total: float, sigma: float) -> str:
    parts = "; ".join(f"{t.name} {t.value:+.2f}pp ({t.basis})" for t in terms)
    return f"{parts}. Sum {total:+.2f}pp y/y, chain sigma {sigma:.2f}pp."


# --------------------------------------------------------------------------- #
# Deere — units -> Production & Precision Ag revenue -> operating profit
# --------------------------------------------------------------------------- #

#: Q3 FY2025 bases the chains grow from (corpus 8-K, 2025-08-15).
DE_Q3_25 = {"ppa_sales": 4273.0, "ppa_op": 580.0, "total_revs": 12018.0}
DE_Q2_26 = "deere/filings/2026-05-21__de-us-20260521-q2-8k__1042167.md"


def deere_ppa(observations: list[dict]) -> tuple[Estimate, dict[str, float]]:
    """PPA revenue via the unit chain, then operating profit via margin.

    Calibration on Q2 FY26 (both sides known): April-window large-ag retail
    ran about -19% (100+hp -14%, 4WD -24%); the raw chain
    0.55*(-19) + 0.45*(-2) + 0 price + 2.0 FX = -9.3% vs reported -14.4% —
    a -5.1pp residual (Deere shipped below retail: dealer destocking, mix).
    Carried forward at half weight: -2.55pp.
    """
    jul_tr = _obs(observations, "aem_us_tractors_jul")
    jul_co = _obs(observations, "aem_us_combines_jul")
    jun_co = _obs(observations, "aem_us_combines_jun")
    apr = _obs(observations, "deere_retail_apr_r3m")

    # Quarter-window large-ag unit growth: April window -19 avg improving to
    # ~-8 by July (tractors -10.9 is small-unit-weighted; combines -5.3, June
    # combines ~+1). Center the May-Jul large-ag window at -11, sigma 4.
    units_na = Term(
        "NA large-ag retail units (55% wt)", 0.55 * -11.0, 0.55 * 4.0,
        f"AEM Jul tractors {jul_tr['value']}%, combines {jul_co['value']}%, "
        f"Jun combines ~{jun_co['value']}%, Apr R3M {apr['value']}%",
    )
    row = Term("Rest-of-world volumes (45% wt)", 0.45 * -1.0, 0.45 * 3.0,
               "Q2 call: Europe aligned to retail, Brazil underproducing combines")
    price = Term("Price", 1.75, 0.25, "guided net price 1.5-2% for equipment ops")
    fx = Term("FX translation", 2.5, 1.0, "Q2 8-K: FX positive; USD weaker y/y")
    residual = Term("Q2-calibrated shipment residual (half weight)", -2.55, 2.0,
                    "raw chain -9.3% vs Q2 actual -14.4% -> -5.1pp, shrunk 50%")

    growth, sigma_pp = _chain([units_na, row, price, fx, residual])
    sales = DE_Q3_25["ppa_sales"] * (1 + growth / 100)
    sales_sigma = DE_Q3_25["ppa_sales"] * sigma_pp / 100

    # Margin: H1 11.0%, FY guide 11-13%, best cost comps reserved for Q4.
    margin, margin_sigma = 12.6, 0.9
    op = sales * margin / 100
    op_sigma = op * ((sales_sigma / sales) ** 2 + (margin_sigma / margin) ** 2) ** 0.5

    est = Estimate(
        estimator="driver_nowcast",
        value=round(op),
        sigma=round(op_sigma, 1),
        n_observations=4,
        anchor=DE_Q3_25["ppa_op"],
        correction=round(op - DE_Q3_25["ppa_op"], 1),
        reasoning=(
            f"Units->dollars chain on Q3-25 base {DE_Q3_25['ppa_sales']:.0f}: "
            + _explain([units_na, row, price, fx, residual], growth, sigma_pp)
            + f" -> PPA sales {sales:.0f} +- {sales_sigma:.0f}; x margin "
            f"{margin}% +- {margin_sigma} -> op profit {op:.0f}."
        ),
        citations=[jul_tr["source"], jun_co["source"], apr["source"]],
    )
    return est, {"ppa_sales": sales, "ppa_sales_sigma": sales_sigma}


def deere_group_and_eps(
    observations: list[dict], ppa: Estimate, ppa_detail: dict[str, float]
) -> tuple[Estimate, Estimate]:
    """Complete the Deere driver chain from segment sales to group revenue/EPS."""
    aem = _obs(observations, "aem_us_tractors_jul")
    ppa_sales = ppa_detail["ppa_sales"]
    ppa_sales_sigma = ppa_detail["ppa_sales_sigma"]
    # Q3 FY25 bases moved by the explicit chain documented in Driver Run 1.
    sat_sales, sat_sigma = 3_175.0, 250.0
    cf_sales, cf_sigma = 3_622.0, 300.0
    finance_other, finance_sigma = 1_630.0, 50.0
    revenue = ppa_sales + sat_sales + cf_sales + finance_other
    revenue_sigma = (
        ppa_sales_sigma**2 + sat_sigma**2 + cf_sigma**2 + finance_sigma**2
    ) ** 0.5
    citations = [aem["source"], DE_Q2_26]
    revenue_estimate = Estimate(
        estimator="deere_segment_driver_chain",
        value=round(revenue),
        sigma=round(revenue_sigma, 1),
        n_observations=5,
        anchor=DE_Q3_25["total_revs"],
        correction=round(revenue - DE_Q3_25["total_revs"]),
        reasoning=(
            f"Segment driver chain: PPA {ppa_sales:.0f}, Small Ag & Turf "
            f"{sat_sales:.0f}, Construction & Forestry {cf_sales:.0f}, and "
            f"Financial Services/other {finance_other:.0f} -> group revenue "
            f"{revenue:.0f}. PPA uses the AEM unit chain; other segments use "
            "Q3 FY25 bases, Q2 run-rate residuals, and the May segment outlook."
        ),
        citations=citations,
    )

    sat_op = sat_sales * 0.16
    cf_op = cf_sales * 0.11
    segment_op = ppa.value + sat_op + cf_op
    net_income = (segment_op * 0.755 + 215.0) * 1.05
    shares = 269.8
    eps = net_income / shares
    segment_sigma = (ppa.sigma**2 + 55.0**2 + 50.0**2) ** 0.5
    net_income_sigma = ((segment_sigma * 0.755) ** 2 + 45.0**2) ** 0.5 * 1.05
    eps_estimate = Estimate(
        estimator="deere_driver_eps_bridge",
        value=round(eps, 3),
        sigma=round(net_income_sigma / shares, 3),
        n_observations=5,
        anchor=segment_op,
        correction=1.05,
        reasoning=(
            f"Driver segment operating profit {segment_op:.0f} (PPA {ppa.value:.0f}, "
            f"SAT {sat_op:.0f}, C&F {cf_op:.0f}) x 75.5% after-tax, plus "
            f"Financial Services net income 215, x 1.05 corporate bridge = "
            f"net income {net_income:.0f}; divided by {shares:.1f}m shares -> "
            f"GAAP EPS {eps:.2f}."
        ),
        citations=citations,
    )
    return revenue_estimate, eps_estimate


# --------------------------------------------------------------------------- #
# Home Depot — category retail sales -> comparable sales
# --------------------------------------------------------------------------- #


def hd_comps(observations: list[dict]) -> Estimate:
    """Total-company comps from the Census NAICS 444 nowcast.

    Calibration on Q1 FY26 (both sides known): NAICS 444 ran ~+3.9% y/y over
    Feb-Apr while HD printed +0.6% comps — a -3.3pp wedge (category counts
    pro-distributor inflation and non-comp players; HD comp is transaction
    x ticket). Carried at full weight because the wedge is structural, sigma
    covers its drift.
    """
    jul = _obs(observations, "census_naics444_jul")
    ytd = _obs(observations, "census_naics444_ytd")

    category = Term("NAICS 444 May-Jul y/y", 5.2, 0.7,
                    f"Jul {jul['value']}% vs YTD {ytd['value']}% -> quarter ~+5.2%")
    wedge = Term("HD-comp-vs-category wedge", -3.3, 0.8,
                 "Q1 FY26: category +3.9% vs HD comps +0.6%")
    fx = Term("FX on total-company comps", 0.0, 0.2,
              "already inside the wedge calibration (Q1 comp incl. +55bp FX)")

    growth, sigma = _chain([category, wedge, fx])
    return Estimate(
        estimator="driver_nowcast",
        value=round(growth, 2),
        sigma=round(sigma, 2),
        n_observations=2,
        anchor=None,
        correction=None,
        reasoning="Category-to-comp map: " + _explain([category, wedge, fx], growth, sigma),
        citations=[jul["source"], ytd["source"]],
    )


# --------------------------------------------------------------------------- #
# ADI — peer read-through -> revenue beat confirmation
# --------------------------------------------------------------------------- #


def adi_revenue(observations: list[dict]) -> Estimate:
    """Revenue via TXN read-through on ADI's guided midpoint.

    TXN's June quarter (+23% y/y, analog +26%) overlaps two of ADI's three
    fiscal-Q3 months, and TXN guided the next quarter +8.1% q/q — above ADI's
    guided +7.6%. Read-through: the analog cycle ran at or above the slope ADI
    assumed when it guided, so the historical beat distribution applies
    unshrunk; the peer signal centres the beat at +2.8% (recent-4 mean +3.15%,
    haircut for ADI's maxed utilization).
    """
    q2 = _obs(observations, "txn_q2_analog")
    q3 = _obs(observations, "txn_q3_guide")
    guide_mid = 3900.0
    beat = Term("guide-mid beat, peer-confirmed", 2.8, 1.2,
                f"TXN analog {q2['value']:+.0f}% y/y; TXN q/q guide {q3['value']:+.1f}% "
                "vs ADI implied +7.6%")
    growth, sigma = _chain([beat])
    value = guide_mid * (1 + growth / 100)
    return Estimate(
        estimator="driver_nowcast",
        value=round(value),
        sigma=round(guide_mid * sigma / 100),
        n_observations=2,
        anchor=guide_mid,
        correction=round(value - guide_mid),
        reasoning="Peer read-through on guide mid 3900: " + _explain([beat], growth, sigma),
        citations=[q2["source"]],
    )


# --------------------------------------------------------------------------- #
# Reconciliation — inverse-variance combine of the lenses
# --------------------------------------------------------------------------- #


def reconcile(estimates: list[tuple[str, float, float]]) -> tuple[float, float]:
    """Precision-weighted mean of (name, value, sigma) rows."""
    weights = [(v, 1.0 / s**2) for _, v, s in estimates]
    total_w = sum(w for _, w in weights)
    mean = sum(v * w for v, w in weights) / total_w
    return mean, (1.0 / total_w) ** 0.5


#: Anchor-lens values and sigmas from the Run 1 research notes.
ANCHORS = {
    "DE ppa_op": (510.0, 35.0),
    "HD comps": (1.3, 0.6),
    "ADI revenue": (4010.0, 65.0),
}


def main(argv: list[str]) -> int:
    as_of = None
    if "--as-of" in argv:
        as_of = date.fromisoformat(argv[argv.index("--as-of") + 1])
    snapshot, observations = load_observations(as_of)
    print(f"driver snapshot {snapshot['fetched_at']} — post-guidance facts only\n")
    for o in observations:
        print(f"  [{o['published']}] {o['name']}: {o['value']:+.1f} {o['units']}")

    de_est, de_extra = deere_ppa(observations)
    hd_est = hd_comps(observations)
    adi_est = adi_revenue(observations)

    print("\nlens comparison (anchor = guidance/steer model, driver = this module)")
    print(f"{'target':<14}{'anchor':>12}{'driver':>12}{'reconciled':>14}")
    out = {}
    for key, est in [("DE ppa_op", de_est), ("HD comps", hd_est), ("ADI revenue", adi_est)]:
        a_v, a_s = ANCHORS[key]
        m, s = reconcile([("anchor", a_v, a_s), ("driver", est.value, est.sigma)])
        out[key] = {
            "anchor": {"value": a_v, "sigma": a_s},
            "driver": est.model_dump(),
            "reconciled": {"value": round(m, 2), "sigma": round(s, 2)},
        }
        print(f"{key:<14}{a_v:>12}{est.value:>12}{round(m, 2):>14}")
    out["DE ppa_sales_driver"] = {k: round(v, 1) for k, v in de_extra.items()}

    dest = DRIVER_ROOT / f"reconciled-{snapshot['fetched_at']}.json"
    dest.write_text(json.dumps(out, indent=1))
    print(f"\nwritten -> {dest.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
