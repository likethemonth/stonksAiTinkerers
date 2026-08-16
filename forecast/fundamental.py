"""Compose the deterministic company model with post-guidance driver nowcasts."""

from __future__ import annotations

from datetime import date

from forecast import drivers
from forecast.estimators import reconcile
from forecast.metrics import spec, submitted_specs
from forecast.ml import hd_estimates
from forecast.schema import Company, Estimate, MetricForecast


def _driver_estimates(as_of: date | None) -> dict[tuple[Company, str], Estimate]:
    try:
        _, observations = drivers.load_observations(as_of)
    except FileNotFoundError:
        return {}
    deere, _ = drivers.deere_ppa(observations)
    return {
        (Company.ADI, "revenue"): drivers.adi_revenue(observations),
        (Company.HD, "comp_sales_pct"): drivers.hd_comps(observations),
        (Company.DE, "ppa_operating_profit"): deere,
    }


def enrich_with_drivers(
    company: Company,
    metrics: list[MetricForecast],
    *,
    as_of: date | None = None,
) -> list[MetricForecast]:
    """Reconcile compatible driver nowcasts inside the fundamental engine."""
    driver_by_target = _driver_estimates(as_of)
    ml_by_target = hd_estimates(as_of or date.today())
    by_label = {metric.label: metric for metric in metrics}
    result: list[MetricForecast] = []
    for metric_spec in submitted_specs(company):
        current = by_label[metric_spec.label or ""]
        driver = driver_by_target.get((company, metric_spec.key))
        ml_estimate = ml_by_target.get((company, metric_spec.key))
        extras: list[Estimate] = []
        if driver is not None and not any(
            estimate.estimator == "driver_nowcast" for estimate in current.estimates
        ):
            extras.append(driver)
        if ml_estimate is not None:
            extras.append(ml_estimate)
        if not extras:
            result.append(current)
            continue
        core = Estimate(
            estimator="fundamental_core",
            value=current.value,
            sigma=current.sigma or max(abs(current.value) * 0.08, 0.05),
            n_observations=sum(estimate.n_observations for estimate in current.estimates),
            reasoning=current.reasoning,
            citations=current.citations,
        )
        combined = reconcile(metric_spec.label or "", metric_spec.units, [core, *extras])
        combined.needs_review = combined.needs_review or current.needs_review
        for warning in current.warnings:
            if warning not in combined.warnings:
                combined.warnings.append(warning)
        result.append(combined)
    return result


def source_families(company: Company, metric: MetricForecast) -> list[str]:
    """Summarize evidence families so the top-level reconciler can spot overlap."""
    families = {"company_filings"}
    names = {estimate.estimator for estimate in metric.estimates}
    if any("guidance" in name or name == "fundamental_core" for name in names):
        families.add("management_guidance")
    if any("consensus" in name for name in names):
        families.add("company_consensus")
    if "driver_nowcast" in names:
        families.add("external_drivers")
    if any(name.startswith("ml_") for name in names):
        families.add("historical_actuals_ml")
    # Touch the registry here so a mislabeled metric fails at the composition
    # boundary instead of silently producing an incomplete source declaration.
    matching = [item for item in submitted_specs(company) if item.label == metric.label]
    if not matching:
        raise KeyError(f"{company.value}: unknown submitted label {metric.label!r}")
    spec(company, matching[0].key)
    return sorted(families)
