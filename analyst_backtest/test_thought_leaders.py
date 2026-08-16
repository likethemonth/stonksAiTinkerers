import unittest

from analyst_backtest.scoring import BacktestError
from analyst_backtest.thought_leaders import DIMENSIONS, normalize_thesis_claim, score_thought_leaders


def claim(index, outcome="supported", stage="initial"):
    return {
        "claim_id": f"c{index}", "leader_id": "a", "leader_display": "A",
        "company": "Company", "ticker": "CO", "source_url": "https://example.com",
        "published_at": f"202{index}-01-01", "claim_stage": stage, "claim_type": "thesis",
        "claim_text": "testable", "outcome_status": outcome,
        **({"outcome_source_url": "https://example.com/outcome"} if outcome not in {"open", "not_testable"} else {}),
    }


def card(level=3):
    return {
        "leader_id": "a", "leader_display": "A", "company": "Company", "ticker": "CO",
        "searched_from": "2020-01-01", "searched_to": "2026-01-01",
        "dimension_levels": {name: level for name in DIMENSIONS},
    }


class ThoughtLeaderTests(unittest.TestCase):
    def test_popularity_is_not_an_input_and_small_history_is_case_study(self):
        row = score_thought_leaders([{**claim(1), "followers": 99_000_000}], [card()])[0]
        self.assertEqual(row["eligibility"], "case-study")
        self.assertIsNone(row["rank"])
        self.assertNotIn("followers", row)

    def test_rankable_requires_five_families_three_matured(self):
        claims = [claim(1), claim(2), claim(3), claim(4, "open"), claim(5, "open")]
        row = score_thought_leaders(claims, [card()])[0]
        self.assertEqual(row["eligibility"], "rankable")
        self.assertEqual(row["rank"], 1)

    def test_revision_does_not_inflate_family_count(self):
        rows = [claim(1), claim(2), claim(3), claim(4, "open"), claim(5, "open"), claim(6, stage="revision")]
        row = score_thought_leaders(rows, [card()])[0]
        self.assertEqual(row["families"], 5)
        self.assertEqual(row["records"], 6)

    def test_bad_dimension_level_fails_closed(self):
        scorecard = card()
        scorecard["dimension_levels"]["causal_depth"] = 5
        with self.assertRaises(BacktestError):
            score_thought_leaders([claim(1)], [scorecard])

    def test_extractor_aliases_are_normalized(self):
        row = normalize_thesis_claim({
            "person_id": "p", "display_name": "P", "thesis_stage": "initial",
            "outcome_status": "resolved_missed", "outcome": "missed",
        })
        self.assertEqual(row["leader_id"], "p")
        self.assertEqual(row["leader_display"], "P")
        self.assertEqual(row["outcome_status"], "contradicted")
        self.assertEqual(row["claim_stage"], "initial")


if __name__ == "__main__":
    unittest.main()
