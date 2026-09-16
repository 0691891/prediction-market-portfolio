#!/usr/bin/env python3
"""v0.3.2 transparent fair-probability model.
Goal-space model: base scoring rates -> multiplicative attack/defense strengths -> log-lambda adjustments -> Poisson score matrix.
Sportsbook/Kalshi prices are NOT inputs to My Fair.
"""
import json,pathlib,math,datetime,re
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/"data"
def read(n):return json.loads((DATA/n).read_text())
def write(n,o):(DATA/n).write_text(json.dumps(o,indent=2,ensure_ascii=False)+"\n")
def pois(k,l):return math.exp(-l)*l**k/math.factorial(k)
def shrink(rate,base,n,k):return (n*rate+k*base)/(n+k) if rate is not None else base
def rest_adj(a,b,cap=.08):
    # relative rest only; 4+ days treated as broadly normal
    if a is None or b is None:return 0
    return max(-cap,min(cap,0.018*(a-b)))
def probs(lh,la,maxg=8):
    ph=pd=pa=0
    for h in range(maxg+1):
      for a in range(maxg+1):
        p=pois(h,lh)*pois(a,la)
        if h>a:ph+=p
        elif h==a:pd+=p
        else:pa+=p
    s=ph+pd+pa; return ph/s,pd/s,pa/s
def market_prob(market,home,away,p1x2,lh,la,maxg=8):
    s=market.lower(); ph,pd,pa=p1x2
    if "win" in s and norm(home) in norm(s):return ph
    if "win" in s and norm(away) in norm(s):return pa
    # Asian -1.5 / +1.5 etc as binary cover probability
    mt=re.search(r"([+-]\d+(?:\.\d+)?)",s)
    team=home if norm(home) in norm(s) else (away if norm(away) in norm(s) else None)
    if mt and team:
      line=float(mt.group(1)); out=0
      for h in range(maxg+1):
       for a in range(maxg+1):
        p=pois(h,lh)*pois(a,la); margin=(h-a) if team==home else (a-h)
        if margin+line>0:out+=p
      return out
    mt=re.search(r"(\d+(?:\.\d+)?)",s)
    if mt and ("over" in s or "under" in s):
      line=float(mt.group(1)); out=0
      for h in range(maxg+1):
       for a in range(maxg+1):
        p=pois(h,lh)*pois(a,la); total=h+a
        if ("over" in s and total>line) or ("under" in s and total<line):out+=p
      return out
    return None
def norm(s):return re.sub(r"[^a-z0-9]","",s.lower())
def main():
    cfg=read("config.json"); board=read("board.json"); intel=read("football_intelligence.json"); manual=read("manual_adjustments.json")
    fc=cfg["data_engine"]["fair_model"]; iby={x.get("pick_id"):x for x in intel.get("items",[])}; mby={x.get("pick_id"):x for x in manual.get("items",[])}
    outputs=[]
    for p in board.get("picks",[]):
      x=iby.get(p.get("id")); man=mby.get(p.get("id"),{})
      if not x or x.get("status")!="OK":
        outputs.append({"pick_id":p.get("id"),"status":"NO_MODEL_UPDATE","fair_probability":p.get("fair_probability"),"source":"existing research estimate"});continue
      bh=x["league_home_goals_avg"] or 1.45; ba=x["league_away_goals_avg"] or 1.15; k=fc["shrinkage_matches"]
      hg=shrink(x["home"]["weighted_gf"],bh,x["home"]["matches"],k); hga=shrink(x["home"]["weighted_ga"],ba,x["home"]["matches"],k)
      ag=shrink(x["away"]["weighted_gf"],ba,x["away"]["matches"],k); aga=shrink(x["away"]["weighted_ga"],bh,x["away"]["matches"],k)
      home_attack=hg/bh; away_def=aga/bh; away_attack=ag/ba; home_def=hga/ba
      lh=bh*home_attack*away_def*math.exp(fc["home_advantage_log"]); la=ba*away_attack*home_def
      components={"team_strength_home_log":round(math.log(max(.01,home_attack*away_def)),4),"team_strength_away_log":round(math.log(max(.01,away_attack*home_def)),4),"home_advantage_log":fc["home_advantage_log"]}
      ra=rest_adj(x.get("home_rest_days"),x.get("away_rest_days"),fc["adjustment_caps_log_lambda"]["rest"]); lh*=math.exp(ra); la*=math.exp(-ra); components["relative_rest_home_log"]=round(ra,4)
      # Manual/research adjustments are explicit bounded log-lambda deltas, never hidden.
      for key in ("recent_form","lineup","injuries","tactical","motivation","weather"):
        vals=man.get(key,{}); cap=fc["adjustment_caps_log_lambda"][key]
        dh=max(-cap,min(cap,float(vals.get("home_log_lambda",0)))); da=max(-cap,min(cap,float(vals.get("away_log_lambda",0))))
        lh*=math.exp(dh); la*=math.exp(da); components[key+"_home_log"]=dh; components[key+"_away_log"]=da
      lh=max(.15,min(4.5,lh)); la=max(.15,min(4.5,la)); p1=probs(lh,la,fc["max_goals"]); fair=market_prob(p["market"],x["home_team"],x["away_team"],p1,lh,la,fc["max_goals"])
      outputs.append({"pick_id":p.get("id"),"status":"MODELLED","lambda_home":round(lh,4),"lambda_away":round(la,4),"home_win":round(p1[0],4),"draw":round(p1[1],4),"away_win":round(p1[2],4),"fair_probability":round(fair,4) if fair is not None else None,"components":components,"manual_notes":man.get("notes",[]),"market_prices_used_in_fair":False,"calibrated_params_active":bool(cp.get("active"))})
      if fair is not None:p["fair_probability"]=round(fair,4); p["fair_source"]="v0.3.2 football intelligence model"
    board["updated"]=datetime.datetime.now(datetime.timezone.utc).isoformat(); write("board.json",board); write("model_fair.json",{"updated_utc":board["updated"],"model":"v0.3.3 Poisson + shrunk recency-weighted team attack/defense + calibrated core when validated + bounded research adjustments","items":outputs})
if __name__=="__main__":main()
