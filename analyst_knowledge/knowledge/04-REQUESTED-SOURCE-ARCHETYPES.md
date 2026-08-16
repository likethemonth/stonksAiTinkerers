# Requested source archetypes: target relevance and admissibility

> Scope: public evidence retrieved through 2026-08-16. A negative result means “not found in the tested corpus,” not “never existed.”

## Serenity / @aleabitoreddit

The local archive contains 5,663 dated posts from 2025-07-02 through 2026-06-29, plus an archive-completeness report. An exact case-insensitive search for `Analog Devices`, `$ADI`, `Home Depot`, `$HD`, `Deere`, `$DE`, `Hays plc`, `$HAS`, and `Hasbro` returned zero target-company posts. Serenity is a relevant source archetype for upstream AI/semiconductor supply-chain mapping, but not a qualifying forecaster for these four target-company accounting metrics in the corpus tested.

- Raw archive: [`aleabitoreddit_tweets.json`](../raw/github/serenity/aleabitoreddit_tweets.json)
- Completeness report: [`archive_report.json`](../raw/github/serenity/archive_report.json)
- Third-party track-record reconstruction: [`track-record.md`](../raw/github/serenity/track-record.md)
- Archive warning: the reconstruction explicitly says results are self-reported and the public feed selects for winners.

The third-party archive’s own independent calibration reports roughly 61% 30-day directional accuracy on 49 tested calls, but this statistic is not imported into the target-company leaderboard: it uses a different universe, price outcomes rather than accounting metrics, and a fan-maintained methodology.

## SemiAnalysis / Dylan Patel

SemiAnalysis is a strong domain source for accelerator, HBM, networking, foundry, wafer-fab-equipment, and AI-cost models. Its compliance policy says it does not provide buy/sell/hold recommendations, valuations, or target prices, while permitting product and segment forecasts. Public sitemap/name/ticker searches found no attributable pre-earnings claim for Home Depot, Analog Devices, Hays, or Deere.

- Captured [model catalogue](../raw/web/semianalysis/models-research.html)
- Captured [compliance policy](../raw/web/semianalysis/compliance-policies.html)
- Captured [public post sitemap](../raw/web/semianalysis/post-sitemap.xml)

Verdict: high-quality thematic/context source for ADI, but unranked for the exact challenge until a dated, target-specific forecast passage is produced.

## Keith Gill / Roaring Kitty / DeepFuckingValue

Keith Gill’s sworn testimony establishes that his public thesis concerned GameStop: undervaluation, lower bankruptcy probability than the market implied, console-cycle cash flow, and potential business reinvention. It also acknowledges that many early options expired worthless and that his timing was imperfect. That makes his history an excellent example of why a backtest must retain losses, revisions, thesis horizons, and position-independent outcome rules.

- Kernel-captured [Reddit submitted-history page](../raw/reddit/deepfuckingvalue_submitted.json)
- Kernel-captured [X profile page](../raw/x/roaringkitty_profile.json)
- Primary [congressional testimony](../raw/web/keith_gill/congressional-testimony.pdf)

No public claim about the four target companies was found. His GameStop/Chewy record is therefore not transplanted into an ADI/HD/Hays/Deere ranking.

## Kernel social acquisition

Kernel CLI produced authenticated/read-only captures for X, LinkedIn, and old Reddit. The raw directory retains successful output as well as empty X captures where the dynamic timeline collector yielded no items. Successful captures include target-company X search output, LinkedIn result pages for ADI and Hays, Reddit result pages for all four targets, Gill’s Reddit history, and Gill’s X profile.

Social evidence is admitted to scoring only when it has an identifiable author, a publication time before the event, a falsifiable metric or declared directional rubric, and a later primary outcome. Search-result visibility, likes, and confident prose are not accuracy evidence.

## Why hedge funds are mostly absent

Public 13F filings are delayed holdings snapshots, not earnings forecasts. A hedge fund enters this corpus only through a dated, attributable thesis or model with a target and horizon. Hedgeye’s public Home Depot research met that condition at firm-team level; generic fund ownership did not.
