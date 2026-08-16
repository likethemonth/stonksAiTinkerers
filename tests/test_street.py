from __future__ import annotations

from datetime import date

from forecast.metrics import submitted_specs
from forecast.schema import Company, ContributionStatus, Engine
from forecast.street import street_contribution


def test_street_adapter_covers_all_twelve_targets_at_submission_cutoff() -> None:
    contributions = [
        street_contribution(company, metric, as_of=date(2026, 8, 16))
        for company in Company
        for metric in submitted_specs(company)
    ]
    assert len(contributions) == 12
    assert all(c.engine is Engine.STREET for c in contributions)
    assert all(c.status is ContributionStatus.AVAILABLE for c in contributions)
    assert all(c.estimate and c.estimate.sigma > 0 for c in contributions)


def test_street_adapter_respects_cutoff_before_research_artifact() -> None:
    metric = submitted_specs(Company.DE)[0]
    contribution = street_contribution(Company.DE, metric, as_of=date(2026, 8, 1))
    assert contribution.status is ContributionStatus.ABSTAINED


def test_hays_company_consensus_is_identified_as_its_own_family() -> None:
    metric = submitted_specs(Company.HAS)[0]
    contribution = street_contribution(Company.HAS, metric, as_of=date(2026, 8, 16))
    assert "company_consensus" in contribution.source_families
