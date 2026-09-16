#!/usr/bin/env python3
"""v0.3.5 Alpha Attribution Engine.
Aggregates realized P&L and prospective CLV by league, market type, grade, entry horizon, and edge bucket.
No retroactive fabrication: missing metadata stays UNKNOWN / insufficient.
"""
import json, pathlib, datetime, re
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
def load(path,default):
    p=DATA/path
    return json.loads(p.read_text()) if p.exists() else default
def save(path,obj):
    (DATA/path).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def mtype(s):
    t=(s or '').lower()
    # Combo detection must happen first: a parlay can contain ML/BTTS/totals words.
    if '×' in (s or '') or 'combo' in t or 'parlay' in t:return 'COMBO'
    if 'btts' in t or 'both teams' in t:return 'BTTS'
    if re.search(r'\b(o|over|u|under)\s*\d',t) or 'over ' in t or 'under ' in t:return 'TOTALS'
    if re.search(r'[+-]\d',t):return 'SPREAD'
    if 'win' in t or 'not win' in t or 'moneyline' in t or ' ml' in t:return 'MONEYLINE'
    return 'OTHER'
def edge_bucket(x):
    if x is None:return 'UNKNOWN'
    if x<0:return '<0pp'
    if x<.02:return '0-2pp'
    if x<.04:return '2-4pp'
    if x<.06:return '4-6pp'
    if x<.10:return '6-10pp'
    return '10pp+'
def aggregate(rows,key):
    g={}
    for r in rows:
        k=r.get(key) or 'UNKNOWN'; z=g.setdefault(k,{'n':0,'closed_n':0,'stake_usd':0.,'pnl_usd':0.,'clv_n':0,'clv_sum':0.})
        z['n']+=1
        if r.get('pnl_usd') is not None:
            z['closed_n']+=1; z['stake_usd']+=float(r.get('stake_usd') or 0); z['pnl_usd']+=float(r['pnl_usd'])
        if r.get('clv_pp') is not None:
            z['clv_n']+=1; z['clv_sum']+=float(r['clv_pp'])
    out=[]
    for k,z in g.items():
        out.append({'group':k,'n':z['n'],'closed_n':z['closed_n'],'stake_usd':round(z['stake_usd'],2),'pnl_usd':round(z['pnl_usd'],2),'roi':round(z['pnl_usd']/z['stake_usd'],4) if z['stake_usd'] else None,'clv_n':z['clv_n'],'mean_clv_pp':round(z['clv_sum']/z['clv_n'],4) if z['clv_n'] else None})
    return sorted(out,key=lambda x:(x['group']))
def main():
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    trades=load('trades.json',{'trades':[]}).get('trades',[])
    clv=load('clv.json',{'trade_clv':[]}).get('trade_clv',[])
    board={x.get('id'):x for x in load('board.json',{'picks':[]}).get('picks',[]) if x.get('id')}
    pit={x.get('pick_id'):x for x in load('pit/latest.json',{'items':[]}).get('items',[]) if x.get('pick_id')}
    clv_by={}
    for x in clv:
        tid=x.get('trade_id'); pid=x.get('pick_id')
        if tid or pid:clv_by[(tid,pid)]=x
    rows=[]
    for i,t in enumerate(trades):
        tid=t.get('trade_id') or f'legacy-{i+1}'
        legs=t.get('legs') or ([{'pick_id':t.get('pick_id'),'position':t.get('position'),'entry_probability':t.get('entry_probability')}] if t.get('pick_id') else [])
        if not legs:
            rows.append({'trade_id':tid,'pick_id':None,'league':t.get('league') or 'UNKNOWN','market_type':t.get('market_type') or mtype(t.get('position')),'grade':t.get('grade') or 'UNKNOWN','entry_horizon':t.get('entry_horizon') or 'UNKNOWN','edge_bucket':edge_bucket(t.get('edge_pp')),'stake_usd':t.get('stake_usd'),'pnl_usd':t.get('pnl_usd'),'clv_pp':None})
            continue
        per_stake=(float(t.get('stake_usd') or 0)/len(legs)) if legs else 0
        per_pnl=(float(t['pnl_usd'])/len(legs)) if t.get('pnl_usd') is not None else None
        for leg in legs:
            pid=leg.get('pick_id'); b=board.get(pid,{}); c=clv_by.get((t.get('trade_id'),pid)) or clv_by.get((None,pid),{}); p=pit.get(pid,{})
            rows.append({'trade_id':tid,'pick_id':pid,'league':leg.get('league') or b.get('competition') or t.get('league') or 'UNKNOWN','market_type':leg.get('market_type') or mtype(leg.get('position') or b.get('market') or t.get('position')),'grade':leg.get('grade') or b.get('grade') or t.get('grade') or 'UNKNOWN','entry_horizon':leg.get('entry_horizon') or t.get('entry_horizon') or p.get('bucket') or 'UNKNOWN','edge_bucket':edge_bucket(leg.get('edge_pp',b.get('edge_pp',t.get('edge_pp')))),'stake_usd':round(per_stake,2),'pnl_usd':round(per_pnl,2) if per_pnl is not None else None,'clv_pp':c.get('clv_probability_points')})
    valid_clv=[r['clv_pp'] for r in rows if r.get('clv_pp') is not None]
    valid_closed=[r for r in rows if r.get('pnl_usd') is not None]
    stake=sum(float(r.get('stake_usd') or 0) for r in valid_closed); pnl=sum(float(r['pnl_usd']) for r in valid_closed)
    save('alpha_attribution.json',{'updated_utc':now,'version':'v0.3.5','status':'TRACKING' if rows else 'NO_TRADES','summary':{'rows':len(rows),'closed_rows':len(valid_closed),'tracked_clv_rows':len(valid_clv),'realized_roi':round(pnl/stake,4) if stake else None,'mean_clv_pp':round(sum(valid_clv)/len(valid_clv),4) if valid_clv else None},'by_league':aggregate(rows,'league'),'by_market_type':aggregate(rows,'market_type'),'by_grade':aggregate(rows,'grade'),'by_entry_horizon':aggregate(rows,'entry_horizon'),'by_edge_bucket':aggregate(rows,'edge_bucket'),'notes':'Historical records lacking pick_id/entry probability remain UNKNOWN and are not assigned synthetic CLV. Combo stake/P&L is split evenly across legs only for attribution bookkeeping, not to claim true leg-level economic P&L.'})
if __name__=='__main__':main()
