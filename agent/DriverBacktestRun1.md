# Blinded LLM Replay — Driver-Lens Backtest, Run 1

| | |
|---|---|
| Predictor | Claude Fable 5 (claude-fable-5), one **fresh, tool-less session per packet** |
| Date | 2026-08-16 |
| Packets | `research/llm-replay/packets/` (20: HD×8, ADI×6, DE×6) |
| Responses | `research/llm-replay/responses/` (raw, one JSON per session) |
| Scored artifact | `research/llm-replay/llm-driver-backtest.json` |
| Market companion | `research/polymarket-reliability.json` (`forecast/polymarket_history.py`) |
| Code | `forecast/llm_replay.py` · runner `scripts/run-llm-replay.sh` |
| Page | `architecture/predictions.html` — Driver and Market views now carry these series |

## The problem

The anchor and ML lenses have walk-forward charts because they are formulas: run the formula at an old cutoff, get what it would have said. The driver lens is LLM reasoning — and an LLM replayed on the past has a failure mode formulas don't: **it has already read the future.** Any quarter inside the model's training window is a quarter whose actual it may simply remember. "Please pretend you don't know" is not a control.

## The design — one layer per leak vector

1. **View isolation** (what the pipeline can leak). Each packet is a *time-scoped internet snapshot*: only rows whose original disclosure date is on or before the cutoff (the day before that quarter's print), built through the same extractors the five-year backtest uses. The Census category series is lagged by a publication model (advance estimate ≈ the 16th of the next month), so early-reporting quarters legitimately miss their final category month. Every packet carries a `worldview` manifest: how many corpus documents were visible vs excluded at its cutoff.
2. **Identity blinding** (what the model can remember). No names, tickers, calendar dates, or fiscal-year labels. Periods are relative (`T-1…`), months relative (`M-0…`), and every currency value — including the consensus strike — is multiplied by an undisclosed per-company constant (recorded in the artifact for audit; rotate to re-blind). Memorized actuals live in absolute units under a company name; a scaled unlabelled series gives recall nothing to index on. Percent metrics stay raw (scale-free) — that is the residual risk, and it is measured, not assumed away.
3. **Leakage audit** (trust but verify). A mandatory `identityGuess` field, a suspicious-exactness flag, and an in-training vs post-training error split (training cutoff 2026-01-31).
4. **Session isolation** (what the orchestrator can leak). The orchestrating session that built the packets has seen the actuals, so it never answers one. Each packet goes to a fresh `claude -p` session with all tools disabled; its entire world is the packet text.

## Results (pre-declared gates, identical to the ML panel's)

| | metric | all 6–8 qtrs | post-training only (n=2) | naive | gate | verdict |
|---|---|---|---|---|---|---|
| HD | net sales | **1.05%** | 1.28% | 5.47% | 2% | PASS |
| HD | GAAP EPS | **2.65%** | 6.49% | 5.02% | 5% | PASS (post fails) |
| HD | comp sales | **0.41pp** | 1.4pp | 2.12pp | 0.8pp | PASS (post fails) |
| ADI | revenue | **1.28%** | 0.93% | 18.78% | 2% | PASS |
| ADI | adj EPS | **2.78%** | 3.40% | 25.56% | 5% | PASS |
| ADI | adj gross margin | **0.53pp** | 0.50pp | 2.02pp | 1pp | PASS |
| DE | revenues | **1.63%** | 1.51% | 16.36% | 2% | PASS |
| DE | GAAP EPS | **3.73%** | 8.30% | 34.19% | 5% | PASS (post fails) |
| DE | PPA op profit | **37.44%** | 76.8% | 94.63% | 10% | FAIL |

Two headline findings:

- **The revenue chains genuinely work post-training.** ADI 0.93%, HD 1.28%, DE 1.51% on quarters the model cannot have memorized — guidance-calibration and category-share reasoning survive the blind.
- **DE PPA operating profit fails at almost exactly the ML lens's intrinsic floor** (37.4% vs the 37.2% floor computed from the Q2→Q3 ratio's own dispersion). Two independent methods — a model zoo and a blinded LLM — hit the same wall, which is what an *information* limit looks like, as distinct from a modelling failure.

## P(beat) vs Polymarket, same events

Polymarket's quarterly beat-market series begins Nov 2025: nine resolved markets (3 per US name), harvested with 12-hour CLOB price history. Headline probability = last trade ≥24h pre-print (the market's "day before", matching the packets' cutoff). Filing actuals agree with every resolution.

| Brier (lower better) | HD | ADI | DE | all 9 |
|---|---|---|---|---|
| Market, day before | 0.1955 | 0.0075 | 0.0972 | **0.1001** |
| Blinded LLM, same events | 0.1145 | 0.0228 | 0.1498 | 0.0957 |
| Always guess the base rate | | | | 0.0988 |

8 of 9 markets resolved YES. Neither the market nor the LLM meaningfully beats "always guess the base rate" on nine events — the honest conclusion is that the market's information is mostly in the **strike** (the leaked Street consensus), not the price, and that n=9 is too small to rank anyone.

## Leakage audit — what actually leaked

- **Identity blinding failed for the famous names.** 18 of 20 sessions disclosed a guess; every HD and DE session recognized the company, mostly from the COVID-era comp fingerprint (+24.5%, +31.0%) or Deere's Q1 seasonal collapse. Two even reverse-engineered the scale factor by matching remembered revenue levels. ADI was recognized in 2 of 6 sessions (Maxim-jump fingerprint), guessed as "KLA or TI" in others.
- **In-training quarters show recall despite instructions.** HD FY2025Q2: net sales 0.01% error, comps exact. HD FY2025Q3: net sales 0.04%. These are recall, not forecasting — which is precisely why the artifact and the page report the post-training split separately.
- **Post-training quarters are leak-free by construction** (reported after the predictor's training window). They carry the honest signal.

Verdict: for periods inside a model's training window, *blinding reduces but does not eliminate* recall of famous companies; a credible LLM backtest must either use post-training periods or report the split. This page does the latter.

## Reproduce / benchmark another model

```bash
.venv/bin/python -m forecast.polymarket_history --refresh   # harvest + score markets
.venv/bin/python -m forecast.llm_replay emit                # build blinded packets
scripts/run-llm-replay.sh 5                                 # fresh sessions + score
.venv/bin/python -m forecast.build_predictions_page         # regenerate the page
```

To run the identical packets through any other model (delete or move `responses/` first — the runner skips existing responses):

```bash
LLM_CMD="your-model-cli --no-tools" scripts/run-llm-replay.sh 5
```

Guards: `tests/test_llm_replay.py` (prompt blinding, cutoff isolation, error recomputation).

## Addendum — live forecasts and the probability-chart redesign (same day)

- Binary markets are now drawn as what they are: **P(YES) per event with the resolution marked** (green dot = priced the right side of 50%, orange = wrong side, hollow = unresolved), a 50% coin-flip line, and "off by Xpp" per resolved event. No more fake 0/100 "actual" line.
- The same blinded machinery emitted **live packets** (`emit --live`, cutoff 2026-08-16) for the three unreported quarters; three more fresh sessions produced:

| | quarter | LLM (blinded, live) | driver lens | P(beat strike) LLM vs market |
|---|---|---|---|---|
| HD | FY2026Q2 | net sales 48,003 · GAAP EPS 4.46 · comps +1.8 | 47,770 · adj 4.74 · +1.9 | **0.40** vs 0.785 (strike 4.73) |
| ADI | FY2026Q3 | revenue 4,009 · adj EPS 3.48 · GM 73.8 | 4,009 · 3.51 · 72.9 | 0.88 vs 0.94 (3.33) |
| DE | FY2026Q3 | revenue 12,569 · GAAP EPS 4.96 · PPA OP 389 | 12,470 · 5.00 · 513 | 0.68 vs 0.91 (4.72) |

Independent convergence on revenue everywhere; the LLM is a notable contrarian on HD's beat (0.40 vs the market's 0.785 — it was also the only one under 50% on the single historical NO). PPA operating profit diverges, as its backtest says it must.
