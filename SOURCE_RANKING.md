# Forecast-source ranking and current calls

**Point-in-time cutoff:** 16 August 2026  
**Targets:** the 12 challenge metrics, not stock-price direction

## What the backtest can defend

The closed dataset contains 39 timestamped forecast/actual pairs. It supports a source × company × metric ranking for public consensus on HD, ADI and Deere, plus a first (heavily shrunk) test of ADI management guidance. The model rejects forecasts dated on or after the result date, applies a two-year half-life, estimates signed bias, and shrinks small samples toward an 8% error prior.

| Rank | Source history | Company / metric | N | Recency-weighted error | Shrunk error | Finding |
|---:|---|---|---:|---:|---:|---|
| 1 | Public analyst consensus | HD net sales | 6 | 0.62% | 3.62% | Best verified exact-metric history |
| 2 | Public analyst consensus | ADI revenue | 8 | 2.76% | 4.60% | Consistently conservative |
| 3 | Public analyst consensus | HD adjusted EPS | 6 | 2.56% | 4.77% | Small negative bias |
| 4 | Public analyst consensus | ADI adjusted EPS | 8 | 5.05% | 6.09% | Persistent under-forecast bias |
| 5 | ADI management guidance | ADI revenue | 1 | 4.51% | 7.38% | Useful but sample is not yet rankable |
| 6 | ADI management guidance | ADI adjusted EPS | 1 | 6.34% | 7.70% | Useful but sample is not yet rankable |
| 7 | Public analyst consensus | Deere GAAP EPS | 7 | 10.02% | 9.26% | Strong historical under-forecast bias |
| 8 | Public analyst consensus | HD total-company comps | 2 | 37.74% | 16.53% | Too sparse/unstable to trust alone |

The exact calculations and all component weights are emitted to `research/backtest-results.json` and `research/backtest-results.md` by `npm run forecast`.

The historical consensus values come from retrospective earnings tables that label the estimate used for each event; they are not immutable archives of every intraday revision or each contributing analyst. The ranking is therefore defensible at the aggregate-source level, not as a licensed constituent-level point-in-time database. It also does not yet cover closed Hays, ADI gross-margin, Deere total-revenue or Deere PPA-profit forecasts.

## Best sources by company

### Home Depot

1. **Refinitiv/S&P public consensus** — best verified source for net sales and EPS. The current preview gives $47.2bn and $4.73. [Kiplinger earnings preview](https://www.kiplinger.com/investing/stocks/17494/next-week-earnings-calendar-stocks)
2. **Brian Nagel, Oppenheimer** — the best attributable current individual call found: $4.66 EPS, below Street. It is included at reduced confidence because a comparable historical series was not publicly available. [Same preview](https://www.kiplinger.com/investing/stocks/17494/next-week-earnings-calendar-stocks)
3. **Home Depot guidance and transcripts** — primary evidence for the 0–2% FY2026 comp range and demand drivers. [Home Depot IR](https://ir.homedepot.com/events-and-presentations)
4. **Housing/remodelling experts** — use for comp-sales direction, not as numeric forecasts: NAHB remodeler confidence, Harvard JCHS remodeling outlook, mortgage rates, existing-home turnover, and Lowe's read-through.

**Named specialists to monitor next (not yet accuracy-ranked):** Scot Ciccarelli (Truist), Seth Sigman (Barclays), Christopher Horvers (JPMorgan), Michael Lasser (UBS), Simeon Gutman (Morgan Stanley), Zachary Fadem (Wells Fargo), Chuck Grom (Gordon Haskett), Zhihan Ma (Bernstein), and Brian Nagel (Oppenheimer). Their participation is verified in the May 2026 call transcript; only Nagel had a public current numeric call in this search.

### Analog Devices

1. **Public consensus** — the strongest backtested external source; current public snapshots are around $3.91–3.96bn revenue and $3.32–3.36 adjusted EPS. [Benzinga](https://www.benzinga.com/quote/adi/earnings), [FXEmpire](https://www.fxempire.com/stocks/adi/earnings)
2. **ADI management guidance** — $3.9bn ±$100m revenue and $3.30 ±$0.15 adjusted EPS. Management also indicated adjusted gross margin about 50bp below Q2's 73%, yielding a 72.5% anchor. [SEC filing](https://www.sec.gov/Archives/edgar/data/6281/000000628126000050/adi2q26exhibit991earnings.htm)
3. **Semiconductor channel experts** — distributor inventory, WSTS/SIA analog demand, automotive production, industrial automation, and hyperscaler power-management demand are the useful independent checks.

**Named specialists to monitor next (not yet accuracy-ranked):** Tore Svanberg, Vivek Arya (BofA), Joe Moore (Morgan Stanley), Joshua Buchalter (TD Cowen), Matthew Prisco (Cantor), Stacy Rasgon (Bernstein), William Stein (Truist), Chris Caso (Wolfe), and Tom O'Malley (Barclays), all verified participants in ADI's May 2026 earnings Q&A.

### Hays

1. **Hays-published nine-analyst consensus** — uniquely covers all three exact metrics: £902.4m net fees, £45.3m operating profit and 1.13p EPS as of 11 August. This is the highest-quality direct source, but no public historical constituent panel was available for analyst-level ranking. [Hays consensus](https://www.haysplc.com/investors/analysts-consensus)
2. **Hays trading statement** — management expects operating profit at the top of the £37–46m range, which pulls the model above the consensus midpoint. [Hays results centre](https://www.haysplc.com/investors/results-centre)
3. **Labour-market experts** — German/UK PMIs, official vacancies, Indeed job-posting trends, SIA staffing data and recruiter peers PageGroup/Adecco/Randstad are the best independent drivers.

**Named specialists to monitor next (not yet accuracy-ranked):** James Rowland Clark (Barclays), Simon Van Oppen (Kepler Cheuvreux), Rory McKenzie (UBS), Karl Green (RBC), Andy Grobler (BNP Paribas), Zack Al-Qaryooti (Morgan Stanley), and Steve Woolf (Deutsche Bank), verified in Hays 2026 call transcripts.

### Deere

1. **Public consensus for GAAP EPS** — current sources cluster around $4.69–$4.83, but the seven-quarter history has a -9.78% signed bias, so the model adjusts upward. [Kiplinger](https://www.kiplinger.com/investing/stocks/17494/next-week-earnings-calendar-stocks), [FXEmpire](https://www.fxempire.com/stocks/deere/earnings)
2. **Deere segment guidance and transcripts** — the primary source for Production & Precision Ag: FY sales down 5–10%, 11–13% operating margin, Q4 revenue/cost comparison better than Q3. [Deere Q2 materials](https://www.sec.gov/Archives/edgar/data/315189/000110465926064747/de-20260521xex99d2.htm)
3. **Agricultural experts** — USDA WASDE/crop prices, AEM monthly tractor/combine sales, dealer inventories, farmer income and CNH/AGCO results are the best independent PPA checks.
4. **Metric warning** — public sites often call $10.78–11.05bn “revenue,” but this aligns with equipment net sales. The challenge asks for *worldwide net sales and revenues*, which also includes Financial Services. The model bridges to the exact target instead of copying the mismatched consensus field.

**Named specialists to monitor next (not yet accuracy-ranked):** Steve Volkmann Fisher (Jefferies), Kyle Menges (Citi), Angel Castillo (Morgan Stanley), Kristen Owen (Oppenheimer), Jerry Revich (Wells Fargo), Tami Zakaria (JPMorgan), Chad Dillard (Bernstein), Mig Dobre (Baird), and Tim Thein (Raymond James), verified in Deere's May 2026 earnings Q&A.

## Hedge funds and social sources

No public hedge-fund source found supplied repeatable, timestamped forecasts for these exact 12 accounting metrics. SEC 13F holdings are delayed position disclosures, not earnings forecasts; ranking funds from them would be category error. They are therefore excluded from the numeric ensemble unless an explicit public thesis contains a dated number.

Kernel CLI downloaded X, LinkedIn and Reddit searches into `research/raw/`. X and LinkedIn returned usable posts; modern Reddit presented a human-verification challenge, so the old Reddit read-only surface was used. Social items are admitted only when they contain an explicit number, date, metric and attributable author. Qualitative posts remain research leads and receive no numeric weight.

## Current model output

| Company | Metric | Forecast |
|---|---|---:|
| HD | Net sales | $47,416m |
| HD | Adjusted diluted EPS | $4.774 |
| HD | Comparable sales, total company | 1.048% |
| ADI | Revenue | $4,038m |
| ADI | Adjusted diluted EPS | $3.512 |
| ADI | Adjusted gross margin | 72.458% |
| Hays | Net fees | £902.4m |
| Hays | Pre-exceptional basic EPS | 1.13p |
| Hays | Pre-exceptional operating profit | £45.641m |
| Deere | Worldwide net sales and revenues | $12,650m |
| Deere | Diluted EPS (GAAP) | $5.092 |
| Deere | PPA operating profit | $474.839m |

These are forecasting outputs, not investment advice. The weakest exact-metric calls are Deere PPA profit, Deere worldwide revenue, and HD comparable sales because no robust public point-in-time panel exists for those fields.
