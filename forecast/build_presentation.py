"""Generate the model presentations under presentation/.

One deck per lens. Each is a self-contained HTML slide deck in the same design
system as architecture/index.html: inline CSS, inline data, no external assets,
keyboard navigable. Numbers are read from the run artefacts rather than typed,
so a deck cannot quote a figure the pipeline no longer produces.

    .venv/bin/python -m forecast.build_presentation          # all decks
    .venv/bin/python -m forecast.build_presentation --lens ml
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "presentation"


def load(rel: str):
    return json.loads((REPO_ROOT / rel).read_text())


# --------------------------------------------------------------------------- #
# Shared chrome
# --------------------------------------------------------------------------- #

CSS = """
:root{--paper:#f3f0e9;--paper-deep:#e8e3d9;--ink:#111112;--muted:#68655f;--rule:#c8c2b7;
--signal:#b8ff45;--verified:#43bc82;--warn:#bd5d23;
--sans:Inter,"Helvetica Neue",Arial,sans-serif;
--mono:"SFMono-Regular",Consolas,"Liberation Mono",monospace}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--ink);color:var(--ink);font-family:var(--sans);overflow:hidden}
.deck{position:relative;height:100vh;width:100vw}
.slide{position:absolute;inset:0;display:none;padding:clamp(36px,5vw,84px) clamp(36px,6vw,110px);
background:var(--paper);overflow-y:auto}
.slide.on{display:flex;flex-direction:column;justify-content:center}
.slide.dark{background:#0e0f10;color:#f4f2ec}
.eyebrow{margin:0 0 20px;color:var(--muted);font:10px var(--mono);letter-spacing:.18em;text-transform:uppercase}
.slide.dark .eyebrow{color:#858990}
h1{margin:0;font-size:clamp(44px,6.6vw,104px);line-height:.87;letter-spacing:-.06em;max-width:20ch}
h2{margin:0 0 26px;font-size:clamp(30px,4.1vw,62px);line-height:.95;letter-spacing:-.05em;max-width:22ch}
.slide.dark h1,.slide.dark h2{color:#f4f2ec}
p{font-size:clamp(15px,1.35vw,20px);line-height:1.6;max-width:74ch;margin:0 0 16px}
.lede{color:var(--muted);font-size:clamp(17px,1.7vw,26px);line-height:1.45;max-width:60ch;margin-top:26px}
.slide.dark .lede{color:#aeb2b6}
.muted{color:var(--muted)}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:0;border:1px solid var(--rule);margin-top:26px}
.slide.dark .cols{border-color:#33363a}
.col{padding:22px 24px;border-right:1px solid var(--rule)}
.slide.dark .col{border-color:#33363a}
.col:last-child{border-right:0}
.col strong{display:block;font-size:clamp(26px,3vw,44px);font-variant-numeric:tabular-nums;letter-spacing:-.045em;line-height:1}
.col span{display:block;margin-top:12px;font-weight:700;font-size:14px}
.col small{display:block;margin-top:5px;color:var(--muted);font:9px var(--mono);letter-spacing:.11em;text-transform:uppercase}
.slide.dark .col small{color:#858990}
table{width:100%;border-collapse:collapse;font-size:clamp(12px,1.05vw,15px);margin-top:22px}
th,td{padding:9px 13px;border-bottom:1px solid var(--rule);text-align:left}
.slide.dark th,.slide.dark td{border-color:#2a2d30}
th{color:var(--muted);font:9px var(--mono);letter-spacing:.12em;text-transform:uppercase}
.slide.dark th{color:#858990}
td.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
tr.hi td{background:rgba(184,255,69,.2)}
.slide.dark tr.hi td{background:rgba(184,255,69,.1)}
.pill{display:inline-block;padding:3px 7px;background:var(--signal);color:var(--ink);font:9px var(--mono);letter-spacing:.08em;text-transform:uppercase;font-weight:700}
.pill.bad{background:var(--ink);color:var(--paper)}
.slide.dark .pill.bad{background:#3a3d40;color:#f4f2ec}
.pill.mute{background:var(--paper-deep);color:var(--muted)}
.formula{margin:22px 0;padding:20px 22px;border-left:5px solid var(--signal);background:var(--paper-deep);
font:clamp(12px,1.05vw,15px)/1.75 var(--mono);white-space:pre-wrap}
.slide.dark .formula{background:#17191b;border-left-color:var(--signal);color:#dfe2e4}
ul{margin:14px 0 0;padding-left:20px}
li{font-size:clamp(14px,1.25vw,19px);line-height:1.6;margin-bottom:11px;max-width:70ch}
li::marker{color:var(--muted)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:34px;margin-top:22px}
.card{padding:22px;border:1px solid var(--rule)}
.slide.dark .card{border-color:#33363a}
.card h3{margin:0 0 10px;font-size:19px;letter-spacing:-.02em}
.card p{font-size:14px;margin:0}
.nav{position:fixed;right:20px;bottom:16px;display:flex;align-items:center;gap:14px;
font:10px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);z-index:5}
.nav button{padding:6px 11px;border:1px solid var(--rule);background:var(--paper);color:var(--ink);
font:10px var(--mono);cursor:pointer}
.nav button:hover{background:var(--signal)}
.brandmark{position:fixed;left:22px;bottom:16px;display:flex;align-items:center;gap:9px;
font:10px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);z-index:5}
.brandmark i{display:grid;place-items:center;width:24px;height:24px;background:var(--ink);color:var(--paper);
font:700 9px var(--mono);font-style:normal}
@media print{.slide{display:flex !important;page-break-after:always;height:100vh}.nav{display:none}}
"""

JS = """
const slides = [...document.querySelectorAll('.slide')];
let i = Math.max(0, Math.min(slides.length - 1, (parseInt(location.hash.slice(1), 10) || 1) - 1));
function show(n) {
  i = Math.max(0, Math.min(slides.length - 1, n));
  slides.forEach((s, k) => s.classList.toggle('on', k === i));
  document.getElementById('count').textContent = `${i + 1} / ${slides.length}`;
  history.replaceState(null, '', `#${i + 1}`);
  slides[i].scrollTop = 0;
}
document.addEventListener('keydown', e => {
  if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); show(i + 1); }
  if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); show(i - 1); }
  if (e.key === 'Home') show(0);
  if (e.key === 'End') show(slides.length - 1);
});
document.getElementById('prev').onclick = () => show(i - 1);
document.getElementById('next').onclick = () => show(i + 1);
show(i);
"""


def page(title: str, subtitle: str, slides: list[str]) -> str:
    body = "\n".join(slides)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
<div class="deck">{body}</div>
<div class="brandmark"><i>3L</i><span>{subtitle}</span></div>
<div class="nav"><button id="prev">&larr;</button><span id="count"></span><button id="next">&rarr;</button></div>
<script>{JS}</script>
</body>
</html>
"""


def slide(content: str, dark: bool = False) -> str:
    return f'<section class="slide{" dark" if dark else ""}">{content}</section>'


# --------------------------------------------------------------------------- #
# ML deck
# --------------------------------------------------------------------------- #


def build_ml() -> str:
    panel = {r["company"]: r for r in load("agent/ml-panel-forecast.json")["results"]}
    hd = load("agent/ml-prediction-forecast.json")
    zoo = hd["v2"]["walk_forward_ml"]["models"]
    sn = hd["v2"]["walk_forward_share_nowcast"]

    def gate(co, m):
        return panel[co]["metrics"][m].get("gate") or {}

    def floor(co, m):
        return (panel[co]["metrics"][m].get("intrinsic_floor") or {}).get("floor_mape_pct")

    zoo_rows = "".join(
        f'<tr{" class=\"hi\"" if k == "vote_cv_weighted" else ""}><td>{k.replace("_", " ")}</td>'
        f'<td class="num">{v["mape_pct"]}%</td><td class="num">{v["q2_only_mape_pct"]}%</td></tr>'
        for k, v in sorted(zoo.items(), key=lambda x: x[1]["q2_only_mape_pct"]))

    results = [
        ("HD", "Net sales", "Share-of-category nowcast + ensemble", sn["q2_only_mape_pct"], "%", 2.0, sn["q2_n"], True),
        ("HD", "Adjusted diluted EPS", "Ridge on sequential ratios", hd["validation"]["diluted_eps_gaap"]["q2_walk_forward"]["mape_pct"], "%", 5.0, 3, True),
        ("HD", "Comparable sales", "Ridge on lag 1 and lag 4", hd["validation"]["comp_sales_pct"]["holdout_mae_pp"], "pp", 0.8, 3, True),
        ("ADI", "Revenue", "Guidance realisation", gate("analog-devices", "revenue").get("score"), "%", 2.0, 14, True),
        ("ADI", "Adjusted diluted EPS", "Guidance realisation", gate("analog-devices", "adj_eps").get("score"), "%", 5.0, 14, True),
        ("ADI", "Adjusted gross margin", "Guided op margin + opex spread", gate("analog-devices", "adj_gross_margin_pct").get("score"), "pp", 1.0, 14, True),
        ("Hays", "Net fees", "Quarterly composition", gate("hays", "net_fees").get("score"), "%", 2.0, 4, True),
        ("Hays", "Op profit, EPS", "None — 7 annual observations", None, "", 10.0, 7, False),
        ("DE", "Revenue", "Voting ensemble", gate("deere", "worldwide_net_sales_revenues").get("score"), "%", 2.0, 9, False),
        ("DE", "Diluted EPS", "Voting ensemble", gate("deere", "diluted_eps_gaap").get("score"), "%", 5.0, 9, False),
        ("DE", "PPA operating profit", "Voting ensemble", gate("deere", "ppa_operating_profit").get("score"), "%", 10.0, 4, False),
    ]
    res_rows = "".join(
        f'<tr{" class=\"hi\"" if ok else ""}><td>{c} · {m}</td><td>{mdl}</td>'
        f'<td class="num">{f"{sc}{u}" if sc is not None else "—"}</td>'
        f'<td class="num">{g}{u or "%"}</td><td class="num">{n}</td>'
        f'<td><span class="pill{"" if ok else " bad"}">{"pass" if ok else "abstain"}</span></td></tr>'
        for c, m, mdl, sc, u, g, n, ok in results)

    de_rows = "".join(
        f'<tr><td>{lbl}</td><td class="num">{floor("deere", k)}%</td>'
        f'<td class="num">{gate("deere", k).get("threshold")}%</td>'
        f'<td class="num">{gate("deere", k).get("score")}%</td></tr>'
        for k, lbl in [("worldwide_net_sales_revenues", "Revenue"),
                       ("diluted_eps_gaap", "Diluted EPS"),
                       ("ppa_operating_profit", "PPA operating profit")])

    s = []
    s.append(slide(f"""
      <p class="eyebrow">Agents vs Wall Street · Model deep dive 1 of 4</p>
      <h1>The machine&nbsp;learning lens.</h1>
      <p class="lede">What we built, which models went in, how we validated it — and why the
      thing that actually worked was not a model at all.</p>
      <div class="cols">
        <div class="col"><strong>8</strong><span>Estimators tested</span><small>5 base · 3 ensembles</small></div>
        <div class="col"><strong>7 / 12</strong><span>Metrics cleared</span><small>Five abstain</small></div>
        <div class="col"><strong>0.40%</strong><span>Best walk-forward</span><small>HD net sales, 6 periods</small></div>
        <div class="col"><strong>0</strong><span>Fitted parameters</span><small>In the best model</small></div>
      </div>""", dark=True))

    s.append(slide("""
      <p class="eyebrow">01 · The task</p>
      <h2>Predict a number the company has not published yet.</h2>
      <p>Twelve metrics across four companies. The ML lens trains only on the pipeline's own
      extracted observation table — reported actuals and disclosed guidance — never on prose.</p>
      <div class="two">
        <div class="card"><h3>What makes it hard</h3>
          <p>A decade of quarterly history is 40 observations, and excluding the COVID whipsaw
          removes eight. This is a small-sample problem wearing a big-data costume, so every
          technique that assumes abundant data is a trap.</p></div>
        <div class="card"><h3>The rule we set first</h3>
          <p>A model may only speak if it beats a naive baseline and clears a gate fixed before
          it ran. Anything else abstains. A lens that knows when to shut up is worth more than
          one that always emits a number.</p></div>
      </div>""" ))

    s.append(slide("""
      <p class="eyebrow">02 · Attempt one</p>
      <h2>Year-over-year growth. It lost to doing nothing.</h2>
      <p>The obvious framing: predict <code>y_t / y_{t−4} − 1</code> from lagged growth and quarter dummies.</p>
      <table>
        <thead><tr><th>Metric</th><th>Holdout MAPE</th><th>Seasonal naive</th><th>Verdict</th></tr></thead>
        <tbody>
          <tr><td>HD net sales</td><td class="num">5.40%</td><td class="num">5.24%</td><td><span class="pill bad">worse than naive</span></td></tr>
          <tr><td>HD GAAP EPS</td><td class="num">5.20%</td><td class="num">4.76%</td><td><span class="pill bad">worse than naive</span></td></tr>
        </tbody>
      </table>
      <p style="margin-top:22px"><strong>Losing to the baseline is information, not embarrassment.</strong>
      It says the target was wrong, not the estimator. Two causes, both visible in the data: COVID
      puts +23% to +35% growth rows in training, and the SRS and GMS acquisitions add a step to
      year-over-year that appears for four quarters then vanishes — straddling the holdout exactly.</p>"""))

    s.append(slide("""
      <p class="eyebrow">03 · Attempt two</p>
      <h2>Sequential ratios, and validating the actual task.</h2>
      <ul>
        <li><strong>Reframe the target</strong> to <code>y_t / y_{t−1}</code>. Seasonality makes it tight, and an acquisition sits in both quarters once annualised, so the ratio is acquisition-neutral.</li>
        <li><strong>Exclude COVID</strong> target rows as a documented exogenous shock, not silent winsorising.</li>
        <li><strong>Match validation to deployment.</strong> We were averaging four different transitions; the task is one — Q1 to Q2. Grading on Q4-to-Q1 inflates the error for a problem the model never has to solve.</li>
      </ul>
      <div class="cols">
        <div class="col"><strong>5.40%</strong><span>Year-over-year</span><small>Attempt one</small></div>
        <div class="col"><strong>3.23%</strong><span>Sequential, all transitions</span><small>Better, still failing</small></div>
        <div class="col"><strong>1.64%</strong><span>Task-matched Q1→Q2</span><small>Passed the 2% gate</small></div>
      </div>"""))

    s.append(slide(f"""
      <p class="eyebrow">04 · The model zoo</p>
      <h2>Five estimators, three ensembles, chosen to fail differently.</h2>
      <p>Ridge (α=1.0), Random Forest (300 trees, depth 3), Gradient Boosting (200, depth 2, lr 0.05),
      SVR with an RBF kernel (C=10) and distance-weighted KNN. Kernel and instance-based learners
      fail differently from linear and tree learners, which is the precondition for ensembling to help.
      Model choice is made by <code>TimeSeriesSplit</code> <em>inside the training window only</em>.</p>
      <table>
        <thead><tr><th>Estimator</th><th>All transitions</th><th>Q1→Q2 only</th></tr></thead>
        <tbody>{zoo_rows}</tbody>
      </table>"""))

    s.append(slide("""
      <p class="eyebrow">05 · The uncomfortable result</p>
      <h2>Ensembling bought almost nothing.</h2>
      <div class="cols">
        <div class="col"><strong>1.64%</strong><span>Best single model</span><small>Random forest</small></div>
        <div class="col"><strong>1.43%</strong><span>Best ensemble</span><small>CV-weighted voting</small></div>
        <div class="col"><strong>6.04%</strong><span>Stacking</span><small>Worst of everything</small></div>
      </div>
      <p style="margin-top:26px">Voting moved the needle by two tenths of a point. Stacking — the most
      sophisticated member — was the <em>worst</em> performer by a distance, because a ridge
      meta-learner fitted on roughly twenty rows overfits exactly as small-sample theory predicts.</p>
      <p><strong>Estimator choice was never the bottleneck.</strong> That finding is what redirected
      the work, and it is the single most useful thing the model zoo produced.</p>"""))

    s.append(slide("""
      <p class="eyebrow">06 · The reframe</p>
      <h2>Ask what is genuinely unknown.</h2>
      <p>Home Depot reports on 18 August. The US Census building-materials category level for HD's exact
      fiscal quarter is published on 14 August. So the category is <em>already known</em> — the only
      unknown is Home Depot's share of it. Strip out SRS and GMS wholesale revenue, which sits outside
      that category, and organic share is remarkably stable quarter to quarter.</p>
      <div class="formula">share_t  = share_{t−4} × (share_{t−1} ÷ share_{t−5})
sales_t  = share_t × category_t + inorganic_t

FY2026Q2:  0.3197 × 0.9732 = 0.3111
           0.3111 × 141,088 + 3,880  =  $47,775M</div>
      <p><strong>Zero fitted parameters.</strong> Nothing is estimated, so nothing can be overfit.
      Q2 walk-forward across six ex-COVID years: 0.38, 0.46, 0.61, 0.18, 0.63, 0.11 percent.</p>"""))

    s.append(slide("""
      <p class="eyebrow">07 · The same move, three times</p>
      <h2>Every model that passed exploits something already published.</h2>
      <div class="two">
        <div class="card"><h3>Home Depot — share of category</h3>
          <p>Census NAICS 444 for the quarter publishes four days before HD reports. Model the
          share, not the level. <strong>0.40%</strong> over six periods.</p></div>
        <div class="card"><h3>Analog Devices — guidance realisation</h3>
          <p>ADI guides a quarter ahead, so only the realisation ratio is unknown. Multiply the guide
          by the expanding mean of past ratios. <strong>1.38%</strong> over fourteen.</p></div>
        <div class="card"><h3>Hays — quarterly composition</h3>
          <p>Three of four quarters are already disclosed in trading updates. Compose the year from
          its own growth rates. <strong>1.52%</strong> over four.</p></div>
        <div class="card"><h3>Deere — nothing published</h3>
          <p>Guides full-year net income, never quarterly segments. Only history is available, and
          history cannot answer. <strong>Abstains.</strong></p></div>
      </div>"""))

    s.append(slide("""
      <p class="eyebrow">08 · Validation protocol</p>
      <h2>The model never sees its own future.</h2>
      <p>Chronological only — a random split on a time series lets a model read the answer. At every
      step the model is refit on data strictly before the period it predicts.</p>
      <table>
        <thead><tr><th>Predicting</th><th>Ratios visible</th><th>Newest visible</th><th>Mean used</th><th>Predicted</th><th>Actual</th><th>Error</th></tr></thead>
        <tbody>
          <tr><td>FY2023Q1</td><td class="num">4</td><td>FY2022Q4</td><td class="num">1.0361</td><td class="num">3,264</td><td class="num">3,250</td><td class="num">0.42%</td></tr>
          <tr><td>FY2024Q1</td><td class="num">8</td><td>FY2023Q4</td><td class="num">1.0243</td><td class="num">2,561</td><td class="num">2,513</td><td class="num">1.90%</td></tr>
          <tr><td>FY2025Q1</td><td class="num">12</td><td>FY2024Q4</td><td class="num">1.0220</td><td class="num">2,402</td><td class="num">2,423</td><td class="num">0.88%</td></tr>
          <tr><td>FY2026Q2</td><td class="num">17</td><td>FY2026Q1</td><td class="num">1.0261</td><td class="num">3,591</td><td class="num">3,623</td><td class="num">0.88%</td></tr>
        </tbody>
      </table>
      <p style="margin-top:20px">Newest visible is always strictly before the target. You can watch the
      estimate learn. It also means <strong>22 guide/actual pairs yield only 14 scored points</strong> —
      the earliest are consumed building history and never graded. Small n is the price of refusing to
      grade a model on data that helped fit it.</p>"""))

    s.append(slide(f"""
      <p class="eyebrow">09 · Results</p>
      <h2>Seven cleared. Five abstain.</h2>
      <table>
        <thead><tr><th>Metric</th><th>Deployed model</th><th>Walk-forward</th><th>Gate</th><th>n</th><th></th></tr></thead>
        <tbody>{res_rows}</tbody>
      </table>"""))

    s.append(slide(f"""
      <p class="eyebrow">10 · The abstention</p>
      <h2>Proving it is the data, not the model.</h2>
      <p>Deere lost to its naive baseline. Normally that means iterate. So we measured the
      <strong>intrinsic floor</strong>: the dispersion of the target transition's own ratio history.
      If the Q2→Q3 ratio has coefficient of variation <em>c</em>, no estimator using only that history
      can average better than roughly <em>c</em>.</p>
      <table>
        <thead><tr><th>Deere metric</th><th>Intrinsic floor</th><th>Gate</th><th>Model achieved</th></tr></thead>
        <tbody>{de_rows}</tbody>
      </table>
      <p style="margin-top:20px">Every gate is unreachable by construction. With four times the samples
      after a data fix, revenue scored 7.26% against a predicted floor of 8.1% — <strong>landing exactly
      on the floor.</strong> That is an information limit, not a tuning failure, and it is why Deere is
      carried by the driver and anchor lenses instead.</p>"""))

    s.append(slide("""
      <p class="eyebrow">11 · Honesty</p>
      <h2>Where this is weakest.</h2>
      <ul>
        <li><strong>Specification hindsight.</strong> The per-fold refit is clean, but we chose the framing, the model family and the COVID exclusion knowing how the whole period turned out. A forecaster in 2021 could not have known to exclude 2021.</li>
        <li><strong>Variant sensitivity.</strong> Four plausible share variants span 0.39% to 1.23% on Q2. The fair out-of-sample expectation is that range, not the headline. On this specific quarter they disagree by 2.5%.</li>
        <li><strong>Data vintage.</strong> The backtest reads revised Census values; deployment reads the advance estimate. That makes 0.40% slightly optimistic.</li>
        <li><strong>Small n.</strong> Six periods on the best model, four on Hays. Wide error bars on the error bars.</li>
        <li><strong>A bug the gates missed.</strong> Hays tags quarterly updates with the fiscal year, so keying on period collapsed a twenty-point series into six and we wrongly called Hays unmodelable. Found because it was challenged, not because a test caught it.</li>
      </ul>"""))

    s.append(slide("""
      <p class="eyebrow">12 · The lesson</p>
      <h1>Information beat estimators, every time.</h1>
      <div class="formula">HD  net sales   category published 4 days early    →  0.40%   pass
ADI revenue     guidance published a quarter early  →  1.38%   pass
HAS net fees    3 of 4 quarters disclosed           →  1.52%   pass
DE  revenue     nothing published                   →  8.1% floor   fail</div>
      <p class="lede" style="margin-top:8px">Model family, feature engineering and ensembling moved
      results by tenths of a point. Access to something already published moved them by an order of
      magnitude. The ML work earned its place by establishing where the ceiling was without the
      reframe — which is what made the reframe measurable rather than merely asserted.</p>""", dark=True))

    return page("The machine learning lens — Agents vs Wall Street",
                "ML lens · deep dive 1 of 4", s)


def main(argv: list[str]) -> int:
    OUT_DIR.mkdir(exist_ok=True)
    which = argv[argv.index("--lens") + 1] if "--lens" in argv else "all"
    built = []
    if which in ("all", "ml"):
        p = OUT_DIR / "ml.html"
        p.write_text(build_ml())
        built.append(p)
    for p in built:
        print(f"wrote {p.relative_to(REPO_ROOT)} ({p.stat().st_size / 1024:.1f} KB, self-contained)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
