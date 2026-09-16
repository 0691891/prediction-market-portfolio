#!/usr/bin/env python3
"""v0.3.4 CLV analytics. Read-only: computes signal/trade CLV from frozen snapshots."""
import json,pathlib,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; PIT=DATA/'pit'
def load(path,default):
    p=DATA/path
    return json.loads(p.read_text()) if p.exists() else default
def save(path,obj):
    (DATA/path).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def implied_from_decimal(x):
    try:return 1/float(x) if float(x)>0 else None
    except:return None
def one_leg(t,leg,cby):
    pid=leg.get('pick_id'); entry=leg.get('entry_probability')
    if entry is None and leg.get('entry_decimal_odds'):entry=implied_from_decimal(leg.get('entry_decimal_odds'))
    close_row=cby.get(pid) if pid else None; sportsbook_close=close_row.get('sportsbook_probability') if close_row else None; kalshi_close=close_row.get('kalshi_probability') if close_row else None
    ref=kalshi_close if kalshi_close is not None else sportsbook_close; clv=(ref-entry) if (ref is not None and entry is not None) else None
    return {'trade_id':t.get('trade_id'),'pick_id':pid,'position':leg.get('position') or t.get('position'),'entry_probability':entry,'closing_kalshi_probability':kalshi_close,'closing_sportsbook_probability':sportsbook_close,'closing_reference_probability':ref,'clv_probability_points':round(clv,4) if clv is not None else None,'status':'OK' if clv is not None else 'INSUFFICIENT_POINT_IN_TIME_DATA'}
def main():
    now=datetime.datetime.now(datetime.timezone.utc).isoformat(); close=load('pit/closing.json',{'items':[]}); cby={x.get('pick_id'):x for x in close.get('items',[]) if x.get('pick_id')}
    trades=load('trades.json',{'trades':[]}).get('trades',[]); trade_rows=[]
    for t in trades:
        legs=t.get('legs') or ([{'pick_id':t.get('pick_id'),'position':t.get('position'),'entry_probability':t.get('entry_probability'),'entry_decimal_odds':t.get('entry_decimal_odds')}] if t.get('pick_id') else [])
        if not legs:
            trade_rows.append({'trade_id':t.get('trade_id'),'pick_id':None,'position':t.get('position'),'entry_probability':None,'closing_reference_probability':None,'clv_probability_points':None,'status':'INSUFFICIENT_POINT_IN_TIME_DATA'});continue
        for leg in legs:trade_rows.append(one_leg(t,leg,cby))
    signal_rows=[]; days=load('pit/index.json',{'days':[]}).get('days',[]); earliest={}
    for name in days:
        doc=load('pit/'+name,{'snapshots':[]})
        for r in doc.get('snapshots',[]):
            pid=r.get('pick_id')
            if not pid:continue
            old=earliest.get(pid)
            if old is None or r.get('snapshot_utc','')<old.get('snapshot_utc',''):earliest[pid]=r
    for pid,c in cby.items():
        e=earliest.get(pid)
        if not e:continue
        row={'pick_id':pid,'match':c.get('match'),'market':c.get('market'),'entry_snapshot_utc':e.get('snapshot_utc'),'closing_snapshot_utc':c.get('snapshot_utc'),'entry_kalshi_probability':e.get('kalshi_probability'),'closing_kalshi_probability':c.get('kalshi_probability'),'entry_sportsbook_probability':e.get('sportsbook_probability'),'closing_sportsbook_probability':c.get('sportsbook_probability')}
        if e.get('kalshi_probability') is not None and c.get('kalshi_probability') is not None:row['kalshi_signal_clv_pp']=round(c['kalshi_probability']-e['kalshi_probability'],4)
        if e.get('sportsbook_probability') is not None and c.get('sportsbook_probability') is not None:row['sportsbook_signal_clv_pp']=round(c['sportsbook_probability']-e['sportsbook_probability'],4)
        signal_rows.append(row)
    valid=[x['clv_probability_points'] for x in trade_rows if x.get('clv_probability_points') is not None]
    save('clv.json',{'updated_utc':now,'definition':'For a YES-side position, positive CLV means the chosen outcome closed at a higher implied probability than entry. Trade CLV prefers Kalshi close, falling back to de-vig sportsbook consensus. Combo trades are evaluated leg by leg unless an explicit combo market is separately mapped.','trade_clv':trade_rows,'signal_clv':signal_rows,'summary':{'tracked_legs':len(valid),'mean_trade_clv_pp':round(sum(valid)/len(valid),4) if valid else None},'limitations':'Historical trades without supported pick mapping and entry probability are not assigned CLV retroactively.'})
if __name__=='__main__':main()
