#!/usr/bin/env python3
"""500-match no-lookahead football pricing + paper-execution backtest.

Train/tune: 2024/25 only.
Holdout: 2025/26, first 100 completed league matches from each of EPL, La Liga,
Serie A, Bundesliga and Ligue 1 (up to 500 matches total).
"""
import csv, io, json, math, pathlib, urllib.request, itertools, datetime as dt
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/"data"
LEAGUES={"E0":"Premier League","SP1":"La Liga","I1":"Serie A","D1":"Bundesliga","F1":"Ligue 1"}
TRAIN_SEASON="2425"; TEST_SEASON="2526"; TEST_PER_LEAGUE=100; MIN_NET_EV=0.05; STAKE_USD=100.0
def write(name,obj):(DATA/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n")
def fetch_csv(season,code):
    url=f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 football-alpha-research"})
    with urllib.request.urlopen(req,timeout=30) as r: raw=r.read().decode("utf-8-sig","replace")
    out=[]
    for i,x in enumerate(csv.DictReader(io.StringIO(raw))):
        try:hg=int(x["FTHG"]);ag=int(x["FTAG"])
        except Exception:continue
        try:d=dt.datetime.strptime(x.get("Date") or "","%d/%m/%Y").replace(tzinfo=dt.timezone.utc)
        except Exception:
            try:d=dt.datetime.strptime(x.get("Date") or "","%d/%m/%y").replace(tzinfo=dt.timezone.utc)
            except Exception:continue
        out.append({"date":d,"home":x.get("HomeTeam"),"away":x.get("AwayTeam"),"hg":hg,"ag":ag,"raw":x,"row":i})
    out.sort(key=lambda z:(z["date"],z["row"]));return out,url
def pois(k,l):return math.exp(-l)*l**k/math.factorial(k)
def p1x2(lh,la,maxg=8):
    z=[0.,0.,0.]
    for h in range(maxg+1):
      for a in range(maxg+1):
        p=pois(h,lh)*pois(a,la);z[0 if h>a else 1 if h==a else 2]+=p
    s=sum(z);return [x/s for x in z]
def outcome(h,a):return 0 if h>a else 1 if h==a else 2
def predict(history,home,away,asof,half,shrink,ha):
    if len(history)<30:return None
    league_g=sum(h+a for _,_,_,h,a in history)/max(1,2*len(history))
    def team(t):
      gf=ga=sw=0.
      for when,hm,aw,hg,ag in history:
        if t!=hm and t!=aw:continue
        age=max(0,(asof-when).total_seconds()/86400);w=math.exp(-math.log(2)*age/half)
        a,b=(hg,ag) if t==hm else (ag,hg);gf+=w*a;ga+=w*b;sw+=w
      if sw==0:return league_g,league_g,0
      return gf/sw,ga/sw,min(sw,30)
    hgf,hga,hn=team(home);agf,aga,an=team(away)
    hgf=(hn*hgf+shrink*league_g)/(hn+shrink);hga=(hn*hga+shrink*league_g)/(hn+shrink)
    agf=(an*agf+shrink*league_g)/(an+shrink);aga=(an*aga+shrink*league_g)/(an+shrink)
    lh=league_g*(hgf/league_g)*(aga/league_g)*math.exp(ha)
    la=league_g*(agf/league_g)*(hga/league_g)*math.exp(-ha)
    return p1x2(max(.15,min(4.5,lh)),max(.15,min(4.5,la)))
def metric(rows):
    if not rows:return {"n":0,"log_loss":None,"brier":None,"accuracy":None}
    ll=br=acc=0.
    for r in rows:
      y,p=r["y"],r["p"];ll-=math.log(max(1e-12,p[y]));br+=sum((p[i]-(1 if i==y else 0))**2 for i in range(3));acc+=int(max(range(3),key=lambda i:p[i])==y)
    n=len(rows);return {"n":n,"log_loss":round(ll/n,5),"brier":round(br/n,5),"accuracy":round(acc/n,5)}
def closing_odds(raw):
    for ks in [("AvgCH","AvgCD","AvgCA"),("AvgH","AvgD","AvgA"),("B365CH","B365CD","B365CA"),("B365H","B365D","B365A"),("PSCH","PSCD","PSCA"),("PSH","PSD","PSA")]:
      try:
        vals=[float(raw[k]) for k in ks]
        if all(v>1 for v in vals):return vals,ks
      except Exception:pass
    return None,None
def evaluate(param,train,test,league):
    half,shrink,ha=param;hist=[(m["date"],m["home"],m["away"],m["hg"],m["ag"]) for m in train];rows=[];trades=[];equity=peak=maxdd=0.
    for m in test[:TEST_PER_LEAGUE]:
      p=predict(hist,m["home"],m["away"],m["date"],half,shrink,ha)
      if p:
        y=outcome(m["hg"],m["ag"]);rows.append({"league":league,"date":m["date"].isoformat(),"home":m["home"],"away":m["away"],"p":p,"y":y})
        odds,src=closing_odds(m["raw"])
        if odds:
          ev=[p[i]*odds[i]-1 for i in range(3)];i=max(range(3),key=lambda k:ev[k])
          if ev[i]>=MIN_NET_EV:
            pnl=STAKE_USD*(odds[i]-1) if y==i else -STAKE_USD;equity+=pnl;peak=max(peak,equity);maxdd=max(maxdd,peak-equity)
            trades.append({"league":league,"date":m["date"].date().isoformat(),"match":m["home"]+" vs "+m["away"],"selection":["H","D","A"][i],"fair":round(p[i],6),"closing_odds":odds[i],"entry_ev":round(ev[i],6),"result":"WIN" if y==i else "LOSS","pnl_usd":round(pnl,2),"odds_source":"/".join(src)})
      hist.append((m["date"],m["home"],m["away"],m["hg"],m["ag"]))
    return rows,trades,maxdd
def calibration(rows):
    bins=[]
    for lo in [0,.1,.2,.3,.4,.5,.6,.7,.8,.9]:
      vals=[]
      for r in rows:
        for i in range(3):
          hi=lo+.1 if lo<.9 else 1.00001
          if lo<=r["p"][i]<hi:vals.append((r["p"][i],1 if r["y"]==i else 0))
      if vals:bins.append({"bin":f"{lo:.1f}-{min(1,lo+.1):.1f}","n":len(vals),"mean_pred":round(sum(x for x,y in vals)/len(vals),4),"actual":round(sum(y for x,y in vals)/len(vals),4)})
    return bins
def main():
    now=dt.datetime.now(dt.timezone.utc);datasets={};sources={};errors=[]
    for code,name in LEAGUES.items():
      try:
        tr,u1=fetch_csv(TRAIN_SEASON,code);te,u2=fetch_csv(TEST_SEASON,code);datasets[code]=(name,tr,te);sources[code]={"train":u1,"holdout":u2,"train_matches":len(tr),"holdout_matches_available":len(te)}
      except Exception as e:errors.append({"league":name,"error":str(e)[:180]})
    if len(datasets)<3:
      write("backtest.json",{"updated_utc":now.isoformat(),"status":"DATA_FETCH_FAILED","errors":errors,"sources":sources});return
    grid=list(itertools.product([30,60,90,120],[4,8,12,16],[0.04,0.08,0.12,0.16]));scored=[]
    for param in grid:
      rr=[]
      for code,(name,tr,te) in datasets.items():
        hist=[]
        for m in tr:
          p=predict(hist,m["home"],m["away"],m["date"],*param)
          if p:rr.append({"y":outcome(m["hg"],m["ag"]),"p":p})
          hist.append((m["date"],m["home"],m["away"],m["hg"],m["ag"]))
      met=metric(rr);scored.append((met["log_loss"] if met["log_loss"] is not None else 999,param,met))
    scored.sort(key=lambda x:x[0]);best=scored[0][1]
    allrows=[];alltrades=[];per=[];dd=[]
    for code,(name,tr,te) in datasets.items():
      rows,trades,maxdd=evaluate(best,tr,te,name);allrows+=rows;alltrades+=trades;dd.append(maxdd);pnl=sum(x["pnl_usd"] for x in trades);stake=STAKE_USD*len(trades)
      per.append({"competition":name,"holdout":metric(rows),"paper_trades":len(trades),"wins":sum(x["result"]=="WIN" for x in trades),"paper_pnl_usd":round(pnl,2),"paper_roi":round(pnl/stake,6) if stake else None})
    pnl=sum(x["pnl_usd"] for x in alltrades);stake=STAKE_USD*len(alltrades);wins=sum(x["result"]=="WIN" for x in alltrades)
    result={"updated_utc":now.isoformat(),"status":"VALIDATED_500" if len(allrows)>=500 else "LIMITED_SAMPLE","method":"2024/25 train-only grid search; 2025/26 chronological holdout; max 100 matches per league; no look-ahead","data_source":"Football-Data.co.uk historical results + closing 1X2 odds","sources":sources,"data_errors":errors,"best_params":{"recent_half_life_days":best[0],"shrinkage_matches":best[1],"home_advantage_log":best[2]},"train_selection_metric":scored[0][2],"holdout":metric(allrows),"holdout_target":500,"calibration":calibration(allrows),"paper_execution":{"rule":f"one 1X2 selection per match when model EV >= {MIN_NET_EV:.0%}; flat USD {STAKE_USD:.0f} stake; historical closing odds","trades":len(alltrades),"wins":wins,"losses":len(alltrades)-wins,"hit_rate":round(wins/len(alltrades),6) if alltrades else None,"stake_usd":round(stake,2),"pnl_usd":round(pnl,2),"roi":round(pnl/stake,6) if stake else None,"max_drawdown_usd_approx":round(max(dd) if dd else 0,2),"trade_log":alltrades},"per_competition":per,"limitations":["Backtest covers the machine 1X2 scoring core, not discretionary tactical/lineup overrides because historical point-in-time versions are unavailable.","Historical closing odds approximate executable prices; transaction costs, limits and slippage are not modeled.","500 holdout matches are an initial diagnostic, not proof of durable alpha."]}
    write("backtest.json",result);write("calibrated_params.json",{"updated_utc":now.isoformat(),"status":result["status"],"source":"500-match public-data holdout","params":result["best_params"],"holdout":result["holdout"],"minimum_holdout_for_activation":500,"active":len(allrows)>=500})
if __name__=="__main__":main()
