from __future__ import annotations

from datetime import date

import pytest

from forecast.numinous import SIGNALS, numinous_constraint, parse_snapshot
from forecast.schema import Company


@pytest.mark.parametrize(
    ("company", "metric_key", "probability", "threshold"),
    [
        (Company.HD, "adj_eps", 0.2931, 4.73),
        (Company.ADI, "adj_eps", 0.1532, 3.33),
        (Company.DE, "diluted_eps_gaap", 0.2912, 4.72),
    ],
)
def test_live_snapshots_load_as_native_constraints(
    company: Company,
    metric_key: str,
    probability: float,
    threshold: float,
) -> None:
    signal = numinous_constraint(company, metric_key, date(2026, 8, 16))
    assert signal is not None
    assert signal.provider == "numinous"
    assert signal.probability == pytest.approx(probability)
    assert signal.threshold == pytest.approx(threshold)
    assert signal.volume is None
    assert signal.source_snapshot.endswith(".json")


def test_cutoff_excludes_future_snapshot() -> None:
    assert numinous_constraint(Company.HD, "adj_eps", date(2026, 8, 15)) is None


def test_parser_rejects_wrong_accounting_basis() -> None:
    definition = SIGNALS[(Company.HD, "adj_eps")]
    payload = {
        "status": "COMPLETED",
        "result": {
            "prediction": 0.75,
            "parsed_fields": {
                "title": (
                    "Will Home Depot report GAAP diluted EPS strictly above $4.73 "
                    "for fiscal Q2 2026?"
                ),
                "cutoff": "2026-08-18T23:59:59Z",
            },
        },
    }
    assert parse_snapshot(definition, payload, "example.json") is None


def test_parser_rejects_noncompleted_job() -> None:
    definition = SIGNALS[(Company.DE, "gaap_eps")]
    assert parse_snapshot(definition, {"status": "RUNNING"}, "example.json") is None
