#!/usr/bin/env python3
"""v0.3.3 walk-forward backtest + calibration.
No look-ahead: every prediction uses only matches completed before kickoff.
Fits hyperparameters on an earlier chronological train window, reports later holdout metrics.
"""
import os,json,pathlib,urllib.request,math,datetime,itertools
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; API="https://api.football-data.org/v4"
COMP={"PL":"Premier League","PD":"La Liga","SA":"Serie A","BL1":"Bundesliga","FL1":"Ligue 1"}
def write(n,o):(DATA/n).write_text(json.dumps(o,indent=2,ensure_ascii=False)+"\n")
def get(path,key):
    req=urllib.request.Request(API+path,headers={"X-Auth-Token":key})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def pois(k,l):return math.exp(-l)*l**k/math.factorial(k)
def p1x2(lh,la,maxg=8):
    z=[0.,0.,0.]
    for h in range(maxg+1):
      for a in range(maxg+1):
        p=pois(h,lh)*pois(a,la); z[0 if h>a else 1 if h==a else 2]+=p
    s=sum(z); return [x/s for x in z]
def outcome(h,a):return 0 if h>a else 1 if h==a else 2
def metrics(rows):
    if not rows:return {"n":0,"log_loss":None,"brier":None,"accuracy":None}
    ll=br=acc=0.
    for r in rows:
      y=r["y"]; p=r["p"]; ll-=math.log(max(1e-12,p[y])); br+=sum((p[i]-(1 if i==y else 0))**2 for i in range(3)); acc+=int(max(range(3),key=lambda i:p[i])==y)
    n=len(rows); return {"n":n,"log_loss":round(ll/n,5),"brier":round(br/n,5),"accuracy":round(acc/n,5)}
def calibration(rows):
    bins=[]
    for lo in [0,.1,.2,.3,.4,.5,.6,.7,.8,.9]:
      vals=[]
      for r in rows:
        for i in range(3):
          if lo<=r["p"][i]<(lo+.1 if lo<.9 else 1.00001):vals.append((r["p"][i],1 if r["y"]==i else 0))
      if vals:bins.append({"bin":f"{lo:.1f}-{min(1,lo+.1):.1f}","n":len(vals),"mean_pred":round(sum(x for x,y in vals)/len(vals),4),"actual":round(sum(y for x,y in vals)/len(vals),4)})
    return bins
def predict(history,home,away,asof,half,shrink,ha):
    if len(history)<30:return None
    league_g=sum(h+a for _,_,h,a in history)/max(1,2*len(history))
    def team(t):
      gf=ga=sw=0.
      for dt,hm,hg,ag in history:
        aw=hm[1]; hn=hm[0]
        if t!=hn and t!=aw:continue
        age=max(0,(asof-dt).total_seconds()/86400); w=math.exp(-math.log(2)*age/half)
        a,b=(hg,ag) if t==hn else (ag,hg); gf+=w*a;ga+=w*b;sw+=w
      if sw==0:return league_g,league_g,0
      return gf/sw,ga/sw,sw
    hgf,hga,hn=team(home); agf,aga,an=team(away)
    # effective weighted sample size is bounded for shrinkage stability
    hn=min(hn,30);an=min(an,30)
    hgf=(hn*hgf+shrink*league_g)/(hn+shrink); hga=(hn*hga+shrink*league_g)/(hn+shrink)
    agf=(an*agf+shrink*league_g)/(an+shrink); aga=(an*aga+shrink*league_g)/(an+shrink)
    lh=league_g*(hgf/league_g)*(aga/league_g)*math.exp(ha)
    la=league_g*(agf/league_g)*(hga/league_g)*math.exp(-ha)
    return p1x2(max(.15,min(4.5,lh)),max(.15,min(4.5,la)))
def rows_for(matches,param,start_i=0,end_i=None):
    half,shrink,ha=param; hist=[]; rows=[]; end_i=len(matches) if end_i is None else end_i
    for i,m in enumerate(matches):
      dt=datetime.datetime.fromisoformat(m["utcDate"].replace("Z","+00:00")); home=m["homeTeam"]["name"]; away=m["awayTeam"]["name"]; ft=m["score"]["fullTime"]; hg=ft["home"];ag=ft["away"]
      if hg is None or ag is None:continue
      if i>=start_i and i<end_i:
        p=predict(hist,home,away,dt,half,shrink,ha)
        if p:rows.append({"date":m["utcDate"],"home":home,"away":away,"p":p,"y":outcome(hg,ag)})
      hist.append((dt,(home,away),hg,ag))
    return rows
def main():
    key=os.getenv("FOOTBALL_DATA_API_KEY"); now=datetime.datetime.now(datetime.timezone.utc)
    if not key:
      write("backtest.json",{"updated_utc":now.isoformat(),"status":"NO_FOOTBALL_DATA_KEY","message":"Add FOOTBALL_DATA_API_KEY; no synthetic results generated."});return
    seasons=[now.year-3,now.year-2,now.year-1,now.year]
    allm=[]; errors=[]
    for code,name in COMP.items():
      lm=[]
      for season in seasons:
        try:
          ms=get(f"/competitions/{code}/matches?season={season}",key).get("matches",[])
          lm += [m for m in ms if m.get("status")=="FINISHED" and m.get("score",{}).get("fullTime",{}).get("home") is not None]
        except Exception as e: errors.append({"competition":code,"season":season,"error":str(e)[:120]})
      # de-duplicate across season requests
      uniq={m["id"]:m for m in lm}; lm=sorted(uniq.values(),key=lambda m:m["utcDate"])
      if lm:allm.append((code,name,lm))
    if not allm:
      write("backtest.json",{"updated_utc":now.isoformat(),"status":"NO_HISTORICAL_DATA","errors":errors});return
    grid=list(itertools.product([30,60,90,120],[4,8,12,16],[0.04,0.08,0.12,0.16]))
    # Per-league chronological 70/30 split; aggregate train loss chooses one global parameter set.
    scored=[]
    for param in grid:
      rr=[]
      for code,name,ms in allm:
        cut=int(len(ms)*.70); rr+=rows_for(ms,param,0,cut)
      met=metrics(rr); scored.append((met["log_loss"] if met["log_loss"] is not None else 999,param,met))
    scored.sort(key=lambda x:x[0]); best=scored[0][1]
    train_rows=[]; test_rows=[]; per=[]
    for code,name,ms in allm:
      cut=int(len(ms)*.70); tr=rows_for(ms,best,0,cut); te=rows_for(ms,best,cut,len(ms)); train_rows+=tr;test_rows+=te
      per.append({"competition":name,"train":metrics(tr),"holdout":metrics(te)})
    result={"updated_utc":now.isoformat(),"status":"VALIDATED" if len(test_rows)>=500 else "LIMITED_SAMPLE","method":"chronological 70/30 holdout; no look-ahead; global grid search on train only","seasons_requested":seasons,"best_params":{"recent_half_life_days":best[0],"shrinkage_matches":best[1],"home_advantage_log":best[2]},"train":metrics(train_rows),"holdout":metrics(test_rows),"calibration":calibration(test_rows),"per_competition":per,"data_errors":errors,"market_metrics":{"clv":"not available without historical closing odds","roi":"not available without historical entry odds"}}
    write("backtest.json",result)
    write("calibrated_params.json",{"updated_utc":now.isoformat(),"status":result["status"],"source":"v0.3.3 walk-forward train fit","params":result["best_params"],"holdout":result["holdout"],"minimum_holdout_for_activation":500,"active":len(test_rows)>=500})
if __name__=="__main__":main()
