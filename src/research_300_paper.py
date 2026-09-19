#!/usr/bin/env python3
"""Prospective 300-fixture market-baseline paper control; never real orders.

One 1X2 virtual entry per fixture, T-120m to kickoff, only with timestamped
pre-kickoff sportsbook quote. Freeze input before result. No invented residual.
"""
import datetime as dt,json,pathlib,os,sys,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"dashboard"))
from live_feed import odds,scores
from residual_pricing import devig
PAPER=ROOT/"paper"
TARGET=300
def read(name,default):
 p=PAPER/name
 return json.loads(p.read_text()) if p.exists() else default
def write(name,obj):(PAPER/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
def utc(x):return dt.datetime.fromisoformat(x.replace("Z","+00:00")).astimezone(dt.timezone.utc)
def norm(s):return re.sub(r"[^a-z0-9]","",str(s).lower())
def main():
 now=dt.datetime.now(dt.timezone.utc)
 key=os.getenv("ODDS_API_KEY")
 rows,errors,fetched=odds(key,"us,uk,eu")
 signals=read("signals.json",{"signals":[]})
 existing={s["match_id"] for s in signals["signals"] if s.get("cohort")=="ALL_MATCHES_300_RESEARCH"}
 state=read("state.json",{"trades":[]})
 existing.update(t["match_id"] for t in state["trades"] if t.get("cohort")=="ALL_MATCHES_300_RESEARCH")
 by={}
 for r in rows:
  if r["market"]!="h2h":continue
  try:
   ko=utc(r["kickoff_utc"]);qt=utc(r["quote_timestamp_utc"])
   if not (now<=ko<=now+dt.timedelta(minutes=120) and qt<ko and dt.timedelta(0)<=now-qt<=dt.timedelta(minutes=30)):continue
  except Exception:continue
  mid="odds:"+str(r["event_id"])
  if mid in existing:continue
  by.setdefault(mid,[]).append(r)
 added=0
 for mid,rr in sorted(by.items(),key=lambda x:x[1][0]["kickoff_utc"]):
  if len(existing)>=TARGET:break
  # Same book, same 1X2 market, all three outcomes and fresh synchronized quotes.
  for book in sorted({r["bookmaker"] for r in rr}):
   group=[r for r in rr if r["bookmaker"]==book]
   home=group[0]["home_team"];away=group[0]["away_team"]
   h=next((r for r in group if norm(r["selection"])==norm(home)),None)
   a=next((r for r in group if norm(r["selection"])==norm(away)),None)
   d=next((r for r in group if norm(r["selection"])=="draw"),None)
   if not all((h,d,a)):continue
   ts=[utc(x["quote_timestamp_utc"]) for x in (h,d,a)]
   if max(ts)-min(ts)>dt.timedelta(minutes=5):continue
   prior=devig([h["decimal_odds"],d["decimal_odds"],a["decimal_odds"]])
   # Deterministic control: highest market-implied probability; ties H,D,A.
   j=max(range(3),key=lambda i:prior[i]);pick=[h,d,a][j]
   # If fixture appears already in existing state, never backfill or re-enter.
   signal={"signal_id":"research-300:"+str(rr[0]["event_id"]),
    "match_id":mid,"match":home+" vs "+away,"competition":pick["competition"],
    "market":"1X2","market_id":"1X2-90m","selection":pick["selection"],
    "quote_timestamp_utc":pick["quote_timestamp_utc"],
    "quote_source":"The Odds API / "+book,"quote_url":"https://the-odds-api.com/",
    "kickoff_utc":pick["kickoff_utc"],"model_version":"v0.5-market-baseline-control",
    "scenario":"One paper position per match; untrained residual = 0; no claimed alpha",
    "cohort":"ALL_MATCHES_300_RESEARCH","entry_reason":"FORCED_RESEARCH_COHORT_NOT_POSITIVE_EV",
    "fair_probability":round(prior[j],8),"market_probability":round(prior[j],8),
    "decimal_odds":pick["decimal_odds"],"stake_usd":100,"grade":"C",
    "fees_usd":0,"entry_phase":"PREMATCH","paper_eligible":True,
    "research_features_status":"PIT_xG_lineup_injury_tactics_not_available",
    "model_training_eligible":False}
   signals["signals"].append(signal);existing.add(mid);added+=1;break
 write("signals.json",signals)
 # Results from ESPN scoreboard; only exact normalized home/away match and final state.
 observations=read("observations.json",{"observations":[]}).get("observations",[])
 final={}
 for x in observations:
  if x.get("state")!="post" or x.get("home_score") is None or x.get("away_score") is None:continue
  k=(norm(x.get("home_team")),norm(x.get("away_team")),str(x.get("kickoff_utc"))[:10])
  final[k]=x
 results=read("results.json",{"results":[]})
 settled={(x.get("match_id"),x.get("market_id"),x.get("selection")) for x in results["results"]}
 for s in signals["signals"]:
  if s.get("cohort")!="ALL_MATCHES_300_RESEARCH":continue
  names=s["match"].split(" vs ",1)
  if len(names)!=2:continue
  x=final.get((norm(names[0]),norm(names[1]),s["kickoff_utc"][:10]))
  if not x:continue
  key=(s["match_id"],s["market_id"],s["selection"])
  if key in settled:continue
  try:
   hg=int(x["home_score"]);ag=int(x["away_score"])
   if hg==ag:win=norm(s["selection"])=="draw"
   else:win=norm(s["selection"])==norm(names[0] if hg>ag else names[1])
   observed=utc(x["observed_at_utc"])
   if observed<=utc(s["kickoff_utc"]):continue
  except Exception:continue
  results["results"].append({"match_id":s["match_id"],"market_id":s["market_id"],
   "selection":s["selection"],"outcome":"WIN" if win else "LOSS",
   "result_source":x.get("url") or "ESPN scoreboard",
   "verified_at_utc":x["observed_at_utc"]})
  settled.add(key)
 write("results.json",results)
 write("research_300_status.json",{"updated_utc":now.isoformat(),"target":TARGET,
  "fixtures_with_signal":len(existing),"new_signals":added,
  "settlements_available":len([r for r in results["results"] if str(r.get("match_id","")).startswith("odds:")]),
  "status":"COLLECTING" if key else "NO_ODDS_API_KEY",
  "provider_errors":errors,
  "warning":"One per match is a market-baseline control, not trained residual alpha. Paper fills are simulated from observed quotes; no real-money orders. Historical records cannot be used as ex-ante xG/lineup/tactics features unless those features were frozen before kickoff."})
 print("research cohort",len(existing),"added",added)
if __name__=="__main__":main()
