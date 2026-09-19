#!/usr/bin/env python3
"""PIT residual-alpha trainer: market-offset multinomial logistic, L2, walk-forward.

Input: data/pit_training/matches.jsonl, one frozen PRE-KICKOFF row per match.
Never generate missing xG, lineup, tactical, injury or price-movement values.
No same-season holdout fitting. This script is safe to run without data.
"""
import json,math,datetime as dt,pathlib,collections,random
from residual_pricing import CAPS,devig
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/pit_training/matches.jsonl"
OUT=ROOT/"data/residual_training_report.json"
WEIGHTS=ROOT/"data/residual_trained_candidate.json"
FEATURES=list(CAPS)
def softmax(v):
    m=max(v);e=[math.exp(x-m) for x in v];return [x/sum(e) for x in e]
def loss(rows,w,mu,sd):
    if not rows:return None
    total=0
    for r in rows:
        p=forecast(r,w,mu,sd)
        total-=math.log(max(1e-12,p[r["y"]]))
    return total/len(rows)
def forecast(r,w,mu,sd):
    z=[max(-2,min(2,(r["f"].get(k,mu[k])-mu[k])/sd[k])) for k in FEATURES]
    logits=[math.log(max(1e-9,p))+sum(w[j][i]*z[j] for j in range(len(FEATURES))) for i,p in enumerate(r["prior"])]
    return softmax(logits)
def read():
    if not SOURCE.exists():return [],["PIT training file not yet supplied"]
    rows=[];errors=[]
    for lineno,line in enumerate(SOURCE.read_text().splitlines(),1):
        if not line.strip():continue
        try:
            r=json.loads(line);snap=dt.datetime.fromisoformat(r["snapshot_utc"].replace("Z","+00:00"))
            ko=dt.datetime.fromisoformat(r["kickoff_utc"].replace("Z","+00:00"))
            if snap.tzinfo is None or ko.tzinfo is None or not snap<ko:raise ValueError("snapshot must be timezone-aware and before kickoff")
            if r.get("market_type")!="1X2":raise ValueError("only 1X2 supported")
            if r.get("feature_observed_utc"):
                for k,t in r["feature_observed_utc"].items():
                    if k in r.get("features",{}) and dt.datetime.fromisoformat(t.replace("Z","+00:00"))>snap:raise ValueError("feature observed after snapshot: "+k)
            f={k:float(v) for k,v in r["features"].items() if k in CAPS and v is not None}
            if any(not math.isfinite(v) for v in f.values()):raise ValueError("nonfinite feature")
            # Input must carry a same-timestamp full 1X2 odds market.
            if dt.datetime.fromisoformat(r["market_observed_utc"].replace("Z","+00:00"))>snap:raise ValueError("future odds")
            if (snap-dt.datetime.fromisoformat(r["market_observed_utc"].replace("Z","+00:00"))).total_seconds()>3600:raise ValueError("stale odds >1h")
            y={"H":0,"D":1,"A":2}[r["result_90m"]]
            rows.append({"id":str(r["match_id"]),"ko":ko,"snap":snap,"league":r["league"],"f":f,"prior":devig(r["market_odds_1x2"]),"odds":[float(v) for v in r["market_odds_1x2"]],"y":y})
        except Exception as e:errors.append(f"line {lineno}: {str(e)[:120]}")
    # One snapshot per match, select most recent snapshot before kickoff.
    uniq={}
    for r in rows:
        if r["id"] not in uniq or uniq[r["id"]]["snap"]<r["snap"]:uniq[r["id"]]=r
    return sorted(uniq.values(),key=lambda r:(r["ko"],r["id"])),errors
def fit(rows,reg=5.,epochs=250,rate=.2):
    mu={};sd={}
    for k in FEATURES:
        v=[r["f"][k] for r in rows if k in r["f"]]
        mu[k]=sum(v)/len(v) if v else 0.
        sd[k]=max(1e-5,(sum((x-mu[k])**2 for x in v)/len(v))**.5) if len(v)>1 else 1.
    w=[[0.,0.,0.] for k in FEATURES]
    n=len(rows)
    for ep in range(epochs):
        grad=[[0.,0.,0.] for k in FEATURES]
        for r in rows:
            z=[max(-2,min(2,(r["f"].get(k,mu[k])-mu[k])/sd[k])) for k in FEATURES]
            p=forecast(r,w,mu,sd)
            for j,x in enumerate(z):
                for i in range(3):grad[j][i]+=(p[i]-(i==r["y"]))*x/n
        step=rate/(1+ep/100)
        for j in range(len(FEATURES)):
            for i in range(3):w[j][i]-=step*(grad[j][i]+reg*w[j][i]/n)
    return w,mu,sd
def metrics(rows,w,mu,sd):
    if not rows:return {"n":0}
    ps=[forecast(r,w,mu,sd) for r in rows]
    return {"n":len(rows),"log_loss":round(-sum(math.log(max(1e-12,p[r["y"]])) for p,r in zip(ps,rows))/len(rows),6),
      "brier":round(sum(sum((p[i]-(r["y"]==i))**2 for i in range(3)) for p,r in zip(ps,rows))/len(rows),6),
      "accuracy":round(sum(max(range(3),key=lambda i:p[i])==r["y"] for p,r in zip(ps,rows))/len(rows),6)}
def paper(rows,w,mu,sd):
    ts=[]
    for r in rows:
        p=forecast(r,w,mu,sd);ev=[max(0,p[i]-.03)*r["odds"][i]-1 for i in range(3)]
        j=max(range(3),key=lambda i:ev[i])
        if ev[j]<.05:continue
        ts.append({"match_id":r["id"],"league":r["league"],"selection":"HDA"[j],"ev":round(ev[j],5),
                   "pnl":round(100*(r["odds"][j]-1) if r["y"]==j else -100,2)})
    pnl=sum(t["pnl"] for t in ts)
    return {"trades":len(ts),"stake_usd":100*len(ts),"pnl_usd":round(pnl,2),
            "roi":round(pnl/(100*len(ts)),6) if ts else None}
def main():
    rows,errors=read();now=dt.datetime.now(dt.timezone.utc).isoformat()
    # Explicit fixed season boundary, no random split or holdout tuning.
    train=[r for r in rows if r["ko"]<dt.datetime(2025,7,1,tzinfo=dt.timezone.utc)]
    hold=[r for r in rows if dt.datetime(2025,7,1,tzinfo=dt.timezone.utc)<=r["ko"]<dt.datetime(2026,7,1,tzinfo=dt.timezone.utc)]
    coverage={k:{"train":sum(k in r["f"] for r in train),"holdout":sum(k in r["f"] for r in hold)} for k in FEATURES}
    report={"updated_utc":now,"status":"INSUFFICIENT_PIT_DATA","rows_total":len(rows),
            "train_matches":len(train),"holdout_matches":len(hold),"coverage":coverage,
            "errors":errors[:50],"method":"1X2 market-offset multiclass L2; fixed 2025-07-01 holdout boundary; training-only z-score; 3pp EV uncertainty; no auto activation",
            "minimum_train":500,"minimum_holdout":300}
    if len(train)>=500 and len(hold)>=300:
        w,mu,sd=fit(train);zero=[[0.,0.,0.] for k in FEATURES]
        report.update({"status":"RESEARCH_TRAINED_NOT_APPROVED","market_baseline":metrics(hold,zero,mu,sd),
                       "residual_model":metrics(hold,w,mu,sd),"paper_proxy":paper(hold,w,mu,sd),
                       "ablation_holdout_log_loss_delta":{k:round(loss(hold,[([0,0,0] if i==j else v) for i,v in enumerate(w)],mu,sd)-loss(hold,w,mu,sd),6) for j,k in enumerate(FEATURES)},
                       "warnings":["No holdout optimization or production activation.","PIT odds at snapshot, not future closing odds; execution still proxy without liquidity/fees.","No missing factor is inferred or fabricated."]})
        WEIGHTS.write_text(json.dumps({"status":"RESEARCH_CANDIDATE_NOT_ACTIVE","trained_utc":now,"weights_by_outcome":dict(zip(FEATURES,w)),"train_means":mu,"train_stds":sd,"holdout":report["residual_model"],"coverage":coverage},indent=2)+"\n")
    OUT.write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
