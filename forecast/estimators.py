"""Estimators and the reconciler.

An estimator turns disclosed evidence into (value, sigma, reasoning, citations).
The sigma is not optional: the reconciler combines estimators by inverse variance,
so an estimator that cannot state its own dispersion cannot contribute a weight.

Currently implemented:

    guidance_realisation   anchor on management's guidance midpoint, corrected by
                           the shrunk historical realisation ratio from calibrate.py
    spread_bridge          derive a metric the company does not guide from one it
                           does, using the historically stable gap between them
    provisional baselines  uncalibrated, cited anchors for companies without an
                           extractor yet (see baselines.py)
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
            f"{target_key} on {source_key} across {n} reported quarters gives "
            f"{target_key} = {intercept:.2f} + {slope:.3f} x {source_key} "
            f"(residual se {rse:.2f}pp). The slope below 1.0 shows the gap "
            f"narrows as margins expand, so a fixed spread would overstate. "
            f"Applied to the {source_key} forecast of "
            f"{source_estimate.value:.2f} this gives {value:.2f}."
        ),
        citations=source_estimate.citations,
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
