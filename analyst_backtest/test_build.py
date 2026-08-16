import unittest

from analyst_backtest.build import normalize_candidates


class BuildTests(unittest.TestCase):
    def test_guidance_issuance_is_separate_metric_class(self):
        records = [
            {
                "claim_id": "g",
                "author_id": "team",
                "author_display": "Team",
                "source_url": "https://example.com",
                "published_at": "2025-01-01",
                "company": "Company",
                "ticker": "C",
                "target_period": "Q2 guidance issued with Q1 results",
                "target_report_date": "2025-02-01",
                "claim_type": "numeric_point",
                "metric": "revenue guidance midpoint",
                "units": "USDm",
                "forecast_value": 100,
                "actual_value": 101,
                "actual_source_url": "https://issuer.example",
                "resolution_status": "resolved",
                "provenance_tier": "secondary",
            }
        ]
        claims, events = normalize_candidates(records)
        self.assertEqual(claims[0]["metric_class"], "guidance_issuance")
        self.assertEqual(len(events), 1)
        self.assertIn("revenue guidance midpoint", events[0]["actuals"])

    def test_non_numeric_actual_is_not_invented(self):
        records = [
            {
                "claim_id": "text",
                "author_id": "team",
                "author_display": "Team",
                "source_url": "https://example.com",
                "published_at": "2025-01-01",
                "company": "Company",
                "ticker": "C",
                "target_period": "Q1",
                "target_report_date": "2025-02-01",
                "claim_type": "directional",
                "metric": "revenue and EPS",
                "direction": "above_consensus",
                "actual_value": "Revenue 100; EPS 2",
                "resolution_status": "resolved",
                "provenance_tier": "secondary",
            }
        ]
        _, events = normalize_candidates(records)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
