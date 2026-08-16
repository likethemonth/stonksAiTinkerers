"""Adapter for Uri's point-in-time Home Depot classical-ML artifact.

The ML lens is an estimator inside the fundamental engine. It never becomes a
fourth top-level vote. Only predictions whose task-matched validation gate passed
are exposed, and sparse validation samples reduce precision by widening sigma.
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from forecast.schema import Company, Estimate

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = REPO_ROOT / "agent" / "ml-prediction-forecast.json"

# Precision multiplier for tiny task-matched holdouts. The reported validation
# error remains the base dispersion; dividing by sqrt(reliability) prevents
# three successful historical transitions from dominating current evidence.
_SPARSE_RELIABILITY = {
    "net_sales": 0.35,
    "adj_eps": 0.35,
    "comp_sales_pct": 0.25,
}


@lru_cache(maxsize=8)
def hd_estimates(as_of: date) -> dict[tuple[Company, str], Estimate]:
    if not ARTIFACT.exists():
        return {}
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    artifact_date = date.fromisoformat(payload["asOf"])
    if artifact_date > as_of:
        return {}

    gates = payload["gates"]
    predictions = payload["prediction"]
    result: dict[tuple[Company, str], Estimate] = {}

    if gates["net_sales"]["passed"] and "net_sales" in predictions:
        row = predictions["net_sales"]
        base_sigma = row["value"] * gates["net_sales"]["mape_pct"] / 100.0
        result[(Company.HD, "net_sales")] = _estimate(
            "ml_q2_sequential_sales",
            row["value"],
            base_sigma,
            "net_sales",
            gates["net_sales"],
            row,
        )

    if gates["diluted_eps_gaap"]["passed"] and "adj_eps_derived" in predictions:
        row = predictions["adj_eps_derived"]
        base_sigma = (
            row["value"] * gates["diluted_eps_gaap"]["mape_pct"] / 100.0
        )
        result[(Company.HD, "adj_eps")] = _estimate(
            "ml_q2_sequential_eps_bridge",
            row["value"],
            base_sigma,
            "adj_eps",
            gates["diluted_eps_gaap"],
            row,
        )

    if gates["comp_sales_pct"]["passed"] and "comp_sales_pct" in predictions:
        row = predictions["comp_sales_pct"]
        result[(Company.HD, "comp_sales_pct")] = _estimate(
            "ml_comp_lag_ridge",
            row["value"],
            gates["comp_sales_pct"]["holdout_mae_pp"],
            "comp_sales_pct",
            gates["comp_sales_pct"],
            row,
        )
    return result


def _estimate(
    estimator: str,
    value: float,
    base_sigma: float,
    key: str,
    gate: dict,
    prediction: dict,
) -> Estimate:
    reliability = _SPARSE_RELIABILITY[key]
    sigma = base_sigma / reliability**0.5
    validation = (
        f"task-matched MAPE {gate['mape_pct']:.2f}%"
        if "mape_pct" in gate
        else f"leave-last-3-out MAE {gate['holdout_mae_pp']:.2f}pp"
    )
    caveat = prediction.get("caveat") or "; ".join(prediction.get("caveats", []))
    return Estimate(
        estimator=estimator,
        value=float(value),
        sigma=max(float(sigma), 1e-6),
        n_observations=3,
        reasoning=(
            f"Classical-ML estimate passed its validation gate ({validation}). "
            f"Sparse-holdout precision factor {reliability:.0%} widens sigma from "
            f"{base_sigma:.3f} to {sigma:.3f}. {caveat}"
        ),
        citations=[
            "agent/ml-prediction-forecast.json",
            "data/observations/home-depot.json",
        ],
    )
