#!/usr/bin/env python3
"""Football Alpha Engine v0.4: prospectively generate all fixtures and independent prices.

This research model never uses Kalshi or sportsbook prices as inputs and never
creates orders. Historical match-day CSVs do not expose kickoff hour: strictly
exclude all matches on the target calendar day to avoid look-ahead.
"""
import datetime as dt
import csv
import io
import urllib.request
import json
import math
import pathlib
import sys
import unicodedata
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
sys.path.insert(0,str(ROOT/"dashboard"))
sys.path.insert(0,str(ROOT/"src"))
from live_feed import scores, ESPN
import backtest as historical

LEAGUE_CODES={name:code for code,name in historical.LEAGUES.items()}
ALIAS={
 "manchester city":"Man City","manchester united":"Man United",
 "nottingham forest":"Nott'm Forest","tottenham hotspur":"Tottenham",
 "newcastle united":"Newcastle","wolverhampton wanderers":"Wolves",
 "west ham united":"West Ham","brighton hove albion":"Brighton",
 "brighton and hove albion":"Brighton","leicester city":"Leicester",
 "ipswich town":"Ipswich","norwich city":"Norwich",
 "leeds united":"Leeds","sheffield united":"Sheffield United",
 "crystal palace":"Crystal Palace","afc bournemouth":"Bournemouth",
 "athletic club":"Ath Bilbao","athletic bilbao":"Ath Bilbao",
 "atletico madrid":"Ath Madrid","real sociedad":"Sociedad",
 "real betis":"Betis","rc celta":"Celta","celta vigo":"Celta",
 "deportivo alaves":"Alaves","espanyol":"Espanol",
 "internazionale":"Inter","inter milan":"Inter",
 "ac milan":"Milan","as roma":"Roma","ssc napoli":"Napoli",
 "borussia dortmund":"Dortmund","bayern munich":"Bayern Munich",
 "bayer leverkusen":"Leverkusen","rb leipzig":"RB Leipzig",
 "borussia monchengladbach":"M'gladbach","borussia mönchengladbach":"M'gladbach",
 "eintracht frankfurt":"Ein Frankfurt","werder bremen":"Werder Bremen",
 "1 fc koln":"FC Koln","fc koln":"FC Koln","hamburger sv":"Hamburg",
 "paris saint germain":"Paris SG","olympique lyonnais":"Lyon",
 "olympique de marseille":"Marseille","stade rennais":"Rennes",
 "losc lille":"Lille","as monaco":"Monaco","ogc nice":"Nice"
}
def slug(s):
    s=unicodedata.normalize("NFKD",str(s or "").lower())
    s="".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s if c.isalnum())
def translate(team, names):
    if not team:return None
    raw=str(team).strip()
    lookup={slug(n):n for n in names}
    if slug(raw) in lookup:return lookup[slug(raw)]
    target=ALIAS.get(raw.lower())
    if target and slug(target) in lookup:return lookup[slug(target)]
    # Reject ambiguous partial/fuzzy mappings instead of inventing matchup strength.
    return None
def parse(s):
    try:
        v=dt.datetime.fromisoformat(str(s).replace("Z","+00:00"))
        return v.astimezone(dt.timezone.utc) if v.utcoffset() is not None else None
    except (ValueError,TypeError):return None
def load(path,default):
    p=ROOT/path
    return json.loads(p.read_text()) if p.exists() else default
def save(path,value):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
def poisson_grid(lh,la,maxg=12):
    arr=[(h,a,math.exp(-lh)*lh**h/math.factorial(h)*math.exp(-la)*la**a/math.factorial(a))
         for h in range(maxg+1) for a in range(maxg+1)]
    z=sum(v for _,_,v in arr)
    return [(h,a,v/z) for h,a,v in arr]
def scores_from_grid(grid):
    p={
      "HOME_WIN":sum(v for h,a,v in grid if h>a),
      "DRAW":sum(v for h,a,v in grid if h==a),
      "AWAY_WIN":sum(v for h,a,v in grid if h<a),
      "OVER_2_5":sum(v for h,a,v in grid if h+a>=3),
      "UNDER_2_5":sum(v for h,a,v in grid if h+a<3),
      "BTTS_YES":sum(v for h,a,v in grid if h>=1 and a>=1),
      "BTTS_NO":sum(v for h,a,v in grid if h==0 or a==0)
    }
    return {k:round(v,6) for k,v in p.items()}
def lambdas(history,home,away,asof,params):
    # The prior season plus THIS season to date; no same-day score leakage.
    hist=[r for r in history if r["date"].date()<asof.date()]
    if len(hist)<30:return None
    league=sum(r["hg"]+r["ag"] for r in hist)/(2*len(hist))
    if league<=0:return None
    half=params.get("recent_half_life_days",120)
    shrink=params.get("shrinkage_matches",4)
    ha=params.get("home_advantage_log",.08)
    def team(t):
        rows=[r for r in hist if t==r["home"] or t==r["away"]]
        if len(rows)<5:return None
        weighted=[]
        for r in rows:
            diff=max(0,(asof-r["date"]).days)
            w=math.exp(-math.log(2)*diff/max(1,half))
            gf,ga=(r["hg"],r["ag"]) if r["home"]==t else (r["ag"],r["hg"])
            weighted.append((w,gf,ga))
        sw=sum(w for w,_,_ in weighted)
        g=sum(w*gf for w,gf,_ in weighted)/sw
        conceded=sum(w*ga for w,_,ga in weighted)/sw
        # Effective sample for recency-weighted observations; shrink small samples.
        eff=min(40.,sw)
        return ((eff*g+shrink*league)/(eff+shrink),
                (eff*conceded+shrink*league)/(eff+shrink),len(rows))
    h=team(home);a=team(away)
    if h is None or a is None:return None
    lh=league*(h[0]/league)*(a[1]/league)*math.exp(ha)
    la=league*(a[0]/league)*(h[1]/league)*math.exp(-ha)
    return (max(.15,min(4.5,lh)),max(.15,min(4.5,la)),
            {"history_matches":len(hist),"home_prior_matches":h[2],
             "away_prior_matches":a[2],"league_goals_per_team":round(league,4)})
def history_data(now):
    output={};errors={}
    current=now.strftime("%y")+str((now.year+1)%100).zfill(2)
    # e.g. Sep 2026 -> 2627; Jul 2027 -> 2627.
    season_start=now.year if now.month>=7 else now.year-1
    seasons=[f"{(season_start-1)%100:02d}{season_start%100:02d}",
             f"{season_start%100:02d}{(season_start+1)%100:02d}"]
    for code in LEAGUE_CODES.values():
        found=[]
        for season in seasons:
            try:
                rows,url=historical.fetch_csv(season,code)
                found.extend([{**r,"source":url} for r in rows])
            except Exception as exc:errors[f"{code}:{season}"]=type(exc).__name__
        output[code]=sorted(found,key=lambda r:r["date"])
    return output,errors
def fixtures_csv(now,days=3):
    """Fallback if ESPN returns 403. Football-data.co.uk free fixtures, UK local Time."""
    url="https://www.football-data.co.uk/matches/resources/fixtures.csv"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 FootballAlpha/0.4"})
        with urllib.request.urlopen(req,timeout=20) as res:
            rows=list(csv.DictReader(io.StringIO(res.read().decode("utf-8-sig","replace"))))
    except Exception as exc:
        return [],{"csv_fixture_feed":type(exc).__name__+":"+str(exc)[:60]}
    out=[];errors={}
    today=now.astimezone(ZoneInfo("America/New_York")).date()
    for i,row in enumerate(rows):
        div=(row.get("Div") or row.get("League") or "").strip()
        league=historical.LEAGUES.get(div)
        if league is None:continue
        dstr=(row.get("Date") or "").strip()
        tstr=(row.get("Time") or "").strip()
        date=None
        for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
            try:date=dt.datetime.strptime(dstr,fmt).date();break
            except ValueError:continue
        if date is None or not tstr:
            errors["missing_kickoff:"+str(i)]="no parseable date / UK local clock time"
            continue
        try:
            hh,mm=map(int,tstr[:5].split(":"))
            ko=dt.datetime(date.year,date.month,date.day,hh,mm,
                           tzinfo=ZoneInfo("Europe/London")).astimezone(dt.timezone.utc)
        except (ValueError,TypeError):
            errors["bad_kickoff:"+str(i)]=dstr+" "+tstr
            continue
        local_date=ko.astimezone(ZoneInfo("America/New_York")).date()
        if not(today<=local_date<=today+dt.timedelta(days=days)):continue
        home=(row.get("HomeTeam") or row.get("Home") or "").strip()
        away=(row.get("AwayTeam") or row.get("Away") or "").strip()
        if not home or not away:continue
        identity="fixture-csv:"+div+":"+date.isoformat()+":"+slug(home)+":"+slug(away)
        out.append({"match_id":identity,"competition":league,
            "match":home+" vs "+away,"home_team":home,"away_team":away,
            "home_score":None,"away_score":None,"kickoff_utc":ko.isoformat(),
            "status":"scheduled","state":"pre","source":url,
            "observed_at_utc":now.isoformat()})
    return out,errors

def openfootball_fixtures(now,days=3):
    """Secondary independent fixture source, no key, with league-local times.

    Openfootball is community-maintained, so these kickoff times are tentative.
    Never use them to assert a verified executable quote/fill.
    """
    sources={"Premier League":("en.1","Europe/London"),
             "La Liga":("es.1","Europe/Madrid"),
             "Serie A":("it.1","Europe/Rome"),
             "Bundesliga":("de.1","Europe/Berlin"),
             "Ligue 1":("fr.1","Europe/Paris")}
    base="https://raw.githubusercontent.com/openfootball/football.json/master/"
    season_year=now.year if now.month>=7 else now.year-1
    season=f"{season_year}-{(season_year+1)%100:02d}"
    today=now.astimezone(ZoneInfo("America/New_York")).date()
    out=[];errors={}
    for league,(code,zone) in sources.items():
        url=base+season+"/"+code+".json"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"FootballAlpha/0.4"})
            with urllib.request.urlopen(req,timeout=15) as res:
                doc=json.load(res)
        except Exception as exc:
            errors[league]=type(exc).__name__+":"+str(exc)[:65]
            continue
        for row in doc.get("matches",[]):
            dstr=str(row.get("date") or "")
            tstr=str(row.get("time") or "")
            if not dstr or not tstr:continue
            try:
                d=dt.date.fromisoformat(dstr)
                hh,mm=map(int,tstr[:5].split(":"))
                ko=dt.datetime(d.year,d.month,d.day,hh,mm,
                    tzinfo=ZoneInfo(zone)).astimezone(dt.timezone.utc)
            except (TypeError,ValueError):continue
            local_date=ko.astimezone(ZoneInfo("America/New_York")).date()
            if not(today<=local_date<=today+dt.timedelta(days=days)):continue
            home=str(row.get("team1") or "").strip()
            away=str(row.get("team2") or "").strip()
            if not home or not away:continue
            mid="openfootball:"+code+":"+d.isoformat()+":"+slug(home)+":"+slug(away)
            out.append({"match_id":mid,"competition":league,
                "match":home+" vs "+away,"home_team":home,"away_team":away,
                "kickoff_utc":ko.isoformat(),"score":None,
                "status":"SCHEDULED_UNVERIFIED_TIME","state":"pre",
                "source":url,"schedule_quality":"COMMUNITY_SOURCE_NEEDS_CROSSCHECK",
                "observed_at_utc":now.isoformat()})
    return out,errors

def discover_fixtures(now,days=2):
    found={};errors={}
    nyday=now.astimezone(ZoneInfo("America/New_York")).date()
    for delta in range(days+1):
        day=nyday+dt.timedelta(days=delta)
        events,errs,observed=scores(day)
        errors.update({f"{day}:{k}":v for k,v in errs.items()})
        for x in events:
            ko=parse(x.get("kickoff_utc"))
            if ko is None:continue
            key=str(x.get("match_id"))
            # Record completed/live as contextual schedule but never backfill fair.
            found[key]={**x,"observed_at_utc":observed}
    if not found:
        fallback,more=fixtures_csv(now)
        for x in fallback:found[str(x["match_id"])]=x
        errors.update(more)
    if not found:
        fallback,more=openfootball_fixtures(now)
        for x in fallback:found[str(x["match_id"])]=x
        errors.update({"openfootball:"+k:v for k,v in more.items()})
    return sorted(found.values(),key=lambda x:x.get("kickoff_utc") or ""),errors
def main(now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    cfg=load("data/config.json",{})
    params=load("data/calibrated_params.json",{}).get("params") or {}
    fixtures,ferrors=discover_fixtures(now)
    hist,herrors=history_data(now)
    old=load("data/board.json",{})
    if not fixtures:
        save("data/v04_fixture_universe.json",{"updated_utc":now.isoformat(),
            "status":"FIXTURE_FEED_UNAVAILABLE_PREVIOUS_BOARD_RETAINED",
            "fixtures":[],"errors":{"schedule":ferrors,"history":herrors},
            "note":"Refuse to erase prior model/board data on a transient zero-fixture response."})
        print(json.dumps({"status":"FIXTURE_FEED_UNAVAILABLE_PREVIOUS_BOARD_RETAINED"}))
        return
    picks=[];model=[];allfixture=[]
    for f in fixtures:
        ko=parse(f.get("kickoff_utc"))
        if not ko:continue
        status="PREMATCH" if ko>now else "IN_PROGRESS_OR_COMPLETED"
        mid=f["match_id"]
        league=f["competition"]
        code=LEAGUE_CODES.get(league)
        rr=hist.get(code,[]) if code else []
        names={r["home"] for r in rr}|{r["away"] for r in rr}
        hm=translate(f.get("home_team"),names) if code else None
        aw=translate(f.get("away_team"),names) if code else None
        lp=lambdas(rr,hm,aw,ko,params) if status=="PREMATCH" and hm and aw else None
        note="MODELLED" if lp else ("NON_TOP_FIVE_LEAGUE_UNSUPPORTED" if not code else
             "MATCH_ALREADY_STARTED_NO_RETRO_PREDICTION" if status!="PREMATCH" else
             "MISSING_HISTORY_OR_TEAM_ALIAS")
        base={"match_id":mid,"competition":league,"match":f.get("match"),
              "home_team":f.get("home_team"),"away_team":f.get("away_team"),
              "kickoff_utc":f.get("kickoff_utc"),"fixture_source":f.get("source"),
              "observed_at_utc":f.get("observed_at_utc"),"state":f.get("state"),
              "schedule_quality":f.get("schedule_quality","PROVIDER_SCHEDULE_UNCROSSCHECKED"),
              "model_fair_status":note}
        allfixture.append(base)
        if status!="PREMATCH":continue
        pp=scores_from_grid(poisson_grid(lp[0],lp[1])) if lp else {}
        for market,selection in (
          ("1X2","HOME_WIN"),("1X2","DRAW"),("1X2","AWAY_WIN"),
          ("TOTALS_2_5","OVER_2_5"),("TOTALS_2_5","UNDER_2_5"),
          ("BTTS","BTTS_YES"),("BTTS","BTTS_NO")
        ):
            pid=mid+":"+selection
            fair=pp.get(selection)
            pick={"id":pid,"match_id":mid,"competition":league,
                  "match":f.get("match"),"home_team":f.get("home_team"),
                  "away_team":f.get("away_team"),"kickoff_utc":f.get("kickoff_utc"),
                  "market":market,"selection":selection,"fair_probability":fair,
                  "grade":"UNRATED","max_units":0,"status":"RESEARCH_ONLY_NO_VERIFIED_KALSHI_QUOTE",
                  "fair_source":"v0.4 independent goal model" if fair is not None else None}
            picks.append(pick)
            model.append({"pick_id":pid,"match_id":mid,"status":"MODELLED" if fair is not None else "INSUFFICIENT_DATA",
              "fair_probability":fair,"selection":selection,
              "lambda_home":round(lp[0],4) if lp else None,
              "lambda_away":round(lp[1],4) if lp else None,
              "model_version":"v0.4-independent-goals-research",
              "feature_snapshot_utc":now.isoformat(),
              "feature_cutoff_note":"Strictly before fixture calendar day; no current-day results",
              "feature_details":lp[2] if lp else {"reason":note},
              "calibrated_for":"Historical core 1X2 params only; TOTALS/BTTS not validated"})
    old.update({"updated":now.isoformat(),"picks":picks,
                "v04_status":"INDEPENDENT_RESEARCH_ONLY",
                "v04_note":"Model never sees Kalshi odds. Grades UNRATED until independent quote/mapping and additional validation."})
    save("data/board.json",old)
    save("data/model_fair.json",{"updated_utc":now.isoformat(),
        "model":"v0.4-independent-goals-research","calibrated_params_active":bool(params),
        "items":model,"limitations":"Historical 1X2 tuned parameters do not validate O/U/BTTS or demonstrate edge; old holdout 1X2 paper proxy lost money."})
    save("data/v04_fixture_universe.json",{"updated_utc":now.isoformat(),
         "fixtures":allfixture,"errors":{"schedule":ferrors,"history":herrors},
         "stats":{"fixtures":len(allfixture),"prospective_picks":len(picks),
         "modelled":sum(x["status"]=="MODELLED" for x in model),
         "unmapped_or_unsupported":sum(x["status"]!="MODELLED" for x in model)}})
    print(json.dumps({"fixtures":len(allfixture),"picks":len(picks),
                      "modelled":sum(x["status"]=="MODELLED" for x in model),
                      "fixture_errors":len(ferrors),"history_errors":len(herrors)}))
if __name__=="__main__":main()
