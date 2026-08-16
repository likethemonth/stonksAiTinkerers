"""Compile candidate JSONL, run the backtest, and generate browsable trails."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scoring import BacktestError, run_backtest
from .thought_leaders import normalize_thesis_claim, score_thought_leaders


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BacktestError(f"{path}:{line_number}: {exc}") from exc
            record.setdefault("raw_record", f"{path}:{line_number}")
            records.append(record)
    return records


def _numeric(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def normalize_candidates(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Add stable event links and split issuer outcomes from source claims.

    Candidate ledgers intentionally preserve the extractor's original shape.
    This normalization is deterministic and does not invent timestamps or turn
    prose into numbers.
    """
    claims: list[dict[str, Any]] = []
    event_map: dict[str, dict[str, Any]] = {}
    for original in records:
        claim = dict(original)
        target_date = claim.get("target_report_date")
        event_id = None
        if target_date:
            event_id = "evt-{}-{}-{}".format(
                slug(str(claim.get("ticker") or "unknown")),
                slug(str(claim.get("target_period") or "unknown")),
                target_date,
            )
            claim["event_id"] = event_id
        guidance_text = " ".join(
            str(claim.get(key) or "") for key in ("target_period", "metric", "metric_definition")
        ).lower()
        claim.setdefault(
            "metric_class",
            "guidance_issuance" if "guidance" in guidance_text else "accounting",
        )
        # Preserve source precision. Date-only calls on the report date will be
        # rejected against the event's midnight timestamp as order-unverified.
        if claim.get("published_at"):
            claim["published_at_precision"] = (
                "timestamp" if "T" in str(claim["published_at"]) else "date"
            )
        actual = _numeric(claim.get("actual_value"))
        if event_id and actual is not None and claim.get("metric"):
            event = event_map.setdefault(
                event_id,
                {
                    "event_id": event_id,
                    "company": claim["company"],
                    "ticker": claim["ticker"],
                    "target_period": claim.get("target_period"),
                    "reported_at": f"{target_date}T00:00:00Z",
                    "actuals": {},
                },
            )
            metric = claim["metric"]
            candidate_actual = {
                "value": actual,
                "units": claim.get("units") or "unspecified",
                "source_url": claim.get("actual_source_url"),
                "resolved_at": claim.get("resolved_at"),
            }
            existing = event["actuals"].get(metric)
            if existing and (
                existing["value"] != candidate_actual["value"]
                or existing["units"] != candidate_actual["units"]
            ):
                # Metric definitions are not silently pooled. A conflicting
                # record gets a claim-specific metric key and remains auditable.
                metric = f"{metric} [{claim['claim_id']}]"
                claim["metric"] = metric
            event["actuals"][metric] = candidate_actual
        claims.append(claim)
    return claims, sorted(event_map.values(), key=lambda row: row["event_id"])


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "unknown"


def render_claim(claim: dict[str, Any]) -> list[str]:
    forecast = claim.get("forecast_value")
    if claim.get("claim_type") == "numeric_range":
        forecast = f"{claim.get('forecast_low')}–{claim.get('forecast_high')}"
    elif claim.get("claim_type") == "directional":
        forecast = claim.get("direction")
    return [
        f"### {claim.get('published_at')} — {claim.get('author_display') or claim.get('author_id')}",
        "",
        f"- Company/period: {claim.get('ticker')} · {claim.get('target_period') or 'unspecified'}",
        f"- Claim: {claim.get('claim_type')} · {claim.get('metric') or 'thesis'} · {forecast if forecast is not None else 'non-numeric'} {claim.get('units') or ''}".rstrip(),
        f"- Resolution: {claim.get('resolution_status')}",
        f"- Evidence: [{claim.get('platform') or claim.get('provenance_tier')}]({claim.get('source_url')})",
        f"- Record: `{claim.get('claim_id')}`",
        "",
        (claim.get("claim_text") or "No text captured.").strip(),
        "",
    ]


def write_trails(root: Path, claims: list[dict[str, Any]]) -> None:
    facets: dict[str, dict[str, list[dict[str, Any]]]] = {
        "authors": defaultdict(list),
        "companies": defaultdict(list),
        "metrics": defaultdict(list),
    }
    for claim in claims:
        facets["authors"][claim.get("author_display") or claim["author_id"]].append(claim)
        facets["companies"][f"{claim['ticker']} — {claim['company']}"] .append(claim)
        facets["metrics"][claim.get("metric") or "Qualitative thesis"].append(claim)
    for facet, groups in facets.items():
        folder = root / "generated" / facet
        folder.mkdir(parents=True, exist_ok=True)
        for name, rows in groups.items():
            rows.sort(key=lambda row: (row.get("published_at") or "", row["claim_id"]), reverse=True)
            lines = [f"# {name}", "", f"Claims: **{len(rows)}**", ""]
            for claim in rows:
                lines.extend(render_claim(claim))
            (folder / f"{slug(name)}.md").write_text("\n".join(lines), encoding="utf-8")


def render_leaderboard(result: dict[str, Any]) -> str:
    lines = [
        "# Author forecast leaderboard",
        "",
        f"As of: **{result['as_of']}**  ",
        f"Revision policy: **{result['revision_policy']}**  ",
        f"Resolved evaluations: **{result['resolved_evaluations']}**  ",
        "",
        "Only rows with at least the configured minimum sample receive a rank. The broad author table pools standardized errors across accounting metrics and horizons within a company; the strict table below does not.",
        "",
        "## Broad author × company source selection",
        "",
        "| Rank | Status | Role | Author | Company | Lane | N | Metrics | Score | Error/hit rate |",
        "|---:|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in result["author_summaries"]:
        diagnostic = row.get("mean_scaled_error", row.get("hit_rate"))
        lines.append(
            "| {rank} | {status} | {role} | {author} | {company} | {lane} | {n} | {metrics} | {score:.3f} | {diag} |".format(
                rank=row["rank"] if row["rank"] is not None else "—", status=row["ranking_status"],
                role=row["source_role"], author=row["author_display"], company=row["company"], lane=row["lane"],
                n=row["observations"], metrics=len(row["metrics"]), score=row["score"],
                diag=f"{diagnostic:.3f}" if diagnostic is not None else "—",
            )
        )
    lines.extend([
        "",
        "## Strict comparable lanes",
        "",
        "| Rank | Status | Author | Company | Metric | Horizon | Lane | N | Score | Error/hit rate | Consensus skill |",
        "|---:|---|---|---|---|---|---|---:|---:|---:|---:|",
    ])
    for row in result["rankings"]:
        diagnostic = row.get("mean_scaled_error", row.get("hit_rate"))
        skill = row.get("mean_consensus_skill")
        lines.append(
            "| {rank} | {status} | {author} | {company} | {metric} | {horizon} | {lane} | {n} | {score:.3f} | {diag} | {skill} |".format(
                rank=row["rank"] if row["rank"] is not None else "—",
                status=row["ranking_status"], author=row["author_display"], company=row["company"],
                metric=row["metric"], horizon=row["horizon_bucket"], lane=row["lane"],
                n=row["observations"], score=row["score"],
                diag=f"{diagnostic:.3f}" if diagnostic is not None else "—",
                skill=f"{skill:+.3f}" if skill is not None else "—",
            )
        )
    return "\n".join(lines) + "\n"


def render_current_outlook(payload: dict[str, Any]) -> str:
    lines = [
        "# Current challenge forecasts",
        "",
        f"> Point-in-time cutoff: {payload.get('as_of')}",
        "> These are accounting forecasts, not stock-price or trading recommendations.",
        "",
        "The point estimates below are the current ensemble output. Historical author research informs source selection, but sparse individual histories do not justify replacing issuer guidance or established consensus with a personality-driven call.",
        "",
        "| Company | Period | Metric | Forecast | Units | Inputs |",
        "|---|---|---|---:|---|---:|",
    ]
    for row in payload.get("forecasts", []):
        lines.append(
            f"| {row['company']} | {row['period']} | {row['metric']} | {row['forecast']} | {row['units']} | {len(row.get('components', []))} |"
        )
    lines.extend(["", "## Component evidence", ""])
    for row in payload.get("forecasts", []):
        lines.extend([f"### {row['company']} — {row['metric']}", ""])
        for component in row.get("components", []):
            url = component.get("source_url") or ""
            name = component.get("source_name") or component.get("source_id")
            value = component.get("raw_forecast")
            history = component.get("observations", 0)
            lines.append(f"- [{name}]({url}): {value}; comparable closed observations in the legacy source panel: {history}.")
        lines.append("")
    lines.extend(
        [
            "## Confidence warning",
            "",
            "Hays net fees/EPS, Deere worldwide revenue/PPA profit, ADI gross margin, and Home Depot comparable sales lack a deep public constituent-level point-in-time panel. Their exact point estimates should be treated as materially less certain than the apparent decimal precision suggests. The JSON output retains unrounded values only for reproducibility.",
            "",
        ]
    )
    return "\n".join(lines)


def render_thought_leaders(results: list[dict[str, Any]], claims: list[dict[str, Any]]) -> str:
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in claims:
        claim = normalize_thesis_claim(raw)
        by_key[(claim["leader_id"], claim["ticker"])].append(claim)
    lines = [
        "# Company thought leaders",
        "",
        "> This is the person-first leaderboard: causal insight, falsifiability, complete history, and honest revisions. Followers and popularity receive zero points.",
        "> A case-study score is not a statistically defensible author rank. It identifies the strongest evidence packet found so far.",
        "",
        "## Best-supported candidates",
        "",
        "| Company | Evidence order | Status | Person / team | Best use | Families | Matured | Score | Construction | Accountability |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---:|",
    ]
    evidence_order: dict[str, int] = defaultdict(int)
    for row in results:
        evidence_order[row["ticker"]] += 1
        lines.append(
            f"| {row['ticker']} | {evidence_order[row['ticker']]} | {row['eligibility']} | {row['leader_display']} | {row.get('best_use') or 'See evidence packet'} | {row['families']} | {row['matured']} | {row['score']:.2f} | {row['construction_score']:.2f}/58 | {row['accountability_score']:.2f}/42 |"
        )
    lines.extend([
        "",
        "Scores measure process and evidence quality, not a buy/sell recommendation. The author-level rank gate is deliberately strict: five families, three matured, 24 months searched, and completeness level 3 are required for `rankable` status.",
        "",
        "## Evidence packets",
        "",
    ])
    for row in results:
        lines.extend([
            f"### {row['ticker']} — {row['leader_display']}",
            "",
            f"- Verdict: **{row['eligibility']}**, {row['interpretation_band']} process score ({row['score']:.2f}/100).",
            f"- Lane: {row['lane']}; best use: {row.get('best_use') or 'not specified'}.",
            f"- Denominator: {row['families']} initial thesis families, {row['matured']} matured, {row['open']} open, {row['records']} total records.",
            f"- Search: {row['searched_from']} to {row['searched_to']} across {', '.join(row['searched_channels']) or 'unspecified channels'}.",
            f"- Largest miss/counterevidence: {row.get('largest_miss') or 'not yet documented'}",
        ])
        if row.get("known_gaps"):
            lines.append(f"- Known gaps: {'; '.join(row['known_gaps'])}.")
        lines.extend(["", "Dated thesis trail:", ""])
        for claim in sorted(by_key.get((row["leader_id"], row["ticker"]), []), key=lambda item: item.get("published_at") or item.get("source_period") or ""):
            outcome = claim.get("outcome_summary") or claim.get("outcome") or claim["outcome_status"]
            published = claim.get("published_at") or claim.get("source_period") or "date unavailable"
            lines.append(
                f"- {published} · **{claim['claim_stage']} / {claim['outcome_status']}** · [{claim.get('thesis_topic') or claim.get('claim_type')}]({claim['source_url']}): {claim['claim_text']} Outcome: {outcome}"
            )
        lines.append("")
    lines.extend([
        "## How to read the result",
        "",
        "The useful answer may be a pair rather than one celebrity: a company-specific causal thinker for understanding the business and a separately backtested accounting forecaster for near-term numbers. Consensus remains the hurdle, not the thought leader.",
        "",
        "See [the full 100-point method](06-THOUGHT-LEADER-METHOD.md), the [accounting leaderboard](02-LEADERBOARD.md), and the two source-history dossiers for source-level limitations.",
        "",
    ])
    return "\n".join(lines)


def build_manifest(
    root: Path,
    claim_count: int,
    event_count: int,
    result: dict[str, Any],
    thought_leaders: list[dict[str, Any]] | None = None,
    thought_claim_count: int = 0,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append(
            {"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": digest}
        )
    return {
        "schema_version": "1.0.0",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "counts": {
            "claims": claim_count,
            "events": event_count,
            "evaluations": result["resolved_evaluations"],
            "exclusions": result["excluded_claims"],
            "strict_rankings": len(result["rankings"]),
            "author_summaries": len(result["author_summaries"]),
            "raw_files": sum(1 for row in files if row["path"].startswith("raw/")),
            "thought_leader_claims": thought_claim_count,
            "thought_leader_scorecards": len(thought_leaders or []),
        },
        "build": {
            "as_of": result["as_of"],
            "revision_policy": result["revision_policy"],
            "minimum_n": result["minimum_n"],
            "command": "python3 -m analyst_backtest.build --as-of <ISO-8601>",
        },
        "files": files,
    }


def render_overview(manifest: dict[str, Any]) -> str:
    count = manifest["counts"]
    return "\n".join(
        [
            "# Analyst forecast knowledge base — overview",
            "",
            f"> Build: `{manifest['generated_at']}` · schema `{manifest['schema_version']}`",
            "",
            "## Corpus",
            "",
            f"- Candidate claims: **{count['claims']}**",
            f"- Linked issuer events: **{count['events']}**",
            f"- Leakage-safe resolved evaluations: **{count['evaluations']}**",
            f"- Preserved exclusions: **{count['exclusions']}**",
            f"- Raw evidence files: **{count['raw_files']}**",
            "",
            "## Navigation",
            "",
            "- [Methodology](01-METHODOLOGY.md)",
            "- [Ranked histories](02-LEADERBOARD.md)",
            "- [Current accounting forecasts](03-CURRENT-OUTLOOK.md)",
            "- [Requested source archetypes](04-REQUESTED-SOURCE-ARCHETYPES.md)",
            "- [Best sources by target company](05-SOURCE-SELECTION.md)",
            "- [Thought-leader evaluation method](06-THOUGHT-LEADER-METHOD.md)",
            "- [Person-first thought-leader results](07-THOUGHT-LEADERS.md)",
            "- [Thought-leader overlay on current forecasts](08-FORECAST-OVERLAY.md)",
            "- [Expert monitoring stack](09-EXPERT-MONITORING-STACK.md)",
            "- [Raw acquisition log](../raw/CAPTURE_LOG.md)",
            "- [ADI and Deere dossier](../dossiers/ADI_DE_INDEPENDENT_HISTORY.md)",
            "- [Home Depot and Hays dossier](../dossiers/HD_HAYS_SOURCE_HISTORY.md)",
            "- [Reference format audit](../reference/REFERENCE_FORMAT_AUDIT.md)",
            "",
            "## Interpretation",
            "",
            "The corpus is intentionally wider than the ranked set. Unresolved theses, undated articles, same-day items without intraday ordering, duplicated revisions, and requested personalities with no target-company calls remain visible but receive no score.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("analyst_knowledge"))
    parser.add_argument("--as-of", default=datetime.now(timezone.utc).isoformat())
    parser.add_argument("--revision-policy", choices=("first", "latest", "all"), default="latest")
    parser.add_argument("--minimum-n", type=int, default=3)
    args = parser.parse_args(argv)

    raw_paths = sorted((args.root / "raw").glob("*_candidate_claims.jsonl"))
    candidates = read_jsonl(raw_paths)
    claims, derived_events = normalize_candidates(candidates)
    events_path = args.root / "dataset" / "events.json"
    events_payload = read_json(events_path) if events_path.exists() else {"events": []}
    supplied_events = events_payload.get("events", events_payload)
    events = supplied_events or derived_events
    if not supplied_events:
        events_payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "description": "Issuer outcomes deterministically separated from candidate claim ledgers.",
            "events": events,
        }
        events_path.write_text(json.dumps(events_payload, indent=2) + "\n", encoding="utf-8")
    canonical = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(claims),
        "source_files": [str(path) for path in raw_paths],
        "claims": claims,
    }
    (args.root / "dataset").mkdir(parents=True, exist_ok=True)
    (args.root / "dataset" / "claims.json").write_text(json.dumps(canonical, indent=2) + "\n", encoding="utf-8")
    result = run_backtest(
        claims, events, as_of=args.as_of, revision_policy=args.revision_policy, minimum_n=args.minimum_n
    )
    (args.root / "dataset" / "backtest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_trails(args.root, claims)
    knowledge = args.root / "knowledge"
    knowledge.mkdir(parents=True, exist_ok=True)
    (knowledge / "02-LEADERBOARD.md").write_text(render_leaderboard(result), encoding="utf-8")
    current_path = Path("research/backtest-results.json")
    if current_path.exists():
        current_payload = read_json(current_path)
        (args.root / "dataset" / "current_outlook.json").write_text(
            json.dumps(current_payload, indent=2) + "\n", encoding="utf-8"
        )
        (knowledge / "03-CURRENT-OUTLOOK.md").write_text(
            render_current_outlook(current_payload), encoding="utf-8"
        )
    thought_paths = sorted((args.root / "raw").glob("*_thought_leader_claims.jsonl"))
    thought_claims = read_jsonl(thought_paths)
    scorecards_path = args.root / "dataset" / "thought_leader_scorecards.json"
    scorecards_payload = read_json(scorecards_path) if scorecards_path.exists() else {"scorecards": []}
    scorecards = scorecards_payload.get("scorecards", scorecards_payload)
    thought_results = score_thought_leaders(thought_claims, scorecards) if scorecards else []
    thought_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_files": [str(path) for path in thought_paths],
        "claim_count": len(thought_claims),
        "results": thought_results,
    }
    (args.root / "dataset" / "thought_leaders.json").write_text(
        json.dumps(thought_payload, indent=2) + "\n", encoding="utf-8"
    )
    (knowledge / "07-THOUGHT-LEADERS.md").write_text(
        render_thought_leaders(thought_results, thought_claims), encoding="utf-8"
    )
    build_time = datetime.now(timezone.utc).isoformat()
    # The overview embeds manifest counts, while the manifest hashes the
    # overview. Render the overview first from a same-timestamp preview, then
    # compute the final hashes. This avoids hashing yesterday's overview and
    # immediately invalidating that hash by rewriting the file afterward.
    preview_manifest = build_manifest(
        args.root, len(claims), len(events), result, thought_results,
        len(thought_claims), generated_at=build_time,
    )
    (knowledge / "00-OVERVIEW.md").write_text(
        render_overview(preview_manifest), encoding="utf-8"
    )
    manifest = build_manifest(
        args.root, len(claims), len(events), result, thought_results,
        len(thought_claims), generated_at=build_time,
    )
    (args.root / "dataset" / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Compiled {len(claims)} claims and {len(events)} events, evaluated {len(result['evaluations'])}, excluded {len(result['exclusions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
