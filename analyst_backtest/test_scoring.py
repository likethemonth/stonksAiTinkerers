import unittest

from analyst_backtest.scoring import BacktestError, evaluate_claims, run_backtest, source_role


def event(event_id="C-Q1", reported_at="2025-02-01T12:00:00Z", actual=100.0):
    return {
        "event_id": event_id,
        "company": "Company",
        "ticker": "C",
        "target_period": "Q1",
        "reported_at": reported_at,
        "actuals": {"Revenue": {"value": actual, "units": "USDm", "source_url": "https://issuer.example"}},
    }


def claim(claim_id="a", **changes):
    base = {
        "claim_id": claim_id,
        "author_id": "author",
        "author_display": "Author",
        "platform": "web",
        "source_url": f"https://source.example/{claim_id}",
        "published_at": "2025-01-01T00:00:00Z",
        "company": "Company",
        "ticker": "C",
        "event_id": "C-Q1",
        "target_period": "Q1",
        "claim_type": "numeric_point",
        "metric": "Revenue",
        "metric_class": "accounting",
        "units": "USDm",
        "forecast_value": 110.0,
        "resolution_status": "resolved",
        "provenance_tier": "primary",
    }
    base.update(changes)
    return base


class ScoringTests(unittest.TestCase):
    def test_rejects_lookahead_without_crashing_corpus(self):
        rows, exclusions = evaluate_claims(
            [claim(published_at="2025-02-01T12:00:00Z")], [event()], as_of="2025-03-01T00:00:00Z"
        )
        self.assertEqual(rows, [])
        self.assertEqual(exclusions[0]["reason"], "lookahead_or_same_time")

    def test_latest_revision_is_only_scored_once(self):
        rows, exclusions = evaluate_claims(
            [claim("first", forecast_value=90), claim("last", published_at="2025-01-15T00:00:00Z", forecast_value=101)],
            [event()], as_of="2025-03-01T00:00:00Z", revision_policy="latest",
        )
        self.assertEqual([row["claim_id"] for row in rows], ["last"])
        self.assertEqual(exclusions[0]["reason"], "superseded_latest")

    def test_range_scores_zero_distance_when_actual_inside(self):
        row = claim("range", claim_type="numeric_range", forecast_value=None, forecast_low=95, forecast_high=105)
        result = run_backtest([row], [event()], as_of="2025-03-01T00:00:00Z")
        self.assertEqual(result["evaluations"][0]["scaled_error"], 0)
        self.assertTrue(result["evaluations"][0]["range_hit"])

    def test_directional_claim_needs_reference_and_scores_hit(self):
        row = claim("direction", claim_type="directional", forecast_value=None, direction="above", consensus_at_claim=95)
        result = run_backtest([row], [event()], as_of="2025-03-01T00:00:00Z")
        self.assertTrue(result["evaluations"][0]["hit"])

    def test_consensus_skill_is_positive_when_author_is_better(self):
        row = claim(forecast_value=101, consensus_at_claim=90)
        result = run_backtest([row], [event()], as_of="2025-03-01T00:00:00Z")
        self.assertAlmostEqual(result["evaluations"][0]["consensus_skill"], 0.09)

    def test_small_samples_are_provisional(self):
        result = run_backtest([claim()], [event()], as_of="2025-03-01T00:00:00Z", minimum_n=3)
        self.assertEqual(result["rankings"][0]["ranking_status"], "provisional")
        self.assertIsNone(result["rankings"][0]["rank"])

    def test_bad_units_fail_closed(self):
        with self.assertRaisesRegex(BacktestError, "unit mismatch"):
            run_backtest([claim(units="GBP")], [event()], as_of="2025-03-01T00:00:00Z")

    def test_resolved_undated_claim_is_preserved_as_exclusion(self):
        rows, exclusions = evaluate_claims(
            [claim(published_at=None)], [event()], as_of="2025-03-01T00:00:00Z"
        )
        self.assertEqual(rows, [])
        self.assertEqual(exclusions[0]["reason"], "missing_publication_timestamp")

    def test_date_only_same_day_claim_is_conservatively_excluded(self):
        rows, exclusions = evaluate_claims(
            [claim(published_at="2025-02-01")], [event(reported_at="2025-02-01T00:00:00Z")],
            as_of="2025-03-01T00:00:00Z",
        )
        self.assertEqual(rows, [])
        self.assertEqual(exclusions[0]["reason"], "lookahead_or_same_time")

    def test_consensus_role_is_not_mislabeled_as_individual(self):
        self.assertEqual(source_role(claim(author_id="consensus:panel")), "consensus")


if __name__ == "__main__":
    unittest.main()
