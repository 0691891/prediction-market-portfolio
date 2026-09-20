#!/usr/bin/env python3
"""Sportsbook consensus engine. Read-only. Uses The Odds API when ODDS_API_KEY is set."""
import os,json,pathlib,urllib.request,urllib.parse,statistics,re,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/"data"
API="https://api.the-odds-api.com/v4"
ALIASES={"EFL Cup":["EFL Cup","League Cup"],"EFL/Carabao Cup":["EFL Cup","League Cup"],"UEFA Champions League":["UEFA Champions League","Champions League"]}
def read(n):return json.loads((DATA/n).read_text())
def write(n,o):(DATA/n).write_text(json.dumps(o,indent=2,ensure_ascii=False)+"\n")
def get(url):
    with urllib.request.urlopen(url,timeout=30) as r:return json.load(r)
def norm(s):return re.sub(r"[^a-z0-9]","",s.lower())
def match_event(p,e):
    parts=re.split(r"\s+(?:vs\.?|v\.?|@)\s+",p["match"],maxsplit=1,flags=re.I)
    if len(parts)<2:return False
    a,b=[norm(x.strip()) for x in parts]
    h,a2=norm(e["home_team"]),norm(e["away_team"])
    return (a in h or h in a or a in a2 or a2 in a) and (b in h or h in b or b in a2 or a2 in b)
def de_vig(prices):
    inv=[1/x for x in prices]; s=sum(inv); return [x/s for x in inv]
def infer_pick(p,outcomes):
    m=p["market"].lower()
    selection=str(p.get("selection") or "").upper()
    if selection=="HOME_WIN":
        return next((i for i,o in enumerate(outcomes) if norm(o.get("name",""))==norm(p.get("home_team",""))),None)
    if selection=="AWAY_WIN":
        return next((i for i,o in enumerate(outcomes) if norm(o.get("name",""))==norm(p.get("away_team",""))),None)
    if selection=="DRAW":
        return next((i for i,o in enumerate(outcomes) if o.get("name","").lower()=="draw"),None)
    for i,o in enumerate(outcomes):
        if o["name"].lower()!="draw" and norm(o["name"]) in norm(m): return i
    if "draw" in m:
        for i,o in enumerate(outcomes):
            if o["name"].lower()=="draw":return i
    return None
def market_consensus(p,event):
    vals=[]; sources=[]
    if p.get("market") in ("TOTALS_2_5","BTTS"):
        # Legacy sportsbook parser expects "Over 2.5"/"Under 2.5";
        # do not accidentally treat BTTS as h2h or label it as a price.
        if p.get("market")=="BTTS":return None
        p=dict(p)
        p["market"]="Over 2.5" if p.get("selection")=="OVER_2_5" else "Under 2.5"
    want="spreads" if re.search(r"[+-]\d",p["market"]) else ("totals" if "over" in p["market"].lower() or "under" in p["market"].lower() else "h2h")
    for book in event.get("bookmakers",[]):
        for mk in book.get("markets",[]):
            if mk.get("key")!=want:continue
            outs=mk.get("outcomes",[])
            if want=="h2h" and len(outs)>=2:
                idx=infer_pick(p,outs)
                if idx is None:continue
                probs=de_vig([float(o["price"]) for o in outs]); vals.append(probs[idx]); sources.append(book["title"])
            elif want=="spreads":
                mt=re.search(r"([+-]\d+(?:\.\d+)?)",p["market"])
                if not mt:continue
                point=float(mt.group(1)); candidates=[o for o in outs if float(o.get("point",999))==point and norm(o["name"]) in norm(p["market"])]
                if not candidates:continue
                target=candidates[0]; opp=[o for o in outs if float(o.get("point",999))==-point]
                if not opp:continue
                probs=de_vig([float(target["price"]),float(opp[0]["price"])]); vals.append(probs[0]); sources.append(book["title"])
            elif want=="totals":
                mt=re.search(r"(\d+(?:\.\d+)?)",p["market"]); direction="over" if "over" in p["market"].lower() else "under"
                if not mt:continue
                point=float(mt.group(1)); pair=[o for o in outs if float(o.get("point",999))==point]
                if len(pair)!=2:continue
                target=[o for o in pair if o["name"].lower()==direction]
                if not target:continue
                other=[o for o in pair if o is not target[0]][0]
                vals.append(de_vig([float(target[0]["price"]),float(other["price"])])[0]); sources.append(book["title"])
    if not vals:return None
    return {"consensus_probability":round(statistics.median(vals),4),"book_count":len(vals),"min_probability":round(min(vals),4),"max_probability":round(max(vals),4),"books":sources}
def main():
    key=os.getenv("ODDS_API_KEY"); board=read("board.json"); cfg=read("config.json"); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not key:
        write("sportsbook_consensus.json",{"updated_utc":now,"status":"NO_ODDS_API_KEY","provider":"The Odds API v4","items":[]});return
    sports=get(f"{API}/sports/?apiKey={urllib.parse.quote(key)}")
    by_title={s["title"]:s["key"] for s in sports if s.get("active")}; cache={}; items=[]
    for p in board.get("picks",[]):
        names=ALIASES.get(p["competition"],[p["competition"]]); sk=next((by_title.get(n) for n in names if by_title.get(n)),None)
        if not sk:
            for title,k in by_title.items():
                if norm(p["competition"]) in norm(title) or norm(title) in norm(p["competition"]):sk=k;break
        if not sk:
            items.append({"pick_id":p.get("id"),"status":"SPORT_NOT_MAPPED"});continue
        if sk not in cache:
            q=urllib.parse.urlencode({"apiKey":key,"regions":cfg["data_engine"]["sportsbook"]["regions"],"markets":cfg["data_engine"]["sportsbook"]["markets"],"oddsFormat":"decimal"})
            try:cache[sk]=get(f"{API}/sports/{sk}/odds/?{q}")
            except Exception:cache[sk]=[]
        ev=next((e for e in cache[sk] if match_event(p,e)),None)
        if not ev:items.append({"pick_id":p.get("id"),"sport_key":sk,"status":"EVENT_NOT_FOUND"});continue
        meta={"sport_key":sk,"event_id":ev["id"],"commence_time":ev.get("commence_time"),"home_team":ev.get("home_team"),"away_team":ev.get("away_team")}
        c=market_consensus(p,ev)
        if not c:items.append({"pick_id":p.get("id"),**meta,"status":"MARKET_NOT_MATCHED"});continue
        fair=p.get("fair_probability")
        items.append({"pick_id":p.get("id"),**meta,"status":"OK",**c,"model_probability":fair,"model_vs_consensus_pp":round(fair-c["consensus_probability"],4) if isinstance(fair,(int,float)) else None})
    write("sportsbook_consensus.json",{"updated_utc":now,"status":"OK","provider":"The Odds API v4","method":"median de-vig probability","items":items})
if __name__=="__main__":main()
