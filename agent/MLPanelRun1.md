# ML Panel — Run 1 (ADI, Deere, Hays)

| | |
|---|---|
| Model | Claude Fable 5 (claude-fable-5) |
| Date | 2026-08-16 |
| Code | `forecast/ml_panel.py` |
| Inputs | `data/observations/{analog-devices,deere,hays}.json` |
| Output | `agent/ml-panel-forecast.json` |
| Predecessor | `MLValidationRun1.md` (Home Depot), which set the protocol this run reuses unchanged |

**Headline: 4 of 9 metrics pass; the pipeline transfers to ADI in full and to Hays net fees.** ADI passes all three gates via a zero-parameter guidance-realisation model. Hays net fees passes at 1.52% MAPE once a loader bug was fixed. Deere fails all three, and the run *proves* that failure is a property of the data rather than of the models.

> **Correction 2 (same day).** A follow-up audit of ADI and Deere found that **all four observation files on disk were stale** — regenerating them from the corpus yields deere 82→116, hays 69→71, home-depot 125→133, analog-devices 360→375 observations. Deere was missing **every Q4** (the extractor handles them; the file predated that). The live pipeline (`run.py`) re-extracts at run time, so the team's submission was never affected — only this lens, which read the on-disk artifacts. Everything below is re-run on regenerated data; **no verdict changed**, and Deere's evidence got substantially stronger (§3).

> **Correction 1 (same day).** The first version of this run concluded Hays had no usable data. That was wrong, and it was my bug, not the data's. `load_series` keyed observations by their `period` string, but Hays tags every quarterly trading update with the **fiscal year** rather than the quarter — so four readings per year collapsed into one and a **20-point quarterly series silently became ~6 annual points**. Section 4 is rewritten around the corrected result. ADI and Deere were unaffected (zero conflicting keys), and the loader now raises rather than overwriting when a period holds two different values.

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
| **Hays** | **Partly** — 20 quarterly net-fee growth readings compose the year; profit/EPS have only 7 annual points | Net fees modelable; profit and EPS abstain |

Gates were fixed before any model ran, set from what would be competitive against a Street benchmark rather than from what the models could hit: ADI/Deere revenue ≤2% MAPE, EPS ≤5%, ADI adj gross margin ≤1.0pp MAE, Deere PPA operating profit ≤10%, Hays net fees ≤2% / profit and EPS ≤10%. Every metric must also **beat its naive baseline**.

---

## 2. ADI — the reframe exists, and it works

`actual_t = guide_mid_t × (expanding mean of past realisation ratios)`

Zero fitted parameters, so nothing can be overfit and the walk-forward is exact. The legality argument is identical to HD's: guidance for quarter *t* is published before quarter *t* is reported. The naive baseline is deliberately strong — **trust the guidance verbatim**, which is what a lazy forecaster does.

| Metric | Walk-forward score (n=14) | Naive (trust guidance) | Gate | Verdict |
|---|---|---|---|---|
| Revenue | **1.38% MAPE** | 2.41% | ≤2% | **PASS** |
| Adjusted EPS | **3.44% MAPE** | 4.74% | ≤5% | **PASS** |
| Adjusted gross margin | **0.89pp MAE** | 1.03pp | ≤1.0pp | **PASS** |

The pure-history framing was also runnable on the regenerated data and lost badly (revenue 6.71% vs guidance-realisation's 1.38%; EPS 16.51% vs 3.44%), which confirms the reframe rather than the estimator is doing the work.

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
| Revenue | **$4,004M** | $4,010M | $3,900M | 0.2% |
| Adjusted EPS | **$3.49** | $3.48 | $3.30 | ~0 |
| Adjusted gross margin | **73.29%** | 72.9% | ~72.5% implied | +0.39pp |

The convergence on revenue and EPS is the most valuable output of this run: a **mechanical, zero-parameter model independently reproduces the anchor lens's judgement calls** (3.484 vs 3.48 on EPS). Two methods sharing no reasoning arrived at the same place.

**The gross-margin disagreement is real and instructive.** The ML model says 73.19% — *above* Q2's 73.0% — because it extrapolates the opex-spread compression and ADI's habitual operating-margin beat. But the CFO explicitly said Q3 gross margin should fall ~50bp because a one-time channel-repricing benefit in Q2 will not repeat. **That is qualitative transcript information, absent from the numeric observation table, so the ML lens is structurally blind to it.** The anchor lens (72.9%) accounts for it. I would keep 72.9% and treat 73.19% as an upside flag, noting the 0.5pp scoring floor makes all three values nearly equivalent anyway.

---

## 3. Deere — the failure is in the data, not the model

No pre-published quarterly information exists, so only pure history was available, and the series has real structural problems: **no Q4 rows at all** (so Q3→Q4 and Q4→Q1 transitions cannot be formed), PPA segment data only from FY2020Q3, and severe post-2024 operating deleverage.

| Metric | Walk-forward | Naive | Gate | Verdict |
|---|---|---|---|---|
| Worldwide net sales & revenues | 7.26% (n=9) | 7.31% | ≤2% | **FAIL** — 3.6× the gate |
| Diluted EPS (GAAP) | 24.25% (n=9) | 19.57% | ≤5% | **FAIL** — loses to naive |
| PPA operating profit | 24.19% (n=4) | 74.80% | ≤10% | **FAIL** — 2.4× the gate |

These are the *regenerated-data* results, with roughly 4× the walk-forward samples of the first run. More data did not help, and the reason is the next table.

Losing to the naive baseline says the model learned nothing. But is that the model's fault or the data's? The pipeline now answers that directly by computing an **intrinsic floor**: the dispersion of the target transition's own ratio history. If the Q2→Q3 ratio has coefficient of variation *c*, no estimator using only that history can average better than roughly *c*% MAPE.

Adding every Q4 back changed none of these, because Q4 does not enter a Q2→Q3 ratio:

| Metric | Q2→Q3 ratio history (ex-COVID) | Floor | Gate | Achievable? |
|---|---|---|---|---|
| Revenue | 0.885, 1.055, 0.909, 0.863, 0.942 | **8.1%** | 2% | **No** |
| Diluted EPS | 0.798, 0.905, 1.057, 0.737, 0.715 | **16.7%** | 5% | **No** |
| PPA operating profit | 1.223, 0.821, 0.704, 0.505 | **37.2%** | 10% | **No** |

**Every Deere gate is unreachable by construction.** A perfect history-only estimator would still miss revenue by ~8% and PPA operating profit by ~37%. The regenerated run is the cleanest possible confirmation: with n=9 walk-forward points the revenue model scored **7.26% against a predicted floor of 8.1%** — it landed exactly where the floor said it would, which is what a genuine information limit looks like as opposed to a tuning failure. The PPA ratio history is the clearest picture of why: 1.223 → 0.821 → 0.704 → 0.505, a monotone collapse as agricultural operating leverage works in reverse. History cannot forecast that; it is precisely what the driver lens (AEM tractor units, dealer inventories) and the anchor lens (management's segment guidance) exist to capture.

This is the run's most useful negative result: **Deere's Q3 is not a machine-learning problem.** Effort spent tuning estimators here would have been wasted, and the intrinsic floor made that visible before any tuning happened.

---

## 4. Hays — net fees is modelable; profit and EPS are not

**The bug first.** Hays publishes a trading update every quarter, but the extraction tags each one with the *fiscal year* (`FY2026`) rather than the quarter — the quarter is only recoverable from `as_of` (October = Q1, January = Q2, April = Q3, July = Q4). My loader keyed on `period`, so each year's four readings overwrote one another and I saw ~6 annual points where **20 quarterly ones existed**. That produced the original, wrong conclusion that Hays had nothing to model.

Two fixes: `load_quarterly_growth()` recovers the quarter from `as_of`, and `load_series()` now **raises** when one period holds two different values instead of silently keeping the last. A check across all three companies found 10 conflicting keys in Hays and **zero in ADI and Deere**, so no other result was affected.

The recovered series (net fee growth, actual basis, % y/y):

```
FY2021  Q2 -16  Q3  -9  Q4 +36        FY2024  Q1  -9  Q2 -12  Q3 -17  Q4 -17
FY2022  Q1 +36  Q2 +32  Q3 +29  Q4 +24   FY2025  Q1 -15  Q2 -15  Q3 -11
FY2023  Q1 +19  Q2 +11  Q3 +10           FY2026  Q2  -9  Q3  -7  Q4  -4
```

### The model: compose the year from its quarters

`FY(Y) = FY(Y−1) × (1 + mean of the four quarterly growth rates)`

Missing quarters are imputed, preferring the like-for-like reading plus that year's observed actual-minus-LFL gap (currency and disposal effects are a within-year constant), falling back to the mean of the observed quarters.

| Year | Quarter rates | Predicted | Actual | Error | Quarters observed |
|---|---|---|---|---|---|
| FY2022 | +36, +32, +29, +24 | 1,195.8 | 1,189.4 | **0.54%** | 4/4 |
| FY2023 | +19, +11, +10, *+13.3* | 1,348.0 | 1,294.6 | 4.12% | 3/4 |
| FY2024 | −9, −12, −17, −17 | 1,116.6 | 1,113.6 | **0.27%** | 4/4 |
| FY2025 | −15, −15, −11, *−13.7* | 961.4 | 972.4 | 1.13% | 3/4 |

**MAPE 1.52% (n=4) against a naive baseline of 15.4%, gate ≤2% → PASS.** On the two complete-four-quarter years the error is **0.41%**; the damage is done entirely by imputing a missing quarter from the mean of the others.

FY2026 has three observed quarters plus Q1 recoverable through the LFL bridge. That bridge is unusually well-supported here: the actual-minus-LFL gap is exactly **+1pp in all three observable FY2026 quarters** (Q2 −9 vs −10, Q3 −7 vs −8, Q4 −4 vs −5), so Q1 actual ≈ LFL(−8) + 1 = **−7**.

```
quarters      -7, -9, -7, -4   ->  mean -6.75%
FY2026 reported basis = 972.4 x 0.9325 = 906.8
less disposed-country net fees (in the table, 15.0) = 891.8   <- continuing operations
```

### Independent cross-check

A structurally tighter variant anchors on the **reported H1 actual** and grows only the prior-year H2 by the observed Q3/Q4 rates — no Q1 imputation, and it uses a hard datum instead of a growth rate:

```
H2 FY2025 = 972.4 - 496.0 = 476.4
H2 FY2026 = 476.4 x (1 - 5.5%) = 450.2
FY2026 = 453.3 + 450.2 = 903.5 reported  ->  888.5 continuing operations
```

Only one closed year can test it (FY2021: predicted 925.7 vs actual 918.1, **0.83%** error), so it cannot clear the n≥3 requirement and is reported as corroboration rather than deployed. **The two methods land 0.4% apart (891.8 and 888.5), and the anchor lens's independent reconstruction of £888m sits at the bottom of that band.** Three routes, one answer.

### Operating profit and EPS still abstain — and the reason is now measured

Seven annual observations with FY2022 missing; no chronological walk-forward is meaningful. The obvious substitute is a consensus-bias model, since the table holds company-compiled consensus for both years at comparable vintages. It fails, informatively:

| | Consensus (same vintage) | Actual | Gap |
|---|---|---|---|
| FY2025 | 56.9 (Apr) / 56.4 (Jun) | 45.6 | **+24.2% overshoot** |
| FY2026 | 45.2 (Apr) / 43.5 (Jul) | — | — |

Applying FY2025's overshoot to FY2026 gives ≈£35m — which flatly contradicts the company's own 10 July steer of "at the top of the £37.0–46.0m range". The reason is that the *direction* of the steer flipped: in June 2025 Hays published consensus alongside a warning it would land **below** it; in July 2026 it published consensus alongside a signal it would land **above** it. The usable signal is the steer's direction relative to consensus, which is qualitative text and absent from a numeric table. A bias model would have been confidently wrong by roughly 25%.

So the abstention stands, but it is now a measured result rather than an assertion — and it locates precisely what the ML lens cannot see.

## 4b. Data audit — checking ADI and Deere for the same class of problem

The Hays bug prompted a systematic audit of the other two files, looking for every way data can hide: collapsed keys, unused metrics, unused `kind`s, and periods missing from the extraction that exist in the corpus.

**ADI — clean.** Each metric shows 24 rows against 22 unique periods, but the two extras are FY2020Q4/FY2021Q1 captured from two documents (the 8-K on 2020-10-24 and a later filing on 2020-11-24) with **identical values**. Zero conflicting keys. No hidden sub-period granularity. No conclusions affected.

**Deere — zero collapsed keys, but the file itself was stale.** The observations on disk had no Q4 rows at all and no guidance rows, which is what drove my original "nothing is pre-published" verdict. Both turned out to be wrong:

1. **Q4 actuals are in the corpus and the extractor already handles them** (`_period()` matches "Fourth Quarter" in the title). The file simply predated that code. Re-running the extractor yields **116 observations across 33 quarters** versus 82 across 25 on disk.
2. **Deere does publish full-year guidance** — net income ranges for FY2021, FY2022, FY2024, FY2025 and FY2026 are all in the corpus. I had used them in the anchor and driver lenses and then wrongly asserted Deere had nothing pre-published, because the *observation table* had no guidance rows.

Checking all four files against a fresh extraction found every one stale:

| Company | On disk | Fresh | Missing |
|---|---|---|---|
| deere | 82 | 116 | +34 (all Q4s) |
| analog-devices | 360 | 375 | +15 |
| home-depot | 125 | 133 | +8 |
| hays | 69 | 71 | +2 |

**The live pipeline is not affected**: `run.py` calls `<company>.extract(...)` and re-writes the observations at run time, so a real run always uses fresh data. Only consumers of the on-disk artifacts — this lens — saw stale input. All results above are re-run on regenerated files.

### Would Deere's recovered guidance have rescued it?

No, and this is worth stating precisely because it is the one place the audit could have overturned a verdict. A Q3 forecaster can only use guidance issued **at or before Q2**, so the realisation ratio has to be estimated within a single vintage:

| Guidance vintage | Samples | Realisation ratios | Dispersion |
|---|---|---|---|
| Start of year (Nov) | 3 | 1.056, 0.888, 0.958 | sd 0.085 |
| Q1 (Feb) | 1 | 0.931 | not estimable |
| **Q2 (May) — the usable one** | **1** | 0.981 | **not estimable** |
| Q3 (Aug) | 2 | 1.028, 1.005 | published after Q3 reports |

The only legally usable vintage has **n=1**. The start-of-year vintage has n=3 but sd 8.5%, which on a $4,750M guide is ±$400M of net income — roughly ±$1.50 of EPS. So completing the extraction gives Deere a much better-documented failure, not a passing model.

## 5. Results summary

| Company | Metric | Score | Gate | Beats naive | Usable |
|---|---|---|---|---|---|
| ADI | Revenue | 1.38% | 2% | ✓ | **$4,004M** |
| ADI | Adjusted EPS | 3.44% | 5% | ✓ | **$3.49** |
| ADI | Adjusted gross margin | 0.89pp | 1.0pp | ✓ | **73.29%** |
| Deere | Net sales & revenues | 7.26% | 2% | ✓ (barely) | abstained |
| Deere | Diluted EPS | 24.25% | 5% | ✗ | abstained |
| Deere | PPA operating profit | 24.19% | 10% | ✓ | abstained |
| **Hays** | **Net fees** | **1.52%** | 2% | ✓ (naive 15.4%) | **£891.8m** |
| Hays | Pre-exc operating profit | n/a | 10% | — | abstained |
| Hays | Pre-exc basic EPS | n/a | 10% | — | abstained |

**4 usable of 9.** Combined with Home Depot's 3 of 3, the ML lens covers **7 of the 12 challenge metrics**, and every one rests on a model whose main input was published before the company reports.

### The generalisable finding

Across four companies, ML lens accuracy tracked one variable almost perfectly — **how much of the answer is published before the company reports**:

```
HD net sales   category level published 4 days early     -> 0.40%  PASS
ADI revenue    guidance published a quarter early        -> 1.45%  PASS
HAS net fees   3 of 4 quarters already disclosed         -> 1.52%  PASS
DE  revenue    nothing published                         -> 8.1% floor    FAIL
HAS op profit  nothing published, n=7 annual             -> abstain       FAIL
```

Model family, feature engineering and ensembling moved results by tenths of a percent. Access to pre-published information moved them by an order of magnitude. **The lesson from the HD run replicated exactly** — and Hays turned out to sit on the passing side of that line once the data was read correctly.

---

## 6. Known weaknesses

- **ADI walk-forward n=13**, starting FY2023Q1 (earlier quarters are consumed as training). Small, though the ablation shows the result is estimator-robust.
- **The ADI realisation ratio assumes the guidance regime is stable.** If ADI changed its guidance philosophy — guiding more conservatively or more aggressively — the historical ratio would mislead, and the model has no way to detect that from numbers alone.
- **ADI adj gross margin is blind to a known one-off** (§2). The numeric table cannot represent "this benefit will not repeat"; only the transcript can.
- **COVID exclusion (FY2020–21) is a judgement call** applied uniformly. For ADI it removes the semiconductor whipsaw; for Deere it thins an already-thin sample.
- **Deere's intrinsic floors rest on n=4–5 ratios**, so the floor estimates themselves are imprecise — but they exceed the gates by 4–10×, far beyond what sampling error could close.
- **Hays net fees rests on n=4 walk-forward years**, two of which needed an imputed quarter. FY2026's own Q1 is imputed (via a +1pp LFL bridge that is exactly constant across the other three quarters, but is still an imputation).
- **The Hays quarter recovery assumes the publication calendar is fixed** (Oct/Jan/Apr/Jul). It has held for every update in the corpus, but a rescheduled update would be mis-assigned.
- **The £15m disposal adjustment is a single disclosed figure** taken at face value; if the reported continuing-operations restatement differs, the error flows straight through.
- **I found the loader bug only because it was questioned.** The same class of silent key collision could exist in any extraction where `period` is not unique; the strict loader now catches it, but it was caught by challenge, not by a test.

## 7. Reproduction

```bash
.venv/bin/python -m forecast.ml_panel      # all three companies, gates, diagnostics
```

`RANDOM_STATE = 26`. The guidance-realisation and intrinsic-floor computations have no random component and are exactly reproducible; only the (unselected) history-framing ensembles use randomness.
