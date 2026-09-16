#!/usr/bin/env python3
"""v0.3.3 transparent live fair-probability model.
Independent of sportsbook/Kalshi prices. Uses calibrated core params only after holdout activation.
"""
import json,pathlib,math,datetime,re
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/"data"
def read(n):return json.loads((DATA/n).read_text())
def write(n,o):(DATA/n).write_text(json.dumps(o,indent=2,ensure_ascii=False)+"\n")
def pois(k,l):return math.exp(-l)*l**k/math.factorial(k)
def shrink(rate,base,n,k):return (n*rate+k*base)/(n+k) if rate is not None else base
def rest_adj(a,b,cap=.08):
    if a is None or b is None:return 0
    return max(-cap,min(cap,0.018*(a-b)))
def probs(lh,la,maxg=8):
    z=[0.,0.,0.]
    for h in range(maxg+1):
      for a in range(maxg+1):
        p=pois(h,lh)*pois(a,la); z[0 if h>a else 1 if h==a else 2]+=p
    s=sum(z);return tuple(x/s for x in z)
def norm(s):return re.sub(r"[^a-z0-9]","",s.lower())
def market_prob(market,home,away,p1,lh,la,maxg=8):
    s=market.lower();ph,pd,pa=p1
    if "win" in s and norm(home) in norm(s):return ph
    if "win" in s and norm(away) in norm(s):return pa
    if "btts" in s or "both teams to score" in s:
      yes=sum(pois(h,lh)*pois(a,la) for h in range(1,maxg+1) for a in range(1,maxg+1))
      return 1-yes if "no" in s else yes
    mt=re.search(r"([+-]\d+(?:\.\d+)?)",s)
    team=home if norm(home) in norm(s) else (away if norm(away) in norm(s) else None)
    if mt and team:
      line=float(mt.group(1));out=0.
      for h in range(maxg+1):
       for a in range(maxg+1):
        margin=(h-a) if team==home else (a-h)
        if margin+line>0:out+=pois(h,lh)*pois(a,la)
      return out
    mt=re.search(r"(\d+(?:\.\d+)?)",s)
    if mt and ("over" in s or "under" in s):
      line=float(mt.group(1));out=0.
      for h in range(maxg+1):
       for a in range(maxg+1):
        total=h+a
        if ("over" in s and total>line) or ("under" in s and total<line):out+=pois(h,lh)*pois(a,la)
      return out
    return None
def main():
    cfg=read("config.json");board=read("board.json");intel=read("football_intelligence.json");manual=read("manual_adjustments.json")
    fc=dict(cfg["data_engine"]["fair_model"]); cp=read("calibrated_params.json") if (DATA/"calibrated_params.json").exists() else {"active":False}
    if cp.get("active"):
      pars=cp.get("params",{})
      for k in ("shrinkage_matches","home_advantage_log"):
        if k in pars:fc[k]=pars[k]
    iby={x.get("pick_id"):x for x in intel.get("items",[])};mby={x.get("pick_id"):x for x in manual.get("items",[])};outputs=[]
    for p in board.get("picks",[]):
      x=iby.get(p.get("id"));man=mby.get(p.get("id"),{})
      if not x or x.get("status")!="OK":
        outputs.append({"pick_id":p.get("id"),"status":"NO_MODEL_UPDATE","fair_probability":p.get("fair_probability"),"source":"existing research estimate"});continue
      bh=x["league_home_goals_avg"] or 1.45;ba=x["league_away_goals_avg"] or 1.15;base=(bh+ba)/2;k=fc["shrinkage_matches"]
      hg=shrink(x["home"]["weighted_gf"],base,x["home"]["matches"],k);hga=shrink(x["home"]["weighted_ga"],base,x["home"]["matches"],k)
      ag=shrink(x["away"]["weighted_gf"],base,x["away"]["matches"],k);aga=shrink(x["away"]["weighted_ga"],base,x["away"]["matches"],k)
      home_attack=hg/base;away_def=aga/base;away_attack=ag/base;home_def=hga/base
      lh=base*home_attack*away_def*math.exp(fc["home_advantage_log"]);la=base*away_attack*home_def*math.exp(-fc["home_advantage_log"])
      components={"team_strength_home_log":round(math.log(max(.01,home_attack*away_def)),4),"team_strength_away_log":round(math.log(max(.01,away_attack*home_def)),4),"home_advantage_log":fc["home_advantage_log"]}
      ra=rest_adj(x.get("home_rest_days"),x.get("away_rest_days"),fc["adjustment_caps_log_lambda"]["rest"]);lh*=math.exp(ra);la*=math.exp(-ra);components["relative_rest_home_log"]=round(ra,4)
      for key in ("recent_form","lineup","injuries","tactical","motivation","weather"):
        vals=man.get(key,{});cap=fc["adjustment_caps_log_lambda"][key];dh=max(-cap,min(cap,float(vals.get("home_log_lambda",0))));da=max(-cap,min(cap,float(vals.get("away_log_lambda",0))))
        lh*=math.exp(dh);la*=math.exp(da);components[key+"_home_log"]=dh;components[key+"_away_log"]=da
      lh=max(.15,min(4.5,lh));la=max(.15,min(4.5,la));p1=probs(lh,la,fc["max_goals"]);fair=market_prob(p["market"],x["home_team"],x["away_team"],p1,lh,la,fc["max_goals"])
      outputs.append({"pick_id":p.get("id"),"status":"MODELLED","lambda_home":round(lh,4),"lambda_away":round(la,4),"home_win":round(p1[0],4),"draw":round(p1[1],4),"away_win":round(p1[2],4),"fair_probability":round(fair,4) if fair is not None else None,"components":components,"manual_notes":man.get("notes",[]),"market_prices_used_in_fair":False,"calibrated_params_active":bool(cp.get("active"))})
      if fair is not None:p["fair_probability"]=round(fair,4);p["fair_source"]="v0.3.3 calibrated football model" if cp.get("active") else "v0.3.3 uncalibrated football model"
    board["updated"]=datetime.datetime.now(datetime.timezone.utc).isoformat();write("board.json",board);write("model_fair.json",{"updated_utc":board["updated"],"model":"v0.3.3 Poisson goal-space model","calibrated_params_active":bool(cp.get("active")),"items":outputs})
if __name__=="__main__":main()
