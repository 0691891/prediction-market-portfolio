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
    # Separate immutable full-time outcome reference for 90-minute league contracts.
    # Cup finals after extra time / penalty shootouts require manual market-rule audit.
    league_comp={"Premier League","La Liga","Serie A","Bundesliga","Ligue 1"}
    result_book=read("verified_match_results.json",{"matches":[]})
    result_by={str(x.get("match_id")):x for x in result_book.get("matches",[]) if x.get("match_id")}
    results_added=0
    for row in current:
        if row.get("state")!="post" or row.get("competition") not in league_comp:continue
        if row.get("home_score") is None or row.get("away_score") is None:continue
        try:h=int(row["home_score"]);a=int(row["away_score"])
        except (ValueError,TypeError):continue
        if h<0 or a<0:continue
        mid=str(row["match_id"])
        if mid in result_by:continue  # provider corrections require explicit reconciliation
        record={"match_id":mid,"competition":row["competition"],
                "match":row.get("match"),"kickoff_utc":row.get("kickoff_utc"),
                "score":{"home":h,"away":a},"status":"FT",
                "settlement_scope":"90_MIN_LEAGUE_REGULATION_ASSUMED_VERIFY_RULES",
                "verified_source":row.get("url"),"observed_utc":fetched}
        result_book.setdefault("matches",[]).append(record)
        result_by[mid]=record;results_added+=1
    result_book["updated_utc"]=fetched
    write("verified_match_results.json",result_book)
    print("fixture_score_observations_added",added,"total",len(history),
          "result_rows_added",results_added,"feed_errors",len(errors))
if __name__=="__main__":main()
