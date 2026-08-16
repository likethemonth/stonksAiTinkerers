"""Blinded LLM point-in-time replay — the driver lens's historical backtest.

The anchor and ML lenses have walk-forward histories because they are formulas:
re-run the formula at an old cutoff and you get what it would have said. The
driver lens is LLM reasoning, and replaying an LLM historically has a failure
mode the other lenses don't: **the model has already read the future.** Any
quarter inside the model's training window is a quarter whose actual it may
simply remember.

First-principles design, one layer per leak vector:

1.  VIEW ISOLATION (what the pipeline can leak). Every packet is built through
    the same extractors and publication dates as the five-year backtest: only
    rows whose original disclosure is on or before the cutoff (the day before
    the target quarter's results) are included. The Census category series uses
    a publication model (advance estimate ≈ the 16th of the following month),
    so a packet can legitimately be missing the target quarter's final month —
    exactly as a real forecaster would have been on that morning.

2.  IDENTITY BLINDING (what the model can remember). Company names, tickers,
    calendar dates and fiscal-year labels never enter the prompt. Periods are
    relative (T-1, T-2, …), months are relative (M-0, M-1, …), and every
    currency value — including the consensus strike — is multiplied by a fixed
    undisclosed per-company factor. A memorized actual is stored in absolute
    units under a company name; a scaled, unlabelled series gives recall
    nothing to index on. Percentages are left raw (they are scale-free), which
    is the residual risk: a model could in principle recognize a memorized
    growth-rate fingerprint. That risk is measured, not assumed away (layer 3).

3.  LEAKAGE AUDIT (trust but verify). Each session must disclose any identity
    guess in a mandatory `identityGuess` field, and the scorer flags
    suspiciously exact predictions (errors far below what the information in
    the packet could support) plus the in-training vs post-training error
    split. If the model were reciting memorized actuals, it would show up here
    as near-zero errors on pre-cutoff-knowledge quarters.

4.  SESSION ISOLATION (what the orchestrator can leak). Every packet is
    answered by a FRESH LLM session whose entire context is the packet text.
    The orchestrating session — which has seen the actuals — never answers
    packets itself. `scripts/run-llm-replay.sh` runs the same packets against
    any CLI model for cross-model benchmarking.

Usage:
    .venv/bin/python -m forecast.llm_replay emit    # build packets
    .venv/bin/python -m forecast.llm_replay score   # join responses + actuals
Artifacts:
    research/llm-replay/packets/<ID>.txt|.json      # blinded prompt / metadata
    research/llm-replay/responses/<ID>.json         # one per LLM session
    research/llm-replay/llm-driver-backtest.json    # scored series for the page
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from forecast.corpus import load
from forecast.extract import adi, deere, home_depot
from forecast.schema import Company, Kind, MetricObservation, Period

REPO_ROOT = Path(__file__).resolve().parent.parent
REPLAY_ROOT = REPO_ROOT / "research" / "llm-replay"
PACKETS = REPLAY_ROOT / "packets"
RESPONSES = REPLAY_ROOT / "responses"
BACKTEST_OUT = REPLAY_ROOT / "llm-driver-backtest.json"
RELIABILITY = REPO_ROOT / "research" / "polymarket-reliability.json"
CENSUS_CSV = REPO_ROOT / "forecast" / "data" / "drivers" / "fred-rsbmgesdn.csv"

EXTRACTORS = {Company.HD: home_depot.extract, Company.ADI: adi.extract,
              Company.DE: deere.extract}
TICKER = {Company.HD: "HD", Company.ADI: "ADI", Company.DE: "DE"}

#: Cutoff between "inside the predictor's training data" and after it. Used
#: only by the leakage audit to split the error series.
TRAINING_CUTOFF = date(2026, 1, 31)


@dataclass(frozen=True)
class MetricSpec:
    key: str            # real store/extractor metric key (never enters the prompt)
    alias: str          # blinded key used in the prompt and the response JSON
    label: str          # blinded description shown in the prompt
    kind: str           # "money" | "eps" | "pct"
    predict: bool       # asked for in the output JSON


@dataclass(frozen=True)
class Blind:
    company: Company
    code: str           # what the prompt calls the company
    scale: float        # undisclosed multiplier on every currency value
    metrics: tuple[MetricSpec, ...]
    n_targets: int
    guides: bool = False
    census: bool = False


#: Scale factors are arbitrary constants fixed before any packet was answered.
#: They are recorded here (and in the artifact) for auditability; rotating them
#: re-blinds the experiment for a future model whose training saw this repo.
BLINDS = [
    Blind(
        company=Company.HD, code="Company R", scale=0.7137, n_targets=8,
        census=True,
        metrics=(
            MetricSpec("net_sales", "net_sales", "quarterly revenue", "money", True),
            MetricSpec("diluted_eps_gaap", "diluted_eps_gaap", "GAAP diluted EPS", "eps", True),
            MetricSpec("comp_sales_pct", "comp_sales_pct", "y/y same-store sales growth, %", "pct", True),
            MetricSpec("adj_eps", "adj_eps", "adjusted non-GAAP diluted EPS", "eps", False),
        ),
    ),
    Blind(
        company=Company.ADI, code="Company S", scale=1.3159, n_targets=6,
        guides=True,
        metrics=(
            MetricSpec("revenue", "revenue", "quarterly revenue", "money", True),
            MetricSpec("adj_eps", "adj_eps", "adjusted non-GAAP diluted EPS", "eps", True),
            MetricSpec("adj_gross_margin_pct", "adj_gross_margin_pct", "adjusted gross margin, %", "pct", True),
            MetricSpec("adj_operating_margin_pct", "adj_operating_margin_pct", "adjusted operating margin, %", "pct", False),
        ),
    ),
    Blind(
        company=Company.DE, code="Company T", scale=0.8473, n_targets=6,
        metrics=(
            MetricSpec("worldwide_net_sales_revenues", "total_revenue", "worldwide net sales and revenues", "money", True),
            MetricSpec("diluted_eps_gaap", "diluted_eps_gaap", "GAAP diluted EPS", "eps", True),
            MetricSpec("ppa_operating_profit", "segment_a_operating_profit", "largest segment's operating profit", "money", True),
            MetricSpec("ppa_net_sales", "segment_a_net_sales", "largest segment's net sales", "money", False),
        ),
    ),
]

#: Pre-declared accuracy gates, identical to the ML panel's so the lenses are
#: directly comparable. Declared before any LLM session answered a packet.
GATES = {
    ("HD", "net_sales"): ("mape", 2.0),
    ("HD", "diluted_eps_gaap"): ("mape", 5.0),
    ("HD", "comp_sales_pct"): ("mae", 0.8),
    ("ADI", "revenue"): ("mape", 2.0),
    ("ADI", "adj_eps"): ("mape", 5.0),
    ("ADI", "adj_gross_margin_pct"): ("mae", 1.0),
    ("DE", "worldwide_net_sales_revenues"): ("mape", 2.0),
    ("DE", "diluted_eps_gaap"): ("mape", 5.0),
    ("DE", "ppa_operating_profit"): ("mape", 10.0),
}


# --------------------------------------------------------------------------- #
# Point-in-time rows
# --------------------------------------------------------------------------- #


def _rows(company: Company) -> list[MetricObservation]:
    docs = sorted(load(company), key=lambda d: (d.published_at, d.path.name))
    return EXTRACTORS[company](docs, [])


def _earliest(rows: list[MetricObservation]) -> dict[tuple[str, str, str], MetricObservation]:
    """(kind, metric, period) -> the original (earliest-published) disclosure."""
    best: dict[tuple[str, str, str], MetricObservation] = {}
    for row in rows:
        key = (row.kind.value, row.metric_key, row.period.key)
        prior = best.get(key)
        if prior is None or (row.as_of, row.source_file) < (prior.as_of, prior.source_file):
            best[key] = row
    return best


def _qidx(period: Period) -> int:
    return period.year * 4 + (period.quarter - 1)


def _targets(blind: Blind, earliest: dict) -> list[Period]:
    primary = blind.metrics[0].key
    periods = sorted(
        (row.period for (kind, metric, _), row in earliest.items()
         if kind == "ACTUAL" and metric == primary and row.period.quarter is not None),
        key=lambda p: p.sort_key,
    )
    return periods[-blind.n_targets:]


def _cutoff(target: Period, earliest: dict) -> date:
    """Day before the target quarter's first disclosure of ANY actual metric."""
    dates = [row.as_of for (kind, _, pkey), row in earliest.items()
             if kind == "ACTUAL" and pkey == target.key]
    return min(dates) - timedelta(days=1)


# --------------------------------------------------------------------------- #
# Census category series (HD only)
# --------------------------------------------------------------------------- #


def _census_months() -> list[tuple[int, int, float]]:
    """(year, month, value) from the frozen FRED CSV."""
    out = []
    with CENSUS_CSV.open() as fh:
        for row in csv.DictReader(fh):
            d = date.fromisoformat(row["observation_date"])
            out.append((d.year, d.month, float(row["RSBMGESDN"])))
    return out


def _census_pub(year: int, month: int) -> date:
    """Publication model: the advance estimate lands ~the 16th of month+1."""
    if month == 12:
        return date(year + 1, 1, 16)
    return date(year, month + 1, 16)


def _hd_quarter_last_month(period: Period) -> tuple[int, int]:
    """(year, month) of the last calendar month in an HD fiscal quarter."""
    # HD FY starts in February of the label year; Qq ends 3q months later.
    month0 = 2 + 3 * period.quarter - 1  # Apr, Jul, Oct, Jan(+1)
    year, month = period.year, month0
    if month > 12:
        year, month = year + 1, month - 12
    return year, month


# --------------------------------------------------------------------------- #
# Prompt assembly
# --------------------------------------------------------------------------- #


def _scaled(value: float, kind: str, scale: float) -> float:
    if kind == "pct":
        return round(value, 2)
    return round(value * scale, 3 if kind == "eps" else 1)


def _market_strikes() -> dict[tuple[str, str], dict]:
    """(ticker, period) -> market row from the Polymarket reliability artifact."""
    if not RELIABILITY.exists():
        return {}
    data = json.loads(RELIABILITY.read_text())
    out = {}
    for ticker, block in data["companies"].items():
        for row in block["rows"]:
            out[(ticker, row["period"])] = {**row, "basis": block["basis"]}
    return out


def build_packet(blind: Blind, target: Period, earliest: dict,
                 strikes: dict) -> dict:
    cutoff = _cutoff(target, earliest)
    ticker = TICKER[blind.company]
    tq = _qidx(target)
    keys = {m.key for m in blind.metrics}
    kinds = {m.key: m.kind for m in blind.metrics}
    sources: dict[str, str] = {}

    # -- quarterly history --------------------------------------------------
    history: dict[int, dict[str, float]] = {}
    for (kind, metric, _), row in earliest.items():
        if (kind != "ACTUAL" or metric not in keys or row.period.quarter is None
                or row.as_of > cutoff or row.period.sort_key >= target.sort_key):
            continue
        history.setdefault(_qidx(row.period), {})[metric] = row.value
        sources[row.source_file] = row.as_of.isoformat()
    hist_lines = []
    for qi in sorted(history):
        rel = tq - qi
        pos = qi % 4 + 1
        vals = ", ".join(
            f"{m.alias}={_scaled(history[qi][m.key], m.kind, blind.scale)}"
            for m in blind.metrics if m.key in history[qi])
        hist_lines.append(f"T-{rel} (Q{pos}): {vals}")
    # Early corpus quarters are comparative-sourced and sparse; the last seven
    # fiscal years carry all the signal and keep the packet compact.
    hist_lines = hist_lines[-28:]

    # -- guidance (ADI) ------------------------------------------------------
    guide_lines = []
    if blind.guides:
        guided: dict[tuple[int, str], dict[str, float]] = {}
        for (kind, metric, _), row in earliest.items():
            if (not kind.startswith("GUIDE") or row.as_of > cutoff
                    or row.period.quarter is None
                    or row.period.sort_key > target.sort_key):
                continue
            guided.setdefault((_qidx(row.period), metric), {})[kind] = row.value
            sources[row.source_file] = row.as_of.isoformat()
        alias_of = {m.key: m.alias for m in blind.metrics}
        for (qi, metric), g in sorted(guided.items()):
            rel = tq - qi
            label = "T (the target quarter)" if rel == 0 else f"T-{rel}"
            metric_alias = alias_of.get(metric, metric)
            kind = kinds.get(metric, "pct" if metric.endswith("pct") else "money")
            if metric in ("revenue",):
                kind = "money"
            if metric == "adj_eps":
                kind = "eps"
            mid = g.get("GUIDE_MID")
            lo, hi = g.get("GUIDE_LOW"), g.get("GUIDE_HIGH")
            parts = []
            if mid is not None:
                parts.append(f"mid {_scaled(mid, kind, blind.scale)}")
            if lo is not None and hi is not None:
                parts.append(f"range {_scaled(lo, kind, blind.scale)}"
                             f"–{_scaled(hi, kind, blind.scale)}")
            guide_lines.append(f"{label} {metric_alias} guide: {', '.join(parts)}")

    # -- census category months (HD) -----------------------------------------
    census_lines: list[str] = []
    census_note = ""
    if blind.census:
        ly, lm = _hd_quarter_last_month(target)
        last_idx = ly * 12 + (lm - 1)
        months = [(y, m, v) for y, m, v in _census_months()
                  if _census_pub(y, m) <= cutoff and y * 12 + (m - 1) <= last_idx]
        for y, m, v in months[-42:]:
            rel = last_idx - (y * 12 + (m - 1))
            census_lines.append(f"M-{rel}: {round(v * blind.scale, 1)}")
        published_last = months[-1][0] * 12 + (months[-1][1] - 1) if months else None
        missing = last_idx - published_last if published_last is not None else 3
        census_note = (
            "Months M-2, M-1, M-0 constitute the target quarter T. "
            + ("All three are published." if missing <= 0 else
               f"The final {missing} month(s) of T are not yet published — extrapolate them.")
            + " Each earlier fiscal quarter T-k spans months M-(3k+2)..M-(3k).")
        sources[str(CENSUS_CSV.relative_to(REPO_ROOT))
                + " (US Census monthly category retail, FRED)"] = "monthly, +16d lag"

    # -- market strike -------------------------------------------------------
    market = strikes.get((ticker, target.key))
    strike_block = ""
    if market:
        basis = market["basis"]
        strike_scaled = round(market["strike"] * blind.scale, 3)
        strike_block = (
            f"\nCONSENSUS STRIKE\nAnalyst consensus for the target quarter's {basis}"
            f" (frozen ~2 weeks before results, same scaled units): {strike_scaled}.\n"
            f"Also output pBeat = your probability that the reported {basis} exceeds"
            f" this strike.")
        sources[f"polymarket strike (scaled), {market['slug']}"] = market["reportDate"]

    predict = [m for m in blind.metrics if m.predict]
    predict_lines = "\n".join(f"- {m.alias}: {m.label}"
                              + (" — scaled currency units" if m.kind != "pct" else "")
                              for m in predict)
    example = ", ".join(f'"{m.alias}": <number>' for m in predict)

    method_hint = {
        Company.HD: ("Use the category months inside T (they are the demand driver for the "
                     "quarter being predicted), the company's share of the category implied "
                     "by recent quarters, and the seasonal structure. Calibrate the "
                     "category-to-company mapping on the most recent quarters where both "
                     "are known."),
        Company.ADI: ("The guidance for T is the anchor. Calibrate how actuals have "
                      "historically realised against the guide midpoints (the beat/miss "
                      "cadence) and apply that calibration. Margins: use guided operating "
                      "margin plus the observed gross-vs-operating spread."),
        Company.DE: ("No forward guidance is available. Use seasonal structure (same "
                     "fiscal quarter in prior years), the trailing trend in y/y growth, "
                     "and the segment's operating leverage visible in the history."),
    }[blind.company]

    prompt = f"""You are an expert earnings nowcaster. Forecast one fiscal quarter of one anonymized company using ONLY the data in this message.

ANONYMIZATION AND RULES
- The company's identity, all calendar dates and fiscal-year labels have been removed. Quarters are labelled relative to the target: T is the target quarter, T-1 the one before it. Q1..Q4 mark each quarter's position within the fiscal year (seasonality is real).
- Every currency value has been multiplied by ONE fixed undisclosed constant. Growth rates, margins, seasonality and all cross-metric relationships are unchanged. Percent metrics are not scaled.
- The target quarter T (position Q{target.quarter}) has ENDED, but its results are NOT yet published. Everything below was published before the results.
- Do not use knowledge of any real-world company or period. If you believe you recognize the company or the period anyway, you MUST disclose that in "identityGuess" — and still derive every number only from the data below.
- Do not use any tools, web access, or external data. Work only from this message.

PREDICT (for quarter T, position Q{target.quarter})
{predict_lines}
{strike_block}

DATA 1 — QUARTERLY ACTUALS AS ORIGINALLY REPORTED (oldest first)
{chr(10).join(hist_lines)}
"""
    if guide_lines:
        prompt += f"""
DATA 2 — MANAGEMENT GUIDANCE (each issued one quarter before the quarter it guides; same scaled units; percent guides unscaled)
{chr(10).join(guide_lines)}
"""
    if census_lines:
        prompt += f"""
DATA 2 — MONTHLY RETAIL SALES OF THE CATEGORY THE COMPANY SELLS INTO (same scaled units, US census-style series; M-0 is the last month of quarter T)
{census_note}
{chr(10).join(census_lines)}
"""
    prompt += f"""
METHOD
{method_hint}
State your derivation chain briefly. Be a forecaster, not a curve-fitter: prefer the freshest information.

OUTPUT — reply with EXACTLY one JSON object and nothing else (no code fences):
{{"predictions": {{{example}}}, "pBeat": {"<number between 0 and 1>" if market else "null"}, "reasoning": "<the chain, max 150 words>", "identityGuess": null}}
"""

    # The packet is a time-scoped "internet snapshot for LLMs": the worldview
    # manifest records exactly how much of the frozen corpus was visible at
    # the cutoff, so every packet is auditable as a view of the world.
    visible = load(blind.company, as_of=cutoff)
    total = load(blind.company)
    packet_id = f"{ticker}-{target.key}"
    return {
        "id": packet_id,
        "prompt": prompt,
        "private": {
            "company": blind.company.value,
            "ticker": ticker,
            "code": blind.code,
            "period": target.key,
            "targetQuarterPosition": target.quarter,
            "cutoff": cutoff.isoformat(),
            "scale": blind.scale,
            "worldview": {
                "rule": "only rows originally disclosed on or before the cutoff; "
                        "census months lagged by a +16-day publication model",
                "corpusDocumentsVisible": len(visible),
                "corpusDocumentsExcluded": len(total) - len(visible),
                "newestVisibleDocument": (visible[0].rel_path if visible else None),
            },
            "market": {k: market[k] for k in ("slug", "strike", "reportDate")} if market else None,
            "historyQuarters": len(hist_lines),
            "censusMonths": len(census_lines),
            "sources": [{"source": s, "published": p} for s, p in sorted(sources.items())],
        },
    }


# --------------------------------------------------------------------------- #
# emit / score
# --------------------------------------------------------------------------- #


def emit() -> int:
    PACKETS.mkdir(parents=True, exist_ok=True)
    RESPONSES.mkdir(parents=True, exist_ok=True)
    strikes = _market_strikes()
    index = []
    for blind in BLINDS:
        earliest = _earliest(_rows(blind.company))
        for target in _targets(blind, earliest):
            packet = build_packet(blind, target, earliest, strikes)
            (PACKETS / f"{packet['id']}.json").write_text(
                json.dumps(packet, indent=1) + "\n")
            (PACKETS / f"{packet['id']}.txt").write_text(packet["prompt"])
            index.append({
                "id": packet["id"], **{k: packet["private"][k] for k in
                                       ("period", "cutoff", "historyQuarters")},
                "hasMarket": packet["private"]["market"] is not None,
            })
            print(f"  {packet['id']:<16} cutoff {packet['private']['cutoff']}  "
                  f"history {packet['private']['historyQuarters']:>2}q  "
                  f"market {'yes' if packet['private']['market'] else 'no'}")
    (REPLAY_ROOT / "INDEX.json").write_text(json.dumps(index, indent=1) + "\n")
    print(f"{len(index)} packets -> {PACKETS.relative_to(REPO_ROOT)}")
    return 0


def _parse_response(path: Path) -> dict | None:
    raw = path.read_text().strip()
    if raw.startswith("```"):
        raw = raw.strip("`\n")
        raw = raw[raw.index("{"):]
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None


def score() -> int:
    strikes = _market_strikes()
    artifact_companies: dict[str, dict] = {}
    all_guesses = []
    suspicious = []

    for blind in BLINDS:
        ticker = TICKER[blind.company]
        earliest = _earliest(_rows(blind.company))
        actual = {(m, pkey): row.value
                  for (kind, m, pkey), row in earliest.items() if kind == "ACTUAL"}
        metric_rows: dict[str, list[dict]] = {m.key: [] for m in blind.metrics if m.predict}
        pbeat_rows: list[dict] = []

        for target in _targets(blind, earliest):
            pid = f"{ticker}-{target.key}"
            packet_path = PACKETS / f"{pid}.json"
            resp_path = RESPONSES / f"{pid}.json"
            if not resp_path.exists():
                print(f"  missing response {pid}", file=sys.stderr)
                continue
            packet = json.loads(packet_path.read_text())
            resp = _parse_response(resp_path)
            if resp is None:
                print(f"  unparseable response {pid}", file=sys.stderr)
                continue
            if resp.get("identityGuess"):
                all_guesses.append({"id": pid, "guess": resp["identityGuess"]})

            for m in blind.metrics:
                preds = resp.get("predictions") or {}
                if not m.predict or (m.alias not in preds and m.key not in preds):
                    continue
                pred_scaled = float(preds.get(m.alias, preds.get(m.key)))
                pred = pred_scaled if m.kind == "pct" else pred_scaled / blind.scale
                act = actual.get((m.key, target.key))
                if act is None:
                    continue
                if m.kind == "pct":
                    err = abs(pred - act)
                else:
                    err = abs(pred - act) / abs(act) * 100.0
                prior = actual.get((m.key, Period(year=target.year - 1,
                                                  quarter=target.quarter).key))
                naive_err = None
                if prior is not None:
                    naive_err = (abs(prior - act) if m.kind == "pct"
                                 else abs(prior - act) / abs(act) * 100.0)
                row = {
                    "period": target.key,
                    "cutoff": packet["private"]["cutoff"],
                    "actual": round(act, 4),
                    "predicted": round(pred, 4),
                    "err": round(err, 2),
                    "naiveErr": round(naive_err, 2) if naive_err is not None else None,
                    "inTraining": date.fromisoformat(
                        packet["private"]["cutoff"]) <= TRAINING_CUTOFF,
                }
                metric_rows[m.key].append(row)
                if err < (0.02 if m.kind == "pct" else 0.05):
                    suspicious.append({"id": pid, "metric": m.key, "err": row["err"]})

            market = packet["private"].get("market")
            p = resp.get("pBeat")
            if market and isinstance(p, (int, float)):
                mrow = strikes.get((ticker, target.key), {})
                outcome = mrow.get("outcome")
                pbeat_rows.append({
                    "period": target.key,
                    "inTraining": date.fromisoformat(
                        packet["private"]["cutoff"]) <= TRAINING_CUTOFF,
                    "strike": market["strike"],
                    "pLLM": round(float(p), 3),
                    "pMarketDayBefore": mrow.get("pDayBefore"),
                    "outcome": outcome,
                    "brierLLM": (round((float(p) - outcome) ** 2, 4)
                                 if outcome is not None else None),
                    "brierMarket": mrow.get("brierDayBefore"),
                })

        metrics_block = {}
        for m in blind.metrics:
            if not m.predict:
                continue
            rows = metric_rows[m.key]
            kind, threshold = GATES[(ticker, m.key)]
            errs = [r["err"] for r in rows]
            naive = [r["naiveErr"] for r in rows if r["naiveErr"] is not None]
            # In-training quarters are recall-prone when the session identified
            # the company (the audit shows several did); post-training quarters
            # cannot be memorized, so their score is reported separately.
            post = [r["err"] for r in rows if not r["inTraining"]]
            score_val = round(sum(errs) / len(errs), 2) if errs else None
            naive_val = round(sum(naive) / len(naive), 2) if naive else None
            metrics_block[m.key] = {
                "rows": rows,
                "gate": {
                    "kind": kind,
                    "score": score_val,
                    "threshold": threshold,
                    "n": len(rows),
                    "naive": naive_val,
                    "postScore": round(sum(post) / len(post), 2) if post else None,
                    "postN": len(post),
                    "beats_naive": (score_val < naive_val
                                    if score_val is not None and naive_val is not None
                                    else None),
                    "passed": score_val is not None and score_val <= threshold,
                },
            }
        scored_p = [r for r in pbeat_rows if r["brierLLM"] is not None]
        post_p = [r for r in scored_p if not r["inTraining"]]

        def _mean(rows, key):
            vals = [r[key] for r in rows if r.get(key) is not None]
            return round(sum(vals) / len(vals), 4) if vals else None

        artifact_companies[ticker] = {
            "scale": blind.scale,
            "metrics": metrics_block,
            "pBeat": {
                "rows": pbeat_rows,
                "brierLLM": _mean(scored_p, "brierLLM"),
                "brierMarket": _mean(scored_p, "brierMarket"),
                "brierLLMPost": _mean(post_p, "brierLLM"),
                "brierMarketPost": _mean(post_p, "brierMarket"),
                "nPost": len(post_p),
            },
        }

    in_training, post = [], []
    for block in artifact_companies.values():
        for m in block["metrics"].values():
            for r in m["rows"]:
                (in_training if r["inTraining"] else post).append(r["err"])
    payload = {
        "meta": {
            "title": "Blinded LLM point-in-time replay (driver-lens backtest)",
            "generated": date.today().isoformat(),
            "predictor": "one fresh claude-fable-5 session per packet; context = packet text only",
            "blinding": "no names/dates; relative periods; currency scaled by an undisclosed per-company constant",
            "gates": "identical to the ML panel's pre-declared gates",
            "packets": str(PACKETS.relative_to(REPO_ROOT)),
            "responses": str(RESPONSES.relative_to(REPO_ROOT)),
        },
        "leakageAudit": {
            "identityGuesses": all_guesses,
            "suspiciouslyExact": suspicious,
            "inTrainingMeanErr": (round(sum(in_training) / len(in_training), 2)
                                  if in_training else None),
            "postTrainingMeanErr": (round(sum(post) / len(post), 2) if post else None),
            "note": "Identity blinding held for magnitude lookup only where the "
                    "fingerprint was weak. Sessions recognized HD and DE from "
                    "COVID-era comp/seasonal fingerprints, and several in-training "
                    "quarters show recall-level (near-zero) errors despite the "
                    "instruction not to use memory. Verdict: treat in-training "
                    "quarters as an upper bound (recall-contaminated); quarters "
                    "whose cutoff postdates the predictor's training window are "
                    "leak-free by construction and carry the honest signal "
                    "(gate.postScore / pBeat.brierLLMPost).",
        },
        "companies": artifact_companies,
    }
    BACKTEST_OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {BACKTEST_OUT.relative_to(REPO_ROOT)}")
    for ticker, block in artifact_companies.items():
        for key, m in block["metrics"].items():
            g = m["gate"]
            print(f"  {ticker:<4}{key:<30}{g['kind']} {g['score']} vs gate "
                  f"{g['threshold']} (naive {g['naive']}, n={g['n']}) "
                  f"{'PASS' if g['passed'] else 'fail'}")
        pb = block["pBeat"]
        if pb["rows"]:
            print(f"  {ticker:<4}{'P(beat) Brier':<30}LLM {pb['brierLLM']} vs "
                  f"market {pb['brierMarket']}")
    return 0


def main(argv: list[str]) -> int:
    if "emit" in argv:
        return emit()
    if "score" in argv:
        return score()
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
