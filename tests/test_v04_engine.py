import datetime as dt
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from v04_engine import slug, translate, lambdas, poisson_grid, scores_from_grid, ALIAS

class V04Tests(unittest.TestCase):
    def test_grid_coherent(self):
        r=scores_from_grid(poisson_grid(1.7,1.1))
        self.assertAlmostEqual(r["HOME_WIN"]+r["DRAW"]+r["AWAY_WIN"],1,places=5)
        self.assertAlmostEqual(r["OVER_2_5"]+r["UNDER_2_5"],1,places=5)
        self.assertAlmostEqual(r["BTTS_YES"]+r["BTTS_NO"],1,places=5)
    def test_alias_exact_or_reject(self):
        names={"Man City","Man United","Chelsea"}
        self.assertEqual(translate("Manchester City",names),"Man City")
        self.assertIsNone(translate("Unknown FC",names))
    def test_history_does_not_see_current_day(self):
        date=dt.datetime(2026,9,19,tzinfo=dt.timezone.utc)
        rows=[]
        for i in range(36):
            rows.append({"date":date-dt.timedelta(days=2+i),"home":"Home","away":"Away","hg":2,"ag":1})
        rows.append({"date":date,"home":"Home","away":"Away","hg":30,"ag":0})
        rows2=rows[:-1]
        params={"recent_half_life_days":90,"shrinkage_matches":4,"home_advantage_log":.08}
        self.assertEqual(lambdas(rows,"Home","Away",date,params),
                         lambdas(rows2,"Home","Away",date,params))
    def test_insufficient_history_returns_none(self):
        date=dt.datetime(2026,9,19,tzinfo=dt.timezone.utc)
        rows=[{"date":date-dt.timedelta(days=1),"home":"Home","away":"Away","hg":1,"ag":0}]
        self.assertIsNone(lambdas(rows,"Home","Away",date,{}))
if __name__=="__main__":unittest.main()
