#!/usr/bin/env python3
"""v0.3.6 transparent live fair-probability model.
Independent of sportsbook/Kalshi prices. Uses calibrated core params only after holdout activation.

v0.3.5 added relative-squad context for cup rotation.\nv0.3.6 adds probability-first portfolio classification for Core Parlay candidates. A rotated elite XI is evaluated
against the opponent actually faced, not only against the elite club's own first XI.
The new terms are transparent priors and must be backtested; one match result never
retroactively determines a coefficient.
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
def bounded(v,cap):return max(-cap,min(cap,float(v)))
def rotation_resilient_lineup(raw,depth_mismatch,resilience):
    """Soften a negative rotation penalty when the rotated squad still has a large
    quality/depth edge over the actual opponent. depth_mismatch is research input
    in [0,1], assessed pre-match. Positive lineup upgrades are unchanged."""
    raw=float(raw); d=max(0.,min(1.,float(depth_mismatch or 0.)))
    return raw*(1-resilience*d) if raw<0 else raw

def portfolio_bucket(fair,market_p,cfg):
    """Classify after My Fair is produced; never feed market price back into My Fair."""
    if fair is None:return {"bucket":"UNCLASSIFIED","core_parlay_eligible":False,"reason":"no fair probability"}
    pcfg=cfg.get("data_engine",{}).get("core_parlay",{})
    if not pcfg:return {"bucket":"UNCLASSIFIED","core_parlay_eligible":False,"reason":"core parlay config missing"}
    f=float(fair)
    if market_p is None:
      if f>=pcfg.get("leg_fair_probability_min",.68):return {"bucket":"CORE_REVIEW","core_parlay_eligible":False,"reason":"high fair probability; current market probability required for price/edge gate"}
      if f>=pcfg.get("value_single_fair_range",[.55,.68])[0]:return {"bucket":"VALUE_SINGLE","core_parlay_eligible":False,"reason":"below core fair threshold"}
      return {"bucket":"SPECULATIVE_OR_PASS","core_parlay_eligible":False,"reason":"low hit-rate; not a core parlay leg"}
    mp=float(market_p); edge=f-mp
    eligible=(mp>=pcfg.get("leg_market_probability_min",.65) and f>=pcfg.get("leg_fair_probability_min",.68) and edge>=pcfg.get("min_model_edge_pp",.03))
    if eligible:return {"bucket":"CORE_PARLAY","core_parlay_eligible":True,"reason":"passes probability + positive-edge gates","model_edge_pp":round(edge,4)}
    if f>=pcfg.get("value_single_fair_range",[.55,.68])[0]:return {"bucket":"VALUE_SINGLE_OR_PASS","core_parlay_eligible":False,"reason":"does not pass all core gates","model_edge_pp":round(edge,4)}
    return {"bucket":"SPECULATIVE_OR_PASS","core_parlay_eligible":False,"reason":"low hit-rate; not a core parlay leg","model_edge_pp":round(edge,4)}

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

      # Confirmed/projected lineup is relative to the opponent, not merely to the
      # club's own best XI. For cup rotation, a pre-match depth-mismatch score can
      # soften a negative lineup penalty for an elite/deep squad facing a weaker tier.
      lineup=man.get("lineup",{});cap=fc["adjustment_caps_log_lambda"]["lineup"]
      raw_h=bounded(lineup.get("home_log_lambda",0),cap);raw_a=bounded(lineup.get("away_log_lambda",0),cap)
      ctx=man.get("rotation_context",{});res=float(fc.get("rotation_depth_resilience",0.65))
      dh=rotation_resilient_lineup(raw_h,ctx.get("home_depth_mismatch",0),res)
      da=rotation_resilient_lineup(raw_a,ctx.get("away_depth_mismatch",0),res)
      lh*=math.exp(dh);la*=math.exp(da)
      components["lineup_home_log_raw"]=raw_h;components["lineup_away_log_raw"]=raw_a
      components["lineup_home_log_effective"]=round(dh,4);components["lineup_away_log_effective"]=round(da,4)
      components["home_depth_mismatch"]=float(ctx.get("home_depth_mismatch",0) or 0);components["away_depth_mismatch"]=float(ctx.get("away_depth_mismatch",0) or 0)

      # Explicit cross-division / squad-depth terms. These must be supported by
      # pre-match evidence and are bounded; they are not inferred from the result.
      for key in ("tier_gap","squad_depth","recent_form","injuries","tactical","motivation","weather"):
        vals=man.get(key,{});cap=fc["adjustment_caps_log_lambda"][key];fh=bounded(vals.get("home_log_lambda",0),cap);fa=bounded(vals.get("away_log_lambda",0),cap)
        lh*=math.exp(fh);la*=math.exp(fa);components[key+"_home_log"]=fh;components[key+"_away_log"]=fa
      lh=max(.15,min(4.5,lh));la=max(.15,min(4.5,la));p1=probs(lh,la,fc["max_goals"]);fair=market_prob(p["market"],x["home_team"],x["away_team"],p1,lh,la,fc["max_goals"])
      bucket=portfolio_bucket(fair,p.get("market_probability"),cfg)
      outputs.append({"pick_id":p.get("id"),"status":"MODELLED","lambda_home":round(lh,4),"lambda_away":round(la,4),"home_win":round(p1[0],4),"draw":round(p1[1],4),"away_win":round(p1[2],4),"fair_probability":round(fair,4) if fair is not None else None,"portfolio_bucket":bucket["bucket"],"core_parlay_eligible":bucket["core_parlay_eligible"],"portfolio_reason":bucket["reason"],"model_edge_pp":bucket.get("model_edge_pp"),"components":components,"manual_notes":man.get("notes",[]),"market_prices_used_in_fair":False,"calibrated_params_active":bool(cp.get("active"))})
      if fair is not None:p["fair_probability"]=round(fair,4);p["fair_source"]="v0.3.6 calibrated football model" if cp.get("active") else "v0.3.6 uncalibrated football model"; p.update(portfolio_bucket(fair,p.get("market_probability"),cfg))
    board["updated"]=datetime.datetime.now(datetime.timezone.utc).isoformat();write("board.json",board);write("model_fair.json",{"updated_utc":board["updated"],"model":"v0.3.6 Poisson + relative squad-depth/rotation + probability-first portfolio classifier","calibrated_params_active":bool(cp.get("active")),"items":outputs})
if __name__=="__main__":main()
