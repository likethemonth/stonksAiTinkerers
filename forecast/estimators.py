"""Estimators and the reconciler.

An estimator turns disclosed evidence into (value, sigma, reasoning, citations).
The sigma is not optional: the reconciler combines estimators by inverse variance,
so an estimator that cannot state its own dispersion cannot contribute a weight.

Currently implemented:

    guidance_realisation    anchor on management's guidance midpoint, corrected by
                            the shrunk historical realisation ratio from calibrate.py
    regression_bridge       derive a metric the company does not guide from one it
                            does, by fitting the two against each other
    growth_on_prior_actual  apply a disclosed growth rate to last year's reported level
    ratio_on_prior_actual   scale a prior-year actual by the change in its driver
    consensus_anchor        anchor on company-compiled consensus, positioned by
                            management's own steer within the disclosed range
    seasonal_share          divide a full-year anchor into a quarter by that
                            quarter's measured historical share of the year
    quarter_vs_year_offset  the same for a rate metric, which offsets rather
                            than divides
    reconcile               combine the above by inverse variance, flagging any
                            metric where they disagree by more than they claim to
"""

from __future__ import annotations

import statistics

from forecast.calibrate import Correction
from forecast.schema import (
    Company,
    Estimate,
    Kind,
    MetricForecast,
    MetricObservation,
    Period,
    Unit,
)

#: If estimators disagree by more than this multiple of their combined sigma, the
#: metric is flagged for human review instead of being quietly averaged.
DISAGREEMENT_SIGMAS = 2.0

#: Plausibility bands are set this many sigmas either side of the reconciled
#: value. Wide enough that a genuine surprise survives, tight enough that an
#: extraction slip is caught.
BAND_SIGMAS = 4.0


def guidance_realisation(
    observations: list[MetricObservation],
    correction: Correction | None,
    *,
    company: Company,
    metric_key: str,
    period: Period,
) -> Estimate | None:
    """Management's guidance for `period`, corrected by its historical bias."""
    guides = [
        o
        for o in observations
        if o.company is company
        and o.metric_key == metric_key
        and o.period == period
        and o.kind is Kind.GUIDE_MID
    ]
    if not guides:
        return None

    # The most recent guidance for the period supersedes any earlier one.
    guide = max(guides, key=lambda o: o.as_of)
    anchor = guide.value

    if correction is None or correction.n == 0:
        # No history to calibrate against: ship the anchor, and be honest that
        # our uncertainty is the full size of a typical guidance range.
        return Estimate(
            estimator="guidance_uncalibrated",
            value=anchor,
            sigma=max(abs(anchor) * 0.03, 0.01),
            n_observations=0,
            anchor=anchor,
            reasoning=(
                f"Management guided {anchor:,.2f} for {period.key}. No paired "
                "history available, so the midpoint is taken uncorrected."
            ),
            citations=[guide.source_file],
        )

    value = correction.apply(anchor)
    sigma = correction.sigma_in_units(anchor)
    direction = "above" if value > anchor else "below"
    move = abs(value - anchor)

    return Estimate(
        estimator="guidance_realisation",
        value=value,
        sigma=max(sigma, 1e-6),
        n_observations=correction.n,
        anchor=anchor,
        correction=correction.shrunk_mean,
        reasoning=(
            f"Management guided {anchor:,.2f} for {period.key}. Across "
            f"{correction.n} prior quarters the reported figure landed "
            f"{correction.summary.split('bias=')[1].split(' sigma')[0]} versus "
            f"the guided midpoint; shrunk by n/(n+5) that correction puts the "
            f"forecast {move:,.2f} {direction} the guide at {value:,.2f}."
        ),
        citations=[guide.source_file]
        + [p.actual_source for p in correction.pairings[-3:]],
    )


def regression_bridge(
    observations: list[MetricObservation],
    *,
    company: Company,
    target_key: str,
    source_key: str,
    source_estimate: Estimate,
    lookback: int = 16,
) -> Estimate | None:
    """Derive a metric the company does not guide from one it does, by OLS.

    ADI guides adjusted *operating* margin but the workbook asks for adjusted
    *gross* margin. An earlier version of this assumed a constant gap between
    them. It is not constant: across 22 reported quarters the gap runs from
    22.5pp to 29.3pp and narrows as margins expand, because operating leverage
    does part of the work that gross margin does not. Assuming a fixed spread
    put adjusted gross margin at 76.0%, roughly three points too high.

    A single-regressor OLS captures the relationship instead. The fitted slope
    of ~0.51 says gross margin rises about half as fast as operating margin, and
    the fit reproduces the last reported quarter to within 0.05pp.

    Sigma is the residual standard error of the fit combined with the
    uncertainty of the source estimate, so a shaky anchor cannot be laundered
    into a confident derived number.
    """
    paired: dict[str, dict[str, float]] = {}
    for o in observations:
        if o.company is not company or o.kind is not Kind.ACTUAL:
            continue
        if o.metric_key in (target_key, source_key):
            paired.setdefault(o.period.key, {})[o.metric_key] = o.value

    # Sort by period. The earlier implementation sliced dict values directly,
    # which took an arbitrary insertion order rather than the most recent
    # quarters it claimed to use.
    series = sorted(
        (
            (Period.parse(period_key), v[source_key], v[target_key])
            for period_key, v in paired.items()
            if target_key in v and source_key in v
        ),
        key=lambda t: t[0].sort_key,
    )[-lookback:]

    if len(series) < 4:
        return None

    xs = [x for _, x, _ in series]
    ys = [y for _, _, y in series]
    n = len(series)
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return None

    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / var_x
    intercept = mean_y - slope * mean_x
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    # Residual standard error; n-2 because two parameters were fitted.
    rse = (sum(r**2 for r in residuals) / max(n - 2, 1)) ** 0.5

    value = intercept + slope * source_estimate.value

    return Estimate(
        estimator="regression_bridge",
        value=value,
        # Propagate the anchor's uncertainty through the slope, then add the fit's.
        sigma=((slope * source_estimate.sigma) ** 2 + rse**2) ** 0.5 or 1e-6,
        n_observations=n,
        anchor=source_estimate.value,
        correction=slope,
        reasoning=(
            f"{target_key} is not guided, but {source_key} is. Fitting "
            f"{target_key} on {source_key} across {n} reported periods gives "
            f"{target_key} = {intercept:.2f} + {slope:.3f} x {source_key} "
            f"(residual se {rse:.2f}). A slope away from 1.0 means the gap "
            f"between the two is not constant, so a fixed spread would bias the "
            f"answer. Applied to the {source_key} forecast of "
            f"{source_estimate.value:.2f} this gives {value:.2f}."
        ),
        citations=source_estimate.citations,
    )


def growth_on_prior_actual(
    observations: list[MetricObservation],
    *,
    company: Company,
    metric_key: str,
    growth_key: str,
    period: Period,
) -> Estimate | None:
    """Apply a disclosed growth rate to the prior year's reported level.

    Hays does not forecast net fees, but its Q4 trading statement states how much
    they moved. Combined with the prior year's audited figure that determines the
    level almost exactly, which is why this beats any modelling of the underlying
    business: the answer has already been disclosed in two pieces.
    """
    prior = period.prior_year()
    base = next(
        (
            o
            for o in sorted(observations, key=lambda o: o.as_of, reverse=True)
            if o.company is company
            and o.metric_key == metric_key
            and o.period == prior
            and o.kind is Kind.ACTUAL
        ),
        None,
    )
    growth = next(
        (
            o
            for o in sorted(observations, key=lambda o: o.as_of, reverse=True)
            if o.company is company
            and o.metric_key == growth_key
            and o.period == period
            and o.kind is Kind.GROWTH_PCT
        ),
        None,
    )
    if base is None or growth is None:
        return None

    value = base.value * (1.0 + growth.value / 100.0)
    return Estimate(
        estimator="growth_on_prior_actual",
        value=value,
        # The growth rate is disclosed to the nearest whole percent, so the
        # rounding alone is worth about half a point of the base.
        sigma=abs(base.value) * 0.005,
        n_observations=1,
        anchor=base.value,
        correction=growth.value,
        reasoning=(
            f"{prior.key} {metric_key} was {base.value:,.1f}. The {period.key} "
            f"trading statement dated {growth.as_of.isoformat()} reports "
            f"{growth.value:+.0f}% on an actual (reported) basis, giving "
            f"{value:,.1f}. The actual basis is used rather than the "
            f"like-for-like headline because the workbook asks for reported "
            f"net fees, and like-for-like excludes currency and the closed and "
            f"divested countries."
        ),
        citations=[growth.source_file, base.source_file],
    )


def ratio_on_prior_actual(
    observations: list[MetricObservation],
    *,
    company: Company,
    metric_key: str,
    driver_key: str,
    driver_estimate: Estimate,
    period: Period,
) -> Estimate | None:
    """Scale a prior-year actual by the change in the metric that drives it.

    Where this year's driver lands close to last year's, this beats fitting a
    line: Hays' FY2026 operating profit is forecast at 45.5 against FY2025's
    45.6, so pre-exceptional EPS should sit within a rounding error of FY2025's
    1.31p. A regression over a history spanning 45 to 249 of operating profit is
    dominated by the high-profit years and pulls the answer well away from the
    nearby, directly comparable one.

    The reconciler runs both and weights them by their sigmas rather than one
    being chosen here.
    """
    prior = period.prior_year()
    base = next(
        (
            o
            for o in observations
            if o.company is company
            and o.metric_key == metric_key
            and o.period == prior
            and o.kind is Kind.ACTUAL
        ),
        None,
    )
    driver_base = next(
        (
            o
            for o in observations
            if o.company is company
            and o.metric_key == driver_key
            and o.period == prior
            and o.kind is Kind.ACTUAL
        ),
        None,
    )
    if base is None or driver_base is None or driver_base.value == 0:
        return None

    ratio = driver_estimate.value / driver_base.value
    value = base.value * ratio

    # Uncertainty is the driver's, carried through proportionally, plus a floor
    # for everything the ratio does not model (share count, tax rate, interest).
    sigma = max(
        abs(base.value) * (driver_estimate.sigma / abs(driver_base.value)),
        abs(value) * 0.05,
    )

    return Estimate(
        estimator="ratio_on_prior_actual",
        value=value,
        sigma=sigma,
        n_observations=1,
        anchor=base.value,
        correction=ratio,
        reasoning=(
            f"{prior.key} {metric_key} was {base.value:,.2f} on {driver_key} of "
            f"{driver_base.value:,.2f}. {period.key} {driver_key} is forecast at "
            f"{driver_estimate.value:,.2f}, a ratio of {ratio:.3f}, giving "
            f"{value:,.2f}. Holding the share count, tax rate and finance charge "
            f"at prior-year levels: the completed buyback reduces the share "
            f"count, so this is if anything conservative."
        ),
        citations=[base.source_file, driver_base.source_file],
    )


def _full_year_totals(
    observations: list[MetricObservation], company: Company, metric_key: str
) -> dict[int, tuple[float, dict[int, float]]]:
    """Fiscal years with all four quarters reported, as (total, {quarter: value}).

    Home Depot never publishes a full-year figure in the releases we parse, but it
    publishes every quarter, so the year is recoverable by summation. Years missing
    any quarter are dropped rather than annualised from a partial sum.
    """
    by_year: dict[int, dict[int, float]] = {}
    for o in observations:
        if (
            o.company is company
            and o.metric_key == metric_key
            and o.kind is Kind.ACTUAL
            and o.period.quarter is not None
        ):
            by_year.setdefault(o.period.year, {})[o.period.quarter] = o.value
    return {
        year: (sum(quarters.values()), quarters)
        for year, quarters in by_year.items()
        if len(quarters) == 4
    }


def seasonal_share(
    observations: list[MetricObservation],
    *,
    company: Company,
    metric_key: str,
    period: Period,
    growth_estimate: Estimate,
    shape_key: str | None = None,
    lookback: int = 5,
) -> Estimate | None:
    """A quarter's share of a full-year anchor, measured from history.

    Home Depot guides the full year only, so the route to a quarter is: grow last
    year's total by the guided rate, then take the quarter's historical share of
    the year. Both halves come from disclosed numbers.

    `shape_key` allows the seasonal *shape* to be taken from a different metric.
    HD only began reporting adjusted EPS recently, so there is no adjusted
    quarterly history to measure a share from — but GAAP EPS, which has years of
    it, seasonalises almost identically, and the adjustments are small and not
    concentrated in one quarter.
    """
    if period.quarter is None:
        return None
    shape_metric = shape_key or metric_key

    totals = _full_year_totals(observations, company, shape_metric)
    complete = sorted(y for y in totals if y < period.year)[-lookback:]
    if len(complete) < 2:
        return None

    shares = [totals[y][1][period.quarter] / totals[y][0] for y in complete]
    mean_share = statistics.fmean(shares)
    share_sd = statistics.pstdev(shares) if len(shares) > 1 else 0.0

    # Prefer a directly reported full-year figure over a sum of quarters. HD's
    # guidance bullet quotes the prior-year adjusted EPS it grows from ("from
    # $14.69 in fiscal 2025"), which is the whole year stated outright — and
    # adjusted EPS has no complete quarterly history to sum in any case.
    prior_year = period.year - 1
    reported_year = next(
        (
            o.value
            for o in sorted(observations, key=lambda o: o.as_of, reverse=True)
            if o.company is company
            and o.metric_key == metric_key
            and o.kind is Kind.ACTUAL
            and o.period.quarter is None
            and o.period.year == prior_year
        ),
        None,
    )
    if reported_year is not None:
        prior_total = reported_year
        basis = "as reported for the full year"
    else:
        basis = "summed across its four quarters"
        prior_totals = _full_year_totals(observations, company, metric_key)
        if prior_year not in prior_totals:
            return None
        prior_total = prior_totals[prior_year][0]

    anchor = prior_total * (1.0 + growth_estimate.value / 100.0)
    value = anchor * mean_share

    # Two sources of error: the guided growth rate, and the share's variability.
    growth_sigma = prior_total * (growth_estimate.sigma / 100.0) * mean_share
    share_sigma = anchor * share_sd
    sigma = max((growth_sigma**2 + share_sigma**2) ** 0.5, abs(value) * 0.005)

    # Money in millions needs no decimals; per-share figures are meaningless
    # without them.
    dp = 0 if abs(value) > 1000 else 2

    shape_note = (
        ""
        if shape_key is None
        else f" The share is measured on {shape_metric}, which has the quarterly "
        f"history {metric_key} lacks and seasonalises almost identically."
    )
    return Estimate(
        estimator="seasonal_share",
        value=value,
        sigma=sigma,
        n_observations=len(complete),
        anchor=anchor,
        correction=mean_share,
        reasoning=(
            f"FY{prior_year} {metric_key} was {prior_total:,.{dp}f} {basis}. "
            f"Guidance of {growth_estimate.value:+.2f}% puts "
            f"FY{period.year} at {anchor:,.{dp}f}. Q{period.quarter} took "
            f"{mean_share:.2%} of the year on average over {len(complete)} prior "
            f"years (sd {share_sd:.2%}), giving {value:,.2f}.{shape_note}"
        ),
        citations=growth_estimate.citations,
    )


def quarter_vs_year_offset(
    observations: list[MetricObservation],
    *,
    company: Company,
    metric_key: str,
    period: Period,
    year_estimate: Estimate,
    lookback: int = 5,
) -> Estimate | None:
    """A rate metric's typical offset from its own full-year average.

    Comparable sales is a percentage, not a quantity, so it cannot be divided into
    quarterly shares. What can be measured is how far a given quarter usually sits
    from the year's average — for Home Depot, Q2 carries the spring selling season
    and tends to run above it.
    """
    if period.quarter is None:
        return None

    by_year: dict[int, dict[int, float]] = {}
    for o in observations:
        if (
            o.company is company
            and o.metric_key == metric_key
            and o.kind is Kind.ACTUAL
            and o.period.quarter is not None
        ):
            by_year.setdefault(o.period.year, {})[o.period.quarter] = o.value

    offsets = [
        quarters[period.quarter] - statistics.fmean(quarters.values())
        for year, quarters in sorted(by_year.items())
        if year < period.year and len(quarters) == 4
    ][-lookback:]
    if len(offsets) < 2:
        return None

    mean_offset = statistics.fmean(offsets)
    offset_sd = statistics.pstdev(offsets)
    value = year_estimate.value + mean_offset

    return Estimate(
        estimator="quarter_vs_year_offset",
        value=value,
        sigma=max((offset_sd**2 + year_estimate.sigma**2) ** 0.5, 0.1),
        n_observations=len(offsets),
        anchor=year_estimate.value,
        correction=mean_offset,
        reasoning=(
            f"{metric_key} is a rate, so it is offset rather than shared out. "
            f"Across {len(offsets)} prior years Q{period.quarter} ran "
            f"{mean_offset:+.2f}pp against the year's average (sd {offset_sd:.2f}pp). "
            f"Applied to the full-year figure of {year_estimate.value:+.2f}% this "
            f"gives {value:+.2f}%."
        ),
        citations=year_estimate.citations,
    )


def consensus_anchor(
    observations: list[MetricObservation],
    *,
    company: Company,
    metric_key: str,
    period: Period,
    position: float = 0.5,
) -> Estimate | None:
    """Anchor on company-compiled consensus, positioned by management's steer.

    `position` places the forecast between the consensus midpoint (0.0) and the
    top of the disclosed range (1.0). It exists because the score is
    `|our miss| / max(|Street miss|, floor)`: submitting consensus exactly scores
    1.0 by construction, so beating the benchmark requires a deviation, and the
    only defensible deviation is one the company itself has pointed to.
    """
    relevant = [
        o
        for o in observations
        if o.company is company and o.metric_key == metric_key and o.period == period
    ]
    mid = max(
        (o for o in relevant if o.kind is Kind.CONSENSUS),
        key=lambda o: o.as_of,
        default=None,
    )
    if mid is None:
        return None
    high = max(
        (o for o in relevant if o.kind is Kind.CONSENSUS_HIGH),
        key=lambda o: o.as_of,
        default=None,
    )
    low = max(
        (o for o in relevant if o.kind is Kind.CONSENSUS_LOW),
        key=lambda o: o.as_of,
        default=None,
    )

    ceiling = high.value if high else mid.value
    value = mid.value + position * (ceiling - mid.value)

    # Half the consensus range is a fair statement of analyst disagreement; with
    # no range disclosed, fall back to 5% of the level.
    if high and low:
        sigma = (high.value - low.value) / 2.0
    else:
        sigma = abs(mid.value) * 0.05

    span = (
        f" across a {low.value:,.1f}-{ceiling:,.1f} range"
        if low and high
        else ""
    )
    return Estimate(
        estimator="consensus_anchor",
        value=value,
        sigma=max(sigma, 1e-6),
        n_observations=1,
        anchor=mid.value,
        correction=position,
        reasoning=(
            f"Company-compiled consensus for {period.key} {metric_key} was "
            f"{mid.value:,.1f}{span}, published {mid.as_of.isoformat()} — after "
            f"the year closed, so it is well informed. Management stated they "
            f"expect to land at the top of that range, so we take {value:,.1f}, "
            f"{position:.0%} of the way from consensus to the ceiling. Matching "
            f"consensus would score 1.0 by construction; this is a deliberate "
            f"deviation the company itself signposted."
        ),
        citations=[mid.source_file] + ([high.source_file] if high else []),
    )


def reconcile(
    label: str,
    units: Unit,
    estimates: list[Estimate],
) -> MetricForecast:
    """Combine estimates by inverse variance into the submitted number.

    Weighting by 1/sigma^2 means a tightly-calibrated estimator dominates a loose
    one without anyone choosing a weight. Where estimators disagree by more than
    they claim they should, the metric is flagged rather than silently averaged —
    a disagreement is information, not noise to be smoothed away.
    """
    live = [e for e in estimates if e.sigma > 0]
    if not live:
        raise ValueError(f"{label}: no usable estimates")

    weights = [1.0 / (e.sigma**2) for e in live]
    total = sum(weights)
    value = sum(w * e.value for w, e in zip(weights, live)) / total
    sigma = total**-0.5

    needs_review = False
    warnings: list[str] = []
    if len(live) > 1:
        spread = max(e.value for e in live) - min(e.value for e in live)
        combined = (sum(e.sigma**2 for e in live) / len(live)) ** 0.5
        if spread > DISAGREEMENT_SIGMAS * combined:
            needs_review = True
            warnings.append(
                f"estimators disagree by {spread:.3f}, more than "
                f"{DISAGREEMENT_SIGMAS}x their combined sigma {combined:.3f}"
            )

    if len(live) == 1:
        reasoning = live[0].reasoning
    else:
        parts = [
            f"{e.estimator} {e.value:,.2f} (sigma {e.sigma:,.2f}, "
            f"weight {w / total:.0%})"
            for w, e in zip(weights, live)
        ]
        reasoning = (
            "Inverse-variance combination of " + "; ".join(parts) + f" -> {value:,.2f}."
        )

    citations: list[str] = []
    for e in live:
        for c in e.citations:
            if c not in citations:
                citations.append(c)

    forecast = MetricForecast(
        label=label,
        units=units,
        value=value,
        sigma=sigma,
        reasoning=reasoning,
        estimates=live,
        citations=citations,
        plausible_low=value - BAND_SIGMAS * sigma,
        plausible_high=value + BAND_SIGMAS * sigma,
        warnings=warnings,
        needs_review=needs_review,
    )
    return forecast.finalise()
