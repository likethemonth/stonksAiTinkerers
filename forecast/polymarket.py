"""Prediction-market proxy estimator ("the market lens").

Turns Polymarket earnings markets into (a) a leaked snapshot of Street
consensus, (b) a market-implied estimate per target metric, and (c) an
*external critic* of our own forecasts. Design follows the strategy chat:

    A. DIRECT TARGET MARKETS      binary "beat" markets whose strike IS the
                                  Street consensus snapshot at market creation
                                  (per Polymarket's own resolution rules).
    B. TARGET-ADJACENT MARKETS    threshold ladders ("revenue above $12.0B?")
                                  and outcome buckets ("comps 0.5%-1%") that
                                  historically appear days before earnings.
    C. MACRO STATE MARKETS        Fed / tariffs / commodities. Informational
                                  only; never converted into metric estimates.

Two rules keep this honest:

1.  **Point-in-time snapshots.** Every API response is written to
    `forecast/data/polymarket/<YYYY-MM-DD>/<slug>.json` when fetched. Replays
    read the newest snapshot directory at or before --as-of and never touch the
    network, mirroring corpus.py's cutoff discipline. The final run can execute
    fully offline from the last snapshot.

2.  **A binary price is a constraint, not a point.** P(actual > strike) = p
    pins one quantile of the market's distribution. A point estimate needs a
    dispersion assumption, so the implied mean is reported under LOW/MID/HIGH
    surprise-sigma scenarios (calibrated from recent quarters' consensus
    misses), and the Estimate's sigma is widened by the scenario spread. The
    primary product is the *critic*: where the market's beat probability and
    our fundamental forecast disagree materially, that disagreement is flagged
    as a research question rather than silently averaged away.

CLI:
    python3 -m forecast.polymarket --refresh          # fetch + snapshot now
    python3 -m forecast.polymarket --as-of 2026-08-16 # offline replay
    python3 -m forecast.polymarket --selftest         # parsers vs closed mkts
"""

from __future__ import annotations

import json
import math
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from forecast.schema import Company, Estimate

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_ROOT = REPO_ROOT / "forecast" / "data" / "polymarket"
GAMMA = "https://gamma-api.polymarket.com"

# --------------------------------------------------------------------------- #
# Market universe
# --------------------------------------------------------------------------- #

#: Layer A — live binary beat-markets, one per EPS target. The slug encodes the
#: strike ("4pt72"); the description re-states it and names the basis (GAAP vs
#: non-GAAP), which matches each challenge metric's basis exactly.
DIRECT_MARKETS: dict[tuple[Company, str], str] = {
    (Company.ADI, "adj_eps"): "adi-quarterly-earnings-nongaap-eps-08-19-2026-3pt33",
    (Company.DE, "gaap_eps"): "de-quarterly-earnings-gaap-eps-08-20-2026-4pt72",
    (Company.HD, "adj_eps"): "hd-quarterly-earnings-nongaap-eps-08-18-2026-4pt73",
    # Hays has no Polymarket coverage (small UK listing). Recorded so the gap
    # is explicit in every output rather than silently absent.
}

#: Layer B — searches to re-run near earnings. Prior-quarter precedents exist
#: for every one of these (all closed now, used by --selftest), so Q3/Q2
#: versions may appear days before the prints; --refresh re-checks.
ADJACENT_SEARCHES: dict[Company, list[str]] = {
    Company.DE: ["deere q3 revenue", "deere production precision"],
    Company.HD: ["home depot q2 comparable sales"],
    Company.ADI: ["analog devices q3 revenue", "analog devices industrial revenue"],
    Company.HAS: ["hays net fees"],
}

#: Dispersion of the actual around the frozen consensus strike, in the metric's
#: own units: (LOW, MID, HIGH) scenarios. Calibrated from the last ~6 quarters
#: of consensus misses visible in the corpus 8-Ks (ADI beats of $0.04-0.21 vs
#: guide-anchored consensus; DE's tariff-era GAAP swings incl. a $272M one-off
#: refund; HD's historically tight $0.02-0.06 adj-EPS surprises). Revisit per
#: quarter; they are assumptions, not fetched facts.
SURPRISE_SIGMA: dict[tuple[Company, str], tuple[float, float, float]] = {
    (Company.ADI, "adj_eps"): (0.05, 0.09, 0.14),
    (Company.DE, "gaap_eps"): (0.20, 0.35, 0.55),
    (Company.HD, "adj_eps"): (0.03, 0.05, 0.09),
}

#: Divergence between market P(beat) and our model's implied P(beat) above
#: which the metric is flagged as an open research question (the chat's
#: "external critic of your posterior").
CRITIC_THRESHOLD = 0.25

_STRIKE_RE = re.compile(r"(\d+)pt(\d+)")
_MONEY_RE = re.compile(r"\$([\d.]+)\s*([BbMm])?")
_PCT_RE = re.compile(r"(-?[\d.]+)\s*%")


# --------------------------------------------------------------------------- #
# Normal quantile (Acklam's approximation — no scipy at the venue)
# --------------------------------------------------------------------------- #


def norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF, |error| < 1.2e-9 on (0, 1)."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0,1), got {p}")
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > phigh:
        return -norm_ppf(1 - p)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1
    )


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# --------------------------------------------------------------------------- #
# Snapshots — the point-in-time boundary
# --------------------------------------------------------------------------- #


def _fetch_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "avws-forecast/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def snapshot_now(extra_slugs: list[str] | None = None) -> Path:
    """Fetch every known + discovered market and write today's snapshot dir."""
    today = date.today().isoformat()
    out = SNAPSHOT_ROOT / today
    out.mkdir(parents=True, exist_ok=True)

    slugs = set(DIRECT_MARKETS.values()) | set(extra_slugs or [])
    # Layer B discovery: search, keep open events that mention the company.
    for company, queries in ADJACENT_SEARCHES.items():
        for q in queries:
            url = f"{GAMMA}/public-search?q={urllib.parse.quote(q)}&limit_per_type=10"
            try:
                found = _fetch_json(url)
            except OSError as exc:
                print(f"  search {q!r} failed: {exc}", file=sys.stderr)
                continue
            for ev in found.get("events", []) if isinstance(found, dict) else []:
                if ev.get("slug") and not ev.get("closed"):
                    slugs.add(ev["slug"])

    manifest = {"fetched_at": datetime.now(timezone.utc).isoformat(), "slugs": []}
    for slug in sorted(slugs):
        try:
            data = _fetch_json(f"{GAMMA}/events?slug={urllib.parse.quote(slug)}")
        except OSError as exc:
            print(f"  fetch {slug} failed: {exc}", file=sys.stderr)
            continue
        if data:
            (out / f"{slug}.json").write_text(json.dumps(data, indent=1))
            manifest["slugs"].append(slug)
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    return out


def snapshot_dir(as_of: date | None = None) -> Path | None:
    """Newest snapshot directory at or before `as_of` (today if None)."""
    if not SNAPSHOT_ROOT.is_dir():
        return None
    cutoff = (as_of or date.today()).isoformat()
    dirs = sorted(d for d in SNAPSHOT_ROOT.iterdir() if d.is_dir() and d.name <= cutoff)
    return dirs[-1] if dirs else None


def load_event(slug: str, as_of: date | None = None) -> dict | None:
    d = snapshot_dir(as_of)
    if d is None:
        return None
    path = d / f"{slug}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data[0] if isinstance(data, list) and data else None


# --------------------------------------------------------------------------- #
# Parsers — one per market shape
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BeatSignal:
    """Layer A: one binary beat-market, decoded."""

    company: Company
    metric_key: str
    slug: str
    strike: float          # Street consensus at market creation — the leak
    p_beat: float          # mid of best bid/ask: P(actual > strike)
    volume: float
    implied: dict[str, float]  # scenario name -> implied mean
    fetched_from: str

    @property
    def url(self) -> str:
        return f"https://polymarket.com/event/{self.slug}"


def _mid_price(market: dict) -> float:
    bid, ask = market.get("bestBid"), market.get("bestAsk")
    if bid is not None and ask is not None and 0 < bid <= ask < 1:
        return (bid + ask) / 2
    prices = json.loads(market.get("outcomePrices") or "[null]")
    if prices and prices[0] is not None:
        return float(prices[0])
    return float(market.get("lastTradePrice") or 0.5)


def parse_beat_market(
    company: Company, metric_key: str, slug: str, as_of: date | None = None
) -> BeatSignal | None:
    event = load_event(slug, as_of)
    if event is None:
        return None
    market = event["markets"][0]
    m = _STRIKE_RE.search(slug)
    if m is None:
        return None
    strike = float(f"{m.group(1)}.{m.group(2)}")
    p = min(0.98, max(0.02, _mid_price(market)))  # clip: a binary cannot pin tails
    z = norm_ppf(p)
    lo, mid, hi = SURPRISE_SIGMA[(company, metric_key)]
    implied = {"low": strike + lo * z, "mid": strike + mid * z, "high": strike + hi * z}
    src = snapshot_dir(as_of)
    return BeatSignal(
        company=company, metric_key=metric_key, slug=slug, strike=strike,
        p_beat=p, volume=float(market.get("volumeNum") or 0.0),
        implied={k: round(v, 3) for k, v in implied.items()},
        fetched_from=str(src.relative_to(REPO_ROOT)) if src else "",
    )


@dataclass(frozen=True)
class ScalarSignal:
    """Layer B: implied mean from a bucket set or a threshold ladder."""

    slug: str
    kind: str              # "buckets" | "ladder"
    implied_mean: float
    pieces: list[tuple[str, float]] = field(default_factory=list)


_RANGE_RE = re.compile(r"(-?[\d.]+)\s*%?\s*-\s*(-?[\d.]+)\s*%")


def _bucket_bounds(title: str) -> tuple[float | None, float | None]:
    """'<16%' -> (None, 16); '16%-18%' -> (16, 18); '1%+' -> (1, None).

    The range separator must be matched *before* signs: in '0%-0.5%' the
    hyphen separates the bounds, it does not negate the second one.
    """
    t = title.strip().replace("–", "-").replace("—", "-")
    if t.startswith("<"):
        nums = _PCT_RE.findall(t)
        return (None, float(nums[0])) if nums else (None, None)
    if t.endswith("+"):
        nums = _PCT_RE.findall(t)
        return (float(nums[0]), None) if nums else (None, None)
    m = _RANGE_RE.search(t)
    if m:
        return float(m.group(1)), float(m.group(2))
    nums = _PCT_RE.findall(t)
    return (float(nums[0]), float(nums[0])) if nums else (None, None)


def parse_bucket_event(event: dict) -> ScalarSignal | None:
    """Mutually-exclusive outcome buckets -> probability-weighted midpoint.

    Open-ended tail buckets take a synthetic midpoint half a modal-bucket-width
    beyond their closed edge — crude, symmetric, and stated.
    """
    rows: list[tuple[float | None, float | None, float]] = []
    for m in event.get("markets", []):
        title = m.get("groupItemTitle") or m.get("question") or ""
        lo, hi = _bucket_bounds(title)
        if lo is None and hi is None:
            continue
        rows.append((lo, hi, _mid_price(m)))
    if not rows:
        return None
    widths = [hi - lo for lo, hi, _ in rows if lo is not None and hi is not None and hi > lo]
    w = min(widths) if widths else 1.0
    total = sum(p for *_ , p in rows) or 1.0
    mean, pieces = 0.0, []
    for lo, hi, p in rows:
        mid = (lo + hi) / 2 if lo is not None and hi is not None else (
            (hi - w / 2) if lo is None else (lo + w / 2)
        )
        mean += (p / total) * mid
        pieces.append((f"[{lo},{hi}]", round(p / total, 3)))
    return ScalarSignal(slug=event.get("slug", ""), kind="buckets",
                        implied_mean=round(mean, 3), pieces=pieces)


def parse_ladder_event(event: dict) -> ScalarSignal | None:
    """'above X' threshold ladder -> survival curve -> implied mean.

    E[X] is integrated over the thresholds; the mass below the first and above
    the last threshold is placed one modal-step beyond, matching the bucket
    convention. Monotonicity violations (thin books) are ironed out.
    """
    rows: list[tuple[float, float]] = []
    for m in event.get("markets", []):
        title = m.get("groupItemTitle") or m.get("question") or ""
        money = _MONEY_RE.search(title)
        if not money:
            continue
        value = float(money.group(1)) * (1000.0 if (money.group(2) or "").lower() == "b" else 1.0)
        rows.append((value, _mid_price(m)))  # value in $M, P(actual > value)
    if len(rows) < 2:
        return None
    rows.sort()
    survival = []
    prev = 1.0
    for value, p in rows:
        p = min(prev, p)  # enforce monotone decreasing
        survival.append((value, p))
        prev = p
    step = min(b - a for (a, _), (b, _) in zip(survival, survival[1:]))
    mean, pieces, p_prev, lower = 0.0, [], 1.0, survival[0][0] - step
    for value, p in survival:
        mass = p_prev - p
        mean += mass * (lower + value) / 2
        pieces.append((f">{value:g}", round(p, 3)))
        p_prev, lower = p, value
    mean += p_prev * (survival[-1][0] + step / 2)
    return ScalarSignal(slug=event.get("slug", ""), kind="ladder",
                        implied_mean=round(mean, 1), pieces=pieces)


# --------------------------------------------------------------------------- #
# Estimates and the critic
# --------------------------------------------------------------------------- #


def beat_to_estimate(sig: BeatSignal) -> Estimate:
    """MID-scenario implied mean, sigma widened by the scenario spread."""
    lo, mid, hi = SURPRISE_SIGMA[(sig.company, sig.metric_key)]
    z = norm_ppf(sig.p_beat)
    scenario_spread = abs(z) * (hi - lo) / 2
    sigma = math.hypot(mid, scenario_spread)
    return Estimate(
        estimator="polymarket_proxy",
        value=sig.implied["mid"],
        sigma=round(sigma, 4),
        n_observations=1,
        anchor=sig.strike,
        correction=round(sig.implied["mid"] - sig.strike, 4),
        reasoning=(
            f"Market prices P(actual > {sig.strike}) = {sig.p_beat:.2f} "
            f"(${sig.volume:,.0f} traded). Strike is the Street consensus frozen at "
            f"market creation. Implied mean = strike + sigma*z(p) = {sig.implied['mid']} "
            f"under the MID surprise-sigma {mid}; scenario range "
            f"{sig.implied['low']}-{sig.implied['high']} is folded into this "
            f"estimate's sigma. A one-quantile constraint, not a point observation."
        ),
        citations=[sig.url],
    )


@dataclass(frozen=True)
class CriticVerdict:
    metric_key: str
    company: Company
    market_p_beat: float
    model_p_beat: float
    divergence: float
    research_question: str | None


def critic(sig: BeatSignal, model_value: float, model_sigma: float) -> CriticVerdict:
    """Compare our forecast's implied beat probability with the market's.

    This is the module's most important product: material disagreement is a
    prompt to go find what the market knows, not an error term to average.
    """
    model_p = norm_cdf((model_value - sig.strike) / max(model_sigma, 1e-9))
    div = abs(model_p - sig.p_beat)
    question = None
    if div > CRITIC_THRESHOLD:
        question = (
            f"{sig.company.name} {sig.metric_key}: our model implies "
            f"P(beat {sig.strike}) = {model_p:.0%} but real-money traders price "
            f"{sig.p_beat:.0%} on ${sig.volume:,.0f} volume. What is the market "
            f"seeing that the model is not (or vice versa)?"
        )
    return CriticVerdict(
        metric_key=sig.metric_key, company=sig.company,
        market_p_beat=round(sig.p_beat, 3), model_p_beat=round(model_p, 3),
        divergence=round(div, 3), research_question=question,
    )


# --------------------------------------------------------------------------- #
# Self-test on resolved markets (parsers vs known outcomes)
# --------------------------------------------------------------------------- #

#: Closed prior-quarter markets with the actuals later reported in the corpus.
#: Proves each parser recovers a value consistent with what actually happened.
SELFTEST_CASES = [
    ("home-depot-q1-comparable-sales-growth", "buckets", 0.6,
     "HD Q1 FY26 comps +0.6% (8-K 2026-05-19); resolved bucket 0.5%-1%"),
    ("will-deere-q2-revenue-be-above", "ladder", 13369.0,
     "DE Q2 FY26 net sales and revenues $13,369M (8-K 2026-05-21); all rungs Yes"),
    ("deere-q2-production-precision-agriculture-operating-margin", "buckets", 15.7,
     "DE Q2 FY26 PPA operating margin 15.7%; resolved bucket <16%"),
]


def run_selftest(as_of: date | None = None) -> bool:
    ok = True
    for slug, kind, actual, note in SELFTEST_CASES:
        event = load_event(slug, as_of)
        if event is None:
            print(f"  SKIP {slug}: no snapshot")
            continue
        sig = parse_bucket_event(event) if kind == "buckets" else parse_ladder_event(event)
        if sig is None:
            print(f"  FAIL {slug}: parser returned nothing")
            ok = False
            continue
        # Resolved books collapse to the winning outcome, so the implied mean
        # must land inside/at the winning bucket — i.e. near the actual.
        tolerance = max(0.75, 0.10 * abs(actual))
        good = abs(sig.implied_mean - actual) <= tolerance
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'} {slug}: implied {sig.implied_mean} "
              f"vs actual {actual}  ({note})")
    return ok


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str]) -> int:
    as_of = None
    if "--as-of" in argv:
        as_of = date.fromisoformat(argv[argv.index("--as-of") + 1])
    if "--refresh" in argv:
        out = snapshot_now()
        print(f"snapshot written: {out.relative_to(REPO_ROOT)}")
    if "--selftest" in argv:
        return 0 if run_selftest(as_of) else 1

    fundamental = {}
    fpath = REPO_ROOT / "agent" / "fable-research-forecast.json"
    if "--fundamental" in argv:
        fpath = Path(argv[argv.index("--fundamental") + 1])
    if fpath.exists():
        raw = json.loads(fpath.read_text())["forecasts"]
        for wb, block in raw.items():
            for m in block["metrics"]:
                fundamental[(wb.split("-")[0], m["label"])] = m["final"]

    # Model sigmas for the critic: fundamental uncertainty per EPS target,
    # consistent with the research notes' stated ranges.
    model_sigma = {Company.ADI: 0.10, Company.DE: 0.30, Company.HD: 0.08}
    fund_key = {
        (Company.ADI, "adj_eps"): ("ADI", "Adjusted diluted EPS"),
        (Company.DE, "gaap_eps"): ("DE", "Diluted EPS (GAAP)"),
        (Company.HD, "adj_eps"): ("HD", "Adjusted diluted EPS"),
    }

    print(f"\nPolymarket proxy — snapshot {snapshot_dir(as_of)}")
    print(f"{'target':<14}{'strike':>8}{'P(beat)':>9}{'implied lo/mid/hi':>24}"
          f"{'ours':>8}{'P_model':>9}{'verdict':>10}")
    estimates, questions = {}, []
    for (company, metric_key), slug in DIRECT_MARKETS.items():
        sig = parse_beat_market(company, metric_key, slug, as_of)
        if sig is None:
            print(f"{company.name+':'+metric_key:<14}{'-- no snapshot --':>50}")
            continue
        est = beat_to_estimate(sig)
        estimates[f"{company.name}:{metric_key}"] = est.model_dump()
        ours = fundamental.get(fund_key[(company, metric_key)])
        verdict_txt, p_model = "", ""
        if ours is not None:
            v = critic(sig, ours, model_sigma[company])
            p_model = f"{v.model_p_beat:.0%}"
            verdict_txt = "ALIGNED" if v.research_question is None else "DIVERGES"
            if v.research_question:
                questions.append(v.research_question)
        imp = f"{sig.implied['low']}/{sig.implied['mid']}/{sig.implied['high']}"
        print(f"{company.name+':'+metric_key:<14}{sig.strike:>8}{sig.p_beat:>9.2f}"
              f"{imp:>24}{ours if ours is not None else '':>8}{p_model:>9}{verdict_txt:>10}")
    print(f"{'HAS:*':<14}{'no Polymarket coverage — company-compiled consensus is the Street lens':>60}")

    d = snapshot_dir(as_of)
    if d:
        out = d / "proxy-estimates.json"
        out.write_text(json.dumps(
            {"as_of": str(as_of or date.today()), "estimates": estimates,
             "research_questions": questions}, indent=1))
        print(f"\nestimates -> {out.relative_to(REPO_ROOT)}")
    for q in questions:
        print(f"RESEARCH QUESTION: {q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
