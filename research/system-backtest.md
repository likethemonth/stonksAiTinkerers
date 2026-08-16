# System backtest — the real pipeline replayed on history

**As of:** 2026-08-16  
**Cells scored:** 75  

Each cell rebuilds the corpus as of the day before the actual was published, runs the same extractors, calibration, estimators and three-engine meta-forecaster the final command runs, and scores the result against a seasonal median-YoY benchmark using the competition's own formula (error ÷ benchmark error, floored, capped at 5.0). Below 1.00 is better.

## Headline

- **Mean score 0.37**, median **0.15** across 75 held-out cells.
- Beat the benchmark on **68 of 75** (91%).
- Mean absolute error 65.29 versus benchmark 373.6.

## Each engine alone, against the aggregate

An engine is judged only on the cells where it actually produced a value, and the aggregate is shown on those same cells so the comparison is like for like. `Aggregate better` counts the cells where the meta-forecast beat that engine on its own.

| Engine | Cells it spoke on | Mean score alone | Median alone | Beat benchmark alone | Aggregate on same cells | Aggregate better |
|---|---:|---:|---:|---:|---:|---:|
| fundamental | 75 | **0.37** | 0.15 | 68/75 | 0.37 | 2/75 |

## By metric

| Company · Metric | n | Mean score | Median | Beat | Mean err | Benchmark err |
|---|---:|---:|---:|---:|---:|---:|
| ADI · Adjusted diluted EPS | 19 | **0.16** | 0.11 | 19/19 | 0.07436 | 0.8082 |
| ADI · Adjusted gross margin | 19 | **0.48** | 0.25 | 18/19 | 0.8551 | 3.182 |
| ADI · Revenue | 19 | **0.20** | 0.09 | 17/19 | 83.74 | 931.1 |
| HD · Adjusted diluted EPS | 5 | **0.76** | 0.95 | 4/5 | 0.1752 | 2.288 |
| HD · Comparable sales, total company | 5 | **0.52** | 0.28 | 4/5 | 0.6213 | 2.42 |
| HD · Net sales | 5 | **0.96** | 0.26 | 3/5 | 650.8 | 2012 |
| LSE:HAS · Net fees | 1 | **0.15** | 0.15 | 1/1 | 18.7 | 127.1 |
| LSE:HAS · Pre-exceptional basic EPS | 1 | **0.39** | 0.39 | 1/1 | 0.7724 | 1.968 |
| LSE:HAS · Pre-exceptional operating profit | 1 | **0.27** | 0.27 | 1/1 | 10.8 | 40.69 |

## Coverage and abstentions

- `engine_failed`: 60 cells
- `scored`: 75 cells
- **Deere & Company excluded.** The Deere engine is an AEM units-to-dollars driver chain anchored to a dated snapshot, not to a fiscal period. No historical cutoff carries the driver observations it consumes, so replaying it would score a model that did not exist at the time.

## Per-cell results

| Company | Period | Metric | Cutoff | Actual | System | Benchmark | Score |
|---|---|---|---|---:|---:|---:|---:|
| ADI | FY2021Q4 | Adjusted diluted EPS | 2021-11-22 | 1.73 | 1.773 | 1.44 | 0.15 |
| ADI | FY2021Q4 | Adjusted gross margin | 2021-11-22 | 70.9 | 71.8 | 70 | 1.00 |
| ADI | FY2021Q4 | Revenue | 2021-11-22 | 2,340 | 1,805 | 1,526 | 0.66 |
| ADI | FY2022Q1 | Adjusted diluted EPS | 2022-02-15 | 1.94 | 1.83 | 1.73 | 0.53 |
| ADI | FY2022Q1 | Adjusted gross margin | 2022-02-15 | 71.9 | 71.35 | 70.9 | 0.55 |
| ADI | FY2022Q1 | Revenue | 2022-02-15 | 2,684 | 2,723 | 2,389 | 0.13 |
| ADI | FY2022Q2 | Adjusted diluted EPS | 2022-05-17 | 2.4 | 2.141 | 1.962 | 0.59 |
| ADI | FY2022Q2 | Adjusted gross margin | 2022-05-17 | 74.2 | 72.51 | 72.3 | 0.89 |
| ADI | FY2022Q2 | Revenue | 2022-05-17 | 2,972 | 2,928 | 2,704 | 0.16 |
| ADI | FY2022Q3 | Adjusted diluted EPS | 2022-08-16 | 2.52 | 2.53 | 2.317 | 0.05 |
| ADI | FY2022Q3 | Adjusted gross margin | 2022-08-16 | 74.1 | 74.09 | 73.5 | 0.01 |
| ADI | FY2022Q3 | Revenue | 2022-08-16 | 3,110 | 3,194 | 3,030 | 1.06 |
| ADI | FY2022Q4 | Adjusted diluted EPS | 2022-11-21 | 2.73 | 2.686 | 2.433 | 0.15 |
| ADI | FY2022Q4 | Adjusted gross margin | 2022-11-21 | 74 | 74.46 | 73.1 | 0.51 |
| ADI | FY2022Q4 | Revenue | 2022-11-21 | 3,248 | 3,292 | 4,084 | 0.05 |
| ADI | FY2023Q1 | Adjusted diluted EPS | 2023-02-14 | 2.75 | 2.721 | 2.842 | 0.32 |
| ADI | FY2023Q1 | Adjusted gross margin | 2023-02-14 | 73.6 | 74.17 | 74.4 | 0.71 |
| ADI | FY2023Q1 | Revenue | 2023-02-14 | 3,250 | 3,288 | 4,624 | 0.03 |
| ADI | FY2023Q2 | Adjusted diluted EPS | 2023-05-23 | 2.83 | 2.88 | 3.459 | 0.08 |
| ADI | FY2023Q2 | Adjusted gross margin | 2023-05-23 | 73.7 | 74.39 | 76.4 | 0.25 |
| ADI | FY2023Q2 | Revenue | 2023-05-23 | 3,263 | 3,338 | 4,839 | 0.05 |
| ADI | FY2023Q3 | Adjusted diluted EPS | 2023-08-22 | 2.49 | 2.636 | 3.572 | 0.13 |
| ADI | FY2023Q3 | Adjusted gross margin | 2023-08-22 | 72.2 | 73.33 | 76 | 0.30 |
| ADI | FY2023Q3 | Revenue | 2023-08-22 | 3,076 | 3,229 | 4,769 | 0.09 |
| ADI | FY2023Q4 | Adjusted diluted EPS | 2023-11-20 | 2.01 | 2.085 | 3.774 | 0.04 |
| ADI | FY2023Q4 | Adjusted gross margin | 2023-11-20 | 70.2 | 71.56 | 75.8 | 0.24 |
| ADI | FY2023Q4 | Revenue | 2023-11-20 | 2,716 | 2,804 | 4,744 | 0.04 |
| ADI | FY2024Q1 | Adjusted diluted EPS | 2024-02-20 | 1.73 | 1.768 | 3.802 | 0.02 |
| ADI | FY2024Q1 | Adjusted gross margin | 2024-02-20 | 69 | 70.47 | 75.4 | 0.23 |
| ADI | FY2024Q1 | Revenue | 2024-02-20 | 2,513 | 2,591 | 4,223 | 0.05 |
| ADI | FY2024Q2 | Adjusted diluted EPS | 2024-05-21 | 1.4 | 1.304 | 3.674 | 0.04 |
| ADI | FY2024Q2 | Adjusted gross margin | 2024-05-21 | 66.7 | 68.41 | 74.3 | 0.23 |
| ADI | FY2024Q2 | Revenue | 2024-05-21 | 2,159 | 2,172 | 3,767 | 0.01 |
| ADI | FY2024Q3 | Adjusted diluted EPS | 2024-08-20 | 1.58 | 1.556 | 2.698 | 0.02 |
| ADI | FY2024Q3 | Adjusted gross margin | 2024-08-20 | 67.9 | 69.24 | 71 | 0.43 |
| ADI | FY2024Q3 | Revenue | 2024-08-20 | 2,312 | 2,347 | 3,210 | 0.04 |
| ADI | FY2024Q4 | Adjusted diluted EPS | 2024-11-25 | 1.67 | 1.69 | 1.733 | 0.31 |
| ADI | FY2024Q4 | Adjusted gross margin | 2024-11-25 | 67.9 | 69.53 | 67.35 | 2.97 |
| ADI | FY2024Q4 | Revenue | 2024-11-25 | 2,443 | 2,479 | 2,479 | 1.01 |
| ADI | FY2025Q1 | Adjusted diluted EPS | 2025-02-18 | 1.63 | 1.588 | 1.356 | 0.15 |
| ADI | FY2025Q1 | Adjusted gross margin | 2025-02-18 | 68.8 | 68.83 | 65.95 | 0.01 |
| ADI | FY2025Q1 | Revenue | 2025-02-18 | 2,423 | 2,386 | 2,181 | 0.15 |
| ADI | FY2025Q2 | Adjusted diluted EPS | 2025-05-21 | 1.85 | 1.741 | 1.097 | 0.15 |
| ADI | FY2025Q2 | Adjusted gross margin | 2025-05-21 | 69.4 | 68.89 | 63.65 | 0.09 |
| ADI | FY2025Q2 | Revenue | 2025-05-21 | 2,640 | 2,539 | 1,874 | 0.13 |
| ADI | FY2025Q3 | Adjusted diluted EPS | 2025-08-19 | 2.05 | 1.983 | 1.238 | 0.08 |
| ADI | FY2025Q3 | Adjusted gross margin | 2025-08-19 | 69.2 | 69.2 | 64.85 | 0.00 |
| ADI | FY2025Q3 | Revenue | 2025-08-19 | 2,880 | 2,792 | 2,006 | 0.10 |
| ADI | FY2025Q4 | Adjusted diluted EPS | 2025-11-24 | 2.26 | 2.296 | 1.309 | 0.04 |
| ADI | FY2025Q4 | Adjusted gross margin | 2025-11-24 | 69.8 | 70.19 | 64.85 | 0.08 |
| ADI | FY2025Q4 | Revenue | 2025-11-24 | 3,076 | 3,050 | 2,120 | 0.03 |
| ADI | FY2026Q1 | Adjusted diluted EPS | 2026-02-17 | 2.46 | 2.363 | 1.445 | 0.10 |
| ADI | FY2026Q1 | Adjusted gross margin | 2026-02-17 | 71.2 | 70.07 | 67.55 | 0.31 |
| ADI | FY2026Q1 | Revenue | 2026-02-17 | 3,160 | 3,151 | 2,258 | 0.01 |
| ADI | FY2026Q2 | Adjusted diluted EPS | 2026-05-19 | 3.09 | 2.974 | 2.072 | 0.11 |
| ADI | FY2026Q2 | Adjusted gross margin | 2026-05-19 | 73 | 72.33 | 69.95 | 0.22 |
| ADI | FY2026Q2 | Revenue | 2026-05-19 | 3,623 | 3,555 | 2,887 | 0.09 |
| HD | FY2025Q1 | Adjusted diluted EPS | 2025-05-19 | 3.45 | 3.479 | 3.42 | 0.95 |
| HD | FY2025Q1 | Comparable sales, total company | 2025-05-19 | -0.3 | 1.013 | -5.05 | 0.28 |
| HD | FY2025Q1 | Net sales | 2025-05-19 | 3.986e+04 | 3.875e+04 | 3.564e+04 | 0.26 |
| HD | FY2025Q2 | Adjusted diluted EPS | 2025-08-18 | 4.58 | 4.624 | 4.372 | 0.21 |
| HD | FY2025Q2 | Comparable sales, total company | 2025-08-18 | 1 | 0.9802 | -3.1 | 0.00 |
| HD | FY2025Q2 | Net sales | 2025-08-18 | 4.528e+04 | 4.559e+04 | 4.287e+04 | 0.13 |
| HD | FY2025Q3 | Adjusted diluted EPS | 2025-11-17 | 3.62 | 3.798 | 3.512 | 1.65 |
| HD | FY2025Q3 | Comparable sales, total company | 2025-11-17 | 0.2 | 0.971 | 0.45 | 1.54 |
| HD | FY2025Q3 | Net sales | 2025-11-17 | 4.135e+04 | 4.078e+04 | 4.132e+04 | 2.75 |
| HD | FY2025Q4 | Adjusted diluted EPS | 2026-02-23 | 2.58 | 2.942 | 2.944 | 0.99 |
| HD | FY2025Q4 | Comparable sales, total company | 2026-02-23 | 0.4 | 0.9555 | 2.55 | 0.26 |
| HD | FY2025Q4 | Net sales | 2026-02-23 | 3.82e+04 | 3.894e+04 | 4.123e+04 | 0.24 |
| HD | FY2026Q1 | Adjusted diluted EPS | 2026-05-18 | 3.43 | 3.694 | 14.16 | 0.02 |
| HD | FY2026Q1 | Comparable sales, total company | 2026-05-18 | 0.6 | 1.047 | 1.45 | 0.53 |
| HD | FY2026Q1 | Net sales | 2026-05-18 | 4.176e+04 | 4.124e+04 | 4.139e+04 | 1.41 |
| LSE:HAS | FY2025 | Net fees | 2025-08-20 | 972.4 | 991.1 | 1,099 | 0.15 |
| LSE:HAS | FY2025 | Pre-exceptional basic EPS | 2025-08-20 | 1.31 | 2.082 | 3.278 | 0.39 |
| LSE:HAS | FY2025 | Pre-exceptional operating profit | 2025-08-20 | 45.6 | 56.4 | 86.29 | 0.27 |
