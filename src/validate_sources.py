#!/usr/bin/env python3
"""v0.4 source verification audit: no false GREEN from fallback or fetched stale bids.

Read-only, writes only aggregate technical status. Does not expose credentials,
generate fills, claim sportsbook data exists, or infer alpha from forecast counts.
"""
import datetime as dt
import json
import pathlib
from collections import Counter
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/"data"

def load(file,default):
    p=ROOT/file
    return json.loads(p.read_text()) if p.exists() else default
def parse(x):
    try:
        d=dt.datetime.fromisoformat(str(x).replace("Z","+00:00"))
        return d.astimezone(dt.timezone.utc) if d.utcoffset() is not None else None
    except (ValueError,TypeError):return None

def audit(fixtures,model,kalshi,mappings,consensus,intelligence,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    fx=fixtures.get("fixtures",[])
    m=model.get("items",[])
    markets=kalshi.get("markets",[])
    valid_prices=0;stale=0;unknown=0;notopen=0;bad=0
    for q in markets:
        ask=q.get("yes_ask_usd")
        updated=parse(q.get("market_updated_utc"))
        status=str(q.get("status","")).lower()
        if status not in ("active","open"):
            notopen+=1;continue
        if not isinstance(ask,(int,float)) or not 0<ask<1:
            bad+=1;continue
        if updated is None:
            unknown+=1;continue
        age=(now-updated).total_seconds()
        if 0<=age<=900:valid_prices+=1
        else:stale+=1
    reason=Counter(x.get("model_fair_status") or "UNKNOWN" for x in fx)
    source=Counter(x.get("schedule_quality") or "PROVIDER_SCHEDULE_UNCROSSCHECKED" for x in fx)
    modelled=sum(x.get("status")=="MODELLED" and isinstance(x.get("fair_probability"),(int,float))
                 for x in m)
    checked=sum(x.get("contract_verified") is True and x.get("fair_is_mapped_side") is True
                for x in mappings.get("mappings",[]))
    source_errors=fixtures.get("errors",{})
    result={
      "updated_utc":now.isoformat(),"status":"RESEARCH_ONLY_INCOMPLETE_INPUTS",
      "fixture":{"observed":len(fx),"source_quality_counts":dict(source),
        "model_status_counts":dict(reason),"schedule_error_count":len(source_errors.get("schedule",{})),
        "history_error_count":len(source_errors.get("history",{})),
        "cross_verified_kickoffs":sum(x.get("schedule_quality")=="CROSS_VERIFIED" for x in fx)},
      "model":{"prospective_market_rows":len(m),"modelled_rows":modelled,
        "independent_model":model.get("model"),"model_data_coverage":round(modelled/len(m),4) if m else None,
        "not_proof_of_alpha":True},
      "kalshi":{"market_rows":len(markets),"recent_open_yes_asks":valid_prices,
        "stale_yes_asks":stale,"unknown_age_yes_asks":unknown,
        "not_open":notopen,"invalid_yes_asks":bad,
        "source_errors":kalshi.get("errors",{}),
        "freshness_max_seconds":900},
      "mapping":{"explicit_rows":len(mappings.get("mappings",[])),
        "verified_market_side_rows":checked},
      "third_party":{"sportsbook":consensus.get("status","UNKNOWN"),
                     "football_intelligence":intelligence.get("status","UNKNOWN")},
      "activation":{"research":len(fx)>0 and modelled>0 and len(markets)>0,
        "automatic_a_grade_paper":False,
        "reason":"Requires independently cross-checked schedule, verified contract semantics, current ASK and fee/capacity as well as out-of-sample calibrated positive-edge evidence."},
      "note":"Github Actions fetch is a periodic observation, not a Kalshi live executable quote or guarantee of true closing price."
    }
    return result

def main():
    report=audit(load("data/v04_fixture_universe.json",{}),
        load("data/model_fair.json",{}),
        load("data/kalshi_public_snapshot.json",{}),
        load("data/kalshi_mappings.json",{}),
        load("data/sportsbook_consensus.json",{}),
        load("data/football_intelligence.json",{}))
    (DATA/"v04_data_health.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"research":report["activation"]["research"],
        "fixt":report["fixture"]["observed"],"modelled":report["model"]["modelled_rows"],
        "kalshi_fresh":report["kalshi"]["recent_open_yes_asks"],
        "mapping_verified":report["mapping"]["verified_market_side_rows"],
        "risk_grade_enabled":report["activation"]["automatic_a_grade_paper"]}))

if __name__=="__main__":main()
