# Reference format audit: `praveenisomer-knowledge`

Audit date: 2026-08-16  
Reference root: `/Users/jooniverse/Downloads/praveenisomer-knowledge`  
Target adaptation: analyst/expert forecasts, outcomes, and point-in-time backtests  
Companion specification: [`SCHEMA_PROPOSAL.json`](SCHEMA_PROPOSAL.json)

## Executive verdict

The reference is a strong **layered research corpus**, not a formal knowledge-base product. Its useful contract is:

```text
raw window captures
  → one enriched canonical JSON corpus
    → deterministic topic and motif views
      → numbered expert synthesis documents
        → optional media archive and reproductions
```

That pattern is directly reusable. The reference succeeds because one native post ID connects raw records, canonical JSON, public URLs, generated Markdown, images, videos, and research claims. It also separates an exclusive primary classification (`topic`) from orthogonal multi-valued facets (`fields`, `motifs`, `motifs_ctx`). The overview then acts as the manual table of contents and statistical dashboard.

It is not safe to copy literally for a forecast backtest. The current reference has no formal schemas, no manifest or hashes, mutable in-place enrichment, uneven optional fields, generated-view drift, shortened IDs in prose, source metrics captured without a dedicated as-of timestamp, and no outcome/backtest entity. Those are documentation inconveniences here; in a forecast evaluation they create look-ahead, revision, identity, and denominator errors.

The recommended adaptation therefore preserves the four layers and human-readable navigation while adding immutable revisions, point-in-time availability, stable analyst/security registries, auditable outcomes, and experiment manifests.

## Audit scope and evidence method

The audit covered:

- every top-level path;
- all ten `knowledge/*.md` documents;
- all `dataset/` metadata and formats, including all topic/motif headers and representative files in full;
- all 38 JSON and three JSONL data files structurally, plus complete representative raw captures from each schema family;
- all collection/classification/index-generation scripts relevant to the format;
- filenames and counts for the 2.5 GB media archive, without decoding the bulk media;
- the recreation directory only as a downstream artifact class, because its bitmap/SVG contents are not part of the requested knowledge/data schema.

All counts below are direct filesystem/JSON measurements on the audit date. File citations point to the load-bearing source definitions or examples. Claims were checked against both prose and canonical data; disagreements are recorded as drift, not silently reconciled.

## F1 — Exact top-level topology [VERIFIED]

Ignoring `.DS_Store`, the root contains:

```text
praveenisomer-knowledge/
├── RESEARCH.md
├── classify.py
├── collect.js
├── collect-media.js
├── collect-timeline.js
├── collect-timeline2.js
├── download-videos.sh
├── fetch-post-media.js
├── fetch-post-media2.js
├── knowledge/                 10 authored Markdown syntheses
├── dataset/                   canonical corpus + generated views + overrides
├── raw/                       38 JSON, 3 JSONL, and diagnostic logs
├── media/                     images/ and videos/
└── recreations/               derived experiments, studies, HTML, SVG, and renders
```

The author’s own methodology names the same canonical layers—`dataset/posts.json`, raw windows, collector, and media archive—and describes media filenames as tweet-ID anchored ([RESEARCH.md:19](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:19), [RESEARCH.md:21](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:21)).

Observed size/count profile:

| Layer | Audit observation | Role |
|---|---:|---|
| `knowledge/` | 10 Markdown files, 92 KB | authored synthesis |
| `dataset/` | 27 files, 896 KB | canonical records, generated indexes, review aids |
| `raw/` | 41 data files plus logs, 720 KB | acquisition evidence and gap repairs |
| `media/` | 393 image-side files; 230 MP4s plus archive/log/status files; 2.5 GB | evidence payload keyed by post ID |
| `recreations/` | 149 MB, many nested studies | derived validation/reproduction artifacts |

**Adaptation:** preserve these roles but name the contract explicitly: `raw/` is immutable evidence, `dataset/` is canonical normalized truth, `dataset/indexes/` is generated navigation, `knowledge/` is authored synthesis, and `experiments/` or `backtests/` is derived evaluation. Do not mix outcomes into source records.

## F2 — Root research document is the methodological and narrative hub [VERIFIED]

`RESEARCH.md` is not a conventional README. It combines:

1. acquisition method and limitations;
2. a single load-bearing thesis;
3. a field map;
4. cross-field patterns;
5. time-series narrative;
6. downstream action mapping;
7. later append-only research extensions;
8. open questions and navigation.

The document begins with scope and yield, then records reproducible collection mechanics and explicit platform limitations ([RESEARCH.md:1](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:1), [RESEARCH.md:7](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:7), [RESEARCH.md:14](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:14)). It explicitly defines “all posts” as all still discoverable posts at the collection date and flags engagement as a collection-time snapshot ([RESEARCH.md:17](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:17)). It ends with links to the overview, canonical data, and collector ([RESEARCH.md:122](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:122)).

**Adaptation:** retain `RESEARCH.md` for the corpus-level thesis, methodology, limitations, and open questions. Add a short `README.md` for operational entry and current manifest status. For analyst forecasts, the methodology must define discoverability, licensing, publication-time recovery, revisions, withdrawn calls, and what “all forecasts” means.

## F3 — Numbered knowledge files are authored thematic chapters [VERIFIED]

### Naming

The exact pattern is `knowledge/NN-kebab-case-title.md`, except `00-OVERVIEW.md` uses uppercase `OVERVIEW`:

```text
00-OVERVIEW.md
01-ascii-dither-visual-language.md
02-figma-technique-catalog.md
03-tool-stack-pipeline.md
04-brand-client-work.md
05-freelance-economics.md
06-ai-design-discourse.md
07-growth-audience-playbook.md
08-gradient-deep-research.md
09-light-expression.md
```

The overview contains an explicit document map with relative Markdown links and a one-line statement of each chapter’s purpose ([00-OVERVIEW.md:117](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:117)). `RESEARCH.md` is linked back as the comprehensive synthesis ([00-OVERVIEW.md:129](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:129)).

### Repeated internal shape

There is no YAML frontmatter. Chapters use:

- one H1 title;
- optional opening blockquotes for scope/evidence notation;
- numbered H2 sections;
- tables for timelines, catalogs, comparisons, and quantitative summaries;
- direct quotations in blockquotes or inline quotes;
- a terminal “principles extracted,” open-questions, or corpus-note section.

Examples:

- `01` declares its compact evidence notation at the top, then moves through timeline → implementation → data use → formula → recurring formats → principles ([01-ascii-dither-visual-language.md:3](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/01-ascii-dither-visual-language.md:3), [01-ascii-dither-visual-language.md:8](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/01-ascii-dither-visual-language.md:8), [01-ascii-dither-visual-language.md:103](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/01-ascii-dither-visual-language.md:103)).
- `08` uses catalog IDs (`R1`–`R13`, `V1`–`V3`) as stable local anchors for detailed reverse-engineered cases ([08-gradient-deep-research.md:28](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/08-gradient-deep-research.md:28), [08-gradient-deep-research.md:180](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/08-gradient-deep-research.md:180)).
- `09` frames a taxonomy, comparison table, corpus evidence, implementation mapping, and open questions ([09-light-expression.md:15](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/09-light-expression.md:15), [09-light-expression.md:28](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/09-light-expression.md:28), [09-light-expression.md:66](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/09-light-expression.md:66)).

**Adaptation:** use numbered authored chapters for analyst profiles, taxonomy, themes, revisions/catalysts, calibration/bias, regimes, backtests, and source limitations. Require a common scope/data/build header and explicit counterevidence section; the reference’s flexible prose is readable but not sufficient to bind a claim to a corpus version.

## F4 — Overview is the manual navigation and statistics index [VERIFIED]

`00-OVERVIEW.md` carries four kinds of entry-point metadata:

- acquisition date, date range, corpus count, dataset paths, and media mapping ([00-OVERVIEW.md:3](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:3));
- subject profile;
- corpus statistics and taxonomy;
- narrative arc and document map.

It explicitly documents the exclusive `topic` partition and the orthogonal `form` and legacy `fields` facets ([00-OVERVIEW.md:48](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:48), [00-OVERVIEW.md:66](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:66)). It separately documents multi-valued motifs and context-only motif matches ([00-OVERVIEW.md:72](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:72)).

**Adaptation:** make `00-OVERVIEW.md` generated from `dataset/manifest.json` for counts and tables, with authored interpretation clearly delimited. It should expose denominators: sources, forecasts, analysts, instruments, resolved forecasts, backtest-eligible forecasts, exclusions, and unresolved calls.

## F5 — `dataset/posts.json` is the canonical denormalized corpus [VERIFIED]

### Envelope

The current file is a single JSON object:

```json
{
  "handle": "praveenisomer",
  "collected": "2026-07-12",
  "since": "2025-07-25",
  "count": 702,
  "posts": [ ... ]
}
```

These envelope fields appear at the beginning of the file ([posts.json:1](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/posts.json:1)). `count` equals the 702 unique post objects observed in the audit.

### Canonical post fields

Across 702 records, the complete union is:

| Field | Type/presence | Semantics |
|---|---|---|
| `id` | string, 702/702 | native tweet/status ID; effective primary key |
| `user` | string, 702/702 | source handle |
| `url` | string, 702/702 | canonical public status URL |
| `time` | ISO timestamp string, 702/702 | source publication time |
| `text` | string, 702/702 | authored post text, sometimes empty |
| `social` | string or null, 702/702 | UI social context such as pinned/reposted |
| `replyCtx` | boolean, 702/702 | whether collector UI identified a reply |
| `quoted` | string or null, 702/702 | quoted-post text only, not quoted-post ID |
| `replies`, `reposts`, `likes`, `views` | number, 702/702 | engagement snapshot |
| `imgs` | number, 702/702 | image count observed in DOM |
| `video` | boolean, 702/702 | video presence |
| `imgSrcs` | array, 257/702 | captured image URLs; absent in older/late records |
| `poster` | string/null, 303/702 | video poster URL; field itself often absent |
| `vsrcs` | array, 298/702 | browser video sources, often blob URLs |
| `videoFileAlias` | string, 3/702 | exceptional media filename key |
| `card` | string/null, 702/702 | external card URL |
| `links` | string array, 702/702 | display text of links/mentions extracted from post text |
| `fields` | string array, 702/702 | legacy, multi-label semantic classification |
| `topic` | string, 702/702 | exclusive primary topic |
| `form` | string, 702/702 | orthogonal content form |
| `motifs` | string array, 689/702 | own-text multi-label motifs |
| `motifs_ctx` | string array, 689/702 | quote-context-only motifs |

The opening records illustrate both the envelope and optional enrichment fields ([posts.json:7](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/posts.json:7), [posts.json:39](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/posts.json:39)).

### Taxonomies observed

`topic` currently contains 11 values: `ai-discourse`, `ascii-dither`, `brand-identity`, `business`, `growth-community`, `interaction`, `motion-craft`, `personal`, `tools-stack`, `ui-web-product`, and `uncategorized`.

`form` contains seven values: `announce`, `build-thread`, `opinion`, `reply-substantive`, `showcase`, `social`, `tutorial`.

`fields` contains 13 legacy values, including `business-economics`, `community-growth`, `figma-technique`, `framer-web`, `generative-math`, `motion-3d`, `paper-workflow`, and `product-ui`. `motifs` contains nine values: `cards`, `glass`, `gradient`, `halftone`, `illustration-vector`, `metal`, `particle-data`, `poster`, `shader`.

**Adaptation:** the denormalized “one record contains all facets” pattern is excellent for generated indexes, but forecasts need normalized registries for analysts, securities, and sources. Use JSONL for append-friendly immutable forecast/source/outcome ledgers; retain a small manifest envelope in `dataset/manifest.json`.

## F6 — Raw JSON uses a collection-window envelope [VERIFIED]

All 36 raw JSON files use an object envelope with:

```json
{
  "count": 2,
  "iter": 11,
  "retries": 0,
  "url": "https://x.com/search?...",
  "posts": [ ... ]
}
```

`retries` is absent from some earlier/probe captures; all other envelope keys are stable. A complete two-record gap-repair example is a compact one-line document ([gap-2026-02-26.json:1](/Users/jooniverse/Downloads/praveenisomer-knowledge/raw/gap-2026-02-26.json:1)). Empty captures are retained rather than deleted, preserving negative acquisition evidence ([m-2026-06-10-b.json:1](/Users/jooniverse/Downloads/praveenisomer-knowledge/raw/m-2026-06-10-b.json:1)). A timeline capture uses the same schema while its URL targets the profile rather than search ([timeline.json:1](/Users/jooniverse/Downloads/praveenisomer-knowledge/raw/timeline.json:1)).

There are two post-schema generations:

1. base records with 16 fields through `links`;
2. media-enriched records adding `imgSrcs`, `poster`, and `vsrcs`.

The collector returns exactly the raw envelope after sorting records reverse-chronologically ([collect.js:103](/Users/jooniverse/Downloads/praveenisomer-knowledge/collect.js:103), [collect.js:117](/Users/jooniverse/Downloads/praveenisomer-knowledge/collect.js:117)). The media collector extends extraction with original image URLs and video/poster sources, then returns the same envelope ([collect-media.js:53](/Users/jooniverse/Downloads/praveenisomer-knowledge/collect-media.js:53), [collect-media.js:77](/Users/jooniverse/Downloads/praveenisomer-knowledge/collect-media.js:77), [collect-media.js:127](/Users/jooniverse/Downloads/praveenisomer-knowledge/collect-media.js:127)).

### Raw filenames

The naming is operational rather than formally specified:

- `w-YYYY-MM-DD[letter].json`: base/window capture;
- `m-YYYY-MM[-DD][-YYYY-MM-DD].json`: media-enriched capture;
- `gap-YYYY-MM-DD.json`: targeted gap repair;
- `probe-YYYY-MM.json`: diagnostic broad search;
- `timeline*.json`, `retweets.json`: alternate acquisition routes;
- `missing-media*.jsonl`, `new-media.jsonl`: per-post repair results;
- `*.err`: captured diagnostic stderr.

**Adaptation:** retain the capture envelope and empty results, but add `capture_id`, provider, collector version, started/finished timestamps, query parameters, authentication profile identifier (never secret material), response/content hash, pagination cursor, and parent capture for repairs. Use an explicit provider/date directory hierarchy rather than filename prefixes alone.

## F7 — JSONL is used for sparse media repair results [VERIFIED]

The three JSONL files have one object per nonblank line with fields:

```json
{"id":"...","imgSrcs":["..."],"poster":null}
```

`missing-media.jsonl` contains 15 objects, `missing-media2.jsonl` six, and `new-media.jsonl` three. Blank separator lines are present, so consumers must ignore blank lines. A repair can validly produce empty media arrays, preserving the attempted lookup ([missing-media.jsonl:1](/Users/jooniverse/Downloads/praveenisomer-knowledge/raw/missing-media.jsonl:1), [missing-media.jsonl:7](/Users/jooniverse/Downloads/praveenisomer-knowledge/raw/missing-media.jsonl:7)). The single-post collector explicitly returns `{id,imgSrcs,poster}` or the same shape plus `error` ([fetch-post-media.js:18](/Users/jooniverse/Downloads/praveenisomer-knowledge/fetch-post-media.js:18)).

**Adaptation:** use JSONL as the main immutable event format for sources, forecasts, outcomes, and backtest runs. Disallow blank lines in canonical files, validate every line independently, and record sparse repair/upsert operations in a separate correction ledger rather than mutating canonical history silently.

## F8 — Classification is deterministic rules plus human overrides [VERIFIED]

`classify.py` defines a priority-ordered list of ten topics and applies regular expressions to own text, then quoted text, then media/reply fallbacks ([classify.py:10](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:10), [classify.py:29](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:29), [classify.py:41](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:41)). `form` is derived independently from text/reply/media rules ([classify.py:62](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:62)).

Human review is a TSV overlay:

```text
# hand-review corrections: id <TAB> topic <TAB> form
2070877311071916387    ascii-dither    showcase
```

The audited file contains 170 active override rows and 11 comments/blank lines. Overrides replace inferred topic/form after classification ([overrides.tsv:1](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/overrides.tsv:1), [classify.py:78](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:78), [classify.py:88](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:88)). The script then overwrites `posts.json` in place and writes a grouped review dump ([classify.py:99](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:99), [classify.py:107](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:107)).

**Adaptation:** keep deterministic first-pass classification and explicit human overrides. Expand override columns to field, old/new values, reviewer, reviewed-at, and reason. Build a new canonical version instead of overwriting; put source and output hashes in the manifest.

## F9 — Motifs are orthogonal own-text/context facets with generated trails [VERIFIED]

`dataset/build-motifs.py` defines nine regex-driven motifs with descriptions ([build-motifs.py:5](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/build-motifs.py:5)). It separates motifs found in the author’s own text from motifs found only in quoted context ([build-motifs.py:19](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/build-motifs.py:19)).

Each generated `dataset/motifs/<motif>.md` has this schema:

```markdown
# 모티프: <motif>

<description>

- 본문 매치 N + 문맥 M | 원본 평균 LN · 최대 LN
- 주제 분포: <topic count, ...>

---

- **YYYY-MM-DD** L<n> [<topic>/<form>] <RE?> <text truncated to 160 chars>
  <source-url> · img media/images/<id>-* · vid media/videos/<id-or-alias>-1.mp4

## 문맥 매치 (QT 상대)

- YYYY-MM-DD L<n> <text truncated to 90 chars> | <source-url>
```

This format is emitted directly in the generator ([build-motifs.py:33](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/build-motifs.py:33), [build-motifs.py:38](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/build-motifs.py:38), [build-motifs.py:47](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/build-motifs.py:47)).

**Adaptation:** map `motifs` to multi-valued thesis/catalyst/risk tags. Preserve the critical context distinction: an analyst mentioning a thesis directly is different from quoting or rebutting someone else’s thesis. Add tag provenance (`explicit`, `rule`, `model`, `human`) and confidence.

## F10 — Topic Markdown is a generated chronological record index [VERIFIED]

There are ten `dataset/topics/*.md` files. Their common header schema is:

```markdown
# <display title> (<topic-id>)

<definition/inclusion statement>

- 포스트 N (원본 M) | 원본 평균 Lx · 중앙값 Ly · 최대 Lz
- 형식: form n, ...

---
```

Each entry is:

```markdown
### YYYY-MM-DD · L<n> · <RE?> · [<form>](https://x.com/<user>/status/<id>)

> <full post text>
>
> ↳ QT: <quoted text, when present>
>
> 미디어: img×N → media/images/<id>-*.jpg | video → media/videos/<id>-1.mp4
```

The first entries in `ascii-dither.md` show the exact header and entry layout ([ascii-dither.md:1](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/topics/ascii-dither.md:1), [ascii-dither.md:10](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/topics/ascii-dither.md:10)). Mixed image/video and quote-context rendering is visible in `motion-craft.md` ([motion-craft.md:62](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/topics/motion-craft.md:62)).

The index is chronological ascending, while raw captures are reverse chronological. This is a useful separation: acquisition order is retained in raw files, research reading order is normalized in generated views.

**Adaptation:** generate parallel analyst, instrument, sector, primary-topic, and thesis-tag trails. A forecast entry must add stable `forecast_id`, target/horizon, publication and first-seen timestamps, source tier, revision link, outcome status, and backtest eligibility.

## F11 — Review and digest files are compact human inspection views [VERIFIED]

`dataset/review.txt` groups records by topic and emits a single compact row containing date, reply marker, likes, form, truncated text, quote context, and ID. This exact layout is produced by the classifier ([classify.py:107](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:107)).

`digest-originals.txt` and `digest-replies.txt` are source-order, one-line summaries using an informal bracket grammar:

```text
[YYYY-MM-DD L<n> QT:<...> imgN vid links:<...>] <text> | id:<native-id>
```

They are not parsed back into the corpus and serve as analyst-readable inspection artifacts.

**Adaptation:** retain generated review queues, especially records with low extraction confidence, conflicting analyst identity, ambiguous horizon, or unresolvable ticker. Do not treat text digests as canonical data.

## F12 — Native IDs are the corpus join key [VERIFIED]

The 19-digit X status ID is preserved as a JSON string and embedded in the canonical URL ([posts.json:8](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/posts.json:8)). The same ID anchors:

- raw/canonical deduplication (`Map` keyed by ID) ([collect.js:45](/Users/jooniverse/Downloads/praveenisomer-knowledge/collect.js:45), [collect.js:48](/Users/jooniverse/Downloads/praveenisomer-knowledge/collect.js:48));
- topic/motif links;
- image names `<tweetID>-<ordinal>.<ext>`;
- video names `<tweetID>-<ordinal>.mp4`;
- a video manifest containing only `{id,url}` records ([video-posts.json:1](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/video-posts.json:1));
- downloader skip/resume and yt-dlp output naming ([download-videos.sh:11](/Users/jooniverse/Downloads/praveenisomer-knowledge/download-videos.sh:11), [download-videos.sh:15](/Users/jooniverse/Downloads/praveenisomer-knowledge/download-videos.sh:15), [download-videos.sh:20](/Users/jooniverse/Downloads/praveenisomer-knowledge/download-videos.sh:20)).

The audit found 702 unique IDs and no duplicate canonical post IDs. Three records use `videoFileAlias` to decouple a post record from a reused/downloaded video’s filename, which the motif generator respects ([build-motifs.py:42](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/build-motifs.py:42)).

**Adaptation:** preserve native IDs but namespace them by provider. Forecast IDs must identify a forecast revision, not just a document; one report can contain multiple instruments/metrics/horizons. Security IDs must not be ticker-only.

## F13 — Citation style is compact, useful, and lossy [VERIFIED]

The corpus uses four citation forms:

1. full source link in generated topic/motif indexes;
2. local data/media paths;
3. compact prose evidence `(date, L=likes, id last six digits)`;
4. local research case labels such as `R5` or `V2`.

`01` explicitly defines the shortened-ID notation ([01-ascii-dither-visual-language.md:3](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/01-ascii-dither-visual-language.md:3)); its timeline then applies date/likes/suffix citations ([01-ascii-dither-visual-language.md:10](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/01-ascii-dither-visual-language.md:10)). Generated topic indexes preserve full URLs, making them the practical resolution layer ([ascii-dither.md:10](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/topics/ascii-dither.md:10)).

Weaknesses:

- a six-digit suffix is not globally safe;
- likes are mutable source observations but no engagement-as-of timestamp is attached per record;
- deep research sometimes cites a full ID in headings, but citation discipline varies;
- quoted post text lacks a quoted-post ID/URL;
- locators within images/videos are prose, not structured page/frame/timestamp references.

**Adaptation:** cite full `forecast_id` and `source_id`, retain source URL and content hash, and attach page/paragraph/timestamp/character offsets. Keep verbatim evidence separate from normalized thesis. Never use current market data or revised documents to retroactively decorate a historical citation without `available_at`.

## F14 — Collection provenance is documented but not fully represented in data [VERIFIED]

Strengths:

- collector version and acquisition strategy are stated in prose ([RESEARCH.md:7](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:7));
- exact search URL is retained per raw capture;
- scroll iterations and retries are retained;
- known platform limitations, deletions, and snapshot semantics are explicit ([RESEARCH.md:14](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:14));
- raw windows and gap repairs remain available.

Missing machine-readable provenance:

- capture start/end timestamp;
- collector code/version hash per raw file;
- content and file hashes;
- first-seen timestamp per post;
- time when engagement metrics were observed;
- parent/repair relationship between overlapping windows;
- reason and merge rule for canonical record selection;
- immutable corpus version.

**Adaptation:** these fields are mandatory for forecasts. A report’s nominal publication date is not enough: `published_at`, `first_seen_at`, `available_at`, `ingested_at`, and `effective_at` must be distinct to support a point-in-time backtest.

## F15 — The reference intentionally keeps raw and enriched data together, but mutates canonical data [VERIFIED]

The pipeline is recoverable from code:

```text
X DOM search/profile
  → collect.js / collect-media.js raw window envelope
    → manual merge/enrichment into dataset/posts.json
      → classify.py writes topic/form in place
        → overrides.tsv replaces reviewed values
          → build-motifs.py writes motifs in place
            → generated topic/motif/review/digest views
              → authored knowledge synthesis
```

The classifier and motif generator both overwrite `dataset/posts.json` ([classify.py:99](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:99), [build-motifs.py:25](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/build-motifs.py:25)). This is acceptable for an exploratory personal corpus but destroys transformation lineage unless version control captures every intermediate state.

**Adaptation:** each build writes a new content-addressed corpus version and manifest. Forecast revisions are domain events and must never be confused with extraction corrections. Record those in separate revision and correction lineages.

## F16 — Generated indexes and overview have substantial count drift [VERIFIED]

This is the most important structural defect to avoid.

The current canonical envelope says 702 posts since 2025-07-25 ([posts.json:2](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/posts.json:2)). The overview says 688 posts from 2025-08-01 and then presents statistics explicitly labeled for 588 posts ([00-OVERVIEW.md:3](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:3), [00-OVERVIEW.md:33](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:33)). `RESEARCH.md` likewise retains the original 588-post summary while later appending the 688-post extension ([RESEARCH.md:5](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:5), [RESEARCH.md:90](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:90)).

The ten topic Markdown files sum to 588 and have no `uncategorized.md`, while the current corpus contains 702 records and an `uncategorized` topic. Motif files were regenerated later and reflect a newer corpus: for example, the overview reports 35 own-text `cards` matches while `cards.md` currently reports 37; the generator emits this number directly from canonical data ([00-OVERVIEW.md:77](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:77), [build-motifs.py:35](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/build-motifs.py:35)). The overview’s 310 image files/211 videos is also behind the audited archive of 392 actual JPG/PNG images and 230 MP4s ([00-OVERVIEW.md:6](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:6)).

**Adaptation:** every generated Markdown header includes a manifest hash and generation timestamp. CI fails if counts, facet values, or hashes disagree. Authored prose can discuss older snapshots only when it names the snapshot version.

## F17 — Optional-field drift and stale taxonomies are tolerated [VERIFIED]

Thirteen late canonical records lack `motifs` and `motifs_ctx`; `imgSrcs`, `poster`, and `vsrcs` are inconsistently present rather than consistently empty/null. The classifier’s hard-coded `TOPICS` list has ten values and no `uncategorized`, while canonical data now includes `uncategorized` records ([classify.py:10](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:10)). `fields` and `topic` use overlapping but differently named vocabularies without a formal mapping.

**Adaptation:** publish JSON Schema, require explicit null/empty-array conventions, centralize enumerations in the manifest/schema, and validate that generators recognize every value. Schema evolution gets a version and migration note.

## F18 — Engagement is a snapshot, not a time series [VERIFIED]

The collector parses counters from the UI’s accessibility label and stores integer replies/reposts/likes/views ([collect.js:18](/Users/jooniverse/Downloads/praveenisomer-knowledge/collect.js:18)). `RESEARCH.md` correctly discloses that the values are collection-time snapshots ([RESEARCH.md:17](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:17)), but the record stores only publication `time`, not engagement observation time. Overlapping raw windows can therefore contain different engagement values without an explicit temporal model.

**Adaptation:** analyst targets and ratings are also revision-prone. Store each forecast as an immutable event with publication/availability time; store subsequent revision as a new linked event. If source popularity is analyzed, model it as separate timestamped observations.

## F19 — Media mapping is deliberately simple and mostly deterministic [VERIFIED]

Actual image filenames follow `<19-digit-id>-<ordinal>.jpg|png`; actual video filenames follow `<19-digit-id>-<ordinal>.mp4`. The downloader is resumable via `.archive`, skips an ID if any matching file exists, and records failures ([download-videos.sh:3](/Users/jooniverse/Downloads/praveenisomer-knowledge/download-videos.sh:3), [download-videos.sh:15](/Users/jooniverse/Downloads/praveenisomer-knowledge/download-videos.sh:15), [download-videos.sh:21](/Users/jooniverse/Downloads/praveenisomer-knowledge/download-videos.sh:21)). Generated Markdown sometimes uses wildcard image extensions and assumes video ordinal `1` ([build-motifs.py:41](/Users/jooniverse/Downloads/praveenisomer-knowledge/dataset/build-motifs.py:41)).

**Adaptation:** use `media/<source-id>/<ordinal>.<ext>` and store each attachment’s hash, MIME type, bytes, source URL, acquisition time, and legal status in the source record. PDFs and transcripts are first-class evidence, not anonymous bulk assets.

## F20 — Reproductions are downstream evidence, not canonical observations [VERIFIED]

`recreations/` separates:

- `ref/`: source/reference frames;
- `study/`: measurements, analyses, and calibration attempts;
- `copy-*`: runnable HTML or rendered recreations;
- `svg/`: generated text/SVG variants;
- contact sheets and representative shots.

`RESEARCH.md` records this as a later four-layer reconstruction study and links its measured outputs back into the synthesis ([RESEARCH.md:98](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:98)). `08-gradient-deep-research.md` similarly distinguishes corpus evidence, workflow transcription, and concrete study artifacts ([08-gradient-deep-research.md:220](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/08-gradient-deep-research.md:220), [08-gradient-deep-research.md:234](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/08-gradient-deep-research.md:234)).

**Adaptation:** the forecast equivalent is `backtests/` or `experiments/`: immutable run configurations, artifacts, plots, and reports keyed by `backtest_run_id`. They must cite a dataset manifest hash and remain downstream of canonical forecasts/outcomes.

## What to copy, strengthen, or reject

| Reference convention | Decision | Analyst-forecast adaptation |
|---|---|---|
| raw → canonical → indexes → synthesis | Copy | Keep as the primary architecture. |
| native string ID everywhere | Copy + namespace | Use provider-native source IDs; mint revision-level forecast IDs. |
| exact source URL on each record | Copy | Also add content hash and locator. |
| exclusive `topic` plus orthogonal `form` | Copy | Use exclusive primary topic plus forecast kind/action/direction/horizon. |
| multi-valued motifs and context motifs | Copy | Use thesis/catalyst/risk tags with direct-vs-quoted provenance. |
| generated per-facet Markdown trails | Copy | Generate analyst, instrument, sector, topic, and thesis views. |
| numbered authored knowledge chapters | Copy | Use for profiles, methodology, regimes, calibration, and backtest synthesis. |
| explicit limitations/open questions | Copy | Add licensing, coverage bias, timestamp quality, and leakage risks. |
| human TSV corrections | Strengthen | Add field, old/new, reviewer, timestamp, and reason. |
| engagement snapshot stored on post | Replace | Use immutable forecasts and separately timestamped observations/outcomes. |
| one mutable `posts.json` | Replace | Use append-only JSONL ledgers plus versioned manifest. |
| prose-only collection metadata | Replace | Machine-readable capture and build provenance. |
| truncated IDs in claims | Reject | Cite full stable IDs and source locators. |
| hand-maintained overview counts | Reject | Generate from a hashed manifest. |
| ticker as natural identity | Reject | Use FIGI/provider/security IDs with valid-time ticker aliases. |
| same record for source and evaluation | Reject | Separate source, forecast, outcome, and backtest entities. |

## Proposed analyst-knowledge layout

```text
analyst_knowledge/
├── README.md
├── RESEARCH.md
├── knowledge/
│   ├── 00-OVERVIEW.md
│   ├── 01-analyst-profiles.md
│   ├── 02-forecast-taxonomy.md
│   ├── 03-sector-and-theme-playbooks.md
│   ├── 04-revision-and-catalyst-patterns.md
│   ├── 05-calibration-and-bias.md
│   ├── 06-market-regime-analysis.md
│   ├── 07-backtest-results.md
│   └── 08-source-quality-and-limitations.md
├── dataset/
│   ├── manifest.json
│   ├── analysts.json
│   ├── instruments.json
│   ├── sources.jsonl
│   ├── forecasts.jsonl
│   ├── outcomes.jsonl
│   ├── backtest-runs.jsonl
│   ├── overrides.tsv
│   └── indexes/
│       ├── analysts/
│       ├── instruments/
│       ├── sectors/
│       ├── topics/
│       └── theses/
├── raw/<provider>/<YYYY>/<YYYY-MM-DD>/
├── media/<source-id>/
├── backtests/<backtest-run-id>/
├── schemas/
└── scripts/
```

The machine-readable definitions, identifier grammar, Markdown templates, and validation invariants are in `SCHEMA_PROPOSAL.json`.

## Forecast-specific non-negotiables

The reference does not need these; a credible forecast backtest does.

1. **Revision lineage:** upgrades, target changes, reiterations, withdrawals, and corrections are distinct immutable records linked by family and ordinal.
2. **Point-in-time availability:** distinguish nominal publication, first seen, ingestion, effective, and horizon timestamps.
3. **Instrument identity:** resolve ticker changes, mergers, share classes, delistings, and corporate actions through point-in-time IDs.
4. **Outcome policy:** freeze entry/exit price, calendar, adjustment, FX, benchmark, and resolution rules before scoring.
5. **Denominators:** report eligible, evaluated, and excluded counts with reason codes in every result.
6. **Source hierarchy:** label primary, licensed secondary, reputable secondary, aggregator, or unverified, and preserve the original analyst attribution.
7. **Leakage gates:** no feature or observation with `available_at > decision_at`; no revised security master or survivorship-filtered universe unless reconstructed point-in-time.
8. **Experiment identity:** every backtest records dataset hash, code commit, hypothesis, split, parameters, costs, baselines, confidence intervals, and artifacts.
9. **Claim/evidence split:** verbatim forecast text is never silently replaced by a normalized interpretation.
10. **Build reproducibility:** indexes and overviews carry the manifest hash and fail validation on drift.

## Hypothesis verdicts

| Hypothesis | Verdict | Evidence |
|---|---|---|
| The reference’s core organizing principle is a layered evidence pipeline, not a flat document collection. | **VERIFIED** | Root methodology names raw, canonical dataset, media, collectors, and knowledge documents ([RESEARCH.md:19](/Users/jooniverse/Downloads/praveenisomer-knowledge/RESEARCH.md:19)); scripts show deterministic transforms. |
| One native ID provides end-to-end traceability. | **VERIFIED** | Collector deduplicates by ID ([collect.js:45](/Users/jooniverse/Downloads/praveenisomer-knowledge/collect.js:45)); downloader and indexes reuse it. |
| Topic and motif views are both generated from the current canonical corpus. | **REFUTED** | Topic totals reflect 588, current corpus is 702, and motif views reflect a later build. |
| The reference has a formal schema and reproducible corpus version. | **REFUTED** | No schema/manifest exists; enrichment scripts overwrite canonical JSON in place ([classify.py:99](/Users/jooniverse/Downloads/praveenisomer-knowledge/classify.py:99)). |
| Its structure can support analyst forecast backtesting unchanged. | **REFUTED** | It lacks revision, availability, instrument, outcome, and experiment entities; counts and optional fields drift. |
| Its human-readable navigation pattern is worth preserving. | **VERIFIED** | Overview map, chronological topic trails, motif crosscuts, and numbered synthesis chapters form a coherent reading path ([00-OVERVIEW.md:117](/Users/jooniverse/Downloads/praveenisomer-knowledge/knowledge/00-OVERVIEW.md:117)). |

## Implementation acceptance checklist

- [ ] `dataset/manifest.json` validates and matches every canonical file’s count/hash.
- [ ] All JSONL lines validate independently; no blank canonical lines.
- [ ] Every forecast resolves analyst, instrument (when applicable), and source foreign keys.
- [ ] Every revision has monotonic family ordinal and predecessor link.
- [ ] Publication/first-seen/availability/ingestion/effective/horizon timestamps are separately populated.
- [ ] Every numerical claim has unit, currency where applicable, and evidence locator.
- [ ] Every resolved forecast has a declared observation and corporate-action policy.
- [ ] Every generated index displays its manifest hash and generation time.
- [ ] Overview/index facet counts exactly match the canonical ledger.
- [ ] Backtest run records code commit, corpus hash, split, costs, denominators, exclusions, baselines, uncertainty, and leakage checks.
- [ ] No authored chapter presents a current count without naming the manifest version.
- [ ] Raw captures and superseded/corrected records remain recoverable.

## Bottom line

Use the reference’s **shape and navigation**, not its looseness. Its best idea is that a reader can move from a high-level thesis to a thematic chapter, then to a chronological generated index, then to a canonical record, then to raw evidence or media—all through the same identifier. The forecast knowledge base should preserve that path and add the temporal, identity, revision, outcome, and reproducibility guarantees required for an honest backtest.
