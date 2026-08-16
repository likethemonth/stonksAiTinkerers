# Home Depot / Hays source history

Research cut: 16 August 2026 (Europe/London)  
Coverage target: dated, public, pre-results claims from 2022–2026, resolved against later company results  
Machine-readable ledger: `analyst_knowledge/raw/hd_hays_candidate_claims.jsonl`

## Executive result

This pass produced **35 candidate claim records**: **24 Home Depot** and **11 Hays**. Thirty-three are numerically or directionally resolved; two are retained as unresolvable because the public forecast and reported metric do not cleanly share a basis. The records represent **11 distinct author IDs**, including four people or stable public pseudonyms. That difference matters: repeated consensus snapshots are useful calibration baselines, not an analyst leaderboard.

The strongest individually attributable history is:

- **W. Andrew Carter (Stifel):** one clean FY2023 Home Depot comparable-sales point forecast, -3.0% versus -3.2% actual.
- **Christopher Horvers (JPMorgan):** one clean relative Q4 FY2024 call that Home Depot would outcompete Lowe's; Home Depot comps rose 0.8% versus Lowe's 0.2%.
- **Value Voyager (independent Seeking Alpha contributor):** one clean Q3 FY2024 Home Depot revenue point forecast, $39.50bn versus $40.2bn actual; the paired EPS forecast is not rankable because the source does not say GAAP or adjusted.
- **Neil Shah (Edison Group):** one broad Hays FY2024 deterioration signal, directionally supported by a 46% LFL fall in pre-exceptional operating profit, but too qualitative for numeric ranking.
- **Hedgeye Retail Sector:** a stable organization-level research identity with two dated Home Depot model vintages and multiple resolved metrics. It is rankable as a research desk, not as a person.

Hays has a thinner public archive. Most broker research is paywalled and public reporting strips the analyst name. The usable numeric history is therefore dominated by company-compiled, Bloomberg, UBS, and Jefferies organization-level forecasts.

## Research questions and verdicts

| ID | Question / hypothesis | Verdict | Load-bearing evidence |
|---|---|---|---|
| H1 | Public pre-earnings Home Depot forecasts can support individual attribution. | **VERIFIED, but sparse.** Carter and Value Voyager are clean; most other public numbers are consensus or desk-level. | Benzinga Carter preview; Seeking Alpha Value Voyager article. |
| H2 | Hays has enough public named-analyst forecasts for an individual leaderboard. | **REFUTED for this pass.** Numeric forecasts are mostly organization or consensus-level. | Alliance News identifies UBS but no analyst; Investing.com identifies Jefferies but no analyst; Hays publishes aggregate consensus. |
| H3 | Multiple forecast vintages can be preserved without falsely inflating author breadth. | **VERIFIED.** Hedgeye August and November 2023 models and Hays consensus revisions are separately dated but share author IDs. | Hedgeye model sheets; Hays April/June/August 2025 consensus snapshots. |
| H4 | Forum/social searching will add clearly attributable, falsifiable earnings forecasts. | **INCONCLUSIVE.** Search exposed several Reddit comments and LinkedIn recaps, but public indexing often omitted comment authors or the posts were after the event. | Reddit search result pages, LinkedIn posts described below. |

## Candidate inventory

### Home Depot: 24 records

| Claim group | Forecast | Actual | Assessment |
|---|---:|---:|---|
| Carter FY2023 comps | -3.0% | -3.2% | Clean named analyst point call; absolute error 0.2 ppt. |
| Benzinga Q3 FY2023 consensus EPS | $3.58 | $3.81 | Consensus baseline; beat by $0.23. |
| Benzinga Q3 FY2023 consensus revenue | $35.66bn | $37.7bn | Consensus baseline; actual higher by $2.04bn. |
| Hedgeye Aug-2023 FY2023 EPS | $14.77 | $15.11 | Desk-level; actual higher by $0.34. |
| Hedgeye Aug-2023 FY2024 EPS | $13.53 | $14.91 | Desk-level; actual higher by $1.38. |
| Hedgeye Aug-2023 FY2023 revenue | $152bn | $152.7bn | Very close; 0.46% error. |
| Hedgeye Aug-2023 FY2024 revenue | $147bn | $159.5bn | Miss; later SRS acquisition and 53rd week impair like-for-like interpretation. |
| Hedgeye Nov-2023 FY2023 EPS | $15.04 | $15.11 | Revision improved accuracy; $0.07 error. |
| Hedgeye Nov-2023 FY2024 EPS | $13.59 | $14.91 | Miss low; same acquisition/calendar caveats. |
| Hedgeye Nov-2023 FY2023 revenue | $152bn | $152.7bn | Repeated model value; not a new author. |
| Hedgeye Nov-2023 FY2024 revenue | $147bn | $159.5bn | Repeated model value; not a new author. |
| Hedgeye FY2023 revenue growth | -3.3% | -3.0% | 0.3 ppt error. |
| Hedgeye FY2024 revenue growth | -3.6% | +4.5% | Direction miss; later M&A and 53rd week materially changed total sales. |
| Benzinga Q1 FY2024 consensus EPS | $3.60 | $3.63 | Same-day premarket consensus; $0.03 error. |
| Benzinga Q1 FY2024 consensus revenue | $36.68bn | $36.4bn | Company release rounds actual; roughly $0.28bn error. |
| Benzinga Q3 FY2024 consensus EPS | $3.64 adjusted | $3.78 adjusted | Beat by $0.14. |
| Benzinga Q3 FY2024 consensus revenue | $39.17bn | $40.2bn | Beat by about $1.03bn. |
| Benzinga Q4 FY2024 consensus EPS | $3.00 adjusted | $3.13 adjusted | Beat by $0.13. |
| Benzinga Q4 FY2024 consensus revenue | $39.14bn | $39.7bn | Beat by about $0.56bn. |
| Horvers Q4 FY2024 relative call | HD outcomps LOW | HD +0.8%; LOW +0.2% | Supported; 0.6 ppt comp advantage. |
| Benzinga Q1 FY2025 consensus EPS | $3.60 adjusted | $3.56 adjusted | Miss by $0.04. |
| Benzinga Q1 FY2025 consensus revenue | $39.33bn | $39.9bn | Beat by about $0.57bn. |
| Value Voyager Q3 FY2024 revenue | $39.50bn | $40.2bn | Clean independent point call; about $0.70bn error. |
| Value Voyager Q3 FY2024 EPS | $3.69 | $3.67 GAAP / $3.78 adjusted | Unresolvable without forecast basis. |

### Hays: 11 records

| Claim group | Forecast | Actual | Assessment |
|---|---:|---:|---|
| UBS FY2024 operating profit | £174m | £105.1m | Large miss; organization-level public attribution only. |
| UBS H1 FY2024 adjusted EBITA | £80m | £60.1m operating profit | Retained but unresolvable due public metric-label mismatch. |
| Aug-2023 market consensus FY2024 profit range | £154m–£223m | £105.1m | Actual below the entire range. |
| Neil Shah FY2024 concern | Down / challenging | -46% LFL profit | Directionally supported; not numeric. |
| Bloomberg Jul-2024 FY2024 profit range | £106m–£113m | £105.1m | Actual £0.9m below low end. |
| Hays Apr-2025 compiled FY2025 profit consensus | £56.9m | £45.6m | Missed high by £11.3m. |
| Hays Jun-2025 compiled FY2025 profit consensus | £56.4m | £45.6m | Snapshot immediately before company warning; missed high by £10.8m. |
| Jefferies Jun-2025 FY2025 adjusted EBIT | £43m | £45.6m | Close organization-level call; £2.6m error. |
| Hays Aug-2025 compiled FY2025 net-fee consensus | £971m | £972.4m | Very close; £1.4m error. |
| Hays Aug-2025 compiled FY2025 profit consensus | £50.6m | £45.6m | £5.0m error. |
| Hays Aug-2025 compiled FY2025 EPS consensus | 1.61p | 1.31p pre-exceptional | 0.30p error; forecast table does not state basis beyond “EPS.” |

The Hays total reaches 11 because the August 2025 Shares table yields three separately falsifiable claims: net fees, operating profit, and EPS.

## Who is actually rankable?

### Rankable now

1. **Hedgeye Retail Sector (desk level).** Eight clean numeric Home Depot points across two model vintages plus two year-over-year growth points. Do not count the August and November sheets as different authors. For FY2024 total-sales claims, attach an M&A/calendar comparability flag before scoring.
2. **W. Andrew Carter (individual).** One clean point. Accurate, but sample size is one; no leaderboard claim is defensible.
3. **Christopher Horvers (individual).** One clean peer-relative directional call; supported, but sample size is one.
4. **Value Voyager (stable pseudonym).** Revenue call is clean. EPS is excluded from scoring until basis is known.
5. **Jefferies Equity Research (desk level).** One clean Hays FY2025 profit call; close to actual. Public source does not expose the individual analyst.
6. **UBS Equity Research (desk level).** One clean full-year Hays call; the H1 record is excluded from scoring because EBITA/operating-profit labels do not align.

### Baselines, not analyst ranks

- **Benzinga Pro analyst consensus**: useful as the market hurdle for Home Depot; never attribute it to the article byline.
- **Hays company-compiled sell-side consensus**: useful for tracking revisions from £56.9m to £56.4m to £50.6m in FY2025; three snapshots are not three authors.
- **Bloomberg consensus range** and the August 2023 market range: useful range baselines, not individual calls.

### Not rankable

- **Neil Shah:** directional signal only.
- **Value Voyager EPS:** GAAP/adjusted ambiguity.
- **UBS H1 FY2024:** EBITA/operating-profit ambiguity.
- Reddit commenters surfaced in search results without stable comment-author attribution.
- LinkedIn authors whose posts merely repeated already-released results or company guidance.

## Source chronology

### Home Depot

- **15 Aug 2023 — Hedgeye Retail Sector model.** Public sheet gave FY2023/FY2024 revenue and EPS, a bearish 12-month comps thesis, and Street comparison. The exact numeric model is preserved; conditional 12-month base/bear comps were not scored because the sheet does not define how to aggregate the four future quarterly comps into one actual.
- **13 Nov 2023 — Benzinga preview by Surbhi Jain.** Contains W. Andrew Carter’s own FY2023 comparable-sales call and a separate Benzinga consensus for next-day EPS/revenue. JSON author IDs intentionally distinguish the analyst from consensus.
- **14 Nov 2023 — Hedgeye model revision.** FY2023 EPS moved from $14.77 to $15.04; FY2024 EPS moved from $13.53 to $13.59. Revenue forecasts were unchanged.
- **14 May 2024 — Benzinga premarket watch by Avi Kapoor.** Same-day consensus preserved because the article timestamp precedes the before-open report.
- **7 Nov 2024 — Value Voyager on Seeking Alpha.** Independent Q3 FY2024 revenue/EPS forecast. Seeking Alpha’s related-analysis index supplies the date where direct article fetch was blocked.
- **11 Nov 2024 — Benzinga Q3 preview.** Consensus values resolved against Home Depot’s 12 Nov primary release.
- **23 Jan 2025 — JPMorgan Christopher Horvers via Benzinga.** Predicted Home Depot would outcompete Lowe's in Q4; later company releases showed comparable sales of +0.8% for Home Depot and +0.2% for Lowe's.
- **24 Feb 2025 — Benzinga Q4 preview by Chris Katje.** Consensus values resolved against 25 Feb primary release.
- **20 May 2025 — Benzinga premarket watch by Avi Kapoor.** Same-day values published at 02:42 ET, before Home Depot’s release.

Primary resolution anchors:

- [Home Depot Q3 FY2023](https://ir.homedepot.com/news-releases/2023/11-14-2023-110056256)
- [Home Depot FY2023](https://ir.homedepot.com/news-releases/2024/02-20-2024-110037286)
- [Home Depot Q1 FY2024](https://ir.homedepot.com/news-releases/2024/05-14-2024-110058012)
- [Home Depot Q3 FY2024](https://ir.homedepot.com/news-releases/2024/11-12-2024-110156861)
- [Home Depot FY/Q4 FY2024](https://ir.homedepot.com/news-releases/2025/02-25-2025-110147741)
- [Home Depot Q1 FY2025](https://ir.homedepot.com/news-releases/2025/05-20-2025-110127912)

### Hays

- **24 Aug 2023 — Alliance News by Heather Rydings.** Reports UBS forecasts and a broad market-consensus range; also identifies Edison Group’s Neil Shah. It does not name the UBS analyst.
- **11 Jul 2024 — Hays Q4 RNS.** The company states Bloomberg’s FY2024 consensus range of £106m–£113m and separately says company expectation is about £105m. Only the external range is in the candidate ledger.
- **16 Apr 2025 — Hays Q3 RNS.** Company-compiled FY2025 consensus £56.9m based on nine updated analysts.
- **19 Jun 2025 — Hays pre-close update.** Company-compiled consensus £56.4m based on ten analysts; company then warns it expects about £45m.
- **19 Jun 2025 — Investing.com.** Jefferies cuts FY2025 adjusted EBIT to £43m. The article does not expose the individual analyst.
- **14 Aug 2025 — Shares Magazine by Ian Conway.** “What the market expects” table, data correct 11 Aug, sourced to company-compiled consensus: net fees £971m, operating profit £50.6m, EPS 1.61p.

Primary resolution anchors:

- [Hays H1 FY2024](https://www.investegate.co.uk/announcement/rns/hays--has/half-year-report/8050045)
- [Hays FY2024](https://www.investegate.co.uk/announcement/rns/hays--has/final-results/8378830)
- [Hays FY2025](https://www.investegate.co.uk/announcement/rns/hays--has/preliminary-report-2025/9066698)

## Forum and social research log

The forum search was not omitted; it produced mostly low-integrity or non-attributable candidates.

### Reddit

Reviewed indexed Home Depot earnings discussions including:

- r/wallstreetbets “Most Anticipated Earnings Releases” threads for May and August 2023;
- r/wallstreetbets “Home Depot Earnings Report” before the August 2024 result;
- r/RealDayTrading May 2023 premarket thread;
- r/options expected-move threads;
- r/stocks post-result discussions for February and August 2024;
- r/Options_Beginners 2025 “HD Earnings” posts.

Search indexes exposed falsifiable comments such as “It’s going to be bad” and “Expectations are earnings around $4.5/share,” but omitted the comment author. Reddit’s oEmbed endpoint identified the August 2024 post author as `u/Environmental-Log748`, not the authors of those comments. Attributing comment claims to the post author would be fabrication, so no Reddit comment entered the JSONL.

The August 2023 r/wallstreetbets thread contained a deliberately inverted statement (“earnings … not good so … buy calls”) and replies explaining the joke. It is not a stable directional forecast. Post-result link reposts were excluded because they are outcomes, not predictions.

### LinkedIn

Reviewed indexed posts from:

- Adil Mawani on Hays’ June 2025 profit warning;
- Dirk Hahn and Thomas Way on released Hays results;
- David Phillips on Hays FY2024 results;
- The Home Depot corporate account and several finance-summary authors after results.

These were after-event recaps or repeated company guidance. Adil Mawani’s £45m reference came from Hays’ warning, not his own forecast. None entered the candidate ledger.

### Seeking Alpha and StockTwits

Seeking Alpha yielded the usable Value Voyager numeric forecast. StockTwits pages did not surface stable historical messages with enough date/author/metric context in public search. No StockTwits claim was invented from snippets.

## Dead ends and exclusions

1. **Paywalled broker notes.** Search surfaced UBS/Jefferies desk forecasts but not the analyst names or original notes. Organization-level attribution is the highest defensible level.
2. **Hays current consensus page.** It now shows FY2026–FY2028 and was last updated 1 July 2026. It cannot reconstruct prior snapshots and is not used for historical FY2024/FY2025 claims.
3. **TipRanks Home Depot Q4 FY2022 preview.** Useful Greg Melich language and consensus numbers were found, but a reliable publication date was not exposed in the accessible page. Excluded from JSONL rather than guessing.
4. **Morningstar Q4 FY2022 preview.** Search exposed Jaime Katz’s discussion and consensus revenue, but direct open failed and the historical page appears to have been replaced by a current template. Excluded.
5. **Hedgeye 12-month comp ranges.** Numerically clear but target-period aggregation is not. The following reported quarters can be inspected, but no weighted 12-month comparable-sales actual was published as one number.
6. **Hays management guidance.** The June 2025 company expectation of about £45m was almost exact, but management guidance is not an external analyst forecast and therefore is not a candidate.
7. **Price targets.** UBS’ public Hays rating/target history is rich, but this assignment resolves earnings claims against earnings, not target prices against share prices.

## Bias and comparability warnings

- A forecast published on the report date but before the market open is preserved with `horizon_days: 0`; downstream scoring should keep it separate from multi-month calls.
- Do not turn one forecast into multiple “wins” without metric-level denominators. Revenue and EPS are separate claims but share one author-event.
- Do not compare adjusted forecast EPS with GAAP actual EPS. The JSON uses adjusted actuals where the preview clearly uses adjusted consensus; ambiguous sources are marked.
- Home Depot FY2024 total sales include the SRS acquisition and a 53rd week. Long-horizon organic forecasts made in 2023 are mechanically disadvantaged. Keep the resolution, but flag the structural break.
- Hays “operating profit,” “adjusted EBIT,” “pre-exceptional operating profit,” and “EBITA” are not interchangeable by default. Two ambiguous cases are withheld from ranking.
- Consensus revisions are longitudinal observations from one aggregate author ID, not independent analysts.

## Validation

- JSONL line count: expected **35**.
- Resolution status expected: **33 resolved**, **2 unresolvable**, **0 open**.
- Company split expected: **24 Home Depot**, **11 Hays**.
- All evidence quotes are deliberately short (25 words or fewer).
- Every resolved record has a later company-results URL; no numeric actual was inferred from stock-price reaction.

## Findings ledger

### F1 — Home Depot supports a small individual track record [INFO] [INFO]
- evidence: Carter, Horvers, and Value Voyager source URLs above.
- detail: Two identifiable people/pseudonyms made clean, pre-event numeric calls, and Horvers made a clean relative directional call. Sample sizes remain too small for durable person-level rankings.
- verdict: VERIFIED.
- action: Accumulate additional quarters before publishing rankings.

### F2 — Hedgeye offers the richest public longitudinal model [INFO] [INFO]
- evidence: 15 Aug and 14 Nov 2023 Hedgeye sheets.
- detail: Same desk, two vintages, multiple metrics. Its FY2023 calls were close; FY2024 bearish total-sales calls were overtaken by acquisition/calendar changes.
- verdict: VERIFIED.
- action: Rank only at desk level and carry structural-break flags.

### F3 — Public Hays attribution is organization-heavy [INFO] [INFO]
- evidence: Alliance News UBS story; Investing.com Jefferies story; Hays consensus RNS documents.
- detail: Public pages reveal firms and aggregate numbers but usually remove analyst names. Naming an individual would exceed the evidence.
- verdict: VERIFIED.
- action: Seek licensed/original broker notes if person-level Hays rankings become required.

### F4 — Forum evidence is discoverable but attribution-fragile [INFO] [INFO]
- evidence: Reddit and LinkedIn research log.
- detail: Indexed snippets preserve statements but often not comment authors; social recaps frequently occur after results. Neither is sufficient for a clean forecast ledger without direct post evidence.
- verdict: VERIFIED.
- action: Use direct-social records only when author, timestamp, metric, and pre-event status are all visible.

### F5 — Metric-basis errors can invert apparent accuracy [INFO] [INFO]
- evidence: Value Voyager EPS and UBS H1 records.
- detail: A $3.69 EPS call is near GAAP $3.67 but farther from adjusted $3.78; UBS EBITA cannot be assumed identical to Hays operating profit.
- verdict: VERIFIED.
- action: Exclude both from scoring until basis is independently confirmed.
