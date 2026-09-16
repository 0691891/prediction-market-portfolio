#!/usr/bin/env python3
"""v0.3.5 deterministic market-data + risk-gate engine. No trading."""
import json, pathlib, urllib.request, datetime
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
        edge=q.get("edge_pp")
        ev=q.get("ev")
        liq=q.get("liquidity_usd")
        mapped=bool(ticker)
        c=cby.get(p.get("id"),{})
        gap=c.get("model_vs_consensus_pp")
        maxgap=gate.get("sportsbook",{}).get("max_model_consensus_gap_for_auto_ready",0.12)
        consensus_ok = gap is None or abs(gap)<=maxgap
        passes=(mapped and edge is not None and ev is not None and
                edge>=gate["min_edge_pp"] and ev>=gate["min_ev"] and
                (liq is None or liq>=gate["min_liquidity_usd"]) and consensus_ok)
        status="READY FOR APPROVAL" if passes else ("NEEDS TICKER MAP" if not mapped else ("MODEL/CONSENSUS REVIEW" if not consensus_ok else "WATCH / FAILS GATE"))
        items.append({"signal":f'{p["match"]} — {p["market"]}',"grade":p["grade"],"suggested_units":p["max_units"] if passes else 0,"max_entry":f'Edge≥{gate["min_edge_pp"]:.0%}, EV≥{gate["min_ev"]:.0%}',"kalshi_ticker":ticker,"sportsbook_consensus":c.get("consensus_probability"),"model_vs_consensus_pp":gap,"status":status})
        snap.append(q)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    write("market_snapshot.json",{"updated_utc":now,"markets":snap})
    write("approval.json",{"updated":now,"items":items,"mode":"PAPER / MANUAL APPROVAL","real_money_execution":False})
if __name__=="__main__": main()
