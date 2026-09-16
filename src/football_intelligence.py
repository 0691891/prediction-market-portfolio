#!/usr/bin/env python3
"""v0.3.2 Football Intelligence Layer.
Builds reproducible team-strength/form/rest features from football-data.org.
No key => explicit NO_FOOTBALL_DATA_KEY; never invents features.
"""
import os,json,pathlib,urllib.request,urllib.parse,datetime,math,re
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; API="https://api.football-data.org/v4"
def read(n):return json.loads((DATA/n).read_text())
def write(n,o):(DATA/n).write_text(json.dumps(o,indent=2,ensure_ascii=False)+"\n")
def get(path,key):
    req=urllib.request.Request(API+path,headers={"X-Auth-Token":key})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def norm(s):return re.sub(r"[^a-z0-9]","",s.lower())
def decay(days,half):return math.exp(-math.log(2)*days/half)
def team_match(name,m):
    n=norm(name); h=norm(m["homeTeam"]["name"]); a=norm(m["awayTeam"]["name"])
    return "home" if (n in h or h in n) else ("away" if (n in a or a in n) else None)
def stats(team,matches,asof,half):
    rows=[]
    for m in matches:
        side=team_match(team,m)
        if not side or m.get("status")!="FINISHED":continue
        d=datetime.datetime.fromisoformat(m["utcDate"].replace("Z","+00:00")); age=max(0,(asof-d).total_seconds()/86400); w=decay(age,half)
        fs=m.get("score",{}).get("fullTime",{}); hg=fs.get("home"); ag=fs.get("away")
        if hg is None or ag is None:continue
        gf,ga=(hg,ag) if side=="home" else (ag,hg)
        rows.append((w,gf,ga,side,d.isoformat()))
    sw=sum(x[0] for x in rows)
    return {"matches":len(rows),"weighted_gf":round(sum(w*gf for w,gf,ga,s,d in rows)/sw,4) if sw else None,"weighted_ga":round(sum(w*ga for w,gf,ga,s,d in rows)/sw,4) if sw else None,"last_match_utc":max((d for *_,d in rows),default=None)}
def split_match(s):
    parts=re.split(r"\s+(?:vs\.?|v\.?|@)\s+",s,flags=re.I)
    return (parts[0].strip(),parts[1].strip()) if len(parts)>=2 else (None,None)
def main():
    cfg=read("config.json"); board=read("board.json"); fc=cfg["data_engine"]["football_intelligence"]; key=os.getenv(fc["api_key_env"]); now=datetime.datetime.now(datetime.timezone.utc)
    if not key:
        write("football_intelligence.json",{"updated_utc":now.isoformat(),"status":"NO_FOOTBALL_DATA_KEY","provider":fc["provider"],"items":[]});return
    cache={}; items=[]
    start=(now-datetime.timedelta(days=fc["lookback_days"])).date().isoformat(); end=now.date().isoformat()
    for p in board.get("picks",[]):
        code=fc["competition_codes"].get(p["competition"])
        home,away=split_match(p["match"])
        if not code or not home or not away:
            items.append({"pick_id":p.get("id"),"status":"COMPETITION_OR_MATCH_UNMAPPED"});continue
        if code not in cache:
            try:cache[code]=get(f"/competitions/{code}/matches?dateFrom={start}&dateTo={end}",key).get("matches",[])
            except Exception as e:cache[code]=[]
        ms=cache[code]; hs=stats(home,ms,now,fc["recent_half_life_days"]); aws=stats(away,ms,now,fc["recent_half_life_days"])
        all_finished=[m for m in ms if m.get("status")=="FINISHED" and m.get("score",{}).get("fullTime",{}).get("home") is not None]
        if all_finished:
            hg=sum(m["score"]["fullTime"]["home"] for m in all_finished)/len(all_finished); ag=sum(m["score"]["fullTime"]["away"] for m in all_finished)/len(all_finished)
        else:hg=ag=None
        def rest(last):
            if not last:return None
            return round((now-datetime.datetime.fromisoformat(last)).total_seconds()/86400,2)
        items.append({"pick_id":p.get("id"),"status":"OK" if hs["matches"] and aws["matches"] else "INSUFFICIENT_MATCH_HISTORY","competition":p["competition"],"home_team":home,"away_team":away,"league_home_goals_avg":round(hg,4) if hg else None,"league_away_goals_avg":round(ag,4) if ag else None,"home":hs,"away":aws,"home_rest_days":rest(hs["last_match_utc"]),"away_rest_days":rest(aws["last_match_utc"]),"source_fields":["finished scores","venue","recency","rest days"],"not_yet_automated":["xG/xGA","injuries/suspensions","confirmed lineup","tactical matchup","weather"]})
    write("football_intelligence.json",{"updated_utc":now.isoformat(),"status":"OK","provider":fc["provider"],"items":items})
if __name__=="__main__":main()
