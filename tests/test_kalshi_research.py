"""Offline invariants for the public Kalshi research adapter; no API calls."""
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"dashboard"))
import kalshi_research as research
import kalshi_feed as feed

class KalshiResearchTests(unittest.TestCase):
    def test_football_discovery_word_boundaries(self):
        self.assertTrue(feed._football_title({"title":"English Premier League match winner","ticker":"KXTEST"}))
        self.assertFalse(feed._football_title({"title":"NFL football match winner","ticker":"KXTEST"}))

    def test_buy_cost_is_ask_not_last_or_bid(self):
        m=feed.market_row({"ticker":"TEST","yes_bid_dollars":"0.40",
                           "yes_ask_dollars":"0.44",
                           "last_price_dollars":"0.30","status":"open"},"2026-01-01T00:00:00Z","test")
        self.assertAlmostEqual(research.quote_for(m,"yes"),0.44)
        self.assertIsNone(research.quote_for(m,"no"))

    def test_only_confirmed_binary_settlement_counts(self):
        self.assertIsNone(research.settlement({"status":"open","result":"yes"}))
        self.assertEqual(research.settlement({"status":"settled","result":"yes"}),"yes")
        self.assertEqual(research.settlement({"status":"settled","settlement_value_dollars":"0.0000"}),"no")
        self.assertIsNone(research.settlement({"status":"settled","settlement_value_dollars":"0.5000"}))

    def test_zero_or_missing_price_is_not_tradable(self):
        self.assertIsNone(research.valid_probability(None))
        self.assertIsNone(research.valid_probability(0))
        self.assertIsNone(research.valid_probability(1))
        self.assertAlmostEqual(research.valid_probability("0.6100"),0.61)

if __name__=="__main__":unittest.main()
