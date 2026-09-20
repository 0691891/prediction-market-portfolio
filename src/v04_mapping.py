#!/usr/bin/env python3
"""v0.4 Kalshi event-candidate mapping queue, without guessing contract semantics.

This module NEVER auto-approves market tickers: fixture/event association and
contract rules require independent verification before fair/EV/P&L comparison.
"""
import datetime as dt
import json
import pathlib
import re
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from v04_engine import slug, ALIAS, parse

def load(path,default):
    p=ROOT/path
    return json.loads(p.read_text()) if p.exists() else default

def main():
    fx=load("data/v04_fixture_universe.json",{"fixtures":[]}).get("fixtures",[])
    markets=load("data/kalshi_public_snapshot.json",{"markets":[]}).get("markets",[])
    approved=load("data/kalshi_mappings.json",{"mappings":[]}).get("mappings",[])
    by_event={}
    for row in markets:
        key=row.get("event_ticker")
        if key:by_event.setdefault(key,[]).append(row)
    out=[];now=dt.datetime.now(dt.timezone.utc).isoformat()
    for fixture in fx:
        if fixture.get("state") in ("post","in"):continue
        h=fixture.get("home_team");a=fixture.get("away_team")
        if not h or not a:continue
        # Event group must visibly name BOTH teams, not just one team's "wins".
        hs=[slug(h),slug(ALIAS.get(h.lower(),"")),
            slug(fixture.get("resolved_history_home_team"))]
        aws=[slug(a),slug(ALIAS.get(a.lower(),"")),
            slug(fixture.get("resolved_history_away_team"))]
        # Do not consider a lone generic "City"/"United" as an identity.
        hs=[v for v in hs if len(v)>=5 and v not in ("united","city","real")]
        aws=[v for v in aws if len(v)>=5 and v not in ("united","city","real")]
        kickoff=parse(fixture.get("kickoff_utc"))
        if not kickoff or kickoff<=dt.datetime.now(dt.timezone.utc):continue
        for event,tickers in by_event.items():
            text=slug(" ".join(str(r.get("title") or "")+" "+str(r.get("subtitle") or "") for r in tickers))
            if not any(q and len(q)>=4 and q in text for q in hs):continue
            if not any(q and len(q)>=4 and q in text for q in aws):continue
            # Kalshi event date YYYY MMM DD (e.g. -26SEP20...) is a
            # candidate filter, not a verified settlement or kickoff time.
            stamp=re.search(r"-(\\d{2})([A-Z]{3})(\\d{2})",event.upper())
            if stamp:
                try:
                    ed=dt.datetime.strptime("20"+stamp.group(1)+stamp.group(2)+stamp.group(3),
                                            "%Y%b%d").date()
                    if abs((ed-kickoff.date()).days)>1:continue
                except ValueError:continue
            out.append({"match_id":fixture.get("match_id"),"match":fixture.get("match"),
                "kickoff_utc":fixture.get("kickoff_utc"),"event_ticker":event,
                "candidate_markets":[{"ticker":r.get("ticker"),"title":r.get("title"),
                    "yes_ask_usd":r.get("yes_ask_usd"),"no_ask_usd":r.get("no_ask_usd"),
                    "status":r.get("status"),"fetched_utc":r.get("fetched_utc")}
                    for r in tickers],
                "status":"MANUAL_EVENT_DATE_RULES_AND_SIDE_REVIEW",
                "reason":"Both team labels observed in event market group, but identity and settlement not yet independently verified."})
    p=ROOT/"data/v04_mapping_candidates.json"
    p.write_text(json.dumps({"updated_utc":now,"candidates":out,
        "fixtures_scanned":len(fx),"event_groups_scanned":len(by_event),
        "approved_mapping_count":len(approved),
        "rule":"Do not promote fuzzy suggestions to approved ticker mapping without exact match/market rules."},
        indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"mapping_candidates":len(out),"approved":len(approved)}))
if __name__=="__main__":main()
