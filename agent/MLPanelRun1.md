# ML Panel — Run 1 (ADI, Deere, Hays)

| | |
|---|---|
| Model | Claude Fable 5 (claude-fable-5) |
| Date | 2026-08-16 |
| Code | `forecast/ml_panel.py` |
| Inputs | `data/observations/{analog-devices,deere,hays}.json` |
| Output | `agent/ml-panel-forecast.json` |
| Predecessor | `MLValidationRun1.md` (Home Depot), which set the protocol this run reuses unchanged |

**Headline: the pipeline transfers to 1 company of 3, and the system correctly abstains on 6 of 9 metrics.** ADI passes all three gates via a zero-parameter guidance-realisation model. Deere and Hays fail, and the run proves the failures are properties of the *data*, not of the models — which is the difference between "iterate on the model" and "stop, this metric is not learnable here".

---

## 1. What was transferred, and the hypothesis being tested

The Home Depot run established a protocol and a lesson:

- **Protocol** — chronological-only validation, a mandatory naive baseline, gates declared before running, predictions stored only on PASS.
- **Lesson** — estimator choice was never the bottleneck (SVR, KNN, voting and stacking bought ~0.2pp). What mattered was **reframing the target so that already-published information carries most of the answer.** For HD that was share-of-category: the Census category level is published before HD reports, so only HD's share of it is unknown.

So the hypothesis for this run was not "will RandomForest work on Deere" but: **does each company have its own equivalent of already-published information?** That question turns out to decide every result below.

| Company | Pre-published information about the target period | Consequence |
|---|---|---|
| **ADI** | **Yes** — ADI guides revenue, adjusted EPS and adjusted operating margin one quarter ahead, and the FY2026Q3 guides are already in the table (rev $3,900M, EPS $3.30, aOM 49.0%) | Only the *realisation ratio* is unknown; 20 historical ratios exist |
| **Deere** | **No** — Deere guides full-year net income, never quarterly segment lines | Pure history only |
| **Hays** | **No, and it isn't an ML problem** — 7–8 annual observations | Abstain |

Gates were fixed before any model ran, set from what would be competitive against a Street benchmark rather than from what the models could hit: ADI/Deere revenue ≤2% MAPE, EPS ≤5%, ADI adj gross margin ≤1.0pp MAE, Deere PPA operating profit ≤10%, Hays net fees ≤2% / profit and EPS ≤10%. Every metric must also **beat its naive baseline**.

---

## 2. ADI — the reframe exists, and it works

`actual_t = guide_mid_t × (expanding mean of past realisation ratios)`

Zero fitted parameters, so nothing can be overfit and the walk-forward is exact. The legality argument is identical to HD's: guidance for quarter *t* is published before quarter *t* is reported. The naive baseline is deliberately strong — **trust the guidance verbatim**, which is what a lazy forecaster does.

| Metric | Walk-forward score (n=13) | Naive (trust guidance) | Gate | Verdict |
|---|---|---|---|---|
| Revenue | **1.45% MAPE** | 2.36% | ≤2% | **PASS** |
| Adjusted EPS | **3.44% MAPE** | 4.68% | ≤5% | **PASS** |
| Adjusted gross margin | **0.83pp MAE** | 1.05pp | ≤1.0pp | **PASS** |

Recent walk-forward points (revenue): FY2025Q4 0.08%, FY2026Q1 0.66%, FY2026Q2 0.92%. The realisation ratio is remarkably stable — mean 1.026, sd 0.018, and 19 of 20 quarters above 1.0. ADI beats its own guidance almost every quarter, by a consistent amount.

**Adjusted gross margin has no direct guide**, so it was decomposed one level down — the same "shrink the unknown" move:

```
adj gross margin = adj operating margin + opex-as-%-of-revenue
                 = (guided aOM × realisation ratio) + forecast opex spread
```

The operating-margin half *is* guided, so only the opex spread needs modelling — and that spread is smooth and strongly autocorrelated (28.3 → 28.2 → 27.0 → 26.3 → 25.7 → 24.0 over the last six quarters, compressing as revenue scales).

### Robustness check: does the answer depend on the estimator choice?

This was HD's main weakness — there, four plausible share variants spanned 0.39%–1.23%, a 3× spread that undermined the headline. Same ablation here:

| Ratio estimator | Revenue MAPE | Adj EPS MAPE |
|---|---|---|
| last_only | **1.33%** | 3.62% |
| expanding_median | 1.44% | 3.29% |
| **expanding_mean (deployed)** | **1.45%** | **3.44%** |
| trailing4 | 1.53% | **3.02%** |
| trailing8 | 1.54% | 3.62% |

**Spread of 0.21pp on revenue and 0.60pp on EPS — and every variant passes its gate.** This is a materially stronger result than HD's: the ADI conclusion does not depend on which ratio estimator is chosen.

Note that `expanding_mean` is *not* the best variant in either column. It was fixed before the ablation ran and was deliberately **not** switched afterwards — swapping to the post-hoc winner would be selection on the test set, exactly the error the protocol exists to prevent. The cost of that discipline is small (1.45% vs 1.33%).

### ADI predictions, and how they compare to the other lenses

| Metric | **ML panel** | Anchor lens | Guide | Gap |
|---|---|---|---|---|
| Revenue | **$4,002M** | $4,010M | $3,900M | 0.2% |
| Adjusted EPS | **$3.48** | $3.48 | $3.30 | ~0 |
| Adjusted gross margin | **73.19%** | 72.9% | ~72.5% implied | +0.29pp |

The convergence on revenue and EPS is the most valuable output of this run: a **mechanical, zero-parameter model independently reproduces the anchor lens's judgement calls** (3.484 vs 3.48 on EPS). Two methods sharing no reasoning arrived at the same place.

**The gross-margin disagreement is real and instructive.** The ML model says 73.19% — *above* Q2's 73.0% — because it extrapolates the opex-spread compression and ADI's habitual operating-margin beat. But the CFO explicitly said Q3 gross margin should fall ~50bp because a one-time channel-repricing benefit in Q2 will not repeat. **That is qualitative transcript information, absent from the numeric observation table, so the ML lens is structurally blind to it.** The anchor lens (72.9%) accounts for it. I would keep 72.9% and treat 73.19% as an upside flag, noting the 0.5pp scoring floor makes all three values nearly equivalent anyway.

---

## 3. Deere — the failure is in the data, not the model

No pre-published quarterly information exists, so only pure history was available, and the series has real structural problems: **no Q4 rows at all** (so Q3→Q4 and Q4→Q1 transitions cannot be formed), PPA segment data only from FY2020Q3, and severe post-2024 operating deleverage.

| Metric | Walk-forward | Naive | Gate | Verdict |
|---|---|---|---|---|
| Worldwide net sales & revenues | 4.03% (n=2) | 3.02% | ≤2% | **FAIL** — loses to naive |
| Diluted EPS (GAAP) | 32.19% (n=4) | 23.81% | ≤5% | **FAIL** — loses to naive |
| PPA operating profit | not runnable | — | ≤10% | **FAIL** — insufficient history |

Losing to the naive baseline says the model learned nothing. But is that the model's fault or the data's? The pipeline now answers that directly by computing an **intrinsic floor**: the dispersion of the target transition's own ratio history. If the Q2→Q3 ratio has coefficient of variation *c*, no estimator using only that history can average better than roughly *c*% MAPE.

| Metric | Q2→Q3 ratio history (ex-COVID) | Floor | Gate | Achievable? |
|---|---|---|---|---|
| Revenue | 0.885, 1.055, 0.909, 0.863, 0.942 | **8.1%** | 2% | **No** |
| Diluted EPS | 0.798, 0.905, 1.057, 0.737, 0.715 | **16.7%** | 5% | **No** |
| PPA operating profit | 1.223, 0.821, 0.704, 0.505 | **37.2%** | 10% | **No** |

**Every Deere gate is unreachable by construction.** A perfect history-only estimator would still miss revenue by ~8% and PPA operating profit by ~37%. The PPA ratio history is the clearest picture of why: 1.223 → 0.821 → 0.704 → 0.505, a monotone collapse as agricultural operating leverage works in reverse. History cannot forecast that; it is precisely what the driver lens (AEM tractor units, dealer inventories) and the anchor lens (management's segment guidance) exist to capture.

This is the run's most useful negative result: **Deere's Q3 is not a machine-learning problem.** Effort spent tuning estimators here would have been wasted, and the intrinsic floor made that visible before any tuning happened.

---

## 4. Hays — abstention is the correct output

Hays reports semi-annually and the observation table holds **7–8 annual observations** (net fees FY2018–FY2025; operating profit and EPS n=7, with FY2022 missing entirely). There is no honest chronological walk-forward at that sample size, so the pipeline abstains on operating profit and EPS rather than emitting a number.

For net fees one quantitative check was possible — an **H1→FY ratio model**, since H1 FY2026 net fees (£453.3m) are reported:

| Year | H1/FY ratio |
|---|---|
| FY2019 | 0.5028 |
| FY2020 | 0.5552 |
| FY2021 | 0.4605 |
| FY2025 | 0.5101 |

Mean ratio 0.507 → **£893.8m**, walk-forward error 6.86% (gate 2%: FAIL). More usefully, the ratio *spread* (0.46–0.56) maps H1's £453.3m to a range of **£809m–£985m**. That band contains both the continuing-operations figure (£888m) and the stale-basis consensus (£902m), so **the model cannot discriminate between the two — which is the entire question for Hays.** It confirms the order of magnitude and nothing more.

The honest framing: Hays FY2026 is already closed. It is a *reconstruction* problem (sum the disclosed halves, subtract the disposed countries), not a prediction problem — which is exactly what the anchor lens did to reach £888m. Machine learning has nothing to add.

---

## 5. Results summary

| Company | Metric | Score | Gate | Beats naive | Usable |
|---|---|---|---|---|---|
| ADI | Revenue | 1.45% | 2% | ✓ | **$4,002M** |
| ADI | Adjusted EPS | 3.44% | 5% | ✓ | **$3.48** |
| ADI | Adjusted gross margin | 0.83pp | 1.0pp | ✓ | **73.19%** |
| Deere | Net sales & revenues | 4.03% | 2% | ✗ | abstained |
| Deere | Diluted EPS | 32.19% | 5% | ✗ | abstained |
| Deere | PPA operating profit | n/a | 10% | — | abstained |
| Hays | Net fees | 6.86% | 2% | — | abstained |
| Hays | Pre-exc operating profit | n/a | 10% | — | abstained |
| Hays | Pre-exc basic EPS | n/a | 10% | — | abstained |

**3 usable of 9.** Combined with Home Depot's 3 of 3, the ML lens covers **6 of the 12 challenge metrics**, and every one of those six rests on a model whose main input was already published before the company reports.

### The generalisable finding

Across four companies, ML lens accuracy tracked one variable almost perfectly — **how much of the answer is published before the company reports**:

```
HD    category level published 4 days early   -> 0.4%   PASS
ADI   guidance published a quarter early      -> 1.45%  PASS
DE    nothing published                       -> 8.1% floor   FAIL
HAS   nothing published, n=7                  -> abstain      FAIL
```

Model family, feature engineering and ensembling moved results by tenths of a percent. Access to pre-published information moved them by an order of magnitude. **The lesson from the HD run replicated exactly.**

---

## 6. Known weaknesses

- **ADI walk-forward n=13**, starting FY2023Q1 (earlier quarters are consumed as training). Small, though the ablation shows the result is estimator-robust.
- **The ADI realisation ratio assumes the guidance regime is stable.** If ADI changed its guidance philosophy — guiding more conservatively or more aggressively — the historical ratio would mislead, and the model has no way to detect that from numbers alone.
- **ADI adj gross margin is blind to a known one-off** (§2). The numeric table cannot represent "this benefit will not repeat"; only the transcript can.
- **COVID exclusion (FY2020–21) is a judgement call** applied uniformly. For ADI it removes the semiconductor whipsaw; for Deere it thins an already-thin sample.
- **Deere's intrinsic floors rest on n=4–5 ratios**, so the floor estimates themselves are imprecise — but they exceed the gates by 4–10×, far beyond what sampling error could close.
- **The Hays H1→FY ratio has n=4** and FY2026's disposals make even the FY2025 comparison non-like-for-like.

## 7. Reproduction

```bash
.venv/bin/python -m forecast.ml_panel      # all three companies, gates, diagnostics
```

`RANDOM_STATE = 26`. The guidance-realisation and intrinsic-floor computations have no random component and are exactly reproducible; only the (unselected) history-framing ensembles use randomness.
