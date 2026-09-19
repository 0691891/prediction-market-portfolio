#!/usr/bin/env python3
"""v0.3.5 deterministic market-data + risk-gate engine. No trading."""
import json, pathlib, urllib.request, datetime
from residual_pricing import price as residual_price, trade as residual_trade
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
def read(name): return json.loads((DATA/name).read_text())
def write(name,obj): (DATA/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
def get_market(base,ticker):
    with urllib.request.urlopen(f"{base}/markets/{ticker}",timeout=15) as r: return json.load(r)["market"]
def fnum(v):
    try:return float(v)
    except:return None
def main():
    cfg=read("config.json")
    board=read("board.json")
    gate=cfg["data_engine"]
    snap=[]
    items=[]
    consensus=read("sportsbook_consensus.json") if (DATA/"sportsbook_consensus.json").exists() else {"items":[]}
    cby={x.get("pick_id"):x for x in consensus.get("items",[])}
    for p in board.get("picks",[]):
        q=dict(p)
        ticker=p.get("kalshi_ticker")
        side=p.get("kalshi_side","yes")
        if ticker:
            try:
                m=get_market(gate["kalshi_base_url"],ticker)
                ask=fnum(m.get(f"{side}_ask_dollars"))
                liq=fnum(m.get("liquidity_dollars")) or 0
                if ask and ask>0:
                    q["market_probability"]=ask
                    q["decimal_odds"]=round(1/ask,4)
                    q["edge_pp"]=round(p["fair_probability"]-ask,4)
                    q["ev"]=round(p["fair_probability"]/ask-1,4)
                q["liquidity_usd"]=liq
                q["market_status"]=m.get("status")
            except Exception as e:
                q["data_error"]=str(e)[:160]
        # The 500-match holdout rejected raw independent Poisson EV as an auto-entry signal.
        # A calibrated residual fair, not a raw historical model fair, is required.
        residual_cfg=cfg["data_engine"].get("residual_model",{})
        baseline=cby.get(p.get("id"),{}).get("consensus_probability")
        if baseline is not None and q.get("decimal_odds"):
            rp=residual_price(float(baseline),p.get("pit_factors",{}),residual_cfg.get("trained_weights"),residual_cfg.get("calibration"))
            q["residual_pricing"]=rp
            if rp["auto_paper_eligible"]:
                q["fair_probability"]=rp["fair_probability"]
                q["edge_pp"]=round(rp["fair_probability"]-1/float(q["decimal_odds"]),6)
                evr=residual_trade(rp["fair_probability"],float(q["decimal_odds"]),model_uncertainty_pp=float(residual_cfg.get("uncertainty_pp",0.03)))
                q["ev"]=round(evr["net_ev"],6)
        edge=q.get("edge_pp")
        ev=q.get("ev")
        liq=q.get("liquidity_usd")
        mapped=bool(ticker)
        c=cby.get(p.get("id"),{})
        gap=c.get("model_vs_consensus_pp")
        maxgap=gate.get("sportsbook",{}).get("max_model_consensus_gap_for_auto_ready",0.12)
        consensus_ok = gap is None or abs(gap)<=maxgap
        passes=(mapped and q.get("residual_pricing",{}).get("auto_paper_eligible") is True and edge is not None and ev is not None and
                edge>=gate["min_edge_pp"] and ev>=gate["min_ev"] and
                (liq is None or liq>=gate["min_liquidity_usd"]) and consensus_ok)
        status="PAPER ENTRY CANDIDATE" if passes else ("NEEDS TICKER MAP" if not mapped else ("MODEL/CONSENSUS REVIEW" if not consensus_ok else "NO PAPER ENTRY / FAILS GATE"))
        items.append({"signal":f'{p["match"]} — {p["market"]}',"grade":p["grade"],"suggested_units":p["max_units"] if passes else 0,"max_entry":f'Edge≥{gate["min_edge_pp"]:.0%}, EV≥{gate["min_ev"]:.0%}',"kalshi_ticker":ticker,"sportsbook_consensus":c.get("consensus_probability"),"model_vs_consensus_pp":gap,"status":status})
        snap.append(q)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    write("market_snapshot.json",{"updated_utc":now,"markets":snap})
    write("approval.json",{"updated":now,"items":items,"mode":"PAPER / AUTO-ENTRY ON VERIFIED POSITIVE RISK-REWARD","real_money_execution":False})
if __name__=="__main__": main()
