"""Score long-horizon thought leaders without confusing popularity with skill.

The evidence ledger and the scorecard are deliberately separate.  A ledger row
records something the author actually published.  A scorecard records a
reviewer's dimension-level judgment under ``06-THOUGHT-LEADER-METHOD.md``.
This module validates and combines the two, but never infers a high score from
followers, likes, titles, or the number of posts.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any, Iterable

from .scoring import BacktestError


DIMENSIONS: dict[str, int] = {
    "originality_lead": 12,
    "causal_depth": 12,
    "falsifiability": 12,
    "revision_conduct": 10,
    "history_completeness": 12,
    "calibration_outcomes": 14,
    "conflict_disclosure": 6,
    "target_relevance": 8,
    "evidentiary_provenance": 14,
}

OUTCOMES = {"supported", "contradicted", "mixed", "open", "not_testable"}
STAGES = {"initial", "revision", "reaffirmation", "postmortem"}


def normalize_thesis_claim(claim: dict[str, Any]) -> dict[str, Any]:
    """Normalize extractor variants without inventing missing evidence."""
    row = dict(claim)
    aliases = {
        "person_id": "leader_id",
        "display_name": "leader_display",
        "thesis_stage": "claim_stage",
        "outcome": "outcome_summary",
    }
    for old, new in aliases.items():
        if old in row and new not in row:
            row[new] = row[old]
    row["outcome_status"] = {
        "resolved_supported": "supported",
        "resolved_mixed": "mixed",
        "resolved_missed": "contradicted",
        "unresolvable": "not_testable",
    }.get(row.get("outcome_status"), row.get("outcome_status"))
    row["claim_stage"] = {
        "update": "revision",
        "closure": "postmortem",
    }.get(row.get("claim_stage"), row.get("claim_stage"))
    stage = str(row.get("claim_stage") or "")
    if stage not in STAGES:
        if "revision" in stage:
            row["claim_stage"] = "revision"
        elif "reaffirm" in stage:
            row["claim_stage"] = "reaffirmation"
        else:
            # Extractors use domain labels such as event_review, causal_thesis,
            # and sector_thesis for the first record in a family.
            row["claim_stage"] = "initial"
    return row


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError) as exc:
        raise BacktestError(f"invalid date: {value!r}") from exc


def validate_thesis_claim(claim: dict[str, Any]) -> None:
    required = (
        "claim_id", "leader_id", "leader_display", "company", "ticker",
        "source_url", "claim_stage", "claim_type",
        "claim_text", "outcome_status",
    )
    missing = [field for field in required if not claim.get(field)]
    if missing:
        raise BacktestError(f"thought-leader claim {claim.get('claim_id', '<unknown>')} missing {missing}")
    if not claim.get("published_at") and not claim.get("source_period"):
        raise BacktestError(f"thought-leader claim {claim['claim_id']} lacks publication date/period")
    if claim.get("published_at"):
        _parse_date(claim["published_at"])
    if claim["claim_stage"] not in STAGES:
        raise BacktestError(f"invalid claim_stage: {claim['claim_stage']}")
    if claim["outcome_status"] not in OUTCOMES:
        raise BacktestError(f"invalid outcome_status: {claim['outcome_status']}")
    if (
        claim["outcome_status"] not in {"open", "not_testable"}
        and claim["claim_stage"] != "postmortem"
        and not claim.get("outcome_source_url")
    ):
        raise BacktestError(f"resolved thesis claim {claim['claim_id']} lacks outcome_source_url")


def _eligibility(*, families: int, matured: int, months: int, completeness: int) -> str:
    if not families:
        return "ineligible"
    if families < 3 or matured < 2:
        return "case-study"
    if families < 5 or matured < 3 or months < 24 or completeness < 3:
        return "provisional"
    if families >= 10 and matured >= 6:
        return "robust"
    return "rankable"


def _band(score: float) -> str:
    if score >= 90:
        return "exemplary"
    if score >= 75:
        return "strong"
    if score >= 60:
        return "credible"
    if score >= 40:
        return "weak"
    return "non-qualifying"


def score_thought_leaders(
    claims: Iterable[dict[str, Any]], scorecards: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return an auditable company-level thought-leader table.

    Only ``initial`` rows count as thesis families. Revisions and postmortems
    affect the reviewer-assigned revision/completeness dimensions but do not
    inflate the sample denominator.
    """
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for raw_claim in claims:
        claim = normalize_thesis_claim(raw_claim)
        validate_thesis_claim(claim)
        if claim["claim_id"] in seen_ids:
            raise BacktestError(f"duplicate thought-leader claim_id: {claim['claim_id']}")
        seen_ids.add(claim["claim_id"])
        grouped[(claim["leader_id"], claim["ticker"])].append(claim)

    results: list[dict[str, Any]] = []
    seen_cards: set[tuple[str, str]] = set()
    for card in scorecards:
        key = (card.get("leader_id"), card.get("ticker"))
        if not all(key):
            raise BacktestError("scorecard lacks leader_id or ticker")
        if key in seen_cards:
            raise BacktestError(f"duplicate thought-leader scorecard: {key}")
        seen_cards.add(key)
        rows = grouped.get(key, [])
        levels = card.get("dimension_levels") or {}
        missing = sorted(set(DIMENSIONS) - set(levels))
        extra = sorted(set(levels) - set(DIMENSIONS))
        if missing or extra:
            raise BacktestError(f"scorecard {key} dimensions missing={missing} extra={extra}")
        for dimension, level in levels.items():
            if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 4:
                raise BacktestError(f"scorecard {key} {dimension} level must be integer 0..4")

        initials = [row for row in rows if row["claim_stage"] == "initial"]
        outcomes = Counter(row["outcome_status"] for row in initials)
        inferred_matured = sum(outcomes[name] for name in ("supported", "contradicted", "mixed"))
        families = int(card.get("families_found", len(initials)))
        matured = int(card.get("matured_families", inferred_matured))
        open_families = int(card.get("open_families", outcomes["open"]))
        if min(families, matured, open_families) < 0 or matured + open_families > families:
            raise BacktestError(f"invalid family denominators in scorecard {key}")
        searched_from = _parse_date(card["searched_from"])
        searched_to = _parse_date(card["searched_to"])
        months = max(0, (searched_to.year - searched_from.year) * 12 + searched_to.month - searched_from.month)
        completeness = levels["history_completeness"]
        eligibility = _eligibility(
            families=families, matured=matured, months=months, completeness=completeness
        )

        weighted = {
            name: DIMENSIONS[name] * levels[name] / 4 for name in DIMENSIONS
        }
        raw_score = sum(weighted.values())
        cap = 100.0
        if levels["falsifiability"] == 0 or levels["target_relevance"] == 0:
            eligibility = "ineligible"
            cap = 0.0
        if levels["history_completeness"] == 0:
            eligibility = "case-study" if eligibility != "ineligible" else eligibility
            cap = min(cap, 49.99)
        if levels["evidentiary_provenance"] == 0:
            eligibility, cap = "ineligible", 0.0
        elif levels["evidentiary_provenance"] == 1:
            cap = min(cap, 59.99)
        if card.get("known_concealed_conflict"):
            cap = min(cap, 59.99)
        score = min(raw_score, cap)
        results.append({
            "leader_id": key[0],
            "leader_display": card.get("leader_display") or (rows[0]["leader_display"] if rows else key[0]),
            "company": card.get("company") or (rows[0]["company"] if rows else None),
            "ticker": key[1],
            "lane": card.get("lane", "company-specific thesis"),
            "eligibility": eligibility,
            "rank": None,
            "score": round(score, 2),
            "raw_score": round(raw_score, 2),
            "interpretation_band": _band(score),
            "construction_score": round(sum(weighted[name] for name in (
                "originality_lead", "causal_depth", "falsifiability", "target_relevance", "evidentiary_provenance"
            )), 2),
            "accountability_score": round(sum(weighted[name] for name in (
                "revision_conduct", "history_completeness", "calibration_outcomes", "conflict_disclosure"
            )), 2),
            "dimension_levels": levels,
            "dimension_points": weighted,
            "families": families,
            "matured": matured,
            "open": open_families,
            "not_testable": outcomes["not_testable"],
            "outcomes": dict(sorted(outcomes.items())),
            "records": len(rows),
            "searched_from": card["searched_from"],
            "searched_to": card["searched_to"],
            "searched_channels": card.get("searched_channels", []),
            "known_gaps": card.get("known_gaps", []),
            "best_use": card.get("best_use"),
            "largest_miss": card.get("largest_miss"),
            "scorecard_sources": card.get("scorecard_sources", []),
        })

    # Rank only genuine author-comparison states. Provisional and case-study
    # records remain ordered by score for browsing but receive no definitive
    # rank number.
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_ticker[result["ticker"]].append(result)
    for ticker_rows in by_ticker.values():
        eligible = [row for row in ticker_rows if row["eligibility"] in {"rankable", "robust"}]
        eligible.sort(key=lambda row: (-row["score"], -row["matured"], row["leader_display"]))
        for rank, row in enumerate(eligible, 1):
            row["rank"] = rank
    return sorted(results, key=lambda row: (row["ticker"], row["rank"] is None, row["rank"] or 999, -row["score"]))
