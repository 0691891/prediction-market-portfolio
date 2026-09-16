#!/usr/bin/env python3
"""Discover candidate Kalshi markets for board matches. Never auto-maps."""
import json, pathlib, urllib.request, urllib.parse, re, datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/"data"
STOP={"town","united","city","real","club","fc","vs","at","the"}
def tokens(s): return {x for x in re.findall(r"[a-z0-9]+",s.lower()) if len(x)>=4 and x not in STOP}
def fetch_open(base,max_pages=5):
    out=[]; cursor=None
    for _ in range(max_pages):
        q={"status":"open","limit":1000,"mve_filter":"exclude"}
        if cursor:q["cursor"]=cursor
        url=base+"/markets?"+urllib.parse.urlencode(q)
        with urllib.request.urlopen(url,timeout=30) as r:d=json.load(r)
        out+=d.get("markets",[]); cursor=d.get("cursor")
        if not cursor:break
    return out
def main():
    cfg=json.loads((DATA/"config.json").read_text()); board=json.loads((DATA/"board.json").read_text())
    markets=fetch_open(cfg["data_engine"]["kalshi_base_url"]); result=[]
    for p in board.get("picks",[]):
        need=tokens(p["match"]); cand=[]
        for m in markets:
            text=" ".join(str(m.get(k,"")) for k in ("title","subtitle","yes_sub_title","no_sub_title"))
            have=tokens(text); overlap=len(need&have)
            if overlap:
                score=overlap/max(1,len(need))
                cand.append({"ticker":m.get("ticker"),"title":m.get("title"),"subtitle":m.get("subtitle"),"yes_ask":m.get("yes_ask_dollars"),"liquidity":m.get("liquidity_dollars"),"score":round(score,3)})
        cand.sort(key=lambda x:(x["score"],float(x["liquidity"] or 0)),reverse=True)
        result.append({"pick_id":p.get("id"),"match":p["match"],"candidates":cand[:10]})
    (DATA/"market_candidates.json").write_text(json.dumps({"updated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"items":result},indent=2,ensure_ascii=False)+"\n")
if __name__=="__main__":main()
