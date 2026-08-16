# Calibration — analog-devices

Point-in-time cutoff: **full frozen corpus**

Each row pairs a guidance figure published *before* a period with the
actual reported *after* it. The bias is shrunk toward zero by
`n / (n + 5)` so a short history cannot swing a forecast far off its
anchor. Sigma is the dispersion about the shrunk mean — the error an
estimator using this correction would actually have made — and is what
the reconciler weights by.

## `adj_eps` (USD / share)

- observations: **12**
- raw bias: **+4.99%**
- shrunk bias: **+3.52%**
- sigma: **4.00%**

| Period | Guided | Actual | Miss | Guidance source | Result source |
|---|---:|---:|---:|---|---|
| FY2023Q3 | 2.52 | 2.49 | -1.19% | `analog-devices/filings/2023-05-24__adi-us-20230524-q2-8k__102668.md` | `analog-devices/filings/2023-08-23__adi-us-20230823-q3-8k-2__488074.md` |
| FY2023Q4 | 2.00 | 2.01 | +0.50% | `analog-devices/filings/2023-08-23__adi-us-20230823-q3-8k-2__488074.md` | `analog-devices/filings/2023-11-21__adi-us-20231121-q4-8k__102653.md` |
| FY2024Q1 | 1.70 | 1.73 | +1.76% | `analog-devices/filings/2023-11-21__adi-us-20231121-q4-8k__102653.md` | `analog-devices/filings/2024-02-21__adi-us-20240221-q1-8k__102673.md` |
| FY2024Q2 | 1.26 | 1.40 | +11.11% | `analog-devices/filings/2024-02-21__adi-us-20240221-q1-8k__102673.md` | `analog-devices/filings/2024-05-22__adi-us-20240522-q2-8k__102675.md` |
| FY2024Q3 | 1.50 | 1.58 | +5.33% | `analog-devices/filings/2024-05-22__adi-us-20240522-q2-8k__102675.md` | `analog-devices/filings/2024-08-21__adi-us-20240821-q3-8k__102648.md` |
| FY2024Q4 | 1.63 | 1.67 | +2.45% | `analog-devices/filings/2024-08-21__adi-us-20240821-q3-8k__102648.md` | `analog-devices/filings/2024-11-26__adi-us-20241126-q4-8k__102666.md` |
| FY2025Q1 | 1.53 | 1.63 | +6.54% | `analog-devices/filings/2024-11-26__adi-us-20241126-q4-8k__102666.md` | `analog-devices/filings/2025-02-19__adi-us-20250219-q1-8k__102670.md` |
| FY2025Q2 | 1.68 | 1.85 | +10.12% | `analog-devices/filings/2025-02-19__adi-us-20250219-q1-8k__102670.md` | `analog-devices/filings/2025-05-22__adi-us-20250522-q2-8k__102679.md` |
| FY2025Q3 | 1.92 | 2.05 | +6.77% | `analog-devices/filings/2025-05-22__adi-us-20250522-q2-8k__102679.md` | `analog-devices/filings/2025-08-20__adi-us-20250820-q3-8k__155976.md` |
| FY2025Q4 | 2.22 | 2.26 | +1.80% | `analog-devices/filings/2025-08-20__adi-us-20250820-q3-8k__155976.md` | `analog-devices/filings/2025-11-25__adi-us-20251125-q4-8k__361005.md` |
| FY2026Q1 | 2.29 | 2.46 | +7.42% | `analog-devices/filings/2025-11-25__adi-us-20251125-q4-8k__361005.md` | `analog-devices/filings/2026-02-18__adi-us-20260218-q1-8k-2__602115.md` |
| FY2026Q2 | 2.88 | 3.09 | +7.29% | `analog-devices/filings/2026-02-18__adi-us-20260218-q1-8k-2__602115.md` | `analog-devices/filings/2026-05-20__adi-us-20260520-q2-8k__1040581.md` |

## `adj_operating_margin_pct` (%)

- observations: **12**
- raw bias: **+0.77pp**
- shrunk bias: **+0.54pp**
- sigma: **0.80pp**

| Period | Guided | Actual | Miss | Guidance source | Result source |
|---|---:|---:|---:|---|---|
| FY2023Q3 | 48.50 | 47.80 | -0.70pp | `analog-devices/filings/2023-05-24__adi-us-20230524-q2-8k__102668.md` | `analog-devices/filings/2023-08-23__adi-us-20230823-q3-8k-2__488074.md` |
| FY2023Q4 | 44.00 | 44.70 | +0.70pp | `analog-devices/filings/2023-08-23__adi-us-20230823-q3-8k-2__488074.md` | `analog-devices/filings/2023-11-21__adi-us-20231121-q4-8k__102653.md` |
| FY2024Q1 | 41.50 | 42.00 | +0.50pp | `analog-devices/filings/2023-11-21__adi-us-20231121-q4-8k__102653.md` | `analog-devices/filings/2024-02-21__adi-us-20240221-q1-8k__102673.md` |
| FY2024Q2 | 37.00 | 39.00 | +2.00pp | `analog-devices/filings/2024-02-21__adi-us-20240221-q1-8k__102673.md` | `analog-devices/filings/2024-05-22__adi-us-20240522-q2-8k__102675.md` |
| FY2024Q3 | 40.00 | 41.20 | +1.20pp | `analog-devices/filings/2024-05-22__adi-us-20240522-q2-8k__102675.md` | `analog-devices/filings/2024-08-21__adi-us-20240821-q3-8k__102648.md` |
| FY2024Q4 | 41.00 | 41.10 | +0.10pp | `analog-devices/filings/2024-08-21__adi-us-20240821-q3-8k__102648.md` | `analog-devices/filings/2024-11-26__adi-us-20241126-q4-8k__102666.md` |
| FY2025Q1 | 40.00 | 40.50 | +0.50pp | `analog-devices/filings/2024-11-26__adi-us-20241126-q4-8k__102666.md` | `analog-devices/filings/2025-02-19__adi-us-20250219-q1-8k__102670.md` |
| FY2025Q2 | 40.50 | 41.20 | +0.70pp | `analog-devices/filings/2025-02-19__adi-us-20250219-q1-8k__102670.md` | `analog-devices/filings/2025-05-22__adi-us-20250522-q2-8k__102679.md` |
| FY2025Q3 | 41.50 | 42.20 | +0.70pp | `analog-devices/filings/2025-05-22__adi-us-20250522-q2-8k__102679.md` | `analog-devices/filings/2025-08-20__adi-us-20250820-q3-8k__155976.md` |
| FY2025Q4 | 43.50 | 43.50 | +0.00pp | `analog-devices/filings/2025-08-20__adi-us-20250820-q3-8k__155976.md` | `analog-devices/filings/2025-11-25__adi-us-20251125-q4-8k__361005.md` |
| FY2026Q1 | 43.50 | 45.50 | +2.00pp | `analog-devices/filings/2025-11-25__adi-us-20251125-q4-8k__361005.md` | `analog-devices/filings/2026-02-18__adi-us-20260218-q1-8k-2__602115.md` |
| FY2026Q2 | 47.50 | 49.00 | +1.50pp | `analog-devices/filings/2026-02-18__adi-us-20260218-q1-8k-2__602115.md` | `analog-devices/filings/2026-05-20__adi-us-20260520-q2-8k__1040581.md` |

## `revenue` (USDm)

- observations: **12**
- raw bias: **+2.35%**
- shrunk bias: **+1.66%**
- sigma: **1.85%**

| Period | Guided | Actual | Miss | Guidance source | Result source |
|---|---:|---:|---:|---|---|
| FY2023Q3 | 3,100.00 | 3,076.00 | -0.77% | `analog-devices/filings/2023-05-24__adi-us-20230524-q2-8k__102668.md` | `analog-devices/filings/2023-08-23__adi-us-20230823-q3-8k-2__488074.md` |
| FY2023Q4 | 2,700.00 | 2,716.00 | +0.59% | `analog-devices/filings/2023-08-23__adi-us-20230823-q3-8k-2__488074.md` | `analog-devices/filings/2023-11-21__adi-us-20231121-q4-8k__102653.md` |
| FY2024Q1 | 2,500.00 | 2,513.00 | +0.52% | `analog-devices/filings/2023-11-21__adi-us-20231121-q4-8k__102653.md` | `analog-devices/filings/2024-02-21__adi-us-20240221-q1-8k__102673.md` |
| FY2024Q2 | 2,100.00 | 2,159.00 | +2.81% | `analog-devices/filings/2024-02-21__adi-us-20240221-q1-8k__102673.md` | `analog-devices/filings/2024-05-22__adi-us-20240522-q2-8k__102675.md` |
| FY2024Q3 | 2,270.00 | 2,312.00 | +1.85% | `analog-devices/filings/2024-05-22__adi-us-20240522-q2-8k__102675.md` | `analog-devices/filings/2024-08-21__adi-us-20240821-q3-8k__102648.md` |
| FY2024Q4 | 2,400.00 | 2,443.00 | +1.79% | `analog-devices/filings/2024-08-21__adi-us-20240821-q3-8k__102648.md` | `analog-devices/filings/2024-11-26__adi-us-20241126-q4-8k__102666.md` |
| FY2025Q1 | 2,350.00 | 2,423.00 | +3.11% | `analog-devices/filings/2024-11-26__adi-us-20241126-q4-8k__102666.md` | `analog-devices/filings/2025-02-19__adi-us-20250219-q1-8k__102670.md` |
| FY2025Q2 | 2,500.00 | 2,640.00 | +5.60% | `analog-devices/filings/2025-02-19__adi-us-20250219-q1-8k__102670.md` | `analog-devices/filings/2025-05-22__adi-us-20250522-q2-8k__102679.md` |
| FY2025Q3 | 2,750.00 | 2,880.00 | +4.73% | `analog-devices/filings/2025-05-22__adi-us-20250522-q2-8k__102679.md` | `analog-devices/filings/2025-08-20__adi-us-20250820-q3-8k__155976.md` |
| FY2025Q4 | 3,000.00 | 3,076.00 | +2.53% | `analog-devices/filings/2025-08-20__adi-us-20250820-q3-8k__155976.md` | `analog-devices/filings/2025-11-25__adi-us-20251125-q4-8k__361005.md` |
| FY2026Q1 | 3,100.00 | 3,160.00 | +1.94% | `analog-devices/filings/2025-11-25__adi-us-20251125-q4-8k__361005.md` | `analog-devices/filings/2026-02-18__adi-us-20260218-q1-8k-2__602115.md` |
| FY2026Q2 | 3,500.00 | 3,623.00 | +3.51% | `analog-devices/filings/2026-02-18__adi-us-20260218-q1-8k-2__602115.md` | `analog-devices/filings/2026-05-20__adi-us-20260520-q2-8k__1040581.md` |
