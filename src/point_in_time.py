#!/usr/bin/env python3
"""Read-only point-in-time snapshot recorder. Never places orders."""
import json,pathlib,datetime,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; PIT=DATA/'pit'; PIT.mkdir(parents=True,exist_ok=True)
def load(path,default):
    p=DATA/path
    return json.loads(p.read_text()) if p.exists() else default
def save(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def ts(x):
    return datetime.datetime.fromisoformat(x.replace('Z','+00:00')) if x else None
def label(minutes):
    if minutes is None:return 'UNSCHEDULED'
    if minutes<0:return 'POST_KICKOFF'
    if minutes<=45:return 'CLOSE'
    if minutes<=120:return 'T-1H'
    if minutes<=540:return 'T-6H'
    if minutes<=2160:return 'T-24H'
    return 'EARLY'
def index(items):
    out={}
    for x in items:
        key=x.get('pick_id') or x.get('id')
        if key:out[key]=x
    return out
def main():
    now=datetime.datetime.now(datetime.timezone.utc); hour=now.replace(minute=0,second=0,microsecond=0)
    board=load('board.json',{'picks':[]}); books=index(load('sportsbook_consensus.json',{'items':[]}).get('items',[])); kal=index(load('market_snapshot.json',{'markets':[]}).get('markets',[])); model=index(load('model_fair.json',{'items':[]}).get('items',[])); intel=index(load('football_intelligence.json',{'items':[]}).get('items',[]))
    rows=[]
    for p in board.get('picks',[]):
        pid=p.get('id'); b=books.get(pid,{}); k=kal.get(pid,{}); m=model.get(pid,{}); i=intel.get(pid,{})
        kickoff=ts(b.get('commence_time')); mins=(kickoff-now).total_seconds()/60 if kickoff else None
        row={'snapshot_utc':now.isoformat(),'snapshot_hour_utc':hour.isoformat(),'pick_id':pid,'competition':p.get('competition'),'match':p.get('match'),'market':p.get('market'),'kickoff_utc':b.get('commence_time'),'minutes_to_kickoff':round(mins,1) if mins is not None else None,'bucket':label(mins),'my_fair':p.get('fair_probability'),'fair_source':p.get('fair_source'),'sportsbook_probability':b.get('consensus_probability'),'sportsbook_book_count':b.get('book_count'),'kalshi_probability':k.get('market_probability'),'kalshi_liquidity_usd':k.get('liquidity_usd'),'model_status':m.get('status'),'football_intelligence_status':i.get('status')}
        row['snapshot_id']=hashlib.sha1((str(pid)+hour.isoformat()).encode()).hexdigest()[:16]; rows.append(row)
    day=PIT/(now.date().isoformat()+'.json'); doc=json.loads(day.read_text()) if day.exists() else {'date':now.date().isoformat(),'snapshots':[]}; seen={x.get('snapshot_id') for x in doc['snapshots']}; doc['snapshots'] += [r for r in rows if r['snapshot_id'] not in seen]; save(day,doc)
    idx=load('pit/index.json',{'days':[]})
    if day.name not in idx['days']:idx['days'].append(day.name);idx['days'].sort()
    idx['updated_utc']=now.isoformat();save(PIT/'index.json',idx);save(PIT/'latest.json',{'updated_utc':now.isoformat(),'items':rows})
    closing=load('pit/closing.json',{'items':[]}); cmap={x['pick_id']:x for x in closing.get('items',[]) if x.get('pick_id')}
    for r in rows:
        mt=r.get('minutes_to_kickoff')
        if mt is None or mt<0:continue
        old=cmap.get(r['pick_id'])
        if old is None or mt<old.get('minutes_to_kickoff',1e18):cmap[r['pick_id']]=r
    save(PIT/'closing.json',{'updated_utc':now.isoformat(),'items':list(cmap.values())})
if __name__=='__main__':main()
