#!/usr/bin/env python3
"""Prospective research archive and counterfactual P&L; never enters the paper trading ledger.

Inputs:
  paper/observations.json: all fixtures, PASS, WATCH and candidate quote observations.
  paper/verified_match_results.json: verified match-level outcomes including score.
Outputs:
  paper/research_archive.json: frozen append-only signal observations
  paper/hypothetical_performance.json: priced theoretical recommendation audit.

This process cannot manufacture a historical point-in-time quote or model estimate.
"""
import datetime as dt
import hashlib
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
PAPER=ROOT/"paper"
UTC=dt.timezone.utc

def read(name,default):
    p=PAPER/name
    return json.loads(p.read_text()) if p.exists() else default

def write(name,doc):
    (PAPER/name).write_text(json.dumps(doc,ensure_ascii=False,indent=2,sort_keys=True)+"\n")

def parse(x):
    if not x:return None
    v=dt.datetime.fromisoformat(x.replace("Z","+00:00"))
    if v.utcoffset() is None:raise ValueError("timestamps must be timezone aware")
    return v.astimezone(UTC)

def result_for(o,r):
    score=r.get("score",{})
    h,a=score.get("home"),score.get("away")
    if not isinstance(h,int) or not isinstance(a,int) or not r.get("verified_source"):return None
    market=str(o.get("market","")).lower()
    sel=str(o.get("selection","")).lower()
    if "over" in market or "under" in market:
        try:threshold=float(o.get("line"))
        except (ValueError,TypeError):return None
        total=h+a
        if total==threshold:return "PUSH"
        return "WIN" if (total>threshold if "over" in market else total<threshold) else "LOSS"
    if market in ("1x2","moneyline","ml"):
        home=str(o.get("home_team","")).lower()
        away=str(o.get("away_team","")).lower()
        winner="draw" if h==a else home if h>a else away
        return "WIN" if sel==winner else "LOSS"
    if market=="btts":
        return "WIN" if ((h>0 and a>0)==(sel in ("yes","true"))) else "LOSS"
    return None

def main():
    obs=read("observations.json",{"observations":[]}).get("observations",[])
    results=read("verified_match_results.json",{"matches":[]}).get("matches",[])
    existing=read("research_archive.json",{"observations":[]}).get("observations",[])
    byid={x["observation_id"]:x for x in existing}
    errors=[]
    for o in obs:
        # IDs stable across runs; do not overwrite previously frozen observations.
        oid=o.get("observation_id") or o.get("signal_id")
        if not oid:
            oid=hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:22]
        if oid in byid:
            if {k:v for k,v in byid[oid].items() if k not in ("observation_id",)} != {k:v for k,v in o.items() if k not in ("observation_id",)}:
                errors.append({"id":oid,"reason":"immutable observation id changed; original retained"})
            continue
        record=dict(o);record["observation_id"]=oid
        decision=str(record.get("decision",record.get("status","PASS"))).upper()
        record["decision"]=decision
        # If a price is described as historical, require original timestamp; no current-time backdating.
        if record.get("decimal_odds") is not None or record.get("fair_probability") is not None:
            try:
                quote=parse(record.get("quote_timestamp_utc"))
                kickoff=parse(record.get("kickoff_utc"))
                if quote is None or kickoff is None:raise ValueError("timestamp missing")
                if record.get("entry_phase","PREMATCH")=="PREMATCH" and quote>=kickoff:
                    raise ValueError("pretend prematch quote after kickoff")
                if record.get("entry_phase")=="LIVE" and quote<kickoff:
                    raise ValueError("live quote before kickoff")
                if record.get("fair_probability") is not None and not record.get("model_version"):
                    raise ValueError("missing model version")
            except (ValueError,TypeError) as exc:
                record["research_quality"]="INVALID_FOR_PIT_OR_PERFORMANCE"
                record["quality_reason"]=str(exc)
        byid[oid]=record

    rby={str(r.get("match_id")):r for r in results if r.get("match_id")}
    audited=[]
    for o in byid.values():
        if o.get("research_quality")=="INVALID_FOR_PIT_OR_PERFORMANCE":continue
        decision=o.get("decision","PASS")
        if decision not in ("PAPER_CANDIDATE","SIMULATED_RECOMMENDATION","RECOMMEND","BUY"):
            continue
        r=rby.get(str(o.get("match_id")))
        if not r or r.get("status")!="FT":continue
        outcome=result_for(o,r)
        if outcome is None:continue
        try:
            odds=float(o["decimal_odds"]);stake=float(o["stake_usd"])
            if odds<=1 or stake<=0:continue
            fair=float(o["fair_probability"])
            if not 0<fair<1:continue
        except (KeyError,ValueError,TypeError):continue
        fees=float(o.get("fees_usd",0))
        pnl=round((stake*(odds-1) if outcome=="WIN" else
                   -stake if outcome=="LOSS" else 0)-fees,2)
        audited.append({"observation_id":o["observation_id"],
                        "match_id":o.get("match_id"),"match":o.get("match"),
                        "market":o.get("market"),"selection":o.get("selection"),
                        "entry_phase":o.get("entry_phase","PREMATCH"),
                        "quote_timestamp_utc":o.get("quote_timestamp_utc"),
                        "quote_source":o.get("quote_source"),"odds":odds,
                        "fair":fair,"stake_usd":stake,"outcome":outcome,
                        "theoretical_pnl_usd":pnl,
                        "quote_executable_verified":o.get("quote_executable_verified",False),
                        "result_source":r.get("verified_source")})
    total=round(sum(x["theoretical_pnl_usd"] for x in audited),2)
    stake=round(sum(x["stake_usd"] for x in audited),2)
    write("research_archive.json",{"schema_version":"1.0","observations":list(byid.values()),
                                    "errors":errors,"quality_rule":"Immutable IDs, no retrospective quotes."})
    write("hypothetical_performance.json",{"schema_version":"1.0",
           "mode":"WHAT_IF_RESEARCH_ONLY_NOT_PAPER_FILLS",
           "initial_virtual_reference_usd":1000000,
           "sample_size":len(audited),"settled_stake_usd":stake,
           "hypothetical_pnl_usd":total,"hypothetical_nav_reference_usd":1000000+total,
           "hypothetical_roi":round(total/stake,6) if stake else None,
           "trades":audited,
           "note":"Only prospectively stored priced signals. Ex-ante conversation reviews remain a separate legacy audit. Paper/account and paper/state unchanged."})
    print(json.dumps({"observations":len(byid),"settled_hypotheticals":len(audited),"what_if_pnl":total}))

if __name__=="__main__":main()
