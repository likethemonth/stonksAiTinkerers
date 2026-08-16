"""Four-lens ensemble — anchor, driver, ML and market combined by measured error.

The architecture diagram has carried an amber warning since the submission:
"measured skill should set engine reliability — not wired, reliability is
still a constant". This module wires it, as a companion output: for every
challenge metric, each lens that offers a value is weighted by the inverse of
its measured backtest error, and the weighted mean is the ensemble figure.
The twelve SUBMITTED numbers are locked and unchanged; the ensemble is the
same evidence combined by measured skill instead of by a constant.

The weighting rule, declared once:

    weight_i ∝ 1 / err_i          (normalized within each metric)

where err_i is, in order of preference:
    validated   the lens's own walk-forward / replay error for that exact
                stock x metric (ML gate score, blinded-LLM-replay score,
                anchor guidance-calibration MAPE);
    market-implied  for the market lens, the MAPE of the day-before implied
                mean against the reported EPS across the resolved beat-markets;
    assumed-at-gate  a lens with a value but no validated history is assumed
                to perform exactly at the metric's pre-declared gate. This is
                deliberately generous to nobody: the gate was set at "what
                would be competitive", so an unvalidated lens neither
                dominates nor vanishes.

Exclusions are structural, not tuned: a lens that abstained (ML under a
failed gate) contributes nothing, and the Hays driver lens is excluded
because it declares itself a carry of the anchor reconstruction — including
it would double-count one lens's information.

Errors mix % (money metrics) and pp (percent metrics), but weights only ever
compare errors within one metric, where the unit is shared.

Usage:
    .venv/bin/python -m forecast.ensemble            # write the artifact
    .venv/bin/python -m forecast.ensemble --inject   # + refresh index.html 03b
Artifact: research/lens-ensemble.json
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

from forecast.build_predictions_page import LLM_METRIC_BY_LABEL, build_model
from forecast.polymarket import SURPRISE_SIGMA, norm_ppf
from forecast.schema import Company

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "research" / "lens-ensemble.json"
INDEX_HTML = REPO_ROOT / "architecture" / "index.html"
RELIABILITY = REPO_ROOT / "research" / "polymarket-reliability.json"
LLM_BACKTEST = REPO_ROOT / "research" / "llm-replay" / "llm-driver-backtest.json"

START = "<!-- ensemble:start -->"
END = "<!-- ensemble:end -->"

#: Pre-declared gates reused as the assumed error for unvalidated lenses.
#: HD/ADI/DE values mirror forecast.llm_replay.GATES; Hays mirrors
#: forecast.ml_panel.GATES. Units: % for money metrics, pp for percent ones.
ASSUMED_AT_GATE = {
    ("HD", "Net sales"): 2.0,
    ("HD", "Adjusted diluted EPS"): 5.0,
    ("HD", "Comparable sales, total company"): 0.8,
    ("ADI", "Revenue"): 2.0,
    ("ADI", "Adjusted diluted EPS"): 5.0,
    ("ADI", "Adjusted gross margin"): 1.0,
    ("DE", "Worldwide net sales and revenues"): 2.0,
    ("DE", "Diluted EPS (GAAP)"): 5.0,
    ("DE", "Production & Precision Ag operating profit"): 10.0,
    ("Hays", "Net fees"): 2.0,
    ("Hays", "Pre-exceptional operating profit"): 10.0,
    ("Hays", "Pre-exceptional basic EPS"): 10.0,
}

#: Which metric each ticker's beat-market prices (the market lens's only value).
MARKET_EPS_LABEL = {
    "HD": "Adjusted diluted EPS",
    "ADI": "Adjusted diluted EPS",
    "DE": "Diluted EPS (GAAP)",
}
MARKET_SIGMA_KEY = {
    "HD": (Company.HD, "adj_eps"),
    "ADI": (Company.ADI, "adj_eps"),
    "DE": (Company.DE, "gaap_eps"),
}

#: (ticker, method) pairs excluded because the lens declares itself a carry
#: of another lens — including it would double-count one vote.
CARRY_EXCLUSIONS = {("Hays", "driver")}


def _market_implied_mape() -> dict[str, dict]:
    """Per ticker: MAPE of the day-before implied mean vs the reported EPS."""
    if not RELIABILITY.exists():
        return {}
    rel = json.loads(RELIABILITY.read_text())
    out = {}
    for ticker, block in rel["companies"].items():
        _, mid, _ = SURPRISE_SIGMA[MARKET_SIGMA_KEY[ticker]]
        errs = []
        for row in block["rows"]:
            p, actual = row.get("pDayBefore"), row.get("actualEps")
            if row.get("outcome") is None or p is None or actual is None:
                continue
            implied = row["strike"] + mid * norm_ppf(min(0.98, max(0.02, p)))
            errs.append(abs(implied - actual) / abs(actual) * 100.0)
        if errs:
            out[ticker] = {"err": round(sum(errs) / len(errs), 2), "n": len(errs)}
    return out


def _series_mape(metric: dict) -> float | None:
    errs = [r["err"] for r in metric.get("series") or [] if r.get("err") is not None]
    return round(sum(errs) / len(errs), 2) if errs else None


def build_ensemble() -> dict:
    model = build_model()
    market_err = _market_implied_mape()
    rows = []

    for ticker, block in model.items():
        anchor_metrics = block["methods"]["anchor"]["metrics"]
        for am in anchor_metrics:
            label, unit = am["label"], am["unit"]
            lenses = []
            for method in ("anchor", "driver", "ml", "market"):
                if (ticker, method) in CARRY_EXCLUSIONS:
                    continue
                metric = next((m for m in block["methods"][method].get("metrics", [])
                               if m["label"] == label), None)
                if metric is None or metric.get("value") is None:
                    continue
                value = metric["value"]
                gate = metric.get("gate") or {}
                if method == "market":
                    m_err = market_err.get(ticker)
                    if m_err is None:
                        continue
                    err, basis = m_err["err"], f"market-implied (n={m_err['n']})"
                elif gate.get("score") is not None:
                    err, basis = gate["score"], f"validated (n={gate.get('n')})"
                elif method == "anchor" and _series_mape(metric) is not None:
                    err, basis = _series_mape(metric), "validated (calibration series)"
                else:
                    err = ASSUMED_AT_GATE[(ticker, label)]
                    basis = "assumed-at-gate"
                lenses.append({"lens": method, "value": value,
                               "err": err, "errBasis": basis})
            if not lenses:
                continue
            total = sum(1.0 / item["err"] for item in lenses)
            for item in lenses:
                item["weight"] = round((1.0 / item["err"]) / total, 4)
            final = sum(item["weight"] * item["value"] for item in lenses)
            rows.append({
                "ticker": ticker,
                "label": label,
                "unit": unit,
                "final": round(final, 2),
                "expectedErr": round(1.0 / total, 2),
                "submitted": am.get("final"),
                "lenses": lenses,
            })

    return {
        "meta": {
            "title": "Four-lens ensemble, weighted by measured error",
            "generated": date.today().isoformat(),
            "rule": "weight ∝ 1/err within each metric; err = validated backtest "
                    "error where one exists, the market's implied-mean MAPE for "
                    "the market lens, and the pre-declared gate for unvalidated "
                    "lenses; abstentions and declared carries contribute nothing",
            "note": "Companion output. The twelve submitted numbers are locked "
                    "and produced by the constant-reliability meta-forecaster "
                    "documented in the audit; this is the same evidence "
                    "re-combined by measured skill.",
        },
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# index.html injection
# --------------------------------------------------------------------------- #


def _fmt(value: float) -> str:
    return f"{value:,.2f}"


def _section_html(payload: dict) -> str:
    body = []
    last_ticker = None
    for row in payload["rows"]:
        cells = {item["lens"]: item for item in row["lenses"]}
        lens_tds = []
        for method, name in (("anchor", "Anchor"), ("driver", "Driver"),
                             ("ml", "ML"), ("market", "Market")):
            item = cells.get(method)
            if item is None:
                reason = ("carried" if (row["ticker"], method) in CARRY_EXCLUSIONS
                          else "abstained")
                lens_tds.append(f'<td class="num muted">{reason}</td>')
                continue
            unit = "pp" if row["unit"] in ("%",) else "%"
            lens_tds.append(
                f'<td class="num">{_fmt(item["value"])}'
                f'<span class="weights"><br>w {item["weight"]*100:.0f}% · '
                f'err {item["err"]}{unit}</span></td>')
        cls = ' class="company-row"' if row["ticker"] != last_ticker else ""
        last_ticker = row["ticker"]
        label = row["label"].replace("&", "&amp;")
        body.append(
            f'<tr{cls}><td>{row["ticker"]}</td><td>{label}</td>'
            + "".join(lens_tds)
            + f'<td class="num"><strong>{_fmt(row["final"])}</strong></td>'
            + f'<td class="num">{_fmt(row["submitted"]) if row["submitted"] is not None else "—"}</td></tr>')

    return f"""{START}
    <section id="ensemble">
      <div class="shell section-grid">
        <div class="section-number">03b / Ensemble</div>
        <div>
          <h2>The four lenses, combined by measured error.</h2>
          <p class="muted">The amber note in the diagrams — measured skill should set the weights — is
          now wired, as a companion output. Each lens is weighted by the inverse of its own backtested
          error for that exact metric: the ML gate score, the blinded LLM replay score, the anchor's
          guidance-calibration error, and the market's implied-mean miss across its resolved
          beat-markets. A lens with a value but no validated history is assumed to perform exactly at
          the metric's pre-declared gate; a lens that abstained, or that declares itself a carry of
          another lens (the Hays driver), contributes nothing. The submitted figures are locked and
          unchanged — the last column is there to show how far measured-skill weighting moves each
          number. Generated by <code>forecast/ensemble.py</code>; machine-readable in
          <code>research/lens-ensemble.json</code>.</p>
          <div class="table-wrap" role="region" aria-label="Four-lens ensemble" tabindex="0">
            <table>
              <thead><tr><th>Company</th><th>Metric</th><th>Anchor</th><th>Driver (blinded LLM)</th>
                <th>ML</th><th>Market</th><th>Ensemble</th><th>Submitted</th></tr></thead>
              <tbody>
                {chr(10).join(body)}
              </tbody>
            </table>
          </div>
          <p class="note">Weights are 1/err normalized within each row · err units follow the metric
          (% for money, pp for percent metrics) · validated errors from
          <a href="predictions.html">the explorer's</a> walk-forward histories</p>
        </div>
      </div>
    </section>
    {END}"""


def inject(payload: dict) -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    section = _section_html(payload)
    if START in html:
        html = re.sub(re.escape(START) + r".*?" + re.escape(END), section,
                      html, flags=re.DOTALL)
    else:
        anchor = '<section id="evidence">'
        html = html.replace(anchor, section + "\n\n    " + anchor, 1)

    # Flip the two amber "not wired" callouts: the wiring now exists (03b).
    html = html.replace(
        '<text class="d-warn" x="800" y="620">MEASURED SKILL SHOULD SET ENGINE RELIABILITY</text>\n'
        '                <text class="d-warn" x="800" y="638">NOT WIRED &#8212; RELIABILITY IS STILL A CONSTANT</text>\n'
        '                <text class="d-mono" x="800" y="662">See 05 / Validation for the per-engine breakdown</text>',
        '<text class="d-good" x="800" y="620">MEASURED SKILL NOW SETS THE FOUR-LENS ENSEMBLE (03B)</text>\n'
        '                <text class="d-mono" x="800" y="638">WEIGHT &#8733; 1/BACKTESTED ERROR &#183; SUBMITTED FIGURES UNCHANGED</text>\n'
        '                <text class="d-mono" x="800" y="662">See 05 / Validation for the per-engine breakdown</text>')
    html = html.replace(
        '<text class="d-warn" x="700" y="256">MEASURED SKILL SHOULD SET ENGINE RELIABILITY &#8212; NOT WIRED, RELIABILITY IS STILL A CONSTANT</text>',
        '<text class="d-good" x="700" y="256">MEASURED SKILL NOW SETS THE FOUR-LENS ENSEMBLE WEIGHTS (03B) &#8212; THE SUBMITTED RUN KEPT ITS DOCUMENTED CONSTANT</text>')
    INDEX_HTML.write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    payload = build_ensemble()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)} ({len(payload['rows'])} metrics)")
    for row in payload["rows"]:
        mix = " · ".join(f"{i['lens']} {i['weight']*100:.0f}%" for i in row["lenses"])
        print(f"  {row['ticker']:<5}{row['label']:<42}{row['final']:>12,.2f}  ({mix})")
    if "--inject" in argv:
        inject(payload)
        print(f"injected 03b into {INDEX_HTML.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
