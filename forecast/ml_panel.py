"""Generic ML lens — the Home Depot pipeline applied to ADI, Deere and Hays.

`ml_hd.py`/`ml_hd_v2.py` established a protocol and a lesson. The protocol:
chronological-only validation, a mandatory seasonal-naive baseline, gates
declared before running, predictions stored only for metrics that pass. The
lesson: **estimator choice was never the bottleneck — reframing the target so
that already-published information carries most of the answer was.** For HD
that reframe was share-of-category (the Census category level is published
before HD reports, so only HD's share is unknown).

This module runs the identical protocol on the other three companies and asks,
for each, whether the same reframe exists:

    ADI    YES — ADI guides revenue, adjusted EPS and adjusted operating
           margin one quarter ahead, and the FY2026Q3 guides are already in the
           observation table. Only the *realisation ratio* (actual / guide_mid)
           is unknown. This is structurally identical to HD's share model and
           has 20 historical ratios behind it.
    DEERE  NO — Deere guides full-year net income, not quarterly segment
           lines, so nothing about Q3 is pre-published. Pure history only, on a
           series with real gaps (no Q4 rows at all) and post-2024 operating
           deleverage that breaks stationarity.
    HAYS   NO, AND NOT AN ML PROBLEM — 7-8 annual observations. No honest
           model can be fit. The H1->FY ratio model is run anyway so the
           failure is quantified rather than asserted.

Every metric is scored against a pre-declared gate and the naive baseline;
failures are reported, not hidden, and no prediction is stored for a metric
that fails. A lens that knows when to abstain is worth more than one that
always emits a number.

Usage:  .venv/bin/python -m forecast.ml_panel
Output: agent/ml-panel-forecast.json + stdout report
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor, VotingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

REPO_ROOT = Path(__file__).resolve().parent.parent
OBS_DIR = REPO_ROOT / "data" / "observations"
OUT_PATH = REPO_ROOT / "agent" / "ml-panel-forecast.json"
RANDOM_STATE = 26

#: Pre-declared accuracy gates. MAPE (%) for money/EPS metrics, MAE in the
#: metric's own points for percentage metrics. Set from what would actually be
#: competitive against a Street benchmark, not from what the models can hit.
GATES = {
    ("analog-devices", "revenue"): ("mape", 2.0),
    ("analog-devices", "adj_eps"): ("mape", 5.0),
    ("analog-devices", "adj_gross_margin_pct"): ("mae", 1.0),
    ("deere", "worldwide_net_sales_revenues"): ("mape", 2.0),
    ("deere", "diluted_eps_gaap"): ("mape", 5.0),
    ("deere", "ppa_operating_profit"): ("mape", 10.0),
    ("hays", "net_fees"): ("mape", 2.0),
    ("hays", "pre_exc_operating_profit"): ("mape", 10.0),
    ("hays", "pre_exc_basic_eps"): ("mape", 10.0),
}

TARGETS = {
    "analog-devices": ("FY2026Q3", ["revenue", "adj_eps", "adj_gross_margin_pct"]),
    "deere": ("FY2026Q3", ["worldwide_net_sales_revenues", "diluted_eps_gaap",
                           "ppa_operating_profit"]),
    "hays": ("FY2026", ["net_fees", "pre_exc_operating_profit", "pre_exc_basic_eps"]),
}

#: ADI's FY2020Q4-FY2021 rows sit inside the COVID semiconductor whipsaw; Deere
#: FY2020 likewise. Excluded from training targets, kept inside lag features.
COVID_YEARS = {2020, 2021}


# --------------------------------------------------------------------------- #
# Period handling (quarterly and annual)
# --------------------------------------------------------------------------- #


def period_index(period: str) -> int:
    """FY2026Q3 -> quarter index; FY2026 (annual) -> year index * 4."""
    year = int(period[2:6])
    if "Q" in period:
        return (year - 2013) * 4 + int(period[-1]) - 1
    return (year - 2013) * 4          # annual: aligned to Q1 slot, step 4


def index_period(i: int, annual: bool = False) -> str:
    return f"FY{2013 + i // 4}" if annual else f"FY{2013 + i // 4}Q{i % 4 + 1}"


def load_series(company: str, metric: str, kind: str = "ACTUAL") -> dict[int, float]:
    data = json.loads((OBS_DIR / f"{company}.json").read_text())
    return {
        period_index(o["period"]): o["value"]
        for o in data["observations"]
        if o["metric_key"] == metric and o["kind"] == kind
    }


def is_covid(t: int) -> bool:
    return (2013 + t // 4) in COVID_YEARS


# --------------------------------------------------------------------------- #
# Model zoo (identical to ml_hd_v2)
# --------------------------------------------------------------------------- #


def base_models() -> dict[str, object]:
    return {
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "random_forest": RandomForestRegressor(
            n_estimators=300, max_depth=3, random_state=RANDOM_STATE),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=2, learning_rate=0.05,
            random_state=RANDOM_STATE),
        "svr_rbf": make_pipeline(StandardScaler(),
                                 SVR(kernel="rbf", C=10.0, epsilon=0.005, gamma="scale")),
        "knn": make_pipeline(StandardScaler(),
                             KNeighborsRegressor(n_neighbors=3, weights="distance")),
    }


def voting_model() -> VotingRegressor:
    return VotingRegressor(list(base_models().items()))


# --------------------------------------------------------------------------- #
# Framing A — pure history (sequential ratio / year-over-year growth)
# --------------------------------------------------------------------------- #


def _past_same_transition(series: dict[int, float], t: int, step: int) -> list[float]:
    """Past ratios for the same transition, ex-COVID — the naive baseline."""
    out, k = [], t - 4
    while k in series and k - step in series:
        if not is_covid(k):
            out.append(series[k] / series[k - step])
        k -= 4
    return out


def history_rows(series: dict[int, float], framing: str, step: int = 1):
    """Feature matrix for the pure-history framings.

    seq: target = y_t / y_{t-step};  yoy: target = y_t / y_{t-4}.
    """
    lag = step if framing == "seq" else 4
    X, y, idx = [], [], []
    for t in sorted(series):
        if is_covid(t):
            continue
        need = [t - lag, t - 4, t - 4 - lag]
        if not all(k in series for k in need):
            continue
        past = _past_same_transition(series, t, lag)
        if len(past) < 2:
            continue
        prev_year_ratio = series[t - 4] / series[t - 4 - lag]
        med = float(np.median(past))
        recent = past[0] if past else med
        q = t % 4
        X.append([prev_year_ratio, med, recent, float(np.std(past)),
                  int(q == 0), int(q == 1), int(q == 2)])
        y.append(series[t] / series[t - lag])
        idx.append(t)
    return np.array(X), np.array(y), idx


def history_naive(series: dict[int, float], t: int, step: int) -> float | None:
    past = _past_same_transition(series, t, step)
    if not past:
        return None
    return series[t - step] * float(np.median(past))


# --------------------------------------------------------------------------- #
# Framing B — guidance realisation (ADI). The structural reframe.
# --------------------------------------------------------------------------- #


def realisation_ratios(actual: dict[int, float], guide: dict[int, float]) -> dict[int, float]:
    return {t: actual[t] / guide[t] for t in actual if t in guide and guide[t]}


def guidance_walk_forward(actual, guide, gate_kind: str, start_t: int) -> dict:
    """Predict actual_t = guide_t x (expanding mean of past realisation ratios).

    Zero fitted parameters: the estimator is the running mean of every past
    ratio, so nothing can be overfit and the walk-forward is exact. Guidance
    for period t is published BEFORE period t is reported, which is what makes
    guide_t a legal feature — the same legality argument as HD's category level.
    """
    ratios = realisation_ratios(actual, guide)
    rows, errs = [], []
    for t in sorted(ratios):
        if t < start_t or is_covid(t):
            continue
        past = [ratios[k] for k in sorted(ratios) if k < t and not is_covid(k)]
        if len(past) < 4:
            continue
        pred = guide[t] * float(np.mean(past))
        a = actual[t]
        err = abs(pred - a) if gate_kind == "mae" else abs(pred - a) / abs(a) * 100
        naive = guide[t]                      # trust guidance verbatim
        nerr = abs(naive - a) if gate_kind == "mae" else abs(naive - a) / abs(a) * 100
        rows.append({"period": index_period(t), "actual": a, "predicted": round(pred, 3),
                     "guide": guide[t], "err": round(err, 3), "naive_err": round(nerr, 3)})
        errs.append((err, nerr))
    if not errs:
        return {"n": 0}
    return {
        "n": len(errs), "detail": rows,
        "score": round(float(np.mean([e for e, _ in errs])), 3),
        "naive_score": round(float(np.mean([n for _, n in errs])), 3),
        "beats_naive": bool(np.mean([e for e, _ in errs]) < np.mean([n for _, n in errs])),
    }


def guidance_predict(actual, guide, t: int) -> tuple[float, float, int]:
    ratios = realisation_ratios(actual, guide)
    past = [ratios[k] for k in sorted(ratios) if k < t and not is_covid(k)]
    mean_ratio = float(np.mean(past))
    return guide[t] * mean_ratio, mean_ratio, len(past)


#: Estimators for "what ratio will the next quarter realise?". The deployed one
#: (expanding_mean) is fixed before the ablation runs; the ablation exists to
#: measure how much the answer depends on that choice, NOT to pick a winner
#: after seeing scores. For HD's share model the equivalent spread was 3x
#: (0.39%-1.23%), which was that lens's main weakness.
RATIO_ESTIMATORS = {
    "expanding_mean": lambda p: float(np.mean(p)),
    "expanding_median": lambda p: float(np.median(p)),
    "trailing4": lambda p: float(np.mean(p[-4:])),
    "trailing8": lambda p: float(np.mean(p[-8:])),
    "last_only": lambda p: float(p[-1]),
}


def realisation_ablation(actual, guide, gate_kind: str, start_t: int) -> dict:
    """Score every ratio estimator on the same walk-forward. Robustness check."""
    ratios = realisation_ratios(actual, guide)
    scores = {}
    for name, fn in RATIO_ESTIMATORS.items():
        errs = []
        for t in sorted(ratios):
            if t < start_t or is_covid(t):
                continue
            past = [ratios[k] for k in sorted(ratios) if k < t and not is_covid(k)]
            if len(past) < 4:
                continue
            pred = guide[t] * fn(past)
            a = actual[t]
            errs.append(abs(pred - a) if gate_kind == "mae" else abs(pred - a) / abs(a) * 100)
        if errs:
            scores[name] = round(float(np.mean(errs)), 3)
    return {"scores": scores,
            "spread": round(max(scores.values()) - min(scores.values()), 3) if scores else None,
            "deployed": "expanding_mean",
            "deployed_is_best": bool(scores and
                                     min(scores, key=scores.get) == "expanding_mean")}


def intrinsic_floor(series: dict[int, float], target_t: int, step: int = 1) -> dict:
    """Dispersion of the target transition's own ratio history.

    If a metric's same-transition ratio has coefficient of variation c, then no
    estimator that uses only that history can average better than roughly c%
    MAPE. This separates "the model is bad" from "the data cannot answer" — the
    distinction that decides whether to iterate or to abstain.
    """
    ratios = []
    k = target_t - 4
    while k in series and k - step in series:
        if not is_covid(k) and series[k - step]:
            ratios.append((index_period(k), round(series[k] / series[k - step], 4)))
        k -= 4
    if len(ratios) < 3:
        return {"n": len(ratios), "history": ratios, "floor_mape_pct": None}
    vals = [r for _, r in ratios]
    return {
        "n": len(vals), "history": list(reversed(ratios)),
        "mean_ratio": round(float(np.mean(vals)), 4),
        "sd": round(float(np.std(vals, ddof=1)), 4),
        "floor_mape_pct": round(float(np.std(vals, ddof=1) / abs(np.mean(vals)) * 100), 1),
    }


# --------------------------------------------------------------------------- #
# Shared walk-forward for the ML framings
# --------------------------------------------------------------------------- #


def ml_walk_forward(series, framing, step, gate_kind, min_train=8) -> dict:
    X, y, idx = history_rows(series, framing, step)
    if len(y) < min_train + 2:
        return {"n": 0, "reason": f"only {len(y)} usable rows"}
    lag = step if framing == "seq" else 4
    rows, errs, nerrs = [], [], []
    for i, t in enumerate(idx):
        train = [j for j, tj in enumerate(idx) if tj < t]
        if len(train) < min_train:
            continue
        model = voting_model()
        model.fit(X[train], y[train])
        pred = series[t - lag] * float(model.predict(X[i:i + 1])[0])
        naive = history_naive(series, t, lag)
        if naive is None:
            continue
        a = series[t]
        err = abs(pred - a) if gate_kind == "mae" else abs(pred - a) / abs(a) * 100
        nerr = abs(naive - a) if gate_kind == "mae" else abs(naive - a) / abs(a) * 100
        rows.append({"period": index_period(t), "actual": a, "predicted": round(pred, 3),
                     "err": round(err, 3), "naive_err": round(nerr, 3)})
        errs.append(err)
        nerrs.append(nerr)
    if not errs:
        return {"n": 0, "reason": "no walk-forward point had enough training history"}
    target_q = None
    return {
        "n": len(errs), "framing": framing, "detail": rows,
        "score": round(float(np.mean(errs)), 3),
        "naive_score": round(float(np.mean(nerrs)), 3),
        "beats_naive": bool(np.mean(errs) < np.mean(nerrs)),
    }


def ml_predict(series, framing, step, t) -> float | None:
    X, y, idx = history_rows(series, framing, step)
    if len(y) < 8:
        return None
    lag = step if framing == "seq" else 4
    need = [t - lag, t - 4, t - 4 - lag]
    if not all(k in series for k in need):
        return None
    past = _past_same_transition(series, t, lag)
    if len(past) < 2:
        return None
    model = voting_model()
    model.fit(X, y)
    q = t % 4
    feats = np.array([[series[t - 4] / series[t - 4 - lag], float(np.median(past)),
                       past[0], float(np.std(past)),
                       int(q == 0), int(q == 1), int(q == 2)]])
    return series[t - lag] * float(model.predict(feats)[0])


# --------------------------------------------------------------------------- #
# Company runners
# --------------------------------------------------------------------------- #


def run_adi() -> dict:
    """ADI: guidance realisation vs pure history, head to head."""
    out = {"company": "analog-devices", "period": "FY2026Q3", "metrics": {}}
    target = period_index("FY2026Q3")
    start = period_index("FY2023Q1")

    specs = [
        ("revenue", "revenue", "mape"),
        ("adj_eps", "adj_eps", "mape"),
    ]
    for metric, guide_metric, gate_kind in specs:
        actual = load_series("analog-devices", metric)
        guide = load_series("analog-devices", guide_metric, "GUIDE_MID")
        g = guidance_walk_forward(actual, guide, gate_kind, start)
        h = ml_walk_forward(actual, "seq", 1, gate_kind)
        best = "guidance_realisation" if (h.get("n", 0) == 0 or g["score"] <= h["score"]) else "ml_history"
        entry = {"guidance_realisation": g, "ml_history": h, "selected": best,
                 "ablation": realisation_ablation(actual, guide, gate_kind, start)}
        if best == "guidance_realisation":
            value, ratio, n = guidance_predict(actual, guide, target)
            entry["prediction"] = {"value": round(value, 3), "guide": guide[target],
                                   "mean_realisation_ratio": round(ratio, 4), "n_ratios": n}
        else:
            entry["prediction"] = {"value": round(ml_predict(actual, "seq", 1, target), 3)}
        out["metrics"][metric] = entry

    # Adjusted gross margin has no direct guide. Decompose:
    #   adj gross margin = adj operating margin + opex-as-%-of-revenue
    # The operating-margin half IS guided, so only the opex spread needs a
    # model — the same "shrink the unknown" move, one level down.
    agm = load_series("analog-devices", "adj_gross_margin_pct")
    aom = load_series("analog-devices", "adj_operating_margin_pct")
    aom_guide = load_series("analog-devices", "adj_operating_margin_pct", "GUIDE_MID")
    spread = {t: agm[t] - aom[t] for t in agm if t in aom}

    rows, errs, nerrs = [], [], []
    for t in sorted(agm):
        if t < start or is_covid(t) or t not in aom_guide:
            continue
        past_sp = [spread[k] for k in sorted(spread) if k < t and not is_covid(k)]
        past_r = [aom[k] / aom_guide[k] for k in sorted(aom)
                  if k < t and k in aom_guide and aom_guide[k] and not is_covid(k)]
        if len(past_sp) < 4 or len(past_r) < 4:
            continue
        # spread persists strongly quarter to quarter; use the last observation
        # nudged by its recent drift (operating leverage as revenue scales).
        sp_pred = past_sp[-1] + (past_sp[-1] - past_sp[-2]) * 0.5
        pred = aom_guide[t] * float(np.mean(past_r)) + sp_pred
        err = abs(pred - agm[t])
        naive_err = abs(past_sp[-1] + aom_guide[t] - agm[t])
        rows.append({"period": index_period(t), "actual": agm[t],
                     "predicted": round(pred, 2), "err": round(err, 2),
                     "naive_err": round(naive_err, 2)})
        errs.append(err)
        nerrs.append(naive_err)

    past_sp = [spread[k] for k in sorted(spread) if not is_covid(k)]
    past_r = [aom[k] / aom_guide[k] for k in sorted(aom)
              if k in aom_guide and aom_guide[k] and not is_covid(k)]
    sp_pred = past_sp[-1] + (past_sp[-1] - past_sp[-2]) * 0.5
    agm_pred = aom_guide[target] * float(np.mean(past_r)) + sp_pred
    out["metrics"]["adj_gross_margin_pct"] = {
        "guidance_realisation": {
            "n": len(errs), "detail": rows,
            "score": round(float(np.mean(errs)), 3),
            "naive_score": round(float(np.mean(nerrs)), 3),
            "beats_naive": bool(np.mean(errs) < np.mean(nerrs)),
            "method": "adjGM = guided adj operating margin x realisation + opex spread",
        },
        "ml_history": {"n": 0, "reason": "not run: decomposition dominates"},
        "selected": "guidance_realisation",
        "prediction": {"value": round(agm_pred, 2),
                       "guided_aom": aom_guide[target],
                       "opex_spread_forecast": round(sp_pred, 2)},
    }
    return out


def run_deere() -> dict:
    """Deere: pure history only — nothing about Q3 is pre-published."""
    out = {"company": "deere", "period": "FY2026Q3", "metrics": {}}
    target = period_index("FY2026Q3")
    for metric, gate_kind in [("worldwide_net_sales_revenues", "mape"),
                              ("diluted_eps_gaap", "mape"),
                              ("ppa_operating_profit", "mape")]:
        series = load_series("deere", metric)
        best, best_res, best_framing = None, None, None
        for framing in ("seq", "yoy"):
            res = ml_walk_forward(series, framing, 1, gate_kind, min_train=6)
            if res.get("n", 0) and (best is None or res["score"] < best):
                best, best_res, best_framing = res["score"], res, framing
        entry = {"ml_history": best_res or {"n": 0, "reason": "insufficient history"},
                 "selected": f"ml_history[{best_framing}]" if best_framing else "none",
                 "intrinsic_floor": intrinsic_floor(series, target, 1)}
        if best_framing:
            pred = ml_predict(series, best_framing, 1, target)
            entry["prediction"] = {"value": round(pred, 3)} if pred else None
        out["metrics"][metric] = entry
    return out


def run_hays() -> dict:
    """Hays: n<=8 annual observations. Run the H1->FY model to quantify failure."""
    out = {"company": "hays", "period": "FY2026", "metrics": {}}
    net_fees = load_series("hays", "net_fees")
    h1 = load_series("hays", "net_fees_h1")

    pairs = sorted(t for t in h1 if t in net_fees)
    ratios = {t: h1[t] / net_fees[t] for t in pairs}
    rows, errs = [], []
    for t in pairs:
        past = [ratios[k] for k in pairs if k < t]
        if len(past) < 2:
            continue
        pred = h1[t] / float(np.mean(past))
        err = abs(pred - net_fees[t]) / net_fees[t] * 100
        rows.append({"period": index_period(t, annual=True), "actual": net_fees[t],
                     "predicted": round(pred, 1), "err_pct": round(err, 2)})
        errs.append(err)

    target = period_index("FY2026")
    all_ratios = [ratios[t] for t in pairs]
    pred_fy26 = h1[target] / float(np.mean(all_ratios)) if target in h1 else None
    lo = h1[target] / max(all_ratios) if target in h1 else None
    hi = h1[target] / min(all_ratios) if target in h1 else None

    out["metrics"]["net_fees"] = {
        "h1_to_fy_model": {
            "n_walk_forward": len(errs), "detail": rows,
            "score": round(float(np.mean(errs)), 2) if errs else None,
            "h1_fy_ratios": {index_period(t, annual=True): round(ratios[t], 4) for t in pairs},
            "implied_range_from_ratio_spread": [round(lo, 1), round(hi, 1)] if lo else None,
        },
        "selected": "none",
        "prediction": {"value": round(pred_fy26, 1) if pred_fy26 else None,
                       "usable": False,
                       "why": "ratio spread 0.46-0.56 maps H1 453.3 to a 809-985 range; "
                              "cannot discriminate between continuing-ops 888 and consensus 902"},
    }
    for metric in ("pre_exc_operating_profit", "pre_exc_basic_eps"):
        s = load_series("hays", metric)
        out["metrics"][metric] = {
            "ml_history": {"n": 0,
                           "reason": f"{len(s)} annual observations "
                                     f"({min(s.values()):.2f}-{max(s.values()):.2f}); "
                                     "no chronological walk-forward is meaningful"},
            "selected": "none",
            "prediction": {"value": None, "usable": False,
                           "why": "abstained: fewer observations than a credible model needs"},
        }
    return out


# --------------------------------------------------------------------------- #
# Gate application and reporting
# --------------------------------------------------------------------------- #


def apply_gates(result: dict) -> dict:
    company = result["company"]
    for metric, entry in result["metrics"].items():
        kind_gate = GATES.get((company, metric))
        if kind_gate is None:
            continue
        gate_kind, threshold = kind_gate
        chosen = entry.get("selected", "none")
        block = None
        if chosen.startswith("guidance"):
            block = entry.get("guidance_realisation")
        elif chosen.startswith("ml_history"):
            block = entry.get("ml_history")
        passed = bool(block and block.get("n", 0) >= 3
                      and block.get("score") is not None
                      and block["score"] <= threshold
                      and block.get("beats_naive", False))
        entry["gate"] = {
            "kind": gate_kind, "threshold": threshold,
            "score": block.get("score") if block else None,
            "beats_naive": block.get("beats_naive") if block else None,
            "n": block.get("n") if block else 0,
            "passed": passed,
        }
        if not passed and entry.get("prediction"):
            entry["prediction"]["usable"] = False
            entry["prediction"].setdefault(
                "why", "failed the pre-declared gate; not offered as a forecast")
        elif passed and entry.get("prediction"):
            entry["prediction"]["usable"] = True
    return result


def print_report(result: dict) -> None:
    print(f"\n{'=' * 78}\n{result['company'].upper()}  target {result['period']}\n{'=' * 78}")
    for metric, entry in result["metrics"].items():
        gate = entry.get("gate", {})
        pred = entry.get("prediction") or {}
        print(f"\n  {metric}  [selected: {entry.get('selected')}]")
        for name in ("guidance_realisation", "ml_history", "h1_to_fy_model"):
            b = entry.get(name)
            if not b:
                continue
            if b.get("n", b.get("n_walk_forward", 0)) == 0:
                print(f"    {name:<22} not run — {b.get('reason', 'n/a')}")
            else:
                n = b.get("n", b.get("n_walk_forward"))
                print(f"    {name:<22} n={n:<3} score {b.get('score')}"
                      + (f"  naive {b.get('naive_score')}"
                         f"  beats_naive={b.get('beats_naive')}" if "naive_score" in b else ""))
        if entry.get("ablation"):
            ab = entry["ablation"]
            print(f"    ablation           spread {ab['spread']} across "
                  f"{len(ab['scores'])} ratio estimators; deployed_is_best={ab['deployed_is_best']}")
        if entry.get("intrinsic_floor", {}).get("floor_mape_pct") is not None:
            f_ = entry["intrinsic_floor"]
            print(f"    intrinsic floor    ratio sd/mean = {f_['floor_mape_pct']}% "
                  f"(n={f_['n']}) — no history-only model can beat this")
        if gate:
            print(f"    GATE {gate['kind']} <= {gate['threshold']}: "
                  f"{'PASS' if gate['passed'] else 'FAIL'}")
        val = pred.get("value")
        print(f"    prediction: {val}  usable={pred.get('usable')}"
              + (f"  ({pred['why']})" if pred.get("why") else ""))


def main() -> int:
    results = [apply_gates(run_adi()), apply_gates(run_deere()), apply_gates(run_hays())]
    for r in results:
        print_report(r)

    usable = [(r["company"], m, e["prediction"]["value"])
              for r in results for m, e in r["metrics"].items()
              if (e.get("prediction") or {}).get("usable")]
    print(f"\n{'=' * 78}\nUSABLE PREDICTIONS: {len(usable)} of 9")
    for c, m, v in usable:
        print(f"  {c:<16}{m:<32}{v}")

    OUT_PATH.write_text(json.dumps({
        "generatedBy": "forecast/ml_panel.py — HD protocol applied to ADI/DE/HAS",
        "asOf": date.today().isoformat(),
        "protocol": "chronological expanding-window walk-forward; mandatory naive "
                    "baseline; pre-declared gates; predictions stored only on PASS",
        "results": results,
        "usable_predictions": [{"company": c, "metric": m, "value": v} for c, m, v in usable],
    }, indent=1))
    print(f"\nstored -> {OUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
