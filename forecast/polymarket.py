"""Prediction-market proxy estimator ("the market lens").

Turns Polymarket earnings markets into (a) a dated snapshot of Street
consensus, (b) a market-implied *scenario* per target metric, and (c) an
*external critic* of our own forecasts. The scenario is retained for research
but is deliberately signal-only in the top-level ensemble: a binary contract
provides one quantile, and the pre-resolution walk-forward archive has not yet
passed its sample-size and exact sign-test promotion gates.

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
    as a research question rather than silently averaged away. The diagnostic
    point scenario receives zero final weight until the market-price
    walk-forward promotion gate passes.

CLI:
    python3 -m forecast.polymarket --refresh          # fetch + snapshot now
    python3 -m forecast.polymarket --as-of 2026-08-16 # offline replay
    python3 -m forecast.polymarket --selftest         # parsers vs closed mkts
"""

from __future__ import annotations

import csv
import json
import math
import re
import statistics
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from forecast.schema import Company, Estimate, ProbabilityConstraint

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_ROOT = REPO_ROOT / "forecast" / "data" / "polymarket"
CONSENSUS_HISTORY = REPO_ROOT / "forecasting" / "data" / "historical_forecasts.csv"
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

#: Conservative fallbacks for the standard deviation of EPS consensus misses.
#: Normal operation estimates this scale from dated rows in CONSENSUS_HISTORY.
FALLBACK_SURPRISE_SIGMA: dict[tuple[Company, str], float] = {
    (Company.ADI, "adj_eps"): 0.12,
    (Company.DE, "gaap_eps"): 0.60,
    (Company.HD, "adj_eps"): 0.12,
}

_HISTORY_KEYS: dict[tuple[Company, str], tuple[str, str]] = {
    (Company.ADI, "adj_eps"): ("Analog Devices", "Adjusted diluted EPS"),
    (Company.DE, "gaap_eps"): ("Deere & Company", "Diluted EPS (GAAP)"),
    (Company.HD, "adj_eps"): ("Home Depot", "Adjusted diluted EPS"),
}

#: Divergence between market P(beat) and our model's implied P(beat) above
#: which the metric is flagged as an open research question (the chat's
#: "external critic of your posterior").
CRITIC_THRESHOLD = 0.25

_STRIKE_RE = re.compile(r"(\d+)pt(\d+)")
_DESCRIPTION_STRIKE_RE = re.compile(
    r"consensus estimate[^$]{0,160}\$([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE | re.DOTALL,
)
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
    """Fetch known/discovered markets into an append-only UTC snapshot.

    Legacy snapshots live directly under ``YYYY-MM-DD``. New snapshots add an
    ``HHMMSS.ffffffZ`` run directory so a second refresh cannot overwrite the
    evidence used by an earlier forecast on the same day.
    """
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    out = SNAPSHOT_ROOT / today / now.strftime("%H%M%S.%fZ")
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

    manifest = {"fetched_at": now.isoformat(), "slugs": []}
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


def _snapshot_runs(as_of: date | None = None) -> list[Path]:
    """All eligible snapshot runs, newest first (including legacy day dirs)."""
    if not SNAPSHOT_ROOT.is_dir():
        return []
    cutoff = (as_of or date.today()).isoformat()
    day_dirs = sorted(
        (
            d
            for d in SNAPSHOT_ROOT.iterdir()
            if d.is_dir()
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name)
            and d.name <= cutoff
        ),
        reverse=True,
    )
    runs: list[Path] = []
    for day_dir in day_dirs:
        runs.extend(sorted((d for d in day_dir.iterdir() if d.is_dir()), reverse=True))
        if any(day_dir.glob("*.json")):
            runs.append(day_dir)
    return runs


def snapshot_dir(as_of: date | None = None) -> Path | None:
    """Newest snapshot run at or before ``as_of`` (today if omitted)."""
    runs = _snapshot_runs(as_of)
    return runs[0] if runs else None


def snapshot_file(slug: str, as_of: date | None = None) -> Path | None:
    """Newest snapshot of this slug at or before the cutoff.

    A partial refresh must not hide a valid older snapshot merely because the
    newer run's manifest omitted that market.
    """
    for run in _snapshot_runs(as_of):
        path = run / f"{slug}.json"
        if path.is_file():
            return path
    return None


def load_event(slug: str, as_of: date | None = None) -> dict | None:
    path = snapshot_file(slug, as_of)
    if path is None:
        return None
    data = json.loads(path.read_text())
    return data[0] if isinstance(data, list) and data else None


def surprise_sigma(
    company: Company,
    metric_key: str,
    as_of: date | None = None,
    *,
    history_path: Path = CONSENSUS_HISTORY,
) -> tuple[tuple[float, float, float], int]:
    """Estimate consensus-miss dispersion without using future outcomes.

    MID is the sample standard deviation of ``actual-consensus`` among resolved,
    pre-cutoff forecasts for the same company and EPS basis. LOW/HIGH are
    explicit sensitivity cases. This calibrates the distributional scale only;
    it does not validate the market-to-point conversion itself.
    """
    key = (company, metric_key)
    fallback = FALLBACK_SURPRISE_SIGMA[key]
    target = _HISTORY_KEYS[key]
    cutoff = as_of or date.today()
    errors: list[float] = []
    if history_path.is_file():
        with history_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if (row.get("company"), row.get("metric")) != target:
                    continue
                if row.get("source_id") != "public_consensus" or not row.get("actual"):
                    continue
                try:
                    forecast_date = date.fromisoformat(row["forecast_date"])
                    event_date = date.fromisoformat(row["event_date"])
                    forecast = float(row["forecast"])
                    actual = float(row["actual"])
                except (KeyError, TypeError, ValueError):
                    continue
                # ``as_of`` is date-granular while earnings usually arrive
                # during that date. Exclude same-day outcomes so a midnight
                # market cutoff cannot calibrate itself on the later result.
                if forecast_date >= event_date or event_date >= cutoff:
                    continue
                errors.append(actual - forecast)

    mid = statistics.stdev(errors) if len(errors) >= 4 else fallback
    scenarios = (0.75 * mid, mid, 1.5 * mid)
    return tuple(round(value, 6) for value in scenarios), len(errors)


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
    surprise_sigma: tuple[float, float, float]
    calibration_n: int
    fetched_from: str

    @property
    def url(self) -> str:
        return f"https://polymarket.com/event/{self.slug}"


def _json_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _mid_price(market: dict) -> float:
    """Read the YES price using Polymarket's documented display convention."""
    labels = [str(item).strip().casefold() for item in _json_list(market.get("outcomes"))]
    prices = _json_list(market.get("outcomePrices"))
    if labels.count("yes") != 1:
        raise ValueError("binary market has no unique YES outcome")
    yes_index = labels.index("yes")

    # Resolved prices are payoffs, never forecasts. They are used only by the
    # closed-market parser self-test.
    if market.get("closed") or market.get("acceptingOrders") is False:
        if yes_index < len(prices) and prices[yes_index] is not None:
            price = float(prices[yes_index])
            if 0 <= price <= 1:
                return price

    bid, ask = market.get("bestBid"), market.get("bestAsk")
    if bid is not None and ask is not None:
        bid, ask = float(bid), float(ask)
        if 0 <= bid <= ask <= 1 and ask - bid <= 0.10:
            return (bid + ask) / 2

    # Polymarket displays the last trade for spreads wider than $0.10.
    last = market.get("lastTradePrice")
    if last is not None:
        last = float(last)
        if 0 <= last <= 1:
            return last

    if yes_index < len(prices) and prices[yes_index] is not None:
        price = float(prices[yes_index])
        if 0 <= price <= 1:
            return price
    raise ValueError("binary market has no valid YES price")


def parse_beat_market(
    company: Company, metric_key: str, slug: str, as_of: date | None = None
) -> BeatSignal | None:
    event = load_event(slug, as_of)
    if event is None:
        return None
    if event.get("slug") != slug or event.get("closed"):
        return None
    markets = event.get("markets")
    if not isinstance(markets, list) or len(markets) != 1:
        return None
    market = markets[0]
    if not isinstance(market, dict) or market.get("closed"):
        return None

    description = str(event.get("description") or market.get("description") or "")
    description_folded = description.casefold()
    if metric_key == "adj_eps" and "non-gaap eps" not in description_folded:
        return None
    if metric_key == "gaap_eps" and (
        "gaap eps" not in description_folded or "non-gaap eps" in description_folded
    ):
        return None

    slug_match = _STRIKE_RE.search(slug)
    description_match = _DESCRIPTION_STRIKE_RE.search(description)
    if slug_match is None or description_match is None:
        return None
    slug_strike = float(f"{slug_match.group(1)}.{slug_match.group(2)}")
    strike = float(description_match.group(1))
    if not math.isclose(slug_strike, strike, abs_tol=0.005):
        return None
    try:
        raw_p = _mid_price(market)
    except (TypeError, ValueError):
        return None
    p = min(0.98, max(0.02, raw_p))  # one binary cannot identify extreme tails
    z = norm_ppf(p)
    scenarios, calibration_n = surprise_sigma(company, metric_key, as_of)
    lo, mid, hi = scenarios
    implied = {"low": strike + lo * z, "mid": strike + mid * z, "high": strike + hi * z}
    src = snapshot_file(slug, as_of)
    return BeatSignal(
        company=company, metric_key=metric_key, slug=slug, strike=strike,
        p_beat=p, volume=float(market.get("volumeNum") or 0.0),
        implied={k: round(v, 3) for k, v in implied.items()},
        surprise_sigma=scenarios, calibration_n=calibration_n,
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
    """Diagnostic MID scenario, not an ensemble-ready point forecast."""
    lo, mid, hi = sig.surprise_sigma
    z = norm_ppf(sig.p_beat)
    scenario_spread = abs(z) * (hi - lo) / 2
    sigma = math.hypot(mid, scenario_spread)
    return Estimate(
        estimator="polymarket_proxy",
        value=sig.implied["mid"],
        sigma=round(sigma, 4),
        n_observations=sig.calibration_n,
        anchor=sig.strike,
        correction=round(sig.implied["mid"] - sig.strike, 4),
        reasoning=(
            f"Market prices P(actual > {sig.strike}) = {sig.p_beat:.2f} "
            f"(${sig.volume:,.0f} traded). Strike is the Street consensus frozen at "
            f"market creation. Implied mean = strike + sigma*z(p) = {sig.implied['mid']} "
            f"under surprise-sigma {mid:.3f}, estimated from {sig.calibration_n} "
            f"resolved point-in-time consensus errors; scenario range "
            f"{sig.implied['low']}-{sig.implied['high']} is folded into this "
            f"estimate's sigma. This is a one-quantile diagnostic, not a validated "
            f"point estimator; the separate walk-forward promotion gate controls "
            f"whether it can ever become eligible for numeric use."
        ),
        citations=[sig.url],
    )


def market_signal(
    company: Company, metric_key: str, as_of: date | None = None
) -> BeatSignal | None:
    """Load one validated, dated direct-market probability constraint.

    Absence is normal: most operating metrics have no economically equivalent
    market and must be represented as an abstention by the caller.
    """
    # The canonical registry calls Deere's target ``diluted_eps_gaap`` while the
    # original market prototype used ``gaap_eps``. Keep the prototype's public
    # keys stable and adapt at this boundary.
    market_key = "gaap_eps" if metric_key == "diluted_eps_gaap" else metric_key
    slug = DIRECT_MARKETS.get((company, market_key))
    if slug is None:
        return None
    return parse_beat_market(company, market_key, slug, as_of)


def market_constraint(
    company: Company, metric_key: str, as_of: date | None = None
) -> ProbabilityConstraint | None:
    """Canonical ensemble-facing representation: probability, not EPS point."""
    signal = market_signal(company, metric_key, as_of)
    if signal is None:
        return None
    return ProbabilityConstraint(
        threshold=signal.strike,
        probability=signal.p_beat,
        volume=signal.volume,
        source_snapshot=signal.fetched_from,
        citation=signal.url,
    )


def market_estimate(
    company: Company, metric_key: str, as_of: date | None = None
) -> Estimate | None:
    """Research-only point scenario; never consumed by the meta-forecaster."""
    signal = market_signal(company, metric_key, as_of)
    return beat_to_estimate(signal) if signal is not None else None


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
        # Resolved books collapse to the winning outcome. This checks parser
        # semantics only; terminal prices cannot validate pre-event forecasts.
        tolerance = max(0.75, 0.10 * abs(actual))
        good = abs(sig.implied_mean - actual) <= tolerance
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'} parser {slug}: implied {sig.implied_mean} "
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

    print(f"\nPolymarket signal-only proxy — snapshot {snapshot_dir(as_of)}")
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
            {
                "as_of": str(as_of or date.today()),
                "role": "signal_only",
                "eligible_for_meta_weight": False,
                "promotion_gate": (
                    "held-out pre-resolution market-price ablation must show "
                    "incremental point-forecast value"
                ),
                "estimates": estimates,
                "research_questions": questions,
            }, indent=1))
        print(f"\nestimates -> {out.relative_to(REPO_ROOT)}")
    for q in questions:
        print(f"RESEARCH QUESTION: {q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
