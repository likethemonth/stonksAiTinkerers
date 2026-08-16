# Thought-leader evaluation method

## Purpose and boundary

This framework evaluates public, long-horizon thesis builders: people who make attributable claims about how an industry, company, technology, policy regime, or market structure will evolve. It is suitable for records analogous in form to a multi-year technology thesis or a deeply documented activist-style investment thesis. It does **not** assume that any named person qualifies, and it does not award status by reputation.

This is a different task from near-term EPS forecasting. The existing point-in-time methodology correctly keeps accounting forecasts, price targets, and broad theses in separate scoring lanes ([01-METHODOLOGY.md:15](/Users/jooniverse/stonksAiTinkerers/analyst_knowledge/knowledge/01-METHODOLOGY.md:15)). A quarterly EPS call can be judged against one well-defined reported number. A long-horizon thesis must instead be judged against an ex-ante causal model, declared horizons, intermediate milestones, revisions, counterevidence, fundamental outcomes, and only then market returns.

```text
                         EVALUATION CUTOFF
                                │
        EX-ANTE RECORD          │        EX-POST ACCOUNTABILITY
                                │
 dated thesis ── causal chain ──┼── milestone observations
      │              │          │          │
      ├─ horizon      ├─ risks   │          ├─ fundamental outcomes
      ├─ confidence   └─ failure │          ├─ revisions / closure
      ├─ target           tests  │          └─ benchmarked returns
      └─ conflicts                │
             │                   │                   │
             └──── frozen thesis-family record ─────┘
                                │
                  quality panel + accountability panel
                                │
                         auditable scorecard
```

The atomic unit is a **thesis family**, not a post, article, trade, or personality. A family contains the initial thesis, all material revisions, declared confidence, causal chain, falsifiers, source record, and a frozen outcome map. Author-level evaluation aggregates eligible thesis families without discarding losses or expired ideas.

## What this method measures

The score answers:

> Did this author produce original, causally useful, falsifiable, well-evidenced theses; maintain them honestly through time; disclose incentives; and demonstrate calibrated judgment on relevant targets across a substantially complete public history?

It does **not** answer:

- Who has the most followers, subscribers, media appearances, likes, reposts, or cultural influence?
- Who produced the single highest-return trade?
- Who writes most confidently or elegantly?
- Who was eventually “directionally right” after an unspecified amount of time?
- Who would have generated an investable portfolio without explicit execution rules?

Historical accuracy alone does not establish causal insight, independence, investability, or future skill ([01-METHODOLOGY.md:28](/Users/jooniverse/stonksAiTinkerers/analyst_knowledge/knowledge/01-METHODOLOGY.md:28)). This method makes those distinctions visible rather than collapsing them into one hit rate.

## Eligibility and minimum evidence

### Thesis-family evidence packet

A thesis family is scoreable only when the packet contains all of the following:

1. **Identity:** a stable `author_id` and evidence connecting aliases to the same author.
2. **Dated source:** an archived source with original URL, publication time, first-seen or availability time, capture time, and content hash.
3. **Verbatim thesis:** the exact contemporaneous passage, not a retrospective paraphrase.
4. **Target:** the company, security, industry, technology, policy, or macro variable to which the thesis directly applies.
5. **Horizon:** an explicit date/duration/event horizon, or a conservative horizon reconstructed solely from contemporaneous language and marked `reconstructed`.
6. **Testable content:** at least one predicted state, measurable consequence, threshold, ordering, or event.
7. **Failure content:** at least one explicit or mechanically derived condition that would count against the thesis.
8. **Revision search:** a documented search for later revisions, withdrawals, reversals, deletions, and follow-ups.
9. **Conflict record:** contemporaneous position, compensation, employment, sponsorship, access, and material affiliation disclosures, or a documented `not found` result.
10. **Frozen outcome map:** milestones and outcome rules defined from the ex-ante record before the evaluator examines later outcomes.

An identifiable author, pre-event timestamp, falsifiable claim, and later primary outcome are already required for social evidence in this corpus ([04-REQUESTED-SOURCE-ARCHETYPES.md:36](/Users/jooniverse/stonksAiTinkerers/analyst_knowledge/knowledge/04-REQUESTED-SOURCE-ARCHETYPES.md:36)). The thought-leader lane adds causal, completeness, revision, and conflict requirements.

### Evidence status

| Status | Requirement | Permitted use |
|---|---|---|
| `ineligible` | identity, date, source integrity, target, or testable content missing | discovery/context only; no score |
| `case-study` | one eligible family, or incomplete history search | thesis-level score with caps; no author rank |
| `provisional` | at least 3 eligible families, at least 2 matured/closed, at least 12 months of searched history | author score shown with uncertainty; no definitive rank |
| `rankable` | at least 5 eligible families, at least 3 matured/closed, at least 24 months of searched history, and completeness level ≥3 | comparable within a declared lane |
| `robust` | at least 10 eligible families across at least 2 independent targets or regimes, at least 6 matured/closed | rankable with sensitivity and leave-one-out analysis |

Open theses remain in the denominator and are marked censored; they are not scored as successes or failures before their frozen horizon.

## Score architecture

Nine dimensions total 100 points. Each dimension receives an integer level from 0 to 4. Weighted points are:

```text
dimension points = dimension weight × level / 4
total score      = sum(dimension points), subject to eligibility caps
```

The two reporting panels must always accompany the total:

- **Thesis construction — 58 points:** originality, causal depth, falsifiability, target relevance, provenance.
- **Longitudinal accountability — 42 points:** revision conduct, history completeness, calibration/outcomes, conflict disclosure.

| Dimension | Weight | Panel |
|---|---:|---|
| 1. Originality and lead time | 12 | thesis construction |
| 2. Causal depth | 12 | thesis construction |
| 3. Falsifiability and specificity | 12 | thesis construction |
| 4. Revision conduct | 10 | longitudinal accountability |
| 5. History completeness, including losers | 12 | longitudinal accountability |
| 6. Calibration and outcome discipline | 14 | longitudinal accountability |
| 7. Conflict disclosure | 6 | longitudinal accountability |
| 8. Target relevance | 8 | thesis construction |
| 9. Evidentiary provenance | 14 | thesis construction |
| **Total** | **100** | |

### Interpretation bands

| Total | Label | Meaning |
|---:|---|---|
| 90–100 | exemplary | rare combination of original work, rigorous evidence, and sustained accountability |
| 75–89.99 | strong | valuable thesis builder with bounded, disclosed weaknesses |
| 60–74.99 | credible | useful in a defined lane, but material evidence, calibration, or completeness limitations |
| 40–59.99 | weak | interesting case study; insufficient basis for thought-leader reliance |
| 0–39.99 | non-qualifying | narrative, promotion, or fragmented evidence rather than auditable leadership |

Bands never override an `ineligible`, `case-study`, or `provisional` status.

## Dimension rubrics

### 1. Originality and lead time — 12 points

**Measured object:** the earliest attributable articulation of the thesis’s load-bearing mechanism relative to a frozen prior-art corpus and the relevant outcome/milestone.

| Level | Rubric |
|---:|---|
| 0 | copied, unattributed, only stated after the outcome, or no prior-art search |
| 1 | common consensus restatement; no distinct mechanism; negligible lead |
| 2 | meaningful synthesis or non-consensus emphasis, but precedents contain the core mechanism; modest lead |
| 3 | independently combines evidence into a materially distinct mechanism before broad recognition; substantial lead |
| 4 | earliest found articulation **within the declared search corpus**, with a distinct testable mechanism and long lead before consensus or milestone evidence |

Rules:

- Never claim “first” without the qualifier “earliest found in the searched corpus.”
- Freeze the comparison corpus and search queries before reading outcomes.
- Measure both calendar lead and normalized lead: `days from first availability to milestone / frozen thesis horizon days`.
- A contrarian conclusion without a new mechanism scores at most level 2.
- Being early and wrong is still early; outcome quality is scored elsewhere.

### 2. Causal depth — 12 points

**Measured object:** a directed causal graph reconstructed only from contemporaneous claims.

| Level | Rubric |
|---:|---|
| 0 | slogan, target price, or conclusion with no mechanism |
| 1 | one unsupported cause→effect assertion |
| 2 | multi-step chain with at least one measurable intermediate variable, but weak alternatives or boundary conditions |
| 3 | coherent chain with measurable intermediates, timing, constraints, alternatives, and explicit risks |
| 4 | level 3 plus quantified or tightly bounded relationships, interaction effects, competing hypotheses, and evidence that can discriminate among them |

The evaluator stores nodes, signed edges, lags, evidence IDs, and alternative explanations. Complexity alone earns nothing: an ornate graph with no discriminating observations scores below a simple, testable mechanism.

### 3. Falsifiability and specificity — 12 points

**Measured object:** whether a reasonable evaluator could decide, using rules known before outcomes, what would support, weaken, or refute the thesis.

| Level | Rubric |
|---:|---|
| 0 | unfalsifiable, purely rhetorical, or indefinitely extendable |
| 1 | direction stated but target, magnitude, horizon, or failure condition absent |
| 2 | target and horizon present with at least one measurable consequence; wide interpretive freedom remains |
| 3 | target, horizon, threshold/range, intermediate milestones, and failure conditions are substantially specified |
| 4 | level 3 plus explicit probability/confidence, competing outcomes, decision boundaries, and treatment of partial realization |

Retrospectively reconstructed horizons cap this dimension at level 2. “Eventually,” “massive,” “the future,” and unconstrained price upside are not horizons or thresholds.

### 4. Revision conduct — 10 points

**Measured object:** how the author maintains, changes, or closes the thesis as new evidence arrives.

| Level | Rubric |
|---:|---|
| 0 | deletes, silently rewrites, denies, or relabels the original thesis after outcomes |
| 1 | selective follow-up; extensions after missed horizons; changes cannot be reconciled |
| 2 | revisions are public but irregular, late, or unclear about changed assumptions/confidence |
| 3 | dated revision chain states new evidence, changed nodes, confidence, horizon, and whether the old thesis is superseded |
| 4 | level 3 plus timely negative updates, explicit closure/withdrawal, preserved originals, and stable version identifiers |

Score the initial, latest-pre-horizon, and all-revisions policies separately as sensitivity checks. This mirrors the existing corpus rule that revisions must be explicit and that `first`, `latest`, and `all` are distinct evaluation policies ([01-METHODOLOGY.md:11](/Users/jooniverse/stonksAiTinkerers/analyst_knowledge/knowledge/01-METHODOLOGY.md:11)).

### 5. History completeness, including losers — 12 points

**Measured object:** how much of the author’s eligible public thesis population is captured, not how many winning examples are presented.

| Level | Rubric |
|---:|---|
| 0 | self-selected winners, marketing summary, or unknown denominator |
| 1 | opportunistic sample; obvious losses, expiries, or reversals absent |
| 2 | documented channel/date search with material gaps; estimated observable coverage 70–89% |
| 3 | reproducible search across declared channels and dates; ≥90% observable coverage; losses, expiries, deletions, and open calls retained |
| 4 | ≥95% observable coverage plus independent archive reconciliation, duplicate/repost control, deleted-item traces, and explicit missingness bounds |

The completeness ratio is:

```text
captured eligible thesis families
────────────────────────────────────────────────────────────
all eligible families found by the frozen multi-route search
```

This is **observable coverage**, not a claim that unknowable private or deleted material never existed. A public history that selects winners is a documented source risk in this corpus ([04-REQUESTED-SOURCE-ARCHETYPES.md:9](/Users/jooniverse/stonksAiTinkerers/analyst_knowledge/knowledge/04-REQUESTED-SOURCE-ARCHETYPES.md:9)); the Gill archetype also illustrates why losses, revisions, and imperfect timing must remain visible ([04-REQUESTED-SOURCE-ARCHETYPES.md:26](/Users/jooniverse/stonksAiTinkerers/analyst_knowledge/knowledge/04-REQUESTED-SOURCE-ARCHETYPES.md:26)).

### 6. Calibration and outcome discipline — 14 points

**Measured object:** whether expressed confidence matches realized outcomes across the substantially complete thesis history, using frozen milestone, fundamental, and return rules.

| Level | Rubric |
|---:|---|
| 0 | no scorable outcomes, only winning anecdotes, or outcome windows selected after the fact |
| 1 | poor discrimination/calibration, repeated horizon misses, or a single lucky return dominates |
| 2 | mixed record; confidence mostly qualitative; results at least reported symmetrically with baselines |
| 3 | useful discrimination and calibration across enough matured theses, with uncertainty, baselines, and lane-specific results |
| 4 | strong out-of-sample calibration and milestone accuracy across targets/regimes, surviving leave-one-out, timing, benchmark, and revision sensitivities |

Required outputs:

- probabilities: Brier score, log loss, calibration plot, calibration slope/intercept;
- ordinal confidence: predeclared confidence bins with empirical outcome rates;
- milestones: weighted milestone support score and time-to-event error;
- fundamentals: standardized direction/error within metric-specific lanes;
- returns: benchmark-relative total return, drawdown, and horizon sensitivity;
- uncertainty: bootstrap or block-bootstrap intervals and effective sample size.

Without contemporaneous numeric probabilities or predeclared confidence bins, the calibration component is capped at level 2. A correct outcome with no ex-ante confidence is accuracy, not calibration.

### 7. Conflict disclosure — 6 points

**Measured object:** contemporaneous transparency about material incentives and changes in those incentives.

| Level | Rubric |
|---:|---|
| 0 | known material conflict concealed, false disclosure, or unverifiable categorical denial |
| 1 | disclosure appears only after challenge/outcome or is materially incomplete |
| 2 | generic disclosure such as “may hold positions,” without target-specific timing or nature |
| 3 | contemporaneous target-specific position/affiliation/compensation disclosure with material limitations |
| 4 | level 3 plus prompt updates when exposure changes, separation of analysis from promotion, and independently reconcilable evidence where lawful |

Position size is not required when disclosure would be unsafe or legally restricted; the author can state the nature and direction of exposure. A disclosed conflict is not a penalty. The score measures transparency, not presumed bias.

### 8. Target relevance — 8 points

**Measured object:** the distance between what the thesis actually targets and the object for which the evaluator wants to rely on it.

| Level | Rubric |
|---:|---|
| 0 | no identifiable relationship to the target |
| 1 | broad adjacent theme with no explicit transmission mechanism to the target |
| 2 | sector/value-chain relevance with an explicit but unquantified target link |
| 3 | direct target-specific thesis or quantified transmission from an upstream/downstream driver |
| 4 | direct target, metric, horizon, causal path, and decision relevance all align |

Target relevance is always scored for a declared task. A strong sector thesis does not become a company-specific forecast by association. The local source-archetype review applies exactly this rule: high-quality thematic work remains unranked for an exact target until a dated target-specific claim is produced ([04-REQUESTED-SOURCE-ARCHETYPES.md:16](/Users/jooniverse/stonksAiTinkerers/analyst_knowledge/knowledge/04-REQUESTED-SOURCE-ARCHETYPES.md:16)).

### 9. Evidentiary provenance — 14 points

**Measured object:** traceability, source quality, and the author’s distinction between observation, inference, and speculation.

| Level | Rubric |
|---:|---|
| 0 | no recoverable source, fabricated/altered evidence, or retrospective quotation without provenance |
| 1 | secondary assertions and screenshots with weak attribution or missing dates |
| 2 | attributable dated sources, but important claims depend on secondary reporting or incomplete locators |
| 3 | archived primary/authoritative sources, precise locators, content hashes, and clear observation-vs-inference labels for most load-bearing claims |
| 4 | level 3 plus triangulation across independent sources, reproducible data/code where applicable, source limitations, and a chain of custody for corrections |

Every load-bearing edge in the causal graph must cite evidence. Source popularity, prestige, or professional title does not substitute for provenance.

## Eligibility caps and hard failures

These caps apply after the weighted score:

| Condition | Consequence |
|---|---|
| no attributable dated source or no testable claim | `ineligible`; no score |
| falsifiability level 0 or target relevance level 0 | context/narrative only; no thought-leader rank |
| completeness level 0 | case-study status; total capped at 49.99 |
| provenance level 0 | `ineligible`; no score |
| provenance level 1 | total capped at 59.99 |
| known material conflict concealed | conflict level 0 and total capped at 59.99 |
| retrospective horizon reconstruction | falsifiability capped at level 2 |
| no probability/confidence history | calibration dimension capped at level 2 |
| fewer than rankable minimum families/maturities | status remains `case-study` or `provisional`, regardless of total |

Hard failures are factual findings and require evidence. Absence of a found disclosure after a bounded search is recorded as `not found`, not automatically as concealment.

## Anti-hindsight protocol

### Dual-pass evaluation

The evaluator performs two isolated passes.

**Pass A — ex ante reconstruction**

Only material available on or before the thesis cutoff is visible. The evaluator freezes:

- verbatim thesis and author identity;
- source availability timestamp;
- target and comparison lane;
- causal graph and competing hypotheses;
- horizon and allowable grace rule;
- milestone list, weights, direction, threshold, and observation source;
- failure conditions and partial-credit rule;
- confidence/probability mapping;
- benchmark and return windows;
- revision-family search protocol.

The packet receives a hash. No future fact may be added as though it were an ex-ante prediction.

**Pass B — outcome adjudication**

The evaluator opens only the sources and windows named in the frozen packet, records observations, and applies the frozen scoring rules. Additional outcomes may be discussed as exploratory evidence but cannot change the confirmatory score.

### Anti-hindsight rules

1. **No outcome-shaped thesis:** later language cannot be imported into the initial thesis.
2. **No flexible horizon:** missed dates remain misses; extensions are revisions, not retroactive clarifications.
3. **No best-window returns:** report every predeclared horizon and the full path, not the local peak.
4. **No winner-only inclusion:** the search protocol runs before case selection and retains losers, withdrawals, expiries, and open theses.
5. **No target substitution:** success in an adjacent company, metric, or theme cannot resolve the original target.
6. **No mechanism substitution:** being right for a different reason receives outcome credit but not causal-confirmation credit.
7. **No revised-source leakage:** use the archived version available at the cutoff, not a silently updated page.
8. **No current-constituent universe:** reconstruct securities, benchmarks, and target membership point-in-time.
9. **No popularity-conditioned sampling:** discovery routes must include archive/time/search sweeps, not only top or viral posts.
10. **No private-trade inference:** public thesis quality is scored independently of unverifiable position timing or P&L.
11. **No duplicated conviction:** reposts, interviews repeating the same thesis, and syndicated articles remain one family.
12. **No one-case author claims:** thesis-level evidence cannot establish author-level calibration.
13. **No silent missingness:** unresolved, inaccessible, deleted, and unobservable cases receive explicit status/reason codes.
14. **No multiplicity concealment:** if many targets, horizons, or milestone definitions are explored, label them exploratory or adjust inference.

The existing backtest’s no-lookahead contract—publication strictly before the outcome, primary actuals, and machine-readable exclusions—remains binding ([01-METHODOLOGY.md:7](/Users/jooniverse/stonksAiTinkerers/analyst_knowledge/knowledge/01-METHODOLOGY.md:7)).

## Comparing a long-horizon thesis to reality

### 1. Freeze the causal graph

Represent the thesis as ordered claims:

```text
driver A ──(+/lag)──> intermediate B ──(+/lag)──> fundamental C
    │                       │                           │
    └─ failure A0           └─ failure B0              └─ valuation/return D
```

Each node records:

- exact predicted state or direction;
- threshold/range;
- earliest/latest expected date;
- source excerpt and locator;
- confidence;
- whether the node is necessary, sufficient, supportive, or contextual;
- competing explanation.

### 2. Predeclare milestones

Milestones are not searched for after the thesis “looks right.” Each milestone receives a frozen weight summing to 1.0.

| Field | Meaning |
|---|---|
| `milestone_id` | stable identifier |
| `prediction` | exact expected state/change |
| `direction` | increase/decrease/occur/not occur |
| `threshold_or_range` | measurable boundary |
| `window_start`, `window_end` | allowed observation window |
| `evidence_source` | primary/authoritative source fixed ex ante |
| `weight` | importance to the causal thesis |
| `necessity` | necessary/supportive/contextual |
| `failure_rule` | what counts against the milestone |

Milestone score:

```text
support value: +1 supported, +0.5 partially supported, 0 ambiguous/unobservable,
               -0.5 weakened, -1 contradicted

weighted milestone support = Σ(weight × support value)
```

Report unobservable weight separately. Do not renormalize it away in the primary result; otherwise missing evidence can make a thesis appear stronger.

### 3. Evaluate fundamentals in comparable lanes

Fundamental outcomes are compared only with metrics the thesis actually implicated:

- demand/volume;
- revenue or bookings;
- unit economics/margins;
- capital intensity/capex;
- capacity/supply;
- market share/adoption;
- balance-sheet durability;
- regulatory/policy state;
- bankruptcy/distress probability;
- valuation multiple, if explicitly predicted.

Use first-party filings, releases, regulatory data, or frozen authoritative datasets. Normalize units, calendars, restatements, and corporate actions. Do not score a technology adoption thesis as an EPS forecast unless the thesis explicitly forecast the EPS transmission.

### 4. Treat returns as a distinct corroboration lane

Returns matter for investment theses but are not proof of the causal story. A price can rise before fundamentals, fall despite eventual fundamental confirmation, or rise for a mechanism the author did not predict.

Primary return rules:

- entry is the first tradable close or next open after `available_at`, fixed in advance;
- horizons are fixed calendar or trading-day windows derived from the ex-ante thesis;
- use total returns with splits, dividends, delistings, mergers, and FX handled consistently;
- compare against a frozen broad benchmark and, when appropriate, sector/factor benchmark;
- report absolute return, excess return, drawdown, time under water, and path, not only endpoint;
- retain every predeclared horizon, even when another window looks better;
- overlapping thesis families are handled by one declared family/portfolio rule;
- author popularity dates and subsequent attention shocks do not redefine entry.

Required comparison table:

| Lane | Primary result | Interpretation |
|---|---|---|
| causal milestones | weighted support and contradicted necessary nodes | did the predicted mechanism unfold? |
| fundamentals | metric-specific standardized result | did the target’s economics evolve as predicted? |
| returns | benchmark-relative path and endpoint | did the market reward the exposure under fixed rules? |
| calibration | predicted confidence versus realized family outcome | was confidence proportionate? |

Never collapse the four lanes into “right” without showing each component.

### 5. Adjudicate overall thesis outcome

The confirmatory outcome uses a frozen decision table:

| Outcome | Default rule |
|---|---|
| `supported` | no necessary node contradicted; weighted milestone support ≥0.60; principal fundamental prediction supported in horizon |
| `partially-supported` | milestone support 0.15–0.59, or mechanism supported but magnitude/timing materially missed |
| `ambiguous` | milestone support -0.14–0.14, excessive unobservable weight, or offsetting necessary evidence |
| `weakened` | milestone support -0.59–-0.15 or key timing/scale claims miss |
| `refuted` | necessary node contradicted or milestone support ≤-0.60 |
| `censored-open` | frozen horizon has not ended |
| `not-evaluable` | outcome sources unavailable or target ceased comparability for exogenous reasons not covered by rules |

Thresholds can change for a domain only if predeclared before outcomes and applied to all comparable theses.

## Aggregating thesis families to an author

Author scores are not simple averages of handpicked cases.

1. Run the frozen discovery protocol over a declared author/channel/date scope.
2. Cluster semantic duplicates into thesis families before viewing returns.
3. Include all eligible families; retain ineligible families and reason codes.
4. Compute dimension levels per family where meaningful.
5. Score author-level revision, completeness, conflict, and calibration from the full history, not by averaging case prose.
6. Weight families equally in the primary author result. Exposure- or conviction-weighted variants are sensitivity analyses only when contemporaneous weights exist.
7. Report median and distribution of thesis-construction scores, not only mean.
8. Use a hierarchical or shrinkage estimate for calibration when sample sizes differ.
9. Publish leave-one-family-out results so one spectacular winner cannot dominate.
10. Partition results by target type, horizon, and regime; do not compare incompatible lanes.

Minimum author report:

```text
searched period / channels
found families / eligible / matured / open / excluded
observable completeness and gaps
construction score distribution
accountability score
calibration with interval
milestone outcomes by status
return outcomes by frozen horizon and benchmark
losers, withdrawals, and largest misses
conflicts and disclosure quality
leave-one-out and rule sensitivities
```

## Explicit exclusion of popularity

Popularity receives **zero points** and is excluded from all tie-breaks.

The following are not score inputs:

- follower/subscriber count;
- likes, reposts, comments, views, quote-posts, or search rank;
- podcast, television, conference, or press appearances;
- celebrity endorsements or institutional prestige;
- meme status, cultural impact, community size, or fan activity;
- writing charisma, certainty, volume, or frequency by itself;
- size of a disclosed profit or notoriety of one trade.

Popularity metadata may be retained only to study dissemination, crowding, or discovery bias. If used for source discovery, the pipeline must also run non-popularity-sorted archive and date searches. Search-result visibility and likes are already excluded as accuracy evidence in this corpus ([04-REQUESTED-SOURCE-ARCHETYPES.md:38](/Users/jooniverse/stonksAiTinkerers/analyst_knowledge/knowledge/04-REQUESTED-SOURCE-ARCHETYPES.md:38)).

## Worked generic examples

These examples are fictional and demonstrate scoring mechanics, not judgments about named people.

### Example A — early infrastructure bottleneck thesis

In January 2022, Author A publishes an archived report arguing that accelerated-computing adoption will be constrained by power delivery and specialized component lead times. The report names a 24–36 month horizon, maps demand → capacity → lead times → capex, assigns 65% confidence, states three failure conditions, cites primary supplier and grid data, and discloses no position. Quarterly revisions preserve the original and lower confidence when one milestone slips. A full archive search finds six thesis families including two losses.

Frozen milestones include component lead-time expansion, data-center power interconnection backlog, supplier capex, and target-customer adoption. Three support the thesis in-window, one is partial, and no necessary node fails. The related basket outperforms the frozen sector benchmark, but returns are reported separately.

| Dimension | Level | Points |
|---|---:|---:|
| originality/lead | 3 | 9.0 |
| causal depth | 4 | 12.0 |
| falsifiability | 4 | 12.0 |
| revisions | 3 | 7.5 |
| completeness | 4 | 12.0 |
| calibration/outcomes | 3 | 10.5 |
| conflict disclosure | 4 | 6.0 |
| target relevance | 4 | 8.0 |
| provenance | 4 | 14.0 |
| **Total** |  | **91.0 — exemplary** |

The return does not create the score. The high result comes from early, testable mechanism design plus a substantially complete and accountable history.

### Example B — rigorous thesis that is wrong

Author B publishes a direct company thesis with a two-year horizon, measurable unit-economics milestones, 60% confidence, primary evidence, and clear position disclosure. The author preserves revisions and closes the thesis after the necessary adoption milestone fails. The stock underperforms and the fundamental outcome contradicts the core mechanism. The complete history includes the loss.

| Dimension | Level | Points |
|---|---:|---:|
| originality/lead | 2 | 6.0 |
| causal depth | 3 | 9.0 |
| falsifiability | 4 | 12.0 |
| revisions | 4 | 10.0 |
| completeness | 4 | 12.0 |
| calibration/outcomes | 1 | 3.5 |
| conflict disclosure | 3 | 4.5 |
| target relevance | 4 | 8.0 |
| provenance | 4 | 14.0 |
| **Total** |  | **79.0 — strong process, poor realized calibration** |

This is intentionally not scored as worthless. It is a high-quality falsified thesis, which is more epistemically useful than an unfalsifiable correct slogan. Repeated false theses would lower author-level calibration and eventually the aggregate score.

### Example C — viral winning narrative

Author C posts “this company will dominate; 10× eventually,” cites no evidence, gives no horizon or failure condition, does not disclose a position, and later reposts the call after the stock rises. Only winning posts are available; old losses appear deleted. The post has millions of views.

| Dimension | Level | Points |
|---|---:|---:|
| originality/lead | 1 | 3.0 |
| causal depth | 1 | 3.0 |
| falsifiability | 0 | 0.0 |
| revisions | 0 | 0.0 |
| completeness | 0 | 0.0 |
| calibration/outcomes | 0 | 0.0 |
| conflict disclosure | 0 | 0.0 |
| target relevance | 2 | 4.0 |
| provenance | 1 | 3.5 |
| raw total |  | 13.5 |

The family is narrative/context only because falsifiability is level 0. Its popularity and realized return add no points.

### Example D — excellent adjacent-domain thinker

Author D produces a well-evidenced, calibrated thesis about an upstream technology bottleneck but never specifies how it affects the requested downstream company. The work can score highly as a sector thesis, while target relevance for a downstream company task is level 1. It must not be imported into the company-specific leaderboard. The correct remedy is a separate sector lane, not a subjective relevance bonus.

## Comparison and reporting rules

Thought-leader comparisons are valid only within declared lanes such as:

- company-specific long thesis, 2–5 years;
- technology adoption thesis, 3–10 years;
- sector capacity/cycle thesis, 1–5 years;
- policy/regulatory thesis, event-defined horizon;
- macro regime thesis, predeclared duration;
- activist/turnaround thesis, company-specific milestone horizon.

Do not compare a ten-year technology scenario directly with a six-month security call. Publish dimension profiles as well as totals: two authors can have the same score while one is an original but poorly calibrated theorist and the other a less original but exceptionally accountable operator.

Every leaderboard must state:

- lane and eligibility status;
- searched sources, dates, and known gaps;
- corpus `as_of` and manifest hash;
- family, matured, open, and excluded denominators;
- weights, caps, and any deviations from this method;
- construction and accountability panels;
- dimension levels with cited evidence;
- outcome distributions and confidence intervals;
- largest winners **and** largest losers;
- leave-one-out and alternate-horizon sensitivity;
- conflict findings and provenance tier;
- an explicit statement that popularity was excluded.

## Quality-control checklist

- [ ] Is the unit a thesis family rather than a post or trade?
- [ ] Was the ex-ante packet frozen before later outcomes were opened?
- [ ] Are full original, revision, and closure records preserved?
- [ ] Does the search protocol include losers, expiries, withdrawals, and deleted traces?
- [ ] Is “earliest” bounded to a declared prior-art corpus?
- [ ] Does each causal edge have contemporaneous evidence and a lag?
- [ ] Are target, horizon, threshold, probability/confidence, and failure rules explicit?
- [ ] Are milestone, fundamental, return, and calibration lanes reported separately?
- [ ] Are all return windows and benchmarks frozen rather than optimized afterward?
- [ ] Are unobservable outcomes shown without denominator renormalization?
- [ ] Are direct and adjacent target relevance kept in separate lanes?
- [ ] Are conflicts assessed as disclosure quality, not presumed guilt?
- [ ] Are author-level conclusions withheld below minimum sample/completeness thresholds?
- [ ] Are uncertainty and leave-one-family-out results published?
- [ ] Are likes, followers, virality, celebrity, and prestige absent from scoring and tie-breaks?

## Final principle

A thought leader is not someone who can be made to look prescient after the fact. Under this method, the strongest record is one that was **distinct before consensus, explicit about how and when change would occur, vulnerable to being proven wrong, updated honestly, complete enough to include failure, calibrated across multiple theses, transparent about incentives, relevant to the target, and traceable to primary evidence**.
