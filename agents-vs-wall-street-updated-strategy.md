# Agents vs Wall Street — Updated Autonomous Forecasting Strategy

## Executive Summary

The hackathon setup changes the strategy in an important way:

- OpenStocks does **not** provide the Wall Street benchmark forecast.
- The benchmark is frozen internally and revealed only for scoring.
- There are **4 companies × 3 metrics = 12 equally weighted prediction targets**.
- The system therefore needs to reconstruct the market view itself, build an independent fundamental forecast, and use external probabilistic signals where they genuinely help.

The strongest architecture is:

> **Three independent forecasting engines — reconstructed Street, autonomous fundamental research, and prediction-market / macro signals — combined by a meta-forecaster.**

The objective is:

> **Where is the hidden Wall Street benchmark likely to be wrong, why, and how much confidence do we have in moving away from it?**

---

# 1. Challenge Structure

## Home Depot (HD) · FY2026 Q2

```text
Net sales · USDm
Adjusted diluted EPS · USD/share
Comparable sales, total company · %
```

## Analog Devices (ADI) · FY2026 Q3

```text
Revenue · USDm
Adjusted diluted EPS · USD/share
Adjusted gross margin · %
```

## Hays plc (LSE: HAS) · FY2026

```text
Net fees · GBPm
Pre-exceptional basic EPS · pence
Pre-exceptional operating profit · GBPm
```

## Deere & Company (DE) · FY2026 Q3

```text
Worldwide net sales and revenues · USDm
Diluted EPS (GAAP) · USD/share
Production & Precision Ag operating profit · USDm
```

There are **12 total metrics** and each one matters equally.

Research effort should therefore be allocated by expected edge, not company prestige:

\[
ResearchPriority_m
\approx
P(beat\ Street_m)
\times
ExpectedEdge_m
\times
Confidence_m
\]

---

# 2. Revised Core Architecture

The benchmark is hidden, so the system should build three independent views:

```text
                        TARGET METRIC
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   RECONSTRUCTED         FUNDAMENTAL        PREDICTION-
   STREET MODEL          RESEARCH MODEL     MARKET MODEL
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                      META-FORECASTER
                             │
                             ▼
                       FINAL NUMBER
```

---

# 3. Engine A — Reconstructed Street Model

The first job is to estimate what Wall Street itself is likely forecasting.

Collect:

```text
Individual analyst estimates
Public consensus estimates
Company-published consensus
Broker revisions
Estimate timestamps
High / low / median
Analyst identity
Historical analyst accuracy
Historical analyst bias
```

The goal is:

> **Reconstruct the benchmark before trying to beat it.**

---

# 4. Find the Best Analyst, Not the Biggest Bank

Do not simply take Goldman, Morgan Stanley, JPMorgan, BofA, or UBS because they are prominent.

Ask:

> **Who has the strongest historical information advantage for this exact company × metric × horizon?**

Hierarchy:

```text
Exact company × exact metric
        ↓
Company × related metric
        ↓
Sector × exact metric
        ↓
Company overall
        ↓
Sector overall
```

The best analyst can differ by metric.

---

# 5. Analyst Reliability Engine

For analyst \(i\), company \(c\), metric \(m\), period \(t\):

\[
e_{i,c,m,t}
=
Forecast_{i,c,m,t}
-
Actual_{c,m,t}
\]

Track:

```text
Mean absolute error
Median absolute error
Mean signed error
Recency-weighted error
Beat-consensus frequency
Surprise-direction accuracy
Forecast staleness
Distance from consensus
Accuracy when contrarian
Observation count
Company-specific accuracy
Metric-specific accuracy
Sector-specific accuracy
```

---

# 6. Bias Correction

Do not automatically remove inaccurate analysts.

A predictably biased analyst may still be useful:

\[
AdjustedForecast_i
=
Forecast_i
-
\widehat{Bias_i}
\]

The important distinction is:

```text
Randomly wrong
vs
Predictably wrong
```

Predictable bias can be corrected.

---

# 7. Reliability Weighting

Simple baseline:

\[
w_i
=
\frac{1}{MAE_i+\epsilon}
\]

Then:

\[
StreetEstimate^*
=
\frac{\sum_i w_i \cdot AdjustedForecast_i}{\sum_i w_i}
\]

Apply recency decay and staleness penalties.

Complex weighting only survives if it improves walk-forward performance.

---

# 8. Analyst Independence / Anti-Herding

Track analysts who repeatedly deviate from consensus and are right when they do.

Potential score:

```text
Distance from consensus
× Correct surprise direction
× Magnitude of eventual surprise
× Historical repeatability
```

This becomes an **Independent Alpha Score**.

---

# 9. Four Street Reconstructions

Backtest:

### A. Public consensus
Baseline.

### B. Trimmed consensus
Remove or down-weight historically poor analysts.

### C. Accuracy-weighted consensus
Weight analysts by historical skill.

### D. Bias-corrected reliability consensus
Correct bias, apply reliability, recency, staleness, and independence.

The best out-of-sample version becomes the model's estimate of the hidden benchmark.

---

# 10. Engine B — Autonomous Fundamental Research

Input:

```text
Company
Target metric
Report period
Estimated Street benchmark
Research budget
```

The system should answer:

```text
1. What drives this exact metric?
2. Which drivers matter most?
3. Where is uncertainty concentrated?
4. Which unknown is worth researching next?
5. Which source can best resolve it?
6. Does the evidence change the forecast?
7. What would prove the current thesis wrong?
8. When should research stop?
```

---

# 11. Autonomous Research Loop

```text
Build metric driver model
        ↓
Identify biggest uncertainty
        ↓
Generate research questions
        ↓
Rank by information value
        ↓
Research top question
        ↓
Verify source + timestamp
        ↓
Update evidence ledger
        ↓
Update driver estimate
        ↓
Rebuild forecast
        ↓
Run skeptic
        ↓
Check convergence
        ↓
Continue OR stop
```

Research priority:

\[
ResearchPriority
=
DriverImportance
\times
CurrentUncertainty
\times
ExpectedSourceQuality
\times
PotentialForecastImpact
\div
ResearchCost
\]

---

# 12. Evidence Ledger

Every forecast-changing claim should become structured evidence:

```json
{
  "company": "ADI",
  "metric": "adjusted_gross_margin",
  "driver": "product_mix",
  "claim": "industrial mix improving",
  "direction": "positive",
  "confidence": 0.79,
  "published_at": "2026-08-12",
  "source_type": "peer_earnings",
  "source": "...",
  "financial_effect": "+30 bps gross margin"
}
```

Store source, timestamp, driver, direction, magnitude, confidence, financial effect, and contradicting evidence.

---

# 13. Competing Hypotheses

Do not let the system build one story.

```text
H1 — Street approximately right
Probability: 40%

H2 — Upside scenario
Probability: 45%

H3 — Downside scenario
Probability: 15%
```

Every new source should update the hypotheses.

---

# 14. Adversarial Research

After a preferred thesis forms, run a skeptic:

> **Assume our current forecast is wrong. Find the strongest point-in-time evidence that explains why.**

Then reconcile:

```text
Main thesis
↓
Adversarial evidence
↓
Revised thesis
↓
Updated forecast
```

---

# 15. Engine C — Numinous / Polymarket

Prediction-market data should be treated as a **macro/event prior**, not a direct EPS model.

Potentially useful:

```text
Fed decision probabilities
Recession probabilities
Tariff outcomes
Election outcomes
Geopolitical events
Commodity-linked outcomes
Crypto-market regime
```

Examples:

```text
Higher recession probability
→ weaker housing activity
→ Home Depot comparable-sales pressure
```

```text
Higher rate-cut probability
→ housing affordability improves
→ potential Home Depot demand benefit
```

```text
Tariff probability
→ Deere demand / cost / margin implications
```

Use Numinous/Polymarket only when the causal chain is economically meaningful.

---

# 16. Meta-Forecaster

Combine:

```text
Reconstructed Street estimate
Fundamental research estimate
Prediction-market / macro adjustment
```

Simple form:

\[
Final
=
w_s Street^*
+
w_f Fundamental
+
w_p PredictionMarket
\]

Weights depend on historical performance and current confidence.

---

# 17. Metric-Specific Research > Company-Level Research

Each of the 12 metrics should have its own:

```text
Driver graph
Analyst leaderboard
Research queue
Evidence ledger
Confidence score
```

For example:

```text
ADI revenue
≠
ADI gross margin
≠
ADI EPS
```

The best analyst and best data source can differ by metric.

---

# 18. Home Depot Strategy

### Targets

```text
Net sales
Adjusted diluted EPS
Comparable sales
```

### Core model

Comparable sales is likely the key operating variable:

```text
Comparable sales
↓
Net sales
↓
Gross profit
↓
Operating income
↓
Adjusted EPS
```

### Research drivers

```text
Existing-home sales
Housing turnover
Mortgage rates
Repair/remodel spending
Consumer confidence
Pro vs DIY demand
Weather
Store count
Lowe's read-through
Card-spend / retail proxies
```

Potential edge:

> Treat HD as a housing/home-improvement nowcasting problem, not generic retail.

---

# 19. Analog Devices Strategy

### Targets

```text
Revenue
Adjusted diluted EPS
Adjusted gross margin
```

### Core question

Where inside or outside management's range will the quarter land?

### Research drivers

```text
Industrial semiconductor recovery
Automotive demand
Inventory normalization
Utilization
Pricing
Product mix
China
Bookings
Distributor inventory
Texas Instruments read-through
NXP read-through
STMicro read-through
```

Potential edge:

> Gross margin may offer more differentiation than headline revenue/EPS.

---

# 20. Hays plc Strategy

### Targets

```text
Net fees
Pre-exceptional basic EPS
Pre-exceptional operating profit
```

### Core opportunity

Hays is likely the strongest candidate for the **Analyst Reliability Engine**.

Attempt to identify:

```text
Analyst
Broker
Current estimate
Historical estimate
Historical forecast error
Bias
Revision timing
```

Then compare:

```text
Published consensus
vs
Accuracy-weighted consensus
vs
Bias-corrected consensus
```

### Research drivers

```text
UK hiring
Germany hiring
Australia hiring
Temp vs permanent hiring
Recruiter headcount
Fee rates
Wage inflation
Cost reductions
Operating leverage
```

---

# 21. Deere Strategy

### Targets

```text
Worldwide net sales and revenues
Diluted EPS
Production & Precision Ag operating profit
```

### Core model

Macro + farm economics + segment operating leverage.

### Research drivers

```text
Corn prices
Soybean prices
Wheat prices
Farmer income
Farm balance sheets
Equipment inventory
Dealer commentary
Large-ag demand
Interest rates
Tariffs
Production costs
Pricing
Competitor results
```

Potential edge:

> Production & Precision Ag operating profit may be more forecastable from segment-specific drivers than from generic Deere EPS analysis.

---

# 22. Point-in-Time Integrity

Every historical test must obey a strict:

```text
knowledge_cutoff
```

Nothing released after the simulated prediction time may enter:

```text
Analyst revisions
Peer earnings
Macro data
Alternative data
Research documents
```

---

# 23. Walk-Forward Backtesting

Do not randomly split financial time series.

Use walk-forward evaluation:

```text
Train through Q4
Predict Q1

Train through Q1
Predict Q2

Train through Q2
Predict Q3
```

For each metric store:

```text
Street proxy
Fundamental forecast
Prediction-market adjustment
Final forecast
Actual
Absolute error
Street-proxy error
```

Measure:

```text
Did we beat reconstructed Street?
How often?
By how much?
Which layer added alpha?
```

---

# 24. Ablation Testing

Test:

```text
A — Public consensus only
B — Reconstructed analyst consensus
C — + Fundamental driver model
D — + Peer/supplier/customer research
E — + Autonomous research loop
F — + Prediction markets
G — + Adversarial critic
```

Keep only components that improve historical performance.

---

# 25. Research Stopping Rule

Stop when:

```text
Major drivers covered
Forecast stable across iterations
Recent research no longer moves estimate
Expected value of next query is low
Research budget exhausted
```

Conceptually:

\[
|\hat{y}_t-\hat{y}_{t-1}|<\epsilon
\]

for several iterations.

---

# 26. UI

For each metric:

```text
HOME DEPOT — COMPARABLE SALES

Hidden Street proxy:     +1.1%
System forecast:         +1.8%
Difference:              +0.7pp
Confidence:              72%
```

Then:

```text
WHY WE DISAGREE

Housing turnover          +0.3pp
Pro demand                +0.4pp
Weather                   +0.2pp
DIY weakness              -0.2pp
```

And:

```text
RESEARCH STATUS

✓ Housing data
✓ Lowe's read-through
✓ Mortgage-rate impact
✓ Analyst revisions
✓ Weather
✓ Consumer spending

Next question:
"Is Pro demand materially stronger than DIY?"

Expected impact: HIGH
```

---

# 27. Full Architecture

```text
                    COMPANY × TARGET METRIC
                              │
                              ▼
                   RECONSTRUCT STREET VIEW
                              │
                   Analyst Reliability Engine
                              │
                              ▼
                      STREET ESTIMATE*
                              │
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
 FUNDAMENTAL MODEL      AUTONOMOUS RESEARCH    PREDICTION MARKETS
 Driver graph           Information-value loop Macro/event priors
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              ▼
                       EVIDENCE LEDGER
                              │
                              ▼
                  COMPETING HYPOTHESES
                              │
                              ▼
                  DETERMINISTIC MODEL
                              │
                              ▼
                   ADVERSARIAL CRITIC
                              │
                              ▼
                     META-FORECASTER
                              │
                              ▼
                       FINAL NUMBER
```

---

# 28. Product Thesis

> **An autonomous financial scientist that reconstructs the hidden Street benchmark, finds the most informative analysts and data sources for each metric, discovers the company's underlying earnings drivers, researches the highest-value unknowns, challenges its own thesis, and outputs a calibrated forecast designed specifically to beat consensus.**

---

# 29. Hackathon Priorities

1. **Reconstruct the hidden Street benchmark**
2. **Find the best analyst by company × metric, not prestige**
3. **Build metric-specific driver models**
4. **Use autonomous research on the highest-value uncertainty**
5. **Exploit peer / supplier / customer read-through**
6. **Use Numinous / Polymarket for economically relevant macro priors**
7. **Keep strict point-in-time integrity**
8. **Run walk-forward backtests**
9. **Use adversarial self-critique**
10. **Expose the full research → calculation trail in the UI**

The core question:

> **What does Wall Street probably believe, where is that belief wrong, and which evidence gives us enough confidence to move away from it?**
