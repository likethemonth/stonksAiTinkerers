"""Calibration — measuring how a company's disclosures actually land.

This is the backtest, and it is not an optional extra: it produces the sigma that
the reconciler weights estimators by, so an uncalibrated estimator literally has
no weight to contribute.

The mechanism. Every forecast in this system has the shape

    forecast = anchor x (1 + correction)

where the anchor is something a company disclosed and the correction is a ratio
whose historical distribution we measure here. For a guidance anchor, each closed
period contributes one observation of

    realisation = actual / guidance_mid

and the distribution of those realisations over the last N quarters is the
correction. Because the observation table records an `as_of` on every row, a pair
is only ever formed from a guidance row published *before* the period it guides
and an actual published after it — there is no way to leak the answer backwards.

Shrinkage. With eight or ten observations the sample mean is a noisy estimate of
the true bias, and over-trusting it is how you turn a good anchor into a bad
forecast. We shrink toward zero correction (i.e. toward "the company's guidance
is right") by the empirical-Bayes factor

    lambda = n / (n + PRIOR_STRENGTH)

so a metric with two observations barely moves off the anchor, while one with
twenty moves most of the way to its measured bias.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from forecast.schema import Company, Kind, MetricObservation, Period, Unit

#: Pseudo-observations of "no bias" mixed into every correction. Higher = more
#: conservative. 5 means a metric needs ~5 quarters of history before it is
#: trusted halfway. Tuned to be deliberately timid: over-correcting a good
#: anchor is the failure mode that costs the most under the accuracy rubric.
PRIOR_STRENGTH = 5.0

#: Floor on relative sigma. No estimator may claim to be more certain than this,
#: however quiet its history — it protects the inverse-variance weighting from
#: being dominated by one metric that happened to have a calm few quarters.
MIN_RELATIVE_SIGMA = 0.005

#: Percentage-point metrics are calibrated additively (a margin that guides 49.0%
#: and lands at 49.4% is +0.4pp, not x1.008); everything else multiplicatively.
ADDITIVE_UNITS = frozenset({Unit.PERCENT})


@dataclass(frozen=True)
class Pairing:
    """One matched (guidance, actual) observation for a closed period."""

    period: Period
    guided: float
    actual: float
    guided_as_of: object  # date; kept loose to avoid an import cycle in typing
    actual_as_of: object
    guided_source: str
    actual_source: str

    @property
    def ratio(self) -> float:
        return self.actual / self.guided if self.guided else float("nan")

    @property
    def delta(self) -> float:
        return self.actual - self.guided


@dataclass
class Correction:
    """The measured, shrunk correction for one (metric, anchor kind) pair."""

    company: Company
    metric_key: str
    units: Unit
    anchor_kind: Kind
    additive: bool
    n: int
    raw_mean: float
    shrunk_mean: float
    sigma: float
    pairings: list[Pairing] = field(default_factory=list)

    def apply(self, anchor: float) -> float:
        """Correct a fresh anchor using the shrunk historical bias."""
        return anchor + self.shrunk_mean if self.additive else anchor * self.shrunk_mean

    def sigma_in_units(self, anchor: float) -> float:
        """Predictive sd expressed in the metric's own units."""
        return self.sigma if self.additive else abs(anchor) * self.sigma

    @property
    def summary(self) -> str:
        if self.additive:
            bias = f"{self.shrunk_mean:+.2f}pp (raw {self.raw_mean:+.2f}pp)"
            spread = f"{self.sigma:.2f}pp"
        else:
            bias = (
                f"{(self.shrunk_mean - 1) * 100:+.2f}% "
                f"(raw {(self.raw_mean - 1) * 100:+.2f}%)"
            )
            spread = f"{self.sigma * 100:.2f}%"
        return f"n={self.n} bias={bias} sigma={spread}"


def _shrink(raw: float, n: int, neutral: float) -> float:
    """Pull a raw mean toward the neutral value by n / (n + PRIOR_STRENGTH)."""
    lam = n / (n + PRIOR_STRENGTH)
    return neutral + lam * (raw - neutral)


def pair_guidance_to_actuals(
    observations: list[MetricObservation],
    *,
    anchor_kind: Kind = Kind.GUIDE_MID,
) -> dict[tuple[Company, str], list[Pairing]]:
    """Match each guidance row to the actual that later reported the same period.

    Point-in-time integrity is structural here: a pairing is only formed when the
    guidance was published strictly before the actual, so nothing that postdates
    a forecast can influence the correction used to make it.
    """
    guided: dict[tuple[Company, str, str], MetricObservation] = {}
    actual: dict[tuple[Company, str, str], MetricObservation] = {}

    for obs in observations:
        index = (obs.company, obs.metric_key, obs.period.key)
        if obs.kind is anchor_kind:
            # Keep the earliest guidance: the first time management committed.
            prior = guided.get(index)
            if prior is None or obs.as_of < prior.as_of:
                guided[index] = obs
        elif obs.kind is Kind.ACTUAL:
            prior = actual.get(index)
            if prior is None or obs.as_of < prior.as_of:
                actual[index] = obs

    out: dict[tuple[Company, str], list[Pairing]] = defaultdict(list)
    for index, g in guided.items():
        a = actual.get(index)
        if a is None or a.as_of <= g.as_of:
            continue  # period still open, or ordering is impossible
        company, metric_key, _ = index
        out[(company, metric_key)].append(
            Pairing(
                period=g.period,
                guided=g.value,
                actual=a.value,
                guided_as_of=g.as_of,
                actual_as_of=a.as_of,
                guided_source=g.source_file,
                actual_source=a.source_file,
            )
        )
    for pairings in out.values():
        pairings.sort(key=lambda p: p.period.sort_key)
    return dict(out)


def calibrate(
    observations: list[MetricObservation],
    *,
    anchor_kind: Kind = Kind.GUIDE_MID,
    lookback: int | None = 12,
) -> dict[tuple[Company, str], Correction]:
    """Measure the correction distribution for every metric with paired history.

    Args:
        observations: The point-in-time observation table.
        anchor_kind: Which disclosure acts as the anchor.
        lookback: Use only the most recent N pairings. Older quarters describe a
            different business (ADI's pre-2024 cycle looks nothing like now), so
            an unbounded window makes the correction stale rather than robust.
    """
    units_of = {(o.company, o.metric_key): o.units for o in observations}
    corrections: dict[tuple[Company, str], Correction] = {}

    for key, pairings in pair_guidance_to_actuals(
        observations, anchor_kind=anchor_kind
    ).items():
        window = pairings[-lookback:] if lookback else pairings
        if not window:
            continue

        units = units_of[key]
        additive = units in ADDITIVE_UNITS
        samples = [p.delta if additive else p.ratio for p in window]
        neutral = 0.0 if additive else 1.0
        n = len(samples)

        raw_mean = statistics.fmean(samples)
        shrunk = _shrink(raw_mean, n, neutral)

        if n >= 2:
            # Dispersion about the *shrunk* mean: that is the error an estimator
            # using this correction would actually have made.
            sigma = (statistics.fmean((s - shrunk) ** 2 for s in samples)) ** 0.5
        else:
            # One observation tells us nothing about spread. Fall back to the
            # size of the correction itself, which is honestly pessimistic.
            sigma = abs(raw_mean - neutral) or MIN_RELATIVE_SIGMA

        scale = 1.0 if additive else 1.0
        sigma = max(sigma, MIN_RELATIVE_SIGMA * scale)

        corrections[key] = Correction(
            company=key[0],
            metric_key=key[1],
            units=units,
            anchor_kind=anchor_kind,
            additive=additive,
            n=n,
            raw_mean=raw_mean,
            shrunk_mean=shrunk,
            sigma=sigma,
            pairings=window,
        )
    return corrections
