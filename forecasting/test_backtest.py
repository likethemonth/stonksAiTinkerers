import tempfile
import unittest
from datetime import date
from pathlib import Path

from forecasting.backtest import (
    STREET_SOURCE_TYPES,
    Observation,
    blend_current,
    load_observations,
    score_sources,
)


class BacktestTests(unittest.TestCase):
    def observation(
        self,
        forecast,
        actual,
        period="Q1",
        *,
        forecast_date=date(2025, 1, 1),
        event_date=date(2025, 2, 1),
        source_type="consensus",
    ):
        return Observation(
            source_id="source",
            source_name="Source",
            source_type=source_type,
            company="Company",
            metric="Revenue",
            period=period,
            forecast_date=forecast_date,
            event_date=event_date,
            forecast=forecast,
            actual=actual,
            units="USDm",
            source_url="https://example.com",
            quality=1.0,
        )

    def test_rejects_lookahead_rows(self):
        header = "source_id,source_name,source_type,company,metric,period,forecast_date,event_date,forecast,actual,units,source_url,quality\n"
        row = "s,S,analyst,C,M,Q1,2025-02-02,2025-02-01,10,11,USDm,https://example.com,1\n"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rows.csv"
            path.write_text(header + row)
            with self.assertRaisesRegex(ValueError, "look-ahead"):
                load_observations(path)

    def test_sparse_history_is_shrunk_toward_prior(self):
        score = score_sources([self.observation(100, 100)], date(2026, 1, 1))[0]
        self.assertGreater(score.shrunk_error, score.weighted_error)
        self.assertLess(score.shrunk_error, 0.08)

    def test_consistent_optimism_is_bias_corrected(self):
        historical = [self.observation(110, 100, "Q1"), self.observation(220, 200, "Q2")]
        score = score_sources(historical, date(2026, 1, 1))
        current = [self.observation(330, None, "Q3")]
        result = blend_current(current, score)[0]
        self.assertAlmostEqual(result["forecast"], 300.0, places=6)

    def test_unresolved_actual_is_not_visible_to_historical_score(self):
        future = self.observation(
            100,
            101,
            event_date=date(2026, 2, 1),
        )
        self.assertEqual(score_sources([future], date(2026, 1, 1)), [])

    def test_street_blend_excludes_internal_models(self):
        current = [
            self.observation(100, None, source_type="consensus"),
            self.observation(200, None, source_type="model"),
        ]
        result = blend_current(
            current,
            [],
            as_of=date(2025, 1, 1),
            source_types=STREET_SOURCE_TYPES,
        )
        self.assertEqual(result[0]["forecast"], 100)
        self.assertEqual(result[0]["components"][0]["source_type"], "consensus")

    def test_current_forecast_after_cutoff_is_hidden(self):
        current = [
            self.observation(100, None, forecast_date=date(2025, 1, 1)),
            self.observation(200, None, forecast_date=date(2025, 1, 2)),
        ]
        result = blend_current(current, [], as_of=date(2025, 1, 1))
        self.assertEqual(result[0]["forecast"], 100)


if __name__ == "__main__":
    unittest.main()
