# Fable Research — Run 1

| | |
|---|---|
| Model | Claude Fable 5 (claude-fable-5) |
| Date | 2026-08-16 (hackathon day; corpus frozen 2026-08-14) |
| Forecast file | `agent/fable-research-forecast.json` |
| Task | Predict 12 soon-to-be-reported metrics (4 companies × 3) for the Agents vs Wall Street challenge |
| Scoring | Per metric: `min(5.0, |my miss| / max(|Wall Street miss|, floor))`; floor = 0.5pp for % metrics, 0.5% of the reported value for money/EPS metrics. Beating the frozen Street benchmark ⇒ score < 1.0 |

## Method

Three lenses per metric, combined by a final positioning judgement:

1. **Fundamental model** — anchored on each company's own guidance and the frozen document corpus (`challenge/offline-data/`), built bottom-up through the P&L.
2. **Guidance-vs-actual calibration** — for serial guiders (ADI, Deere), the corpus provides every past guidance statement and every actual, so the systematic bias of management guidance is measurable and can be re-applied.
3. **Reconstructed Street view** — public consensus quotes, company-compiled consensus (Hays publishes its own), and Polymarket earnings markets as an independent crowd check. The Street view is not the forecast; it locates the benchmark my miss will be divided by, which determines how far from consensus it is rational to stand.

### Street anchor provenance (tiered by strength)

| Anchor | Value | Source | Tier |
|---|---|---|---|
| Hays net fees / op profit / EPS | £902.4m / £45.3m / 1.13p | Company-compiled consensus, haysplc.com, updated 11 Aug 2026, 9 analysts, with ranges | Hard (fetched live) |
| ADI adj EPS | $3.33 | Barchart earnings preview; corroborated by Polymarket strike 3.33 | Hard |
| Deere GAAP EPS (Q3 / FY) | $4.85 / $18.27 | Yahoo Finance earnings preview | Hard |
| HD adj EPS | $4.73 | TipRanks; corroborated by Polymarket strike 4.73 | Hard |
| Deere total revenues | ~$12.4B | Street quotes $10.8B but that is equipment net sales only (sell-side convention); added $1.59–1.66B/qtr observed financial-services+other revenues to convert to the challenge's "worldwide net sales and revenues" definition | Converted |
| ADI revenue | ~$3.94B | Reconstructed: slightly above the $3.9B guidance midpoint, where consensus sits for a serial beater (fresh post-guidance quote not found; LSEG figure in circulation was stale) | Soft |
| ADI adj gross margin | ~72.5% | Guidance-implied (CFO steer on Q2 call); analysts transcribe explicit CFO steers | Soft |
| Deere PPA op profit | ~$520M | Reconstructed from Deere's own segment guidance and phasing comments (segment consensus is paywalled) | Soft |
| HD net sales / comps | ~$47.3B / ~+1.3% | Reconstructed from FY guidance structure and Q1 print | Soft |

### Prediction-market readings (Polymarket, gamma API, 16 Aug 2026)

| Market | Strike | P(above) | Read |
|---|---|---|---|
| `adi-quarterly-earnings-nongaap-eps-08-19-2026-3pt33` | $3.33 | 94% | Beat near-priced-in; question is magnitude |
| `de-quarterly-earnings-gaap-eps-08-20-2026-4pt72` | $4.72 | 91% | Market convinced of an above-consensus print |
| `hd-quarterly-earnings-nongaap-eps-08-18-2026-4pt73` | $4.73 | 78.5% | Moderate beat expected |

No liquid market exists for Hays or for any non-EPS metric; prediction markets were therefore used only as directional confirmation of the EPS stances, never translated mechanically into point estimates.

---

## Analog Devices — FY2026 Q3 (quarter ended 1 Aug 2026, reports 19 Aug 2026)

**Forecast: Revenue $4,010M · Adjusted diluted EPS $3.48 · Adjusted gross margin 72.9%**

### Guidance anchor (Q2 FY26 8-K, 2026-05-20)
> "Revenue of $3.9 billion, +/- $100 million ... adjusted operating margin of approximately 49.0%, +/-100 bps ... adjusted EPS to be $3.30, +/-$0.15." Tax rate 12–14%.

Source: `challenge/offline-data/analog-devices/filings/2026-05-20__adi-us-20260520-q2-8k__1040581.md`

### Calibration table (built from corpus 8-Ks)

| Qtr | Rev guide mid | Actual | Beat | EPS guide | Actual | Beat | Adj GM |
|---|---|---|---|---|---|---|---|
| Q1FY25 | 2,350 | 2,423 | +3.1% | 1.53 | 1.63 | +0.10 | 68.8% |
| Q2FY25 | 2,500 | 2,640 | +5.6% | 1.68 | 1.85 | +0.17 | 69.4% |
| Q3FY25 | 2,750 | 2,880 | +4.7% | 1.92 | 2.05 | +0.13 | 69.2% |
| Q4FY25 | 3,000 | 3,076 | +2.5% | 2.22 | 2.26 | +0.04 | 69.8% |
| Q1FY26 | 3,100 | 3,160 | +1.9% | 2.29 | 2.46 | +0.17 | 71.2% |
| Q2FY26 | 3,500 | 3,623 | +3.5% | 2.88 | 3.09 | +0.21 | 73.0% |

Six consecutive beats of the revenue midpoint (mean +3.55%, last four +3.15%); EPS beats accelerating (+0.17, +0.21 the last two quarters).

### Demand and margin evidence (Q2 call, 2026-05-20)
- "Record bookings across our B2B markets"; Q2 finished above the high end of guidance; data center (>75% of comms) +90% y/y; industrial +56% y/y with lean channel inventories; CFO cites "continued strong growth" signals in the Q3 outlook.
- CFO on Q3 gross margin: assumes **~50bp decline from Q2's 73.0%** because a one-time channel-repricing benefit does not repeat → implied guide ≈ 72.5%; mix a slight tailwind; utilization neutral with factories effectively maxed (revenue upside comes via outsourcing); agreed Q3 GM is a near-term "local peak". Q2 GM itself came in "a little higher than we expected".

### Model
- **Revenue**: 3,900 × (1 + 2.8%) = **4,010**. The +2.8% sits between the recent-four mean beat (+3.15%) and the most conservative recent print (+1.9%), respecting the utilization ceiling while honoring record bookings.
- **Adj GM**: 72.5% implied guide + ~40bp habitual conservatism/mix = **72.9%**. The 0.5pp scoring floor makes any outcome in 72.4–73.4 low-risk.
- **Adj EPS** bottom-up: 4,010 × 72.9% = 2,923 gross profit; opex ~908 (guide-implied 916); adj op income ≈ 2,015 (50.2%, consistent with the +1.5–2.0pt pattern of op-margin beats); nonop 57; tax 12.4% (ADI lands at the low end of its 12–14% guide); ~490M shares → $3.50. Guide-plus-beat-pattern gives 3.30 + 0.17 = $3.47. Point: **$3.48**.

### Risk
A macro/tariff shock landing revenue at or below the midpoint would favor the Street; ADI has not missed its midpoint in six quarters, and mid-quarter conference tone (2026-06-02, in corpus) showed no deterioration.

---

## Hays plc — FY2026 (year ended 30 June 2026, reports 20 Aug 2026)

**Forecast: Net fees £888m · Pre-exceptional operating profit £46.1m · Pre-exceptional basic EPS 1.14p**

The fiscal year is complete; this is reconstruction plus a management steer, not true forecasting.

### Evidence chain
1. **Q4 FY26 trading update** (`hays/filings/2026-07-10__has-ln-20260710-q4-8k__1572805.md`):
   - "We currently expect FY26 pre-exceptional operating profit will be **at the top of the £37.0–46.0m consensus range**" (company-compiled consensus £43.5m, 10 analysts, 9 Jul).
   - Q4 net fees **−4% actual** (−5% LFL); Q3 update (2026-04-16): **−7% actual**.
   - Footnote: the six countries sold to Meraki Capital on 16 Jun 2026 (Czech Republic, Denmark, Hungary, Luxembourg, Romania, Sweden) are "**no longer considered continuing operations**"; they "contributed **c.£15m** to reported group net fees in FY26".
2. **H1 FY26 report** (2026-02-27): H1 net fees **£453.3m**; pre-ex op profit £20.1m; pre-ex basic EPS 0.46p; explicit FY26 guidance: net finance charge **c.£13m**, pre-exceptional ETR **c.45%**.
3. **FY25 results** (2025-08-21): net fees £972.4m (H1 496.0 / H2 476.4); pre-ex op profit £45.6m; pre-ex EPS 1.31p.
4. **Voting rights RNS** (2026-08-03): 1,570.25m shares ex-treasury at 31 Jul 2026; H1 arithmetic implies weighted basic shares ≈ 1.59–1.61bn.
5. **Company consensus page** (haysplc.com, updated 11 Aug 2026, 9 analysts): net fees **£902.4m** (min 894.0), op profit **£45.3m** (max 46.1), EPS **1.13p**.

### Net fees — the deliberate divergence
Reported-group basis (six countries included until disposal): H1 453.3 + Q3 ≈ 236.5×0.93 + Q4 ≈ 239.9×0.96 ≈ **£903m** — matching consensus £902.4m almost exactly. That match demonstrates the sell side is still modelling the **pre-disposal basis**: not one of nine analysts (min £894) has rebased to continuing operations.

The FY26 income statement and headline KPI table will, per Hays' own footnote and IFRS 5, present continuing operations with the six countries in discontinued and FY25 restated (~£955m comparative). Continuing-ops headline ≈ 903 − 15 = **£888m** (band 885–891).

Expected-score comparison at ~88% confidence in the continuing-ops treatment: submitting 888 dominates submitting the consensus-hugging 902 (expected metric score ≈ 0.4 vs ≈ 0.9), with a known bad tail (~3.3) if Hays headline-reports the old basis. This is the highest-conviction, highest-payoff call in the run.

### Operating profit
Steer given 10 July with the year already closed: "at the top of the £37.0–46.0m range". Companies phrase "above the range" when materially higher, so the print distribution centres just above £46.0m; consensus has converged to 45.3 with a 46.1 max. Point: **£46.1m**.

### EPS
(46.1 − 13.0 guided finance charge) × (1 − 0.45 guided ETR) = £18.2m ÷ ~1,595m shares = **1.14p**. Cross-check by halves: H1 actual 0.46p + H2 model 0.68p = 1.14p. Consensus 1.13p — fractionally below us because it embeds the lower 45.3 op profit.

---

## Deere & Company — FY2026 Q3 (quarter ended ~26 Jul 2026, reports 20 Aug 2026)

**Forecast: Worldwide net sales and revenues $12,400M · Diluted EPS (GAAP) $4.95 · Production & Precision Ag operating profit $510M**

### Quarterly actuals (corpus 8-Ks)

| $M | Q1 25 | Q2 25 | Q3 25 | Q4 25 | Q1 26 | Q2 26 |
|---|---|---|---|---|---|---|
| Net sales & revenues | 8,508 | 12,763 | **12,018** | 12,394 | 9,611 | 13,369 |
| Diluted EPS | 3.19 | 6.64 | **4.75** | 3.93 | 2.42 | 6.55 |
| PPA net sales | 3,067 | 5,230 | **4,273** | 4,740 | 3,163 | 4,503 |
| PPA op profit | 338 | 1,148 | **580** | 604 | 139 | 706 |

### FY2026 guidance (Q2 8-K + slides + call, 2026-05-21)
- Net income **$4.5–5.0B** (raised at Q1 after the Feb-2026 SCOTUS invalidation of IEEPA tariffs; maintained at Q2). ETR 24–26%.
- **PPA net sales down 5–10%** (FY25 $17,311M), **margin 11–13%**; SAT up ~15%, margin 13.5–15%; C&F up ~20%, margin 10–12%; financial services NI ~$860M.
- Phasing (call): "**slightly higher revenue in the back half** [y/y], with the **fourth quarter being higher than the third**"; "most favorable cost comparisons in the fourth quarter".
- Tariffs: FY gross exposure ~$1.2B; **~$900M net cost** in the forecast after the $272M IEEPA refund recovery booked in Q2; further accepted refund claims are possible Q3 GAAP upside.

Sources: `deere/filings/2026-05-21__de-us-20260521-q2-8k__1042167.md`, `deere/slides/2026-05-21__de-us-20260521-slide__1042212.md`, `deere/call-transcripts/2026-05-21__de-us-20260521-call-pres__1042774.md`

### Model
- Segment-guide midpoints ⇒ FY equipment ≈ $41.4B ⇒ H2 ≈ $21.65B (+3.4% y/y — matches "slightly higher"); Q3 share ~49% (Q4 > Q3) ⇒ Q3 equipment ≈ $10.6–10.8B; Street's $10.8B equipment consensus sits at the guide-top tilt, justified by Deere's beat cadence (3 of last 4).
- Financial-services + other revenues: $1,590–1,660/qtr for six quarters ⇒ Q3 ≈ $1,630M.
- **Total ≈ 10,770 + 1,630 = $12,400M** (+3.2% y/y).
- **PPA op profit**: Q3 sales ≈ $3,960M (−7% y/y, the H1 rate) × ~12.8% margin (H1 11.0%; FY guide 11–13%; the best cost comps are reserved for Q4) ≈ **$510M**; equivalently ~48% of the H2-implied profit pool.
- **EPS**: FY street $18.27 ⇒ NI ≈ $4.93B — upper half of the maintained guide, Deere's usual landing zone (FY25 printed $5.03B vs $4.75–5.25B). H2 ≈ $2.50B × ~54% Q3 share (FY25: 54.8%) ⇒ ≈ $1.33B ÷ 269.8M shares = $4.93. Bottom-up cross-check: equipment OP ≈ 1,415 × (1−25.5%) + FinSvcs ~215, ×1.05 corporate/pension net ≈ $1,340M ⇒ $4.97. Polymarket 91% above $4.72. Point: **$4.95**.

### Risk
A Q4-heavier production schedule would drag Q3 revenue toward $12.1B; further IEEPA refund recognitions could push GAAP EPS well above $5 (asymmetric upside we are partially positioned for by standing $0.10 over consensus).

---

## Home Depot — FY2026 Q2 (quarter ended ~2 Aug 2026, reports 18 Aug 2026)

**Forecast: Net sales $47,500M · Adjusted diluted EPS $4.80 · Comparable sales +1.3%**

- Q1 FY26 (8-K, 2026-05-19): sales $41.8B (+4.8%), comps +0.6% (US +0.4%, FX +55bp), adj EPS $3.43, "in line with our expectations"; FY26 guidance reaffirmed (comps flat–+2%, GAAP EPS flat–+4% from $14.23).
- The 4.2pt gap between total growth and comps is GMS (closed ~Sep 2025, annualises Q3 26) plus new stores — persists in Q2.
- Q2 FY25 base (8-K, 2025-08-19): sales $45,283M, comps +1.0% (US +1.4%), adj EPS $4.68.
- **Net sales**: 45,283 × (1 + 1.3% comp + 3.3% GMS + 0.3% stores) ≈ **$47,500M**.
- **Comps**: US demand "similar to fiscal 2025" + ~50bp FX tailwind ⇒ **+1.3%**.
- **Adj EPS**: consensus $4.73, Polymarket 78.5% above ⇒ **$4.80** (+2.6% y/y), consistent with HD's average ~$0.05 beat and the FY guide's H2 recovery shape.

---

## Where this run expects to win or lose

| Metric | Stance vs Street | Expected edge |
|---|---|---|
| Hays net fees | −£14.4m below consensus | Largest: consensus appears to be on a stale reporting basis |
| Hays op profit | +£0.8m above | Steer-literal positioning |
| ADI EPS / revenue | +$0.15 / +$70M above | Calibrated serial-beat pattern the Street under-adjusts for |
| Deere EPS | +$0.10 above | Guide-maintenance conservatism + refund skew |
| ADI GM, HD comps | +0.4pp / ≈ consensus | Floor-protected; small expected wins |
| Hays EPS, DE PPA, DE/HD revenue, HD EPS | ≈ consensus ± small | Roughly neutral; accuracy over differentiation |

Known weaknesses: the Hays basis call is binary; ADI consensus revenue was reconstructed, not observed; Deere segment consensus unobserved; no prediction-market coverage for 8 of 12 metrics.

---

## Run 1.1 addendum — driver-nowcast lens (forecast/drivers.py)

The anchor models trust management numbers; the driver lens does not. It maps high-signal external metrics published **after** the companies last guided (all guided 19–21 May 2026) through explicit units→dollars elasticity chains, each **calibrated on the latest closed quarter** where drivers and outcome are both known, with the unexplained residual carried forward at half weight. Post-guidance facts used (snapshot `forecast/data/drivers/2026-08-16.json`):

| Published | Driver | Reading |
|---|---|---|
| 11 Aug | AEM US ag tractor / combine retail units, July | −10.9% / −5.3% y/y (June combines ~+1%; Apr R3M 100+hp −14%, 4WD −24%) |
| 14 Aug | Census NAICS 444 building-materials retail, July | +5.9% y/y, accelerating vs +4.6% YTD |
| 22 Jul | TXN June quarter + Sept guide | analog +26% y/y; guide +8.1% q/q vs ADI's implied +7.6% |

Lens comparison (inverse-variance reconciliation):

| Target | Anchor | Driver | Reconciled | Action |
|---|---|---|---|---|
| DE PPA op profit | 510 | 513 (units −11 ×0.55 + RoW −0.5 + price +1.75 + FX +2.5 + Q2 residual −2.55 → sales ≈ 4,047 × 12.6%) | 511 | keep **510** |
| ADI revenue | 4,010 | 4,009 (peer-confirmed +2.8% beat of guide mid) | 4,009 | keep **4,010** |
| HD comps | +1.3 | +1.9 (category +5.2% − 3.3pp Q1-calibrated comp wedge) | +1.44 | **raise final to +1.4** |

The convergence is the finding: two independent methods (management-anchor calibration vs external units/category data) land within 1% of each other on Deere and ADI, which is precisely the cross-validation the three-lens design was meant to produce. The single divergence — HD comps — comes from genuinely new information (July category acceleration published 14 Aug), so the final moves toward it.
