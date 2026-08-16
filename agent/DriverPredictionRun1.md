# Driver Prediction — Run 1

| | |
|---|---|
| Model | Claude Fable 5 (claude-fable-5) |
| Date | 2026-08-16 |
| Forecast file | `agent/driver-prediction-forecast.json` |
| Code | `forecast/drivers.py` (three primary chains); extended chains documented here |
| Data snapshot | `forecast/data/drivers/2026-08-16.json` (point-in-time, sources + publish dates) |
| Companion run | `agent/fable-research-forecast.json` / `FableResearchRun1.md` (anchor lens) |

## Philosophy

The anchor lens trusts management numbers (guidance, steers) and calibrates their bias. This run deliberately does not. It predicts each metric from **high-signal external data through explicit units→dollars chains**: interest rates and macro conditions act on demand, demand shows up in *measurable physical quantities* (tractors retailed, category retail dollars, peer semiconductor revenue), and those quantities map into segment revenue, margin, and EPS.

Two design rules:

1. **Realized downstream data beats upstream rates at this horizon.** All three fiscal quarters are already over. Rates have already done their work through demand, and the result is *measured*: AEM counted the tractors, Census counted the building-materials dollars, TXN reported the analog cycle. Using rates directly would be re-deriving what the units data already states. (Rates would matter for a longer-horizon forecast, e.g. FY2027.)
2. **Every chain is calibrated on the latest closed quarter, residual carried at half weight.** Raw elasticities at quarterly frequency are unstable (shipments ≠ retail because of dealer inventory; category sales ≠ comps because of scope). So each chain is first run on the last quarter where both drivers and the outcome are known; the unexplained residual is carried forward shrunk by half — the standing compromise between "structural" and "one-off".

The information edge over the anchor lens: ADI, DE and HD all last guided **19–21 May 2026**. Every driver below was published **after** that and covers the tail of the quarters being reported. Guidance cannot contain this; the actuals will.

## Driver observations (all post-guidance)

| Published | Driver | Reading | Source |
|---|---|---|---|
| 2026-08-11 | AEM US ag tractor retail units, July | **−10.9% y/y** | globenewswire.com (AEM July 2026 report) |
| 2026-08-11 | AEM US combine retail units, July | **−5.3% y/y** | same |
| 2026-08-11 | AEM Canada 4WD units, YTD | −22.6% y/y | aem.org |
| 2026-07-23 | AEM US/CA combine units, June | ~+1% y/y ("slight increase") | drgnews.com |
| 2026-05-21 | US/CA large-ag retail, Apr R3M (in-corpus baseline) | 100+hp −14%, 4WD −24%, combines −5% | Deere Q2 slide, corpus |
| 2026-08-14 | Census NAICS 444 building-materials retail, July | **+5.9% y/y** ($45.701B vs $43.162B), accelerating vs +4.6% YTD | census.gov / FRED RSBMGESD |
| 2026-07-22 | TXN June-quarter print | revenue +23% y/y, **analog +26%**, industrial/DC/auto led | TXN 8-K |
| 2026-07-22 | TXN Sept-quarter guide | **+8.1% q/q** at midpoint — above ADI's implied +7.6% | TXN 8-K |

## The chains, metric by metric

### Deere — Production & Precision Ag operating profit → $513M
Quarter-window NA large-ag units centred at **−11 ±4** (Apr window −14/−24 improving to July's −10.9 tractors / −5.3 combines; June combines ~+1).

```
PPA sales y/y = 0.55·(−11) NA units + 0.45·(−1) RoW + 1.75 price + 2.5 FX + (−2.55) residual
             = −5.3%  →  4,273 × 0.947 ≈ $4,047M
PPA op profit = 4,047 × 12.6% margin (H1 11.0%; best cost comps reserved for Q4) ≈ $513M
```
Calibration: raw chain on Q2 gave −9.3% vs reported −14.4% → −5.1pp shipment residual (Deere shipped below retail), carried at half = −2.55pp.

### Deere — Worldwide net sales and revenues → $12,470M
Same construction for the other segments, each calibrated on Q2:

| Segment | Units term | Price | FX | Q2 residual ÷2 | y/y | Q3-25 base | Q3-26e |
|---|---|---|---|---|---|---|---|
| PPA | 0.55·(−11) + 0.45·(−1) | +1.75 | +2.5 | −2.55 | −5.3% | 4,273 | 4,047 |
| SAT | 0.7·(−10) + 0.3·(+1) | +1.75 | +2.0 | **+7.9** | +5.0% | 3,025 | 3,175 |
| C&F | +4 (industry: constr. +5, roadbuilding +10, forestry −5) | +1.75 | +2.0 | **+10.6** | +18.4% | 3,059 | 3,622 |

SAT's and C&F's large positive residuals are the production-normalization effect (FY25 underproduction → FY26 shipments outgrow retail); half-weighting them is the conservative choice. Equipment 10,844 + financial-services & other 1,630 (six-quarter range 1,590–1,660) = **$12,474M → 12,470**.

### Deere — Diluted EPS (GAAP) → $5.00
```
Segment OP: 513 (PPA) + 508 (SAT: 3,175 × 16.0%, the Q3-25 margin) + 398 (C&F: 3,622 × 11.0%) = 1,419
NI = (1,419 × 0.755 tax + 215 FinSvcs) × 1.05 corporate/pension multiplier   [calibrated 1.03–1.085 over 4 qtrs]
   = 1,350  →  ÷ 269.8M shares = $5.00
```

### Home Depot — Comparable sales → +1.9%
```
comps = category − wedge = +5.2% − 3.3pp = +1.9%
```
Category: NAICS 444 quarter window ~+5.2% (July +5.9 accelerating vs +4.6 YTD). Wedge calibrated on Q1 FY26 (category +3.9 vs printed comps +0.6 = −3.3pp; scope + pro-distributor inflation), carried at **full** weight because it is structural, not transient.

### Home Depot — Net sales → $47,770M
```
45,283 × (1 + 1.9 comps + 3.3 GMS inorganic + 0.3 new stores) = 47,774
```
The 3.3pp GMS term is observed, not assumed: Q1's total growth (+4.8%) minus Q1's comps (+0.6%) minus stores.

### Home Depot — Adjusted diluted EPS → $4.74
Sales-to-EPS wedge calibrated on Q1 (sales +4.8% vs adj EPS −3.7% → −8.5pp from GMS margin dilution, acquisition interest, mix), carried at half weight:
```
EPS growth = +5.5% − 4.25pp = +1.25%  →  4.68 × 1.0125 = $4.74
```

### ADI — Revenue → $4,009M
Peer read-through instead of guidance trust: TXN's overlapping quarter ran analog +26% y/y and guided the next quarter +8.1% q/q, above the +7.6% ADI's own outlook implies — the cycle steepened after ADI last spoke. Beat term +2.8 ±1.2 on the $3,900M base → **$4,009M**.

### ADI — Adjusted diluted EPS → $3.51
```
ΔRev q/q = 4,009 − 3,623 = +386
adj OI  = 1,774 + 0.65 × 386 = 2,025      [incrementals ran ~80% last 2 qtrs, structural ~50% → half-shrunk 65%]
EPS     = (2,025 − 57 nonop) × (1 − 12.5%) ÷ 490M = $3.51
```

### ADI — Adjusted gross margin → 72.9% (fallback)
The one metric where external data adds little: utilization is physically maxed, and the mix tailwind (data center above corporate-average GM) gives direction but not magnitude. Carries the anchor-lens value, flagged.

### Hays — 888 / 46.1 / 1.14 (no nowcast possible)
The year ended 30 June. Net fees (£888m) is itself the most driver-pure number in either file — pure arithmetic on disclosed actuals, zero management opinion. Operating profit and EPS depend on a post-year-end company steer plus guided finance charge and tax rate; no external driver is fresher than that, so they carry over, flagged.

## Standalone driver numbers vs the anchor lens

| Metric | Driver run | Anchor run | Spread | Read |
|---|---|---|---|---|
| ADI revenue | 4,009 | 4,010 | ~0 | independent convergence |
| ADI adj EPS | 3.51 | 3.48 | +0.03 | converged; driver slightly hotter on incrementals |
| ADI adj GM | 72.9 | 72.9 | 0 | shared (fallback) |
| DE revenues | 12,470 | 12,400 | +0.6% | driver hotter on SAT/C&F normalization |
| DE GAAP EPS | 5.00 | 4.95 | +0.05 | both above Street 4.85; market-implied 5.19 |
| DE PPA OP | 513 | 510 | +3 | independent convergence |
| HD net sales | 47,770 | 47,500 | +0.6% | driver comps flow through |
| HD adj EPS | 4.74 | 4.80 | −0.06 | Q1 wedge tempers the driver's own sales strength |
| HD comps | +1.9 | +1.3 | +0.6pp | the one real divergence — July category acceleration |
| Hays (×3) | 888 / 46.1 / 1.14 | same | 0 | reconstruction / carried |

## Known weaknesses

- SAT and C&F chains are residual-dominated: the half-weighted production-normalization terms (+7.9pp, +10.6pp) contribute more than the unit terms. If normalization completed in H1, both segments print below this run.
- The NAICS 444 category includes commodity-price inflation (lumber, copper) that HD partly passes through but partly comps against; the wedge is calibrated on one quarter only.
- AEM July tractor total is small-unit-weighted; the 100+hp July split was not retrievable (source pages 403/429), so the large-ag window value (−11) interpolates Apr R3M and July aggregates.
- ADI incremental margin is half-shrunk from an unusually hot two-quarter run; a mix-only quarter would land EPS nearer the anchor's 3.48.
- No driver exists for ADI GM, Hays OP, or Hays EPS — flagged as fallbacks rather than silently blended.
