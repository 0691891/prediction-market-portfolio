#!/usr/bin/env python3
"""v0.4 reproducible 500-match market-anchored proxy experiment.

Only historical result and closing odds are available here. Tests the
market-prior + football-Poisson residual; does NOT claim xG, lineup,
injury, tactical or human-intelligence coefficients have been tested.
"""
import json,math,datetime as dt
import backtest as old
from residual_pricing import devig
DATA=old.DATA
def metric(rows):return old.metric(rows)
def blend(market,football,weight):
    # Multinomial residual: log p_new,i = log p_market,i +
    # weight*(log p_football,i - log p_market,i) - log normalizer.
    v=[math.exp((1-weight)*math.log(max(1e-10,m))+weight*math.log(max(1e-10,f))) for m,f in zip(market,football)]
    return [x/sum(v) for x in v]
def collect(code,train,test,param,limit=None):
    hist=[];rows=[]
    # Historical CSV only records day, so prediction excludes same-day results.
    for m in train if limit is None else test[:limit]:
        if limit is not None and not hist:
            hist=[(x["date"],x["home"],x["away"],x["hg"],x["ag"]) for x in train]
        p=old.predict(hist,m["home"],m["away"],m["date"],*param)
        odds,src=old.closing_odds(m["raw"])
        if p and odds:
            rows.append({"league":old.LEAGUES[code],"date":m["date"].date().isoformat(),
                         "match":m["home"]+" vs "+m["away"],"football":p,"market":devig(odds),
                         "odds":odds,"odds_source":"/".join(src),"y":old.outcome(m["hg"],m["ag"])})
        hist.append((m["date"],m["home"],m["away"],m["hg"],m["ag"]))
    return rows
def scored(rows,w):
    return [{"p":blend(r["market"],r["football"],w),"y":r["y"]} for r in rows]
def trades(rows,w,uncertainty=.03,min_ev=.05,stake=100):
    out=[]
    for r in rows:
        fair=blend(r["market"],r["football"],w)
        # Market-anchored model is a probability estimator, NOT verified alpha.
        ev=[max(0,fair[i]-uncertainty)*r["odds"][i]-1 for i in range(3)]
        j=max(range(3),key=lambda i:ev[i])
        if ev[j]<min_ev:continue
        pnl=stake*(r["odds"][j]-1) if r["y"]==j else -stake
        out.append({"league":r["league"],"date":r["date"],"match":r["match"],
                    "selection":["H","D","A"][j],"market_probability":round(r["market"][j],6),
                    "model_probability":round(fair[j],6),"closing_odds":r["odds"][j],
                    "estimated_conservative_ev":round(ev[j],6),"pnl_usd":round(pnl,2),
                    "result":"WIN" if r["y"]==j else "LOSS"})
    return out
def summary(ts):
    n=len(ts);pnl=sum(t["pnl_usd"] for t in ts)
    return {"trades":n,"wins":sum(t["result"]=="WIN" for t in ts),
            "pnl_usd":round(pnl,2),"stake_usd":100*n,
            "roi":round(pnl/(100*n),6) if n else None}
def main():
    sources={};errors=[];datasets={}
    for code,name in old.LEAGUES.items():
        try:
            a,u=old.fetch_csv("2425",code);b,v=old.fetch_csv("2526",code)
            datasets[code]=(a,b);sources[code]={"train":u,"holdout":v}
        except Exception as e:errors.append({"league":name,"error":str(e)[:200]})
    if len(datasets)!=5:
        old.write("backtest_v04.json",{"status":"DATA_FETCH_FAILED","errors":errors,"sources":sources});return
    # 2024/25 football parameters were tuned previously on training season only.
    params=(120,4,.08)
    train=[];holdout=[]
    for code,(a,b) in datasets.items():
        train.extend(collect(code,a,b,params))
        holdout.extend(collect(code,a,b,params,100))
    # Choose blend weight using TRAIN log loss, never 2025/26 P&L.
    grid=[0,.05,.1,.15,.2,.3,.4,.5,.65,.8,1]
    training=[{"football_weight":w,**metric(scored(train,w))} for w in grid]
    winner=min(training,key=lambda x:x["log_loss"]);w=winner["football_weight"]
    base=metric(scored(holdout,0));pure=metric(scored(holdout,1));combined=metric(scored(holdout,w))
    ts=trades(holdout,w)
    per=[{"league":name,"holdout":metric(scored([r for r in holdout if r["league"]==name],w)),
          "paper":summary([t for t in ts if t["league"]==name])} for name in old.LEAGUES.values()]
    result={"updated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "status":"COMPLETED_500_PROXY" if len(holdout)==500 else "LIMITED_SAMPLE",
      "version":"v0.4 market-prior + goal-model residual PROXY",
      "warning":"Not the full factor model: no point-in-time xG, lineup, injuries, tactics, human factors or true executable T-1H quotes.",
      "method":"Train-only weight selection on 2024/25; first 100 games per league 2025/26 holdout; same-day results excluded; closing odds used as retrospective baseline and proxy execution.",
      "train_matches":len(train),"holdout_matches":len(holdout),"weight_grid":training,
      "selected_football_residual_weight":w,"market_baseline":base,
      "pure_football_model":pure,"market_anchored_proxy":combined,
      "paper_rule":"One highest conservative EV 1X2 pick per match, only if (fair - 3pp)*closing_odds - 1 >= 5%; flat $100, no fees/slippage.",
      "paper":summary(ts),"per_competition":per,"trade_log":ts,"sources":sources,
      "limitations":["Closing odds cannot represent a verified earlier T-1H fill; this is a close-price proxy.",
      "Train weight optimized for log loss, not holdout ROI.",
      "No fee, slippage or market capacity modeled; 500 games do not prove alpha.",
      "Full football factor weights remain unfitted; no automatic activation of v0.4 trading."]}
    old.write("backtest_v04.json",result)
if __name__=="__main__":main()
