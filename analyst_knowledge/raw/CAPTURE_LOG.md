# Raw acquisition log

Retrieval date: 2026-08-16. All browser actions were read-only.

## Kernel CLI captures

| Surface | Query/page | Output | Result |
|---|---|---|---|
| X | `@TheRoaringKitty` profile | `x/roaringkitty_profile.json` | 5,762-byte page extraction; profile and recent post shells visible. |
| X | `$HD OR $ADI OR $DE` live search | `x/target_companies_search.json` | 8,523-byte page extraction. |
| X | `from:aleabitoreddit ADI` | `x/serenity_adi.json` | Empty; dynamic collector stalled at zero items. Preserved as negative acquisition evidence. |
| X | `@aleabitoreddit` timeline | `x/serenity_timeline.json` | Empty; dynamic collector stalled at zero items. A separate public archive was downloaded instead. |
| LinkedIn | Analog Devices earnings forecast | `linkedin/adi_earnings_forecast.json` | 17,147-byte authenticated search-page extraction. |
| LinkedIn | Hays plc earnings forecast | `linkedin/hays_earnings_forecast.json` | 14,782-byte authenticated search-page extraction. |
| Reddit | `u/DeepFuckingValue/submitted` | `reddit/deepfuckingvalue_submitted.json` | 20,314-byte old-Reddit page extraction; GME update history visible. |
| Reddit | Four target-company searches | `reddit/*forecast.json` | Successful extractions for ADI, Deere, Hays, and Home Depot. |
| X | Alex Morris / TSOH | `x/thought_leaders/alex_morris_tsoh.json` | Direct profile/archive capture used in the Home Depot candidate search. |
| X | Hedgeye Retail | `x/thought_leaders/hedgeye_retail.json` | Retail research profile capture; explicit HD model history is resolved separately. |
| X | Machinery Pete | `x/thought_leaders/machinery_pete.json` | Deere-domain auction-data specialist profile capture. |
| X | Chip Stock Investor | `x/thought_leaders/chip_stock_investor.json` | ADI thematic candidate capture; insufficient target history for the core ranking. |
| LinkedIn | Todd Tomalak | `linkedin/thought_leaders/todd_tomalak.json` | Building-products/remodeling specialist profile capture. |
| LinkedIn | Greg Peterson / Machinery Pete | `linkedin/thought_leaders/greg_peterson_machinery_pete.json` | Named Deere-domain profile capture. |
| LinkedIn | Pawel Adrjan, Neil Carberry, Tera Allas | `linkedin/thought_leaders/*.json` | Labour-market and recruitment-domain candidate captures for Hays. |

Earlier Kernel captures used by the current forecast prototype remain under `research/raw/`; they include a LinkedIn Home Depot search and JSONL X results. They are retained in place to avoid rewriting raw evidence.

## Direct public downloads

- Serenity fan archive and its completeness report were downloaded from `WOOK98/serenity-aleabitoreddit` on GitHub.
- SemiAnalysis public HTML/sitemap pages were downloaded from the publisher.
- Keith Gill’s written testimony was downloaded from Congress.gov.

Every file’s byte size and SHA-256 digest is regenerated in `dataset/manifest.json`.
