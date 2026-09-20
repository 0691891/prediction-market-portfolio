#!/usr/bin/env python3
"""Kalshi public price -> independent fair -> EV -> PIT -> settlement research.

Only verified explicit pick_id <-> Kalshi ticker mappings enter model comparisons.
Uses public GET only; never reads account credentials or creates orders.
Research-only P&L never modifies paper/state.json or data/trades.json.
"""
import datetime as dt
import json
import math
import pathlib
import sys
from decimal import Decimal, InvalidOperation
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
PAPER=ROOT/"paper"
sys.path.insert(0,str(ROOT/"dashboard"))
from kalshi_feed import public_markets, get, PREFIX, market_row

def load(path, default):
    p=ROOT/path
    return json.loads(p.read_text()) if p.exists() else default

def save(path, obj):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True)+"\n")

def timeparse(value):
    if not value:return None
    try:
        t=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return t.astimezone(dt.timezone.utc) if t.utcoffset() is not None else None
    except (TypeError,ValueError):return None

def val(x):
    try:
        n=float(Decimal(str(x)))
        return n if math.isfinite(n) else None
    except (InvalidOperation,ValueError,TypeError):return None

def valid_probability(x):
    p=val(x)
    return p if p is not None and 0<p<1 else None

def quote_for(m,side):
    return val(m.get(side+"_ask_usd"))

def settlement(m):
    """Only explicit binary settlement; no score/result guesses."""
    status=str(m.get("status","")).lower()
    if status not in ("settled","finalized"):return None
    result=str(m.get("result","")).lower()
    if result in ("yes","no"):return result
    v=val(m.get("settlement_value_dollars"))
    if v==1:return "yes"
    if v==0:return "no"
    return None

def main():
    cfg=load("data/config.json",{})
    mappings=load("data/kalshi_mappings.json",{"mappings":[]})
    model=load("data/model_fair.json",{"items":[]})
    board=load("data/board.json",{"picks":[]})
    series=cfg.get("data_engine",{}).get("kalshi_series_tickers",[])
    explicit={str(x["ticker"]).upper() for x in mappings.get("mappings",[]) if x.get("ticker")}
    explicit.update(str(p["kalshi_ticker"]).upper() for p in board.get("picks",[]) if p.get("kalshi_ticker"))
    raw,errors,now,meta=public_markets(series_tickers=series,watch_tickers=sorted(explicit),pages_per_series=1)
    # Paged discovery is a candidate screen, not automatic fixture or market mapping.
    public={x["ticker"]:x for x in raw if x.get("ticker")}
    public_list=sorted(public.values(),key=lambda x:x["ticker"])
    save("data/kalshi_public_snapshot.json",{"updated_utc":now,"status":"OK" if public else "EMPTY_OR_SOURCE_ERROR",
         "market_count":len(public),"markets":public_list,"errors":errors,"coverage":meta,
         "note":"Public Kalshi sampled series, NOT exhaustive. Indicative bid/ask not a proven fill."})
    mby={str(x.get("pick_id")):x for x in model.get("items",[]) if x.get("pick_id")}
    pby={str(x.get("id")):x for x in board.get("picks",[]) if x.get("id")}
    mapped={}
    for x in mappings.get("mappings",[]):
        if x.get("pick_id") and x.get("ticker"):
            mapped[str(x["pick_id"])]=dict(x)
    for p in board.get("picks",[]):
        if p.get("id") and p.get("kalshi_ticker") and str(p["id"]) not in mapped:
            mapped[str(p["id"])]={
                "pick_id":str(p["id"]),"ticker":p["kalshi_ticker"],
                "side":p.get("kalshi_side","yes"),
                "kickoff_utc":p.get("kickoff_utc") or p.get("kickoff"),
                "contract_verified":bool(p.get("kalshi_contract_verified",False)),
            }
    rows=[]
    for pid,x in mapped.items():
        side=str(x.get("side","yes")).lower()
        if side not in ("yes","no"):continue
        ticker=str(x["ticker"]).upper()
        m=public.get(ticker)
        # If discovered market not present (closed/settled), fetch exact ticker for settlement.
        if m is None:
            try:
                record=get(PREFIX+"/markets/"+ticker).get("market",{})
                m=market_row(record,now,"Kalshi REST GET exact ticker")
                m["result"]=record.get("result")
                m["settlement_value_dollars"]=record.get("settlement_value_dollars")
            except Exception as exc:
                errors["mapped:"+ticker]=type(exc).__name__
        p=pby.get(pid,{})
        f=mby.get(pid,{})
        kickoff=x.get("kickoff_utc") or p.get("kickoff_utc") or p.get("kickoff")
        kickoff_dt=timeparse(kickoff)
        snapshot_dt=timeparse(now)
        price=quote_for(m,side) if m else None
        opposite=quote_for(m,("no" if side=="yes" else "yes")) if m else None
        raw_fair=valid_probability(f.get("fair_probability")) if f.get("status")=="MODELLED" else None
        # Base model_fair is probability of board's pick, not necessarily Kalshi YES.
        # Only use mapping when verified SAME chosen outcome, no blind YES/NO flipping.
        fair=raw_fair if x.get("fair_is_mapped_side") is True else None
        contract_ok=x.get("contract_verified") is True
        prematch=bool(kickoff_dt and snapshot_dt and snapshot_dt<kickoff_dt)
        status=str((m or {}).get("status","")).lower()
        exchange_time=timeparse((m or {}).get("market_updated_utc"))
        seconds_old=(snapshot_dt-exchange_time).total_seconds() if snapshot_dt and exchange_time else None
        # A freshly fetched JSON is not proof of a recently refreshed exchange quote.
        # Keep stale/un-timestamped bids visible for research but never assign
        # trade-candidate EV or imply they are current executable ask prices.
        recently_updated=seconds_old is not None and 0<=seconds_old<=900
        quote_ok=bool(price is not None and 0<price<1 and status in ("open","active")
                      and prematch and recently_updated)
        edge=(fair-price) if fair is not None and quote_ok and contract_ok else None
        gross_ev=(fair/price-1) if edge is not None else None
        # Fee cannot be treated as zero. Provide net EV only with explicit verified fee input.
        fee=val(x.get("fee_per_contract_usd"))
        net_ev=((fair-price-fee)/(price+fee)) if gross_ev is not None and fee is not None and fee>=0 else None
        row={"pick_id":pid,"ticker":ticker,"side":side,"match":p.get("match") or x.get("match"),
          "competition":p.get("competition") or x.get("competition"),
          "market":p.get("market") or x.get("market"),"kickoff_utc":kickoff,
          "fetched_utc":now,"market_updated_utc":(m or {}).get("market_updated_utc"),
          "kalshi_status":status or None,"market_age_seconds":round(seconds_old,2) if seconds_old is not None else None,"recently_updated":recently_updated,"yes_bid_usd":(m or {}).get("yes_bid_usd"),
          "yes_ask_usd":(m or {}).get("yes_ask_usd"),"no_bid_usd":(m or {}).get("no_bid_usd"),
          "no_ask_usd":(m or {}).get("no_ask_usd"),"entry_ask_usd":price,
          "opposite_ask_usd":opposite,"break_even_probability_gross":price,
          "model_fair_probability":fair,"model_version":model.get("model"),
          "model_status":f.get("status"),"contract_verified":contract_ok,
          "fair_side_verified":x.get("fair_is_mapped_side") is True,
          "fee_per_contract_usd":fee,"edge_pp":round(edge,6) if edge is not None else None,
          "gross_ev":round(gross_ev,6) if gross_ev is not None else None,
          "net_ev":round(net_ev,6) if net_ev is not None else None,
          "prematch":prematch,"quote_available":quote_ok,
          "quote_quality":"INDICATIVE_NO_FILL" if quote_ok else "NOT_ACTIONABLE",
          "result":(m or {}).get("result"),"settlement_value_dollars":(m or {}).get("settlement_value_dollars"),
          "settlement_outcome":settlement(m or {}),"note":"No automatic recommendation/fill. Model-side mapping, fresh market update and fee required for net EV."}
        rows.append(row)
    save("data/kalshi_research.json",{"updated_utc":now,"items":rows,
           "status":"OK" if rows else "NO_VERIFIED_MAPPINGS",
           "notes":"My Fair never inferred from Kalshi quote; no fair when independent model unavailable."})
    # Append-only per-hour snapshots, but keep the earliest timestamped record in that
    # hour; later reruns must not change the history.
    hour=timeparse(now).strftime("%Y-%m-%dT%H")
    archive_path="data/kalshi_pit/"+hour[:10]+".json"
    archive=load(archive_path,{"date":hour[:10],"snapshots":[]})
    seen={(z.get("pick_id"),z.get("side"),z.get("snapshot_hour_utc"))
          for z in archive["snapshots"]}
    for row in rows:
        if not row["prematch"]:continue
        identity=(row["pick_id"],row["side"],hour)
        if identity in seen:continue
        archive["snapshots"].append({**row,"snapshot_hour_utc":hour})
        seen.add(identity)
    save(archive_path,archive)
    # CLV: compare frozen same-ticker+side ask with nearest observed pre-kickoff ask.
    days=sorted((DATA/"kalshi_pit").glob("*.json"))
    timeline=[]
    for day in days:
        try:timeline.extend(json.loads(day.read_text()).get("snapshots",[]))
        except (ValueError,OSError):pass
    groups={}
    for r in timeline:
        if not r.get("prematch") or r.get("entry_ask_usd") is None:continue
        groups.setdefault((r["ticker"],r["side"],r.get("kickoff_utc")),[]).append(r)
    clv=[]
    for key,history in groups.items():
        history.sort(key=lambda x:x["fetched_utc"])
        if len(history)<2:continue
        e,c=history[0],history[-1]
        if e["fetched_utc"]==c["fetched_utc"]:continue
        clv.append({"ticker":key[0],"side":key[1],"kickoff_utc":key[2],
                    "entry_utc":e["fetched_utc"],"close_observed_utc":c["fetched_utc"],
                    "entry_ask":e["entry_ask_usd"],"close_ask":c["entry_ask_usd"],
                    "clv_ask_pp":round(c["entry_ask_usd"]-e["entry_ask_usd"],6),
                    "status":"OBSERVED_PREMATCH_PRICE_MOVE_NOT_GUARANTEED_TRUE_CLOSE"})
    save("data/kalshi_clv.json",{"updated_utc":now,"items":clv,
                                "note":"Only same ticker/side Kalshi ask, observed PREMATCH; no cross-venue fill assumption."})
    # What-if P&L: prospective immutable observations only, exchange-verified binary
    # settlement and exact same market ticker; NOT paper/state or real account.
    observations=load("paper/research_archive.json",{"observations":[]}).get("observations",[])
    closed={r["ticker"]:r for r in rows if r.get("settlement_outcome")}
    whatif=[]
    for o in observations:
        if o.get("decision") not in ("RECOMMEND","SIMULATED_RECOMMENDATION","PAPER_CANDIDATE","BUY"):continue
        ticker=str(o.get("kalshi_ticker") or "").upper()
        side=str(o.get("kalshi_side") or "").lower()
        r=closed.get(ticker)
        if not r or side not in ("yes","no") or o.get("entry_phase","PREMATCH")!="PREMATCH":continue
        entry=timeparse(o.get("quote_timestamp_utc"));kickoff=timeparse(o.get("kickoff_utc"))
        price=val(o.get("entry_ask_usd")); stake=val(o.get("stake_usd"))
        if not entry or not kickoff or entry>=kickoff or price is None or not 0<price<1 or not stake or stake<=0:continue
        # Do not book a retrospective hypothetical without its original, immutable
        # exchange quote in the pre-match PIT archive at the claimed entry time.
        matched=any(z.get("ticker")==ticker and z.get("side")==side
                    and timeparse(z.get("fetched_utc"))==entry
                    and z.get("entry_ask_usd") is not None
                    and abs(float(z["entry_ask_usd"])-price)<0.000001
                    and z.get("prematch") is True for z in timeline)
        if not matched:continue
        if o.get("contract_verified") is not True or o.get("fair_is_mapped_side") is not True:continue
        settled=r["settlement_outcome"]; win=side==settled
        fee=val(o.get("fees_usd"))
        count=stake/price
        gross=round(count*(1-price) if win else -stake,2)
        net=round(gross-fee,2) if fee is not None else None
        whatif.append({"observation_id":o.get("observation_id"),"ticker":ticker,"side":side,
                       "stake_usd":stake,"entry_ask_usd":price,"outcome":"WIN" if win else "LOSS",
                       "gross_pnl_usd":gross,"net_pnl_usd":net,
                       "settlement_source":"Kalshi public settled contract"})
    save("data/kalshi_whatif.json",{"updated_utc":now,"trades":whatif,
         "gross_pnl_usd":round(sum(t["gross_pnl_usd"] for t in whatif),2),
         "net_pnl_usd":round(sum(t["net_pnl_usd"] for t in whatif if t["net_pnl_usd"] is not None),2) if whatif and all(t["net_pnl_usd"] is not None for t in whatif) else None,
         "mode":"RESEARCH_ONLY_NO_REAL_OR_PAPER_LEDGER_MUTATION",
         "note":"Gross excludes fees; net is null if any fee missing. Do not count unpriced leans or PASS."})
    print(json.dumps({"public_markets":len(public),"mapped":len(rows),
                      "valid_model_fairs":sum(r["model_fair_probability"] is not None for r in rows),
                      "clv":len(clv),"settled_whatif":len(whatif),
                      "errors":list(errors)[:8]}))
if __name__=="__main__":main()
