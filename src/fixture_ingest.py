#!/usr/bin/env python3
"""Persist source-stamped score/fixture research for all covered competitions.

Public ESPN scoreboard observation only: not a Kalshi quote, independent My Fair,
confirmed XI, or executable paper fill. No retroactive forecasts.
"""
import datetime as dt
import hashlib
import json
import pathlib
import sys
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"dashboard"))
from live_feed import scores

PAPER=ROOT/"paper"
def read(n,d):
    p=PAPER/n
    return json.loads(p.read_text()) if p.exists() else d
def write(n,obj):
    (PAPER/n).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
def parse(x):
    return dt.datetime.fromisoformat(x.replace("Z","+00:00")).astimezone(dt.timezone.utc)
def main():
    nyday=dt.datetime.now(ZoneInfo("America/New_York")).date()
    current,errors,fetched=scores(nyday)
    observed_at=parse(fetched)
    if not current:
        print("SCORE_FEED_UNAVAILABLE",errors);return
    old=read("observations.json",{"observations":[]})
    history=list(old.get("observations",[]))
    seen={r.get("observation_id") for r in history}
    added=0
    for row in current:
        kickoff=parse(row["kickoff_utc"]) if row.get("kickoff_utc") else None
        if kickoff is None:continue
        live=row.get("state")=="in"
        completed=row.get("state")=="post"
        phase="FINAL_RESULT_OBSERVATION" if completed else "LIVE_RESEARCH" if live else "PREMATCH_RESEARCH" if observed_at<kickoff else "UNKNOWN_STATE"
        oid=hashlib.sha256((str(row["match_id"])+fetched+phase).encode()).hexdigest()[:22]
        if oid in seen:continue
        event={**row,"observation_id":oid,"observed_at_utc":fetched,
               "entry_phase":"LIVE" if live else "PREMATCH" if observed_at<kickoff else "POSTMATCH",
               "phase":phase,"status":"PASS_MISSING_MODEL_AND_EXECUTABLE_PRICE",
               "decision":"PASS","quote_status":"NO_EXECUTABLE_QUOTE",
               "model_status":"NO_INDEPENDENT_FAIR",
               "data_quality":"SCORE_FIXTURE_ONLY",
               "quote_timestamp_utc":None,"fair_probability":None,
               "decimal_odds":None,"stake_usd":0,
               "paper_eligible":False}
        history.append(event);seen.add(oid);added+=1
    old.update({"schema_version":"1.1","updated_utc":fetched,
                "provider":"ESPN public scoreboard; may be delayed",
                "provider_errors":errors,"observations":history})
    write("observations.json",old)
    print("fixture_score_observations_added",added,"total",len(history),"feed_errors",len(errors))
if __name__=="__main__":main()
