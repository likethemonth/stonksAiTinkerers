# Agents vs Wall Street — Standalone Hackathon Strategy

## Overview

This document assumes **no prior context**.

The challenge is to build an AI system that forecasts real company earnings and operating metrics, then compares those forecasts against a hidden Wall Street benchmark.

The key strategic fact is:

> **The Wall Street benchmark is not given to participants.**

So the problem is not simply "take consensus and improve it."

The system must do two things:

1. **Reconstruct what Wall Street is likely forecasting**
2. **Build an independent forecast that can beat it**

There are four companies and three target metrics per company, for **12 total prediction targets**.

The strongest architecture is therefore:

> **A self-driving financial research system with three independent forecasting engines:**
>
> 1. **Reconstructed Street**
> 2. **Autonomous Fundamental Research**
> 3. **Prediction-Market / Macro Signals**
>
> These are combined by a **meta-forecaster** into the final prediction.

---

# 1. Challenge Targets

## 01 — Home Depot (HD) · FY2026 Q2

Targets:

```text
Net sales · USDm
Adjusted diluted EPS · USD/share
Comparable sales, total company · %
```

## 02 — Analog Devices (ADI) · FY2026 Q3

Targets:

```text
Revenue · USDm
Adjusted diluted EPS · USD/share
Adjusted gross margin · %
```

## 03 — Hays plc (LSE: HAS) · FY2026

Targets:

```text
Net fees · GBPm
Pre-exceptional basic EPS · pence
Pre-exceptional operating profit · GBPm
```

## 04 — Deere & Company (DE) · FY2026 Q3

Targets:

```text
Worldwide net sales and revenues · USDm
Diluted EPS (GAAP) · USD/share
Production & Precision Ag operating profit · USDm
```

All 12 metrics matter.

That means research effort should be allocated by **expected edge**, not by which company is most famous.

A useful prioritization rule is:

\[
ResearchPriority_m
\approx
P(\text{beat Street}_m)
\times
ExpectedEdge_m
\times
Confidence_m
\]

---

# 2. Core Problem

The hidden benchmark creates a two-stage problem.

## Stage A — Estimate the Street

What does Wall Street probably believe for this metric?

## Stage B — Estimate Reality

What do we independently think the reported number will be?

Then:

\[
ExpectedEdge
=
Forecast_{system}
-
Forecast_{street}
\]

The system should move away from the estimated Street number only when evidence is strong enough.

---

# 3. Full System Architecture

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

# 4. Engine A — Reconstruct the Street

Because the benchmark is hidden, the first forecasting task is to estimate what Wall Street itself is likely predicting.

Useful inputs:

```text
Public consensus estimates
Individual analyst estimates
Company-published analyst consensus
Broker revisions
High / low / median estimates
Forecast timestamps
Analyst identity
Historical analyst accuracy
Historical analyst bias
```

The objective is:

> **Reconstruct the hidden benchmark as accurately as possible before trying to beat it.**

---

# 5. Do Not Just Pick Famous Banks

Do not assume the best forecast comes from:

```text
Goldman Sachs
Morgan Stanley
JPMorgan
BofA
UBS
```

The important question is:

> **Who has historically been best for this exact company × metric × horizon?**

The ranking hierarchy should be:

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

For example:

- The best ADI EPS analyst may not be the best ADI gross-margin analyst.
- The best Deere analyst may be average on group EPS but excellent on Production & Precision Ag.
- The best Hays forecaster may be especially strong on net fees rather than EPS.

Metric-specific skill matters.

---

# 6. Analyst Reliability Engine

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
Forecast age
Revision age
Distance from consensus
Accuracy when contrarian
Observation count
Company-specific accuracy
Metric-specific accuracy
Sector-specific accuracy
```

Example:

```text
Analyst A × Hays operating profit

Historical observations:      8
MAE:                          4.1%
Signed bias:                 +2.0%
Beat consensus:               6 / 8
Correct surprise direction:   7 / 8
Recent performance:           Strong
```

---

# 7. Bias Correction

Do not automatically remove analysts who are consistently wrong.

There is a difference between:

```text
Randomly wrong
```

and:

```text
Predictably wrong
```

Example:

```text
Forecast     Actual     Error

1.20         1.10       +0.10
1.35         1.26       +0.09
1.48         1.39       +0.09
1.61         1.51       +0.10
```

This analyst is consistently optimistic.

Correct the bias:

\[
AdjustedForecast_i
=
Forecast_i
-
\widehat{Bias_i}
\]

A forecast of 1.75 from an analyst with a persistent +0.095 bias becomes approximately:

```text
1.655
```

---

# 8. Reliability Weighting

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
\frac{\sum_i w_i \cdot AdjustedForecast_i}
{\sum_i w_i}
\]

Apply recency decay:

```text
Most recent quarter      1.00
2 quarters ago           0.80
3 quarters ago           0.64
4 quarters ago           0.51
```

Also penalize stale forecasts.

---

# 9. Analyst Independence / Anti-Herding

An analyst who always sits next to consensus contributes little new information.

Track:

```text
Distance from consensus
× Correct surprise direction
× Magnitude of eventual surprise
× Historical repeatability
```

Example:

```text
Consensus: 1.00
Analyst A: 1.01
Actual:    1.15
```

versus:

```text
Consensus: 1.00
Analyst B: 1.12
Actual:    1.15
```

Analyst B added much more independent information.

Create an **Independent Alpha Score**.

---

# 10. Forecast Staleness

A forecast issued six weeks ago should not necessarily carry the same weight as one revised yesterday.

Store:

```text
forecast_timestamp
revision_timestamp
age_at_prediction
important_events_since_forecast
```

Potential stale-making events:

```text
Management guidance
Peer earnings
Supplier earnings
Macro releases
Commodity moves
Regulatory changes
Product launches
Industry-data releases
```

---

# 11. Four Street Reconstructions

Backtest four versions:

## A. Public Consensus

Baseline.

## B. Trimmed Consensus

Down-weight or remove historically poor analysts.

## C. Accuracy-Weighted Consensus

Better historical forecasters receive more weight.

## D. Bias-Corrected Reliability Consensus

Correct bias, then apply:

```text
Accuracy
Recency
Staleness
Independence
Metric-specific skill
```

The best out-of-sample version becomes the system's estimate of the hidden Street benchmark.

---

# 12. Engine B — Autonomous Fundamental Research

This is the central self-driving research system.

Input:

```text
Company
Target metric
Reporting period
Estimated Street benchmark
Research budget
```

Its job is to answer:

```text
1. What drives this exact metric?
2. Which drivers matter most?
3. Where is uncertainty concentrated?
4. What is the highest-value unanswered question?
5. Which source can resolve it?
6. Does that evidence change the forecast?
7. What evidence would prove the current thesis wrong?
8. When should research stop?
```

---

# 13. Autonomous Research Loop

```text
Build metric driver model
        ↓
Identify biggest uncertainty
        ↓
Generate research questions
        ↓
Rank by expected information value
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

Pseudo-code:

```python
while not converged:

    driver = highest_value_uncertainty()

    questions = generate_questions(driver)

    question = rank_by_information_value(questions)[0]

    evidence = research(question)

    verified = verify_and_timestamp(evidence)

    update_evidence_ledger(verified)

    update_driver_model()

    rebuild_forecast()

    run_adversarial_critic()

    evaluate_stopping_rule()
```

---

# 14. Expected Information Value

The system should not research everything.

It should research what is most likely to change the forecast.

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

This is what makes the system genuinely self-directed.

---

# 15. Evidence Ledger

Every material claim should become structured evidence.

Example:

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

Store:

```text
Source
Publication timestamp
Affected metric
Affected driver
Direction
Magnitude
Confidence
Financial impact
Contradicting evidence
```

---

# 16. Competing Hypotheses

The system should never maintain only one story.

Example:

```text
H1 — Street approximately right
Probability: 40%

H2 — Upside scenario
Probability: 45%

H3 — Downside scenario
Probability: 15%
```

Every new source should update these hypotheses.

The goal is to avoid confirmation bias.

---

# 17. Adversarial Research

Once the main agent prefers one thesis, run a skeptic.

Instruction:

> **Assume our current forecast is wrong. Find the strongest point-in-time evidence that explains why.**

Then:

```text
Main thesis
↓
Adversarial evidence
↓
Reconciliation
↓
Updated forecast
```

---

# 18. Engine C — Numinous / Polymarket

Prediction-market data should be used as a **macro/event prior**, not as a direct earnings forecast.

Potentially useful markets:

```text
Fed decision probabilities
Rate-cut probabilities
Recession probabilities
Tariff outcomes
Election outcomes
Geopolitical events
Commodity-related outcomes
Crypto-market regime
```

Examples:

```text
Higher rate-cut probability
→ improved housing affordability
→ potential Home Depot demand benefit
```

```text
Higher recession probability
→ weaker housing turnover
→ weaker Home Depot comparable sales
```

```text
Tariff probability
→ Deere cost / demand / margin implications
```

Use Numinous / Polymarket only when there is a clear economic transmission mechanism.

---

# 19. Meta-Forecaster

The final model combines:

```text
Reconstructed Street estimate
Independent fundamental forecast
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

Weights should depend on:

```text
Historical performance
Current confidence
Metric type
Evidence quality
Source independence
```

---

# 20. Metric-Specific Research

Each of the 12 metrics should have its own:

```text
Driver graph
Analyst leaderboard
Research queue
Evidence ledger
Confidence score
```

Do not treat all metrics for a company as one forecast.

For example:

```text
ADI revenue
≠
ADI gross margin
≠
ADI EPS
```

---

# 21. Home Depot Strategy

## Targets

```text
Net sales
Adjusted diluted EPS
Comparable sales
```

## Core hypothesis

Comparable sales is likely the most important operating variable.

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

## Research drivers

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

## Potential edge

Treat Home Depot as a **housing and home-improvement nowcasting problem**, not just a retail forecast.

---

# 22. Analog Devices Strategy

## Targets

```text
Revenue
Adjusted diluted EPS
Adjusted gross margin
```

## Core question

Where inside or outside management's guidance range will the quarter land?

## Research drivers

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

## Potential edge

Gross margin may be more differentiated than headline revenue or EPS.

---

# 23. Hays plc Strategy

## Targets

```text
Net fees
Pre-exceptional basic EPS
Pre-exceptional operating profit
```

## Core opportunity

Hays is likely the cleanest company for testing the **Analyst Reliability Engine**.

Attempt to identify:

```text
Analyst
Broker
Current estimate
Historical estimate
Historical forecast error
Bias
Revision timing
Metric-specific performance
```

Then compare:

```text
Published consensus
vs
Accuracy-weighted consensus
vs
Bias-corrected consensus
```

## Research drivers

```text
UK hiring
Germany hiring
Australia hiring
Temporary vs permanent hiring
Recruiter headcount
Fee rates
Wage inflation
Cost reductions
Operating leverage
```

---

# 24. Deere Strategy

## Targets

```text
Worldwide net sales and revenues
Diluted EPS
Production & Precision Ag operating profit
```

## Core model

Macro + farm economics + segment operating leverage.

## Research drivers

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

## Potential edge

Production & Precision Ag operating profit may be easier to differentiate on than headline Deere EPS.

---

# 25. Peer / Supplier / Customer Read-Through

Build relationship graphs:

```text
Target Company
├── Suppliers
├── Customers
├── Competitors
└── Industry proxies
```

Then ask:

> Which related companies have released information after the current Street estimate was formed?

This may reveal information not yet fully incorporated into sell-side models.

---

# 26. Dynamic Model Construction

The system should build small company-specific estimators where appropriate.

Examples:

## Home Depot

```text
Comparable sales
≈
Housing activity
+ Repair/remodel demand
+ Pro demand
+ Weather
```

## Analog Devices

```text
Revenue
≈
End-market demand
× Inventory normalization
× Pricing / mix
```

## Hays

```text
Net fees
≈
Placement volume
× Average fee
× Geographic mix
```

## Deere

```text
PPA operating profit
≈
Segment sales
× Operating margin
```

This turns the system into a **model-building agent**, not just a document-reading agent.

---

# 27. Deterministic Financial Reconstruction

Once driver estimates exist, deterministic code should calculate derived outputs.

Example:

```text
Revenue
× Gross margin
=
Gross profit

Gross profit
-
Opex
=
Operating income

Operating income
-
Tax
=
Net income

Net income
÷
Diluted shares
=
EPS
```

The LLM should not do accounting arithmetic from memory.

---

# 28. Probabilistic Forecasting

Avoid fake precision.

Example:

```text
Bear Case
Probability: 20%
EPS: 4.55

Base Case
Probability: 55%
EPS: 4.78

Bull Case
Probability: 25%
EPS: 4.95
```

Final output should include:

```text
Point forecast
Confidence interval
Probability of beating Street
Main upside driver
Main downside driver
```

---

# 29. Research Stopping Rule

A self-driving researcher needs a stopping condition.

Stop when:

```text
Major drivers are covered
Forecast is stable across iterations
Recent research no longer moves the estimate
Expected value of the next query is low
Research budget is exhausted
```

Conceptually:

\[
|\hat{y}_t-\hat{y}_{t-1}|<\epsilon
\]

for several iterations.

---

# 30. Point-in-Time Integrity

Every historical backtest needs a strict:

```text
knowledge_cutoff
```

Example:

```text
Prediction time:
2025-04-20 16:00 ET

Allowed:
published_at <= cutoff
```

Nothing later may enter:

```text
Analyst revisions
Peer earnings
Macro data
Alternative data
Research documents
```

This is essential to avoid look-ahead leakage.

---

# 31. Walk-Forward Backtesting

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
Public consensus
Reconstructed Street
Fundamental forecast
Prediction-market adjustment
Final forecast
Actual
Absolute error
```

Measure:

```text
Did reconstructed Street improve on public consensus?
Did the full system beat reconstructed Street?
Which layer added alpha?
```

---

# 32. Ablation Testing

Test the architecture layer by layer:

```text
A — Public consensus only
B — Reconstructed analyst consensus
C — + Fundamental driver model
D — + Peer / supplier / customer research
E — + Autonomous research loop
F — + Prediction markets
G — + Adversarial critic
```

Do not force every feature into production.

Keep only what improves out-of-sample performance.

---

# 33. UI

The UI should make the reasoning visible.

Example:

```text
HOME DEPOT — COMPARABLE SALES

Estimated Street:        +1.1%
System forecast:         +1.8%
Expected edge:           +0.7pp
Confidence:               72%
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
AUTONOMOUS RESEARCH

✓ Housing data
✓ Lowe's read-through
✓ Analyst revisions
✓ Mortgage-rate impact
✓ Weather
✓ Consumer spending

NEXT QUESTION

"Is Pro demand materially stronger than DIY?"

Expected impact: HIGH
Status: Researching
```

---

# 34. Hackathon-Day Workflow

For each metric:

```text
Load target
↓
Find public Street estimates
↓
Find individual analysts where possible
↓
Reconstruct hidden Street
↓
Build metric-specific driver graph
↓
Estimate uncertainty
↓
Launch autonomous research
↓
Research highest-value unknown
↓
Update evidence ledger
↓
Build competing hypotheses
↓
Run adversarial critic
↓
Calculate deterministic forecast
↓
Add macro/prediction-market adjustment
↓
Meta-forecast
↓
Stop when stable
↓
Render final number + evidence trail
```

---

# 35. Product Thesis

Do not pitch this as:

> An AI that reads filings and predicts earnings.

Pitch it as:

> **An autonomous financial scientist that reconstructs the hidden Street benchmark, finds the most informative analysts and data sources for each metric, discovers the company's underlying business drivers, researches the highest-value unknowns, challenges its own thesis, and outputs a calibrated forecast designed specifically to beat consensus.**

---

# 36. Priority Order

1. **Reconstruct the hidden Street benchmark**
2. **Find the best analyst by company × metric, not prestige**
3. **Build metric-specific driver models**
4. **Use autonomous research on the highest-value uncertainty**
5. **Exploit peer / supplier / customer read-through**
6. **Use Numinous / Polymarket for economically relevant macro priors**
7. **Maintain strict point-in-time integrity**
8. **Run walk-forward backtests**
9. **Use adversarial self-critique**
10. **Expose the research → evidence → calculation trail in the UI**

The central question is:

> **What does Wall Street probably believe, where is that belief wrong, and which evidence gives us enough confidence to move away from it?**
