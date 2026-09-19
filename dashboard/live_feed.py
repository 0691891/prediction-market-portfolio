"""Read-only live football scoreboard and optional sportsbook feed.

Live screens are not paper trades. APIs may be delayed; always show timestamps.
"""
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import sys
import pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
from european_coverage import VERIFIED_ODDS_KEYS

ESPN={
"Premier League":"eng.1","La Liga":"esp.1","Serie A":"ita.1",
"Bundesliga":"ger.1","Ligue 1":"fra.1",
"UEFA Champions League":"uefa.champions","UEFA Europa League":"uefa.europa",
"EFL/Carabao Cup":"eng.league_cup","FA Cup":"eng.fa",
}
ODDS={
"Premier League":"soccer_epl","La Liga":"soccer_spain_la_liga",
"Serie A":"soccer_italy_serie_a","Bundesliga":"soccer_germany_bundesliga",
"Ligue 1":"soccer_france_ligue_one","UEFA Champions League":"soccer_uefa_champs_league",
"UEFA Europa League":"soccer_uefa_europa_league",
"EFL/Carabao Cup":"soccer_england_efl_cup","FA Cup":"soccer_fa_cup",
}
# Registry is broader than the provider's actual live catalogue.
# Never invent keys: only activate keys returned by the authenticated sports endpoint.
ODDS.update(VERIFIED_ODDS_KEYS)
def get(url,headers=None):
    req=urllib.request.Request(url,headers={"User-Agent":"FootballAlphaResearchDashboard/1.1",**(headers or {})})
    with urllib.request.urlopen(req,timeout=9) as r:
        return json.load(r),dict(r.headers)

def scores(day=None):
    day=day or dt.datetime.now(dt.timezone.utc).date()
    result=[];errors={}
    for league,key in ESPN.items():
        url="https://site.api.espn.com/apis/site/v2/sports/soccer/"+key+"/scoreboard?"+urllib.parse.urlencode({"dates":day.strftime("%Y%m%d"),"limit":100})
        try:
            doc,_=get(url)
            for e in doc.get("events",[]):
                competitions=e.get("competitions") or [{}]
                cs={c.get("homeAway"):c for c in competitions[0].get("competitors",[])}
                h,a=cs.get("home",{}),cs.get("away",{})
                status=e.get("status",{}); typ=status.get("type",{})
                result.append({"match_id":"espn:"+key+":"+str(e.get("id")),
                 "competition":league,"match":e.get("name"),
                 "home_team":h.get("team",{}).get("displayName"),"away_team":a.get("team",{}).get("displayName"),
                 "home_score":h.get("score"),"away_score":a.get("score"),
                 "kickoff_utc":e.get("date"),"status":typ.get("detail"),
                 "state":typ.get("state"),"clock":status.get("displayClock"),
                 "source":"ESPN scoreboard","url":url})
        except (OSError,ValueError,urllib.error.URLError) as exc:
            errors[league]=str(exc)[:120]
    return result,errors,dt.datetime.now(dt.timezone.utc).isoformat()

def odds(api_key,regions="us,uk,eu",leagues=None):
    if not api_key:return [],{"all":"ODDS_API_KEY missing"},None
    rows=[];errors={}; retrieved=dt.datetime.now(dt.timezone.utc).isoformat()
    for league in (leagues or list(ODDS)):
        key=ODDS.get(league)
        if not key or key not in active:continue
        params=urllib.parse.urlencode({"apiKey":api_key,"regions":regions,
                  "markets":"h2h,spreads,totals","oddsFormat":"decimal"})
        url="https://api.the-odds-api.com/v4/sports/"+key+"/odds/?"+params
        try:
            doc,_=get(url)
            for e in doc:
                for book in e.get("bookmakers",[]):
                    for m in book.get("markets",[]):
                        for outcome in m.get("outcomes",[]):
                            price=outcome.get("price")
                            if not isinstance(price,(float,int)) or price<=1:continue
                            rows.append({"competition":league,"event_id":e.get("id"),
                             "kickoff_utc":e.get("commence_time"),"home_team":e.get("home_team"),
                             "away_team":e.get("away_team"),"bookmaker":book.get("title"),
                             "market":m.get("key"),"selection":outcome.get("name"),
                             "point":outcome.get("point"),"decimal_odds":price,
                             "break_even":1/price,"quote_timestamp_utc":m.get("last_update") or book.get("last_update"),
                             "fetched_utc":retrieved,"provider":"The Odds API",
                             "status":"INDICATIVE_NOT_FILL_VERIFIED"})
        except (OSError,ValueError,urllib.error.URLError) as exc:
            errors[league]=str(exc)[:120]
    return rows,errors,retrieved
