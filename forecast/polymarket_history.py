"""Historical Polymarket earnings-market reliability ("was the market lens ever any good?").

polymarket.py reads ONE live snapshot and turns it into a forward estimate. This
module answers the retrospective question the predictions page could not: for
every *resolved* "Will <company> beat quarterly earnings?" market, what did the
market price the day before the print, and what actually happened?

The whole HD/ADI/DE beat-market series on Polymarket starts in Nov 2025, so the
record is nine resolved markets (three per company). Short, but real — and every
row is verifiable three ways: the Polymarket resolution, the CLOB price history,
and the filing actual in the observation store.

Point-in-time discipline matches the rest of the repo:

*   Every Gamma event and CLOB price series is snapshotted to
    ``forecast/data/polymarket/history/`` on --refresh; scoring runs fully
    offline from those files.
*   The headline probability is the last traded price at least 24 hours before
    the scheduled report time — the same "day before the print" cutoff the
    blinded LLM replay uses, so the two reliability series are comparable.

Usage:
    .venv/bin/python -m forecast.polymarket_history --refresh   # fetch + score
    .venv/bin/python -m forecast.polymarket_history             # offline score
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from forecast.corpus import CALENDARS
from forecast.polymarket import _STRIKE_RE
from forecast.schema import Company

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_ROOT = REPO_ROOT / "forecast" / "data" / "polymarket" / "history"
OUTPUT = REPO_ROOT / "research" / "polymarket-reliability.json"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

#: Every quarterly beat-market Polymarket has ever listed for the three covered
#: names, discovered via public-search on 2026-08-16. The series began Nov 2025;
#: there are no earlier quarters to harvest. Slug encodes report date + strike.
SLUGS: dict[Company, list[str]] = {
    Company.HD: [
        "hd-quarterly-earnings-nongaap-eps-11-18-2025-3pt85",
        "hd-quarterly-earnings-nongaap-eps-02-24-2026-2pt52",
        "hd-quarterly-earnings-nongaap-eps-05-19-2026-3pt41",
        "hd-quarterly-earnings-nongaap-eps-08-18-2026-4pt73",
    ],
    Company.ADI: [
        "adi-quarterly-earnings-nongaap-eps-11-25-2025-2pt23",
        "adi-quarterly-earnings-nongaap-eps-02-18-2026-2pt3",
        "adi-quarterly-earnings-nongaap-eps-05-20-2026-2pt9",
        "adi-quarterly-earnings-nongaap-eps-08-19-2026-3pt33",
    ],
    Company.DE: [
        "de-quarterly-earnings-gaap-eps-11-26-2025-3pt87",
        "de-quarterly-earnings-gaap-eps-02-19-2026-2pt1",
        "de-quarterly-earnings-gaap-eps-05-21-2026-5pt74",
        "de-quarterly-earnings-gaap-eps-08-20-2026-4pt72",
    ],
}

#: Which store metric resolves each market. HD/ADI markets are on non-GAAP EPS;
#: DE's are on GAAP. HD only recently began publishing an adjusted figure, so
#: GAAP is the labelled proxy where adj_eps is absent (same rule as the
#: five-year backtest's ACTUAL_ROUTES).
EPS_ROUTE: dict[Company, tuple[str, ...]] = {
    Company.HD: ("adj_eps", "diluted_eps_gaap"),
    Company.ADI: ("adj_eps",),
    Company.DE: ("diluted_eps_gaap",),
}

STORE_SLUG = {Company.HD: "home-depot", Company.ADI: "analog-devices",
              Company.DE: "deere"}
TICKER = {Company.HD: "HD", Company.ADI: "ADI", Company.DE: "DE"}

#: Report-date → fiscal-quarter offset. All three names report 18–28 days after
#: the fiscal quarter closes, so the quarter being reported is the one that
#: contains report_date − 35 days (verified against every slug in SLUGS).
REPORT_LAG_DAYS = 35


# --------------------------------------------------------------------------- #
# Harvest
# --------------------------------------------------------------------------- #


def _fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "avws-forecast/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def refresh() -> None:
    """Snapshot every event and its full CLOB price history."""
    HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
    fetched = []
    for slugs in SLUGS.values():
        for slug in slugs:
            data = _fetch_json(f"{GAMMA}/events?slug={urllib.parse.quote(slug)}")
            if not data:
                print(f"  no event for {slug}", file=sys.stderr)
                continue
            (HISTORY_ROOT / f"{slug}.json").write_text(json.dumps(data, indent=1))
            market = data[0]["markets"][0]
            token = json.loads(market["clobTokenIds"])[0]  # YES token
            # The CLOB prunes high-fidelity history once a market resolves;
            # 12-hour candles are the finest series that survives for every
            # market, so use them uniformly.
            prices = _fetch_json(
                f"{CLOB}/prices-history?market={token}&interval=max&fidelity=720")
            (HISTORY_ROOT / f"{slug}-prices.json").write_text(
                json.dumps(prices, indent=1))
            fetched.append(slug)
    manifest = {"fetched_at": datetime.now(timezone.utc).isoformat(),
                "slugs": fetched}
    (HISTORY_ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    print(f"snapshotted {len(fetched)} events -> {HISTORY_ROOT.relative_to(REPO_ROOT)}")


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def _actual_eps(company: Company) -> dict[str, tuple[float, str, str, str]]:
    """period key -> (value, metric_key, published, source) — earliest disclosure."""
    store = json.loads(
        (REPO_ROOT / "data" / "observations" / f"{STORE_SLUG[company]}.json").read_text())
    best: dict[tuple[str, str], tuple[str, float, str]] = {}
    for row in store["observations"]:
        if row["kind"] != "ACTUAL" or row["metric_key"] not in EPS_ROUTE[company]:
            continue
        key = (row["metric_key"], row["period"])
        if key not in best or row["as_of"] < best[key][0]:
            best[key] = (row["as_of"], row["value"], row["source_file"])
    out: dict[str, tuple[float, str, str, str]] = {}
    for metric in EPS_ROUTE[company]:  # exact key wins over the proxy
        for (mk, period), (as_of, value, src) in best.items():
            if mk == metric and period not in out:
                out[period] = (value, mk, as_of, src)
    return out


def _price_at(history: list[dict], cutoff: datetime) -> float | None:
    """Last traded YES price at or before `cutoff` (UTC)."""
    ts = cutoff.timestamp()
    prior = [p for p in history if p["t"] <= ts]
    return round(prior[-1]["p"], 4) if prior else None


def _period_key(company: Company, report: date) -> str:
    period = CALENDARS[company].period_of(report - timedelta(days=REPORT_LAG_DAYS))
    return period.key


def score() -> dict:
    companies = {}
    resolved_rows = []
    for company, slugs in SLUGS.items():
        actuals = _actual_eps(company)
        rows = []
        for slug in slugs:
            event_path = HISTORY_ROOT / f"{slug}.json"
            if not event_path.exists():
                print(f"  missing snapshot {slug} (run --refresh)", file=sys.stderr)
                continue
            event = json.loads(event_path.read_text())[0]
            market = event["markets"][0]
            m = _STRIKE_RE.search(slug)
            strike = float(f"{m.group(1)}.{m.group(2)}")
            end = datetime.fromisoformat(market["endDate"].replace("Z", "+00:00"))
            report = end.date()
            period = _period_key(company, report)
            prices = json.loads((HISTORY_ROOT / f"{slug}-prices.json").read_text())
            history = prices.get("history", [])
            # endDate is the market's scheduled close, which for a pre-market
            # reporter falls AFTER the release. p at −24h is therefore the last
            # clean pre-print probability; p at −2h may already reflect the
            # actual numbers and is recorded only as pPostPrint context.
            p_day_before = _price_at(history, end - timedelta(hours=24))
            p_post = _price_at(history, end - timedelta(hours=2))

            closed = bool(market.get("closed"))
            outcome = None
            if closed and market.get("umaResolutionStatus") == "resolved":
                outcome = int(float(json.loads(market["outcomePrices"])[0]) > 0.5)
            actual = actuals.get(period)
            row = {
                "slug": slug,
                "url": f"https://polymarket.com/event/{slug}",
                "period": period,
                "reportDate": report.isoformat(),
                "strike": strike,
                "question": market.get("question"),
                "volumeUsd": round(float(market.get("volumeNum") or 0.0), 0),
                "pDayBefore": p_day_before,
                "pPostPrint": p_post,
                "resolved": closed,
                "outcome": outcome,
                "actualEps": actual[0] if actual else None,
                "actualMetric": actual[1] if actual else None,
                "actualPublished": actual[2] if actual else None,
                "actualSource": actual[3] if actual else None,
            }
            if outcome is not None and p_day_before is not None:
                row["brierDayBefore"] = round((p_day_before - outcome) ** 2, 4)
                if actual:
                    # Cross-check: filing actual must agree with the resolution.
                    row["resolutionConsistent"] = (actual[0] > strike) == bool(outcome)
                resolved_rows.append(row)
            rows.append(row)
        done = [r for r in rows if r.get("outcome") is not None]
        scored = [r for r in done if "brierDayBefore" in r]
        companies[TICKER[company]] = {
            "basis": "non-GAAP EPS" if company is not Company.DE else "GAAP EPS",
            "rows": rows,
            "resolved": len(done),
            "beatRate": (round(sum(r["outcome"] for r in done) / len(done), 3)
                         if done else None),
            "brierDayBefore": (round(
                sum(r["brierDayBefore"] for r in scored) / len(scored), 4)
                if scored else None),
        }

    n = len(resolved_rows)
    summary = {
        "resolvedMarkets": n,
        "beatRate": round(sum(r["outcome"] for r in resolved_rows) / n, 3) if n else None,
        "brierDayBefore": (round(
            sum(r["brierDayBefore"] for r in resolved_rows) / n, 4) if n else None),
        # The no-skill reference: always predict the realized base rate.
        "brierBaseRate": (round(sum(
            (sum(r["outcome"] for r in resolved_rows) / n - r["outcome"]) ** 2
            for r in resolved_rows) / n, 4) if n else None),
        "consistencyChecks": {
            "checked": sum("resolutionConsistent" in r for r in resolved_rows),
            "passed": sum(r.get("resolutionConsistent") is True for r in resolved_rows),
        },
    }
    return {
        "meta": {
            "title": "Polymarket quarterly-earnings market reliability",
            "generated": date.today().isoformat(),
            "priceRule": "pDayBefore = last 12h CLOB candle ≥24h before the scheduled "
                         "close, i.e. strictly pre-print; pPostPrint (−2h) may "
                         "already reflect the released numbers",
            "coverage": "The beat-market series begins Nov 2025; nine resolved "
                        "markets exist across HD, ADI and DE. Hays has none.",
            "snapshots": str(HISTORY_ROOT.relative_to(REPO_ROOT)),
        },
        "summary": summary,
        "companies": companies,
    }


def main(argv: list[str]) -> int:
    if "--refresh" in argv:
        refresh()
    payload = score()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    s = payload["summary"]
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)}: {s['resolvedMarkets']} resolved "
          f"markets, day-before Brier {s['brierDayBefore']} "
          f"(base-rate reference {s['brierBaseRate']})")
    for ticker, block in payload["companies"].items():
        for r in block["rows"]:
            flag = ("" if r.get("resolutionConsistent", True)
                    else "  !! filing disagrees with resolution")
            o = {None: "open", 1: "YES", 0: "NO"}[r.get("outcome")]
            print(f"  {ticker:<4}{r['period']:<10}strike {r['strike']:<6}"
                  f"p24h {str(r['pDayBefore']):<7}-> {o:<5}"
                  f"actual {str(r['actualEps']):<7}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
