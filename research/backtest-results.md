# Point-in-time forecast source backtest

**As of:** 2026-08-16  
**Closed observations:** 39  

Look-ahead rows are rejected. Errors are recency weighted and sparse histories are shrunk toward an 8% prior.

## Ranked source × company × metric histories

| Rank | Source | Company | Metric | N | Weighted error | Shrunk error | Bias |
|---:|---|---|---|---:|---:|---:|---:|
| 1 | Public analyst consensus | Home Depot | Net sales | 6 | 0.62% | 3.62% | -0.52% |
| 2 | Public analyst consensus | Analog Devices | Revenue | 8 | 2.76% | 4.60% | -2.76% |
| 3 | Public analyst consensus | Home Depot | Adjusted diluted EPS | 6 | 2.56% | 4.77% | -1.40% |
| 4 | Public analyst consensus | Analog Devices | Adjusted diluted EPS | 8 | 5.05% | 6.09% | -5.05% |
| 5 | ADI management guidance | Analog Devices | Revenue | 1 | 4.51% | 7.38% | -4.51% |
| 6 | ADI management guidance | Analog Devices | Adjusted diluted EPS | 1 | 6.34% | 7.70% | -6.34% |
| 7 | Public analyst consensus | Deere & Company | Diluted EPS (GAAP) | 7 | 10.02% | 9.26% | -9.78% |
| 8 | Public analyst consensus | Home Depot | Comparable sales, total company | 2 | 37.74% | 16.53% | +37.74% |

## Current forecasts

| Company | Period | Metric | Forecast | Units | Inputs |
|---|---|---|---:|---|---:|
| Analog Devices | FY2026Q3 | Adjusted diluted EPS | 3.5100 | USD / share | 1 |
| Analog Devices | FY2026Q3 | Revenue | 4021.0000 | USDm | 1 |
| Deere & Company | FY2026Q3 | Diluted EPS (GAAP) | 5.0900 | USD / share | 2 |
| Hays plc | FY2026 | Net fees | 902.4000 | GBPm | 1 |
| Hays plc | FY2026 | Pre-exceptional basic EPS | 1.1300 | GBp | 1 |
| Hays plc | FY2026 | Pre-exceptional operating profit | 45.3000 | GBPm | 1 |
| Home Depot | FY2026Q2 | Adjusted diluted EPS | 4.7700 | USD / share | 2 |
| Home Depot | FY2026Q2 | Net sales | 47416.0000 | USDm | 3 |

## Interpretation

A low error with a tiny sample remains heavily shrunk. Sources without closed historical calls can contribute only at reduced confidence. Social posts with no explicit numeric, timestamped forecast are preserved as research evidence but are excluded from the numeric ensemble.
