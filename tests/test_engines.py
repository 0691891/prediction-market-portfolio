import json, pathlib, tempfile, unittest, datetime, importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[1]
def mod(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
backtest=mod('backtest',pathlib.Path('src/backtest.py'))
pitmod=mod('point_in_time',pathlib.Path('src/point_in_time.py'))
clvmod=mod('clv_engine',pathlib.Path('src/clv_engine.py'))
alphamod=mod('alpha_attribution',pathlib.Path('src/alpha_attribution.py'))
class EngineSmokeTests(unittest.TestCase):
    def write(self,d,name,obj):
        p=d/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj)); return p
    def test_v033_probability_and_metrics(self):
        p=backtest.p1x2(1.8,1.0)
        self.assertAlmostEqual(sum(p),1.0,places=6)
        self.assertGreater(p[0],p[2])
        rows=[{'p':[.6,.25,.15],'y':0},{'p':[.2,.3,.5],'y':2}]
        m=backtest.metrics(rows)
        self.assertEqual(m['n'],2); self.assertGreater(m['log_loss'],0); self.assertGreater(m['brier'],0)
        self.assertTrue(backtest.calibration(rows))
    def test_v034_pit_and_clv(self):
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td); (d/'pit').mkdir()
            kickoff=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=6)).isoformat()
            self.write(d,'board.json',{'picks':[{'id':'p1','competition':'EPL','match':'A vs B','market':'A win','fair_probability':.64,'fair_source':'test'}]})
            self.write(d,'sportsbook_consensus.json',{'items':[{'pick_id':'p1','consensus_probability':.58,'book_count':5,'commence_time':kickoff}]})
            self.write(d,'market_snapshot.json',{'markets':[{'pick_id':'p1','market_probability':.60,'liquidity_usd':500}]})
            self.write(d,'model_fair.json',{'items':[{'pick_id':'p1','status':'MODELLED'}]}); self.write(d,'football_intelligence.json',{'items':[{'pick_id':'p1','status':'OK'}]})
            self.write(d,'trades.json',{'trades':[{'trade_id':'t1','pick_id':'p1','position':'A win','entry_probability':.55,'stake_usd':10,'pnl_usd':2}]})
            pitmod.DATA=d; pitmod.PIT=d/'pit'; pitmod.main()
            latest=json.loads((d/'pit/latest.json').read_text()); self.assertEqual(len(latest['items']),1); self.assertEqual(latest['items'][0]['pick_id'],'p1')
            close=json.loads((d/'pit/closing.json').read_text()); self.assertEqual(close['items'][0]['kalshi_probability'],.60)
            clvmod.DATA=d; clvmod.PIT=d/'pit'; clvmod.main()
            clv=json.loads((d/'clv.json').read_text()); self.assertEqual(clv['trade_clv'][0]['status'],'OK'); self.assertAlmostEqual(clv['trade_clv'][0]['clv_probability_points'],.05,places=4)
    def test_v035_attribution(self):
        self.assertEqual(alphamod.mtype('A win × B over 2.5'),'COMBO')
        with tempfile.TemporaryDirectory() as td:
            d=pathlib.Path(td); (d/'pit').mkdir()
            self.write(d,'trades.json',{'trades':[{'trade_id':'t1','pick_id':'p1','position':'A win','stake_usd':10,'pnl_usd':2,'grade':'A','entry_horizon':'T-6H'}]})
            self.write(d,'clv.json',{'trade_clv':[{'trade_id':'t1','pick_id':'p1','clv_probability_points':.04}]})
            self.write(d,'board.json',{'picks':[{'id':'p1','competition':'Premier League','market':'A win','grade':'A','edge_pp':.06}]})
            self.write(d,'pit/latest.json',{'items':[{'pick_id':'p1','bucket':'T-6H'}]})
            alphamod.DATA=d; alphamod.main()
            a=json.loads((d/'alpha_attribution.json').read_text()); self.assertEqual(a['summary']['tracked_clv_rows'],1); self.assertAlmostEqual(a['summary']['realized_roi'],.2); self.assertEqual(a['by_market_type'][0]['group'],'MONEYLINE')
if __name__=='__main__': unittest.main()
