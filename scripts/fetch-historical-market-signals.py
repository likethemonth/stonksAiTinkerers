#!/usr/bin/env python3
"""Freeze point-in-time Polymarket earnings signals used by the replay.

The output stores the last traded Yes price strictly before 00:00 UTC on the
result date. A binary threshold probability is preserved as a signal and is
never converted into a point forecast for the target accounting metric.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "forecast" / "data" / "polymarket" / "historical-signals.json"

MARKETS = (
    ("HD", "FY2025Q3", "adj_eps", "hd-quarterly-earnings-nongaap-eps-11-18-2025-3pt85", 3.85),
    ("HD", "FY2025Q4", "adj_eps", "hd-quarterly-earnings-nongaap-eps-02-24-2026-2pt52", 2.52),
    ("HD", "FY2026Q1", "adj_eps", "hd-quarterly-earnings-nongaap-eps-05-19-2026-3pt41", 3.41),
    ("ADI", "FY2025Q4", "adj_eps", "adi-quarterly-earnings-nongaap-eps-11-25-2025-2pt23", 2.23),
    ("ADI", "FY2026Q1", "adj_eps", "adi-quarterly-earnings-nongaap-eps-02-18-2026-2pt3", 2.30),
    ("ADI", "FY2026Q2", "adj_eps", "adi-quarterly-earnings-nongaap-eps-05-20-2026-2pt9", 2.90),
    ("DE", "FY2025Q4", "diluted_eps_gaap", "de-quarterly-earnings-gaap-eps-11-26-2025-3pt87", 3.87),
    ("DE", "FY2026Q1", "diluted_eps_gaap", "de-quarterly-earnings-gaap-eps-02-19-2026-2pt1", 2.10),
    ("DE", "FY2026Q2", "diluted_eps_gaap", "de-quarterly-earnings-gaap-eps-05-21-2026-5pt74", 5.74),
)


def fetch_json(url: str) -> object:
    request = Request(url, headers={"User-Agent": "stonksAiTinkerers-replay/2.0"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def iso_utc(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--retrieved-at", help="Frozen ISO timestamp for reproducible refreshes")
    args = parser.parse_args()
    retrieved_at = args.retrieved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    records = []
    for ticker, period, metric_key, slug, strike in MARKETS:
        events = fetch_json(
            "https://gamma-api.polymarket.com/events?" + urlencode({"slug": slug})
        )
        if not isinstance(events, list) or len(events) != 1:
            raise RuntimeError(f"expected one event for {slug}, received {len(events) if isinstance(events, list) else type(events)}")
        event = events[0]
        market = event["markets"][0]
        condition_id = market["conditionId"]
        trades = fetch_json(
            "https://data-api.polymarket.com/trades?"
            + urlencode({"market": condition_id, "limit": 10000, "takerOnly": "false"})
        )
        if not isinstance(trades, list):
            raise RuntimeError(f"invalid trades payload for {slug}")

        result_date = str(market["endDate"])[:10]
        cutoff = datetime.fromisoformat(result_date).replace(tzinfo=timezone.utc)
        yes_trades = sorted(
            (
                trade
                for trade in trades
                if trade.get("outcome") == "Yes" and int(trade["timestamp"]) < int(cutoff.timestamp())
            ),
            key=lambda trade: int(trade["timestamp"]),
        )
        if not yes_trades:
            raise RuntimeError(f"no pre-cutoff Yes trades for {slug}")
        last = yes_trades[-1]
        outcome_prices = json.loads(market["outcomePrices"])
        binary_outcome = 1 if float(outcome_prices[0]) == 1.0 else 0
        source_material = json.dumps(
            {"event": event, "preCutoffYesTrades": yes_trades},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        last_time = datetime.fromtimestamp(int(last["timestamp"]), tz=timezone.utc)
        probability = float(last["price"])
        records.append(
            {
                "ticker": ticker,
                "period": period,
                "metricKey": metric_key,
                "provider": "Polymarket",
                "relation": "greater_than",
                "strike": strike,
                "units": "USD / share",
                "probability": probability,
                "binaryOutcome": binary_outcome,
                "brierScore": (probability - binary_outcome) ** 2,
                "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
                "lastTradeAt": iso_utc(int(last["timestamp"])),
                "stalenessHours": (cutoff - last_time).total_seconds() / 3600.0,
                "preCutoffYesTrades": len(yes_trades),
                "volumeUsd": float(market.get("volumeNum") or event.get("volume") or 0),
                "marketStart": market.get("startDate"),
                "marketEnd": market.get("endDate"),
                "conditionId": condition_id,
                "slug": slug,
                "title": market.get("question") or event.get("title"),
                "sourceUrl": f"https://polymarket.com/event/{slug}",
                "apiSourceUrl": f"https://data-api.polymarket.com/trades?market={condition_id}",
                "sourceContentSha256": hashlib.sha256(source_material).hexdigest(),
            }
        )

    payload = {
        "schemaVersion": "historical-market-signals-v1",
        "retrievedAt": retrieved_at,
        "cutoffPolicy": "Last traded Yes price strictly before 00:00 UTC on the earnings-result date.",
        "numericUse": "signal_only_zero_weight",
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}: {len(records)} frozen market signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
