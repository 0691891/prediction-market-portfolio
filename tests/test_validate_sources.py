import datetime as dt
import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from validate_sources import audit

class SourceHealthTests(unittest.TestCase):
    def test_cached_fetch_is_not_fresh_market_quote(self):
        now=dt.datetime(2026,9,20,2,0,tzinfo=dt.timezone.utc)
        result=audit({"fixtures":[{"model_fair_status":"MODELLED",
             "schedule_quality":"COMMUNITY_SOURCE_NEEDS_CROSSCHECK"}],"errors":{"schedule":{"EPL":"HTTP 403"}}},
            {"model":"test","items":[{"status":"MODELLED","fair_probability":.64}]},
            {"markets":[{"status":"active","yes_ask_usd":.6,
                "market_updated_utc":"2026-09-19T00:00:00Z",
                "fetched_utc":"2026-09-20T02:00:00Z"}]},
            {"mappings":[]},{"status":"NO_ODDS_API_KEY"},
            {"status":"NO_FOOTBALL_DATA_KEY"},now=now)
        self.assertEqual(result["kalshi"]["recent_open_yes_asks"],0)
        self.assertEqual(result["kalshi"]["stale_yes_asks"],1)
        self.assertEqual(result["fixture"]["cross_verified_kickoffs"],0)
        self.assertFalse(result["activation"]["automatic_a_grade_paper"])
    def test_missing_ask_cannot_count(self):
        now=dt.datetime(2026,9,20,tzinfo=dt.timezone.utc)
        r=audit({}, {},{"markets":[{"status":"active","yes_ask_usd":None,
                            "market_updated_utc":"2026-09-20T00:00:00Z"}]},
                {},{},{},now=now)
        self.assertEqual(r["kalshi"]["invalid_yes_asks"],1)
        self.assertEqual(r["fixture"]["observed"],0)
if __name__=="__main__":unittest.main()
