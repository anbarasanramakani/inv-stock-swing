import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app
from news_provider import (
    extract_ticker_from_headline,
    get_news_preview,
    get_today_news_recommendations,
    run_news_backtest,
)


class NewsProviderTests(unittest.TestCase):
    def test_south_indian_bank_headline_maps_to_symbol(self):
        all_symbols = ["SOUTHBANK.NS", "HDFCBANK.NS", "SBIN.NS"]
        headline = "South Indian Bank shares crash after RBI action and weak deposit growth"

        ticker = extract_ticker_from_headline(headline, all_symbols)

        self.assertEqual(ticker, "SOUTHBANK.NS")

    def test_market_wide_headline_is_returned_without_ticker(self):
        picks = get_today_news_recommendations({}, all_symbols=["RELIANCE.NS"], existing_picks=[])

        self.assertIsInstance(picks, list)
        self.assertTrue(all(isinstance(item, dict) for item in picks))

    def test_news_preview_returns_fast_fallback_items(self):
        preview = get_news_preview(all_symbols=["SOUTHBANK.NS"], existing_picks=[])

        self.assertTrue(preview)
        self.assertIn("Headline", preview[0])
        self.assertIn("Catalyst", preview[0])

    def test_ensure_ticker_column_fills_from_symbol(self):
        df = pd.DataFrame([{"Symbol": "RELIANCE.NS", "Headline": "Reliance update"}])
        normalized = app._ensure_ticker_column(df)

        self.assertEqual(normalized.loc[0, "Ticker"], "RELIANCE.NS")

    def test_news_backtest_supports_30_day_history_window(self):
        dates = pd.date_range("2026-06-15", periods=45, freq="D")
        df = pd.DataFrame(
            {
                "Open": 100.0 + np.arange(45),
                "High": 102.0 + np.arange(45),
                "Low": 99.0 + np.arange(45),
                "Close": 101.0 + np.arange(45),
                "Volume": 1000000 + np.arange(45) * 100,
            },
            index=dates,
        )

        results = run_news_backtest(
            {"RELIANCE.NS": df},
            historical_events=[{"Date": "2026-06-20", "Symbol": "RELIANCE.NS", "Headline": "Reliance update", "Catalyst": "Order Win"}],
            lookback_days=30,
        )

        self.assertTrue(results)
        self.assertEqual(results[0]["Ticker"], "RELIANCE")
