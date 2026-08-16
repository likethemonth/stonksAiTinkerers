"""Auditable scoring for dated analyst claims.

The scorer deliberately keeps accounting forecasts, market-price calls, and
qualitative theses in separate lanes.  It never treats publication after the
reported event as a forecast and never silently turns an article's consensus
number into the named author's own call.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable


class BacktestError(ValueError):
    """Raised when a corpus violates a point-in-time invariant."""


HORIZON_BUCKETS = (
    (0, 7, "0-7d"),
    (8, 30, "8-30d"),
    (31, 90, "31-90d"),
    (91, math.inf, "91d+"),
)

NUMERIC_TYPES = {"numeric_point", "numeric_range"}
VALID_TYPES = NUMERIC_TYPES | {"directional", "thesis"}
VALID_RESOLUTION = {"resolved", "open", "unresolvable"}
VALID_PROVENANCE = {"primary", "direct_social", "secondary", "aggregator"}


def source_role(claim: dict[str, Any]) -> str:
    explicit = claim.get("source_role")
    if explicit:
        return str(explicit)
    author = str(claim.get("author_id") or "").lower()
    display = str(claim.get("author_display") or "").lower()
    if "consensus" in author or "consensus" in display:
        return "consensus"
    if "unknown" in author or "unidentified" in display:
        return "anonymous"
    if "research-team" in author or "research team" in display or "sector" in display:
        return "firm_team"
    return "individual"


def parse_time(value: str) -> datetime:
    """Parse an ISO timestamp; date-only values are midnight UTC."""
    if not value:
        raise BacktestError("missing timestamp")
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise BacktestError(f"invalid ISO timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def horizon_bucket(days: int) -> str:
    for low, high, label in HORIZON_BUCKETS:
        if low <= days <= high:
            return label
    raise BacktestError(f"negative forecast horizon: {days}")


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise BacktestError(f"expected a number, got {value!r}") from exc
    if not math.isfinite(number):
        raise BacktestError(f"non-finite number: {value!r}")
    return number


def _scale(actual: float, units: str | None) -> float:
    # Percentage-point calls should not explode when the actual is close to 0%.
    if units in {"%", "percentage_points", "pp"}:
        return max(abs(actual), 1.0)
    return max(abs(actual), 1e-9)


def _claim_fingerprint(claim: dict[str, Any]) -> str:
    stable = "|".join(
        str(claim.get(key) or "").strip().lower()
        for key in (
            "author_id",
            "event_id",
            "metric",
            "claim_type",
            "forecast_value",
            "forecast_low",
            "forecast_high",
            "direction",
            "claim_text",
        )
    )
    return hashlib.sha256(stable.encode()).hexdigest()[:20]


def validate_claim(claim: dict[str, Any]) -> None:
    required = (
        "claim_id",
        "author_id",
        "company",
        "ticker",
        "claim_type",
        "resolution_status",
        "source_url",
        "provenance_tier",
    )
    missing = [key for key in required if not claim.get(key)]
    if missing:
        raise BacktestError(f"claim {claim.get('claim_id', '<unknown>')} missing {missing}")
    if claim["claim_type"] not in VALID_TYPES:
        raise BacktestError(f"invalid claim_type: {claim['claim_type']}")
    if claim["resolution_status"] not in VALID_RESOLUTION:
        raise BacktestError(f"invalid resolution_status: {claim['resolution_status']}")
    if claim["provenance_tier"] not in VALID_PROVENANCE:
        raise BacktestError(f"invalid provenance_tier: {claim['provenance_tier']}")
    if claim.get("published_at"):
        parse_time(claim["published_at"])
    if claim["claim_type"] == "numeric_point" and _number(claim.get("forecast_value")) is None:
        raise BacktestError(f"numeric point claim {claim['claim_id']} has no forecast_value")
    if claim["claim_type"] == "numeric_range":
        low, high = _number(claim.get("forecast_low")), _number(claim.get("forecast_high"))
        if low is None or high is None or low > high:
            raise BacktestError(f"invalid numeric range in {claim['claim_id']}")
    if claim["claim_type"] == "directional" and claim.get("direction") not in {
        "above", "below", "above_consensus", "below_consensus", "outperform_peer",
        "underperform_peer", "up", "down", "meet", "positive", "negative"
    }:
        raise BacktestError(f"invalid direction in {claim['claim_id']}")


def normalize_events(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        event_id = event.get("event_id")
        if not event_id or event_id in result:
            raise BacktestError(f"missing or duplicate event_id: {event_id!r}")
        parse_time(event["reported_at"])
        if not isinstance(event.get("actuals"), dict):
            raise BacktestError(f"event {event_id} has no actuals map")
        result[event_id] = event
    return result


def _resolve_actual(claim: dict[str, Any], event: dict[str, Any]) -> tuple[float, str]:
    metric = claim.get("metric")
    record = event.get("actuals", {}).get(metric)
    if not record:
        raise BacktestError(f"event {event['event_id']} lacks metric {metric!r}")
    actual = _number(record.get("value"))
    if actual is None:
        raise BacktestError(f"event {event['event_id']} metric {metric!r} lacks a value")
    claim_units, actual_units = claim.get("units"), record.get("units")
    if claim_units and actual_units and claim_units != actual_units:
        raise BacktestError(
            f"unit mismatch in {claim['claim_id']}: {claim_units!r} != {actual_units!r}"
        )
    return actual, actual_units or claim_units or "unspecified"


def _numeric_evaluation(claim: dict[str, Any], actual: float, units: str) -> dict[str, Any]:
    scale = _scale(actual, units)
    if claim["claim_type"] == "numeric_point":
        prediction = float(claim["forecast_value"])
        signed = (prediction - actual) / scale
        error = abs(signed)
        range_hit = None
    else:
        low, high = float(claim["forecast_low"]), float(claim["forecast_high"])
        prediction = (low + high) / 2.0
        signed = (prediction - actual) / scale
        range_hit = low <= actual <= high
        error = 0.0 if range_hit else min(abs(actual - low), abs(actual - high)) / scale
    try:
        consensus = _number(claim.get("consensus_at_claim"))
    except BacktestError:
        # Preserve prose/range consensus in the canonical record, but it cannot
        # support a point benchmark without a declared conversion rule.
        consensus = None
    consensus_error = abs(consensus - actual) / scale if consensus is not None else None
    return {
        "prediction": prediction,
        "actual": actual,
        "units": units,
        "scaled_error": error,
        "signed_scaled_error": signed,
        "range_hit": range_hit,
        "consensus_error": consensus_error,
        "consensus_skill": consensus_error - error if consensus_error is not None else None,
        "hit": None,
    }


def _directional_evaluation(claim: dict[str, Any], actual: float, units: str) -> dict[str, Any]:
    reference = _number(claim.get("reference_value"))
    if reference is None:
        try:
            reference = _number(claim.get("consensus_at_claim"))
        except BacktestError:
            reference = None
    if reference is None and claim.get("direction") in {"above", "below"}:
        reference = _number(claim.get("forecast_value"))
    if reference is None and claim.get("direction") in {
        "up", "down", "positive", "negative", "outperform_peer", "underperform_peer"
    }:
        reference = 0.0
    if reference is None:
        raise BacktestError(f"directional claim {claim['claim_id']} lacks a reference value")
    actual_direction = "meet"
    if actual > reference:
        actual_direction = "above"
    elif actual < reference:
        actual_direction = "below"
    wanted = claim["direction"]
    aliases = {
        "up": "above", "positive": "above", "outperform_peer": "above",
        "down": "below", "negative": "below", "underperform_peer": "below",
        "above_consensus": "above", "below_consensus": "below",
    }
    hit = aliases.get(wanted, wanted) == actual_direction
    probability = _number(claim.get("probability"))
    if probability is not None and not 0 <= probability <= 1:
        raise BacktestError(f"probability outside [0,1] in {claim['claim_id']}")
    brier = (probability - (1.0 if hit else 0.0)) ** 2 if probability is not None else None
    return {
        "prediction": wanted,
        "actual": actual,
        "units": units,
        "actual_direction": actual_direction,
        "hit": hit,
        "brier": brier,
        "scaled_error": 0.0 if hit else 1.0,
        "signed_scaled_error": None,
        "range_hit": None,
        "consensus_error": None,
        "consensus_skill": None,
    }


def evaluate_claims(
    claims: Iterable[dict[str, Any]],
    events: Iterable[dict[str, Any]],
    *,
    as_of: str,
    revision_policy: str = "latest",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return resolved evaluations and exclusions with explicit reasons."""
    if revision_policy not in {"first", "latest", "all"}:
        raise BacktestError(f"unsupported revision policy: {revision_policy}")
    cutoff = parse_time(as_of)
    event_map = normalize_events(events)
    candidates: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_fingerprints: set[str] = set()

    for original in claims:
        claim = dict(original)
        validate_claim(claim)
        claim_id = claim["claim_id"]
        if claim_id in seen_ids:
            raise BacktestError(f"duplicate claim_id: {claim_id}")
        seen_ids.add(claim_id)
        if claim["resolution_status"] != "resolved":
            exclusions.append({"claim_id": claim_id, "reason": claim["resolution_status"]})
            continue
        if not claim.get("published_at"):
            exclusions.append({"claim_id": claim_id, "reason": "missing_publication_timestamp"})
            continue
        published = parse_time(claim["published_at"])
        if published > cutoff:
            exclusions.append({"claim_id": claim_id, "reason": "published_after_as_of"})
            continue
        if claim["claim_type"] == "thesis":
            exclusions.append({"claim_id": claim_id, "reason": "thesis_requires_predefined_rubric"})
            continue
        event = event_map.get(claim.get("event_id"))
        if not event:
            exclusions.append({"claim_id": claim_id, "reason": "missing_event"})
            continue
        reported = parse_time(event["reported_at"])
        if reported > cutoff:
            exclusions.append({"claim_id": claim_id, "reason": "event_after_as_of"})
            continue
        if published >= reported:
            exclusions.append({"claim_id": claim_id, "reason": "lookahead_or_same_time"})
            continue
        fingerprint = _claim_fingerprint(claim)
        if fingerprint in seen_fingerprints:
            exclusions.append({"claim_id": claim_id, "reason": "semantic_duplicate"})
            continue
        seen_fingerprints.add(fingerprint)
        claim["_published"] = published
        claim["_event"] = event
        candidates.append(claim)

    if revision_policy != "all":
        grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for claim in candidates:
            grouped[(claim["author_id"], claim["event_id"], claim.get("metric", ""), claim["claim_type"])].append(claim)
        selected: list[dict[str, Any]] = []
        for revisions in grouped.values():
            revisions.sort(key=lambda row: row["_published"])
            chosen = revisions[0] if revision_policy == "first" else revisions[-1]
            selected.append(chosen)
            for revision in revisions:
                if revision is not chosen:
                    exclusions.append({"claim_id": revision["claim_id"], "reason": f"superseded_{revision_policy}"})
        candidates = selected

    evaluations: list[dict[str, Any]] = []
    for claim in sorted(candidates, key=lambda row: (row["_event"]["reported_at"], row["claim_id"])):
        actual, units = _resolve_actual(claim, claim["_event"])
        if claim["claim_type"] in NUMERIC_TYPES:
            evaluation = _numeric_evaluation(claim, actual, units)
        else:
            try:
                evaluation = _directional_evaluation(claim, actual, units)
            except BacktestError as exc:
                exclusions.append(
                    {"claim_id": claim["claim_id"], "reason": "directional_rubric_missing", "detail": str(exc)}
                )
                continue
        published, reported = claim["_published"], parse_time(claim["_event"]["reported_at"])
        horizon_days = (reported.date() - published.date()).days
        evaluation.update(
            {
                "claim_id": claim["claim_id"],
                "author_id": claim["author_id"],
                "author_display": claim.get("author_display") or claim["author_id"],
                "affiliation": claim.get("affiliation"),
                "source_role": source_role(claim),
                "company": claim["company"],
                "ticker": claim["ticker"],
                "event_id": claim["event_id"],
                "target_period": claim.get("target_period"),
                "metric": claim.get("metric"),
                "metric_class": claim.get("metric_class", "accounting"),
                "claim_type": claim["claim_type"],
                "published_at": claim["published_at"],
                "reported_at": claim["_event"]["reported_at"],
                "horizon_days": horizon_days,
                "horizon_bucket": horizon_bucket(horizon_days),
                "provenance_tier": claim["provenance_tier"],
                "source_url": claim["source_url"],
            }
        )
        evaluations.append(evaluation)
    return evaluations, sorted(exclusions, key=lambda row: row["claim_id"])


def _wilson_interval(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = hits / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def rank_evaluations(evaluations: Iterable[dict[str, Any]], minimum_n: int = 3) -> list[dict[str, Any]]:
    """Rank within comparable author/company/metric/horizon lanes.

    Numeric errors use empirical-Bayes shrinkage toward the corpus median with
    three prior observations. Directional calls use a Beta(1,1) posterior.
    """
    rows = list(evaluations)
    numeric_errors = [row["scaled_error"] for row in rows if row["claim_type"] in NUMERIC_TYPES]
    prior_error = statistics.median(numeric_errors) if numeric_errors else 0.10
    groups: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        lane = "numeric" if row["claim_type"] in NUMERIC_TYPES else "directional"
        key = (
            row["author_id"], row["company"], row.get("metric") or "",
            row["horizon_bucket"], row.get("metric_class") or "accounting", lane,
        )
        groups[key].append(row)

    rankings: list[dict[str, Any]] = []
    for key, items in groups.items():
        author, company, metric, horizon, metric_class, lane = key
        n = len(items)
        base = {
            "author_id": author,
            "author_display": items[0]["author_display"],
            "affiliation": items[0].get("affiliation"),
            "company": company,
            "metric": metric,
            "metric_class": metric_class,
            "horizon_bucket": horizon,
            "lane": lane,
            "observations": n,
            "ranking_status": "ranked" if n >= minimum_n else "provisional",
            "claim_ids": [item["claim_id"] for item in items],
        }
        if lane == "numeric":
            errors = [float(item["scaled_error"]) for item in items]
            signed = [item["signed_scaled_error"] for item in items if item["signed_scaled_error"] is not None]
            shrunk = (sum(errors) + 3.0 * prior_error) / (n + 3.0)
            skills = [item["consensus_skill"] for item in items if item["consensus_skill"] is not None]
            base.update(
                {
                    "mean_scaled_error": statistics.fmean(errors),
                    "median_scaled_error": statistics.median(errors),
                    "shrunk_scaled_error": shrunk,
                    "mean_signed_bias": statistics.fmean(signed) if signed else None,
                    "mean_consensus_skill": statistics.fmean(skills) if skills else None,
                    "score": max(0.0, 1.0 - shrunk),
                }
            )
        else:
            hits = sum(bool(item["hit"]) for item in items)
            posterior = (hits + 1) / (n + 2)
            low, high = _wilson_interval(hits, n)
            briers = [item["brier"] for item in items if item.get("brier") is not None]
            base.update(
                {
                    "hits": hits,
                    "hit_rate": hits / n,
                    "posterior_hit_rate": posterior,
                    "hit_rate_ci95": [low, high],
                    "mean_brier": statistics.fmean(briers) if briers else None,
                    "score": posterior,
                }
            )
        rankings.append(base)

    comparable: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rankings:
        comparable[(row["company"], row["metric"], row["horizon_bucket"], row["metric_class"], row["lane"])].append(row)
    for lane_rows in comparable.values():
        eligible = [row for row in lane_rows if row["ranking_status"] == "ranked"]
        eligible.sort(key=lambda row: (-row["score"], -row["observations"], row["author_id"]))
        for position, row in enumerate(eligible, 1):
            row["rank"] = position
        for row in lane_rows:
            row.setdefault("rank", None)
    return sorted(
        rankings,
        key=lambda row: (
            row["company"], row["metric_class"], row["metric"], row["horizon_bucket"],
            row["rank"] is None, row["rank"] or 10**9, row["author_id"],
        ),
    )


def summarize_authors(evaluations: Iterable[dict[str, Any]], minimum_n: int = 3) -> list[dict[str, Any]]:
    """Broader author × company summaries across accounting metrics/horizons.

    These are useful for source selection but intentionally labelled broad: a
    strict metric/horizon leaderboard remains the primary comparison surface.
    """
    rows = list(evaluations)
    numeric_errors = [row["scaled_error"] for row in rows if row["claim_type"] in NUMERIC_TYPES]
    prior_error = statistics.median(numeric_errors) if numeric_errors else 0.10
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        lane = "numeric" if row["claim_type"] in NUMERIC_TYPES else "directional"
        groups[(row["author_id"], row["company"], row.get("metric_class") or "accounting", lane)].append(row)
    summaries: list[dict[str, Any]] = []
    for (author, company, metric_class, lane), items in groups.items():
        n = len(items)
        base = {
            "author_id": author,
            "author_display": items[0]["author_display"],
            "affiliation": items[0].get("affiliation"),
            "source_role": items[0]["source_role"],
            "company": company,
            "metric_class": metric_class,
            "lane": lane,
            "observations": n,
            "metrics": sorted({item["metric"] for item in items}),
            "horizon_buckets": sorted({item["horizon_bucket"] for item in items}),
            "ranking_status": "ranked" if n >= minimum_n else "provisional",
        }
        if lane == "numeric":
            errors = [float(item["scaled_error"]) for item in items]
            shrunk = (sum(errors) + 3.0 * prior_error) / (n + 3.0)
            skills = [item["consensus_skill"] for item in items if item["consensus_skill"] is not None]
            base.update(
                {
                    "mean_scaled_error": statistics.fmean(errors),
                    "median_scaled_error": statistics.median(errors),
                    "shrunk_scaled_error": shrunk,
                    "mean_consensus_skill": statistics.fmean(skills) if skills else None,
                    "score": max(0.0, 1.0 - shrunk),
                }
            )
        else:
            hits = sum(bool(item["hit"]) for item in items)
            low, high = _wilson_interval(hits, n)
            base.update(
                {
                    "hits": hits,
                    "hit_rate": hits / n,
                    "posterior_hit_rate": (hits + 1) / (n + 2),
                    "hit_rate_ci95": [low, high],
                    "score": (hits + 1) / (n + 2),
                }
            )
        summaries.append(base)

    lanes: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in summaries:
        lanes[(row["company"], row["metric_class"], row["lane"])].append(row)
    for lane_rows in lanes.values():
        eligible = [row for row in lane_rows if row["ranking_status"] == "ranked"]
        eligible.sort(key=lambda row: (-row["score"], -row["observations"], row["author_id"]))
        for position, row in enumerate(eligible, 1):
            row["rank"] = position
        for row in lane_rows:
            row.setdefault("rank", None)
    return sorted(
        summaries,
        key=lambda row: (
            row["company"], row["metric_class"], row["lane"], row["rank"] is None,
            row["rank"] or 10**9, row["author_id"],
        ),
    )


def run_backtest(
    claims: Iterable[dict[str, Any]],
    events: Iterable[dict[str, Any]],
    *,
    as_of: str,
    revision_policy: str = "latest",
    minimum_n: int = 3,
) -> dict[str, Any]:
    evaluations, exclusions = evaluate_claims(
        claims, events, as_of=as_of, revision_policy=revision_policy
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": parse_time(as_of).isoformat(),
        "revision_policy": revision_policy,
        "minimum_n": minimum_n,
        "resolved_evaluations": len(evaluations),
        "excluded_claims": len(exclusions),
        "evaluations": evaluations,
        "author_summaries": summarize_authors(evaluations, minimum_n=minimum_n),
        "rankings": rank_evaluations(evaluations, minimum_n=minimum_n),
        "exclusions": exclusions,
    }
