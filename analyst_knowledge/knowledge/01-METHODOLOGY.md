# Point-in-time analyst backtest methodology

## Unit of analysis

The atomic record is a dated claim by an identifiable author. A claim retains its original URL, publication timestamp, exact target period, metric definition, units, provenance tier, and a short evidence excerpt. Article-level consensus is a separate benchmark and is never attributed to the article author.

## No-lookahead contract

A resolved claim is eligible only when its publication timestamp is strictly earlier than the issuer's report timestamp and both are no later than the selected `as_of` cutoff. The actual must come from a first-party earnings release or filing and match the claim's metric definition and units. Same-time, post-event, missing-event, open, and unresolvable records remain in the corpus but are excluded with a machine-readable reason.

## Revisions and duplication

The default policy scores the latest independently published revision before the event. `first` and `all` are available for sensitivity analysis. Exact semantic duplicates and reposts do not create extra observations. Author aliases must resolve to a stable `author_id`.

## Comparable scoring lanes

Rankings are partitioned by company, metric, horizon bucket, metric class, and numeric versus directional claim type. Accounting forecasts are not mixed with price targets or broad theses.

- Numeric point error is absolute forecast error divided by the absolute actual.
- Numeric ranges receive zero range-distance error when the actual falls inside; otherwise distance to the nearest boundary is scaled by the actual. Midpoint bias is retained separately.
- Directional claims are scored as hits only against a predeclared reference such as point-in-time consensus. Probabilistic calls also receive a Brier score.
- When point-in-time consensus is available, `consensus_skill = consensus_error - author_error`; positive values indicate incremental skill.

## Small samples and rank status

Numeric errors are shrunk toward the corpus median with three prior observations. Directional hit rates use a Beta(1,1) posterior and expose a Wilson 95% interval. Fewer than three observations are labelled `provisional` and do not receive a rank. This threshold is configurable and should be raised for production capital allocation.

## What the ranking does not prove

Historical accuracy does not establish causal insight, independence, investability, or future accuracy. Public histories are subject to deletion and selection bias; paid archives may contain calls absent from the public record. Unverifiable marketing track records are preserved as claims about a source, not accepted as scored evidence.
