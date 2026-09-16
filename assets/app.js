const $=s=>document.querySelector(s);let tab='board',D={};
const pct=x=>x==null?'—':(100*Number(x)).toFixed(1)+'%';
const money=x=>x==null?'—':'$'+Number(x).toFixed(2);
async function j(path,def={}){try{return await fetch(path+'?'+Date.now()).then(r=>r.ok?r.json():def)}catch(e){return def}}
async function load(){
  const names=['board','trades','performance','config','approval','sportsbook_consensus','model_fair','football_intelligence','backtest','calibrated_params','clv'];
  for(const x of names)D[x]=await j('data/'+x+'.json',{});
  D.pit_latest=await j('data/pit/latest.json',{items:[]});D.pit_closing=await j('data/pit/closing.json',{items:[]});
  $('#updated').textContent='最后更新 / Updated: '+(D.board.updated||D.pit_latest.updated_utc||'—');render();
}
function cards(items){return '<div class="cards">'+items.map(([a,b,c=''])=>'<div class="card"><span class="muted">'+a+'</span><div class="metric '+c+'">'+b+'</div></div>').join('')+'</div>'}
function render(){
  document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));let h='';
  const picks=D.board.picks||[];
  if(tab==='board'){
    h=cards([['候选 / Ideas',picks.length],['未平仓 / Open',money(D.performance.open_stake_usd)],['已实现 P&L / Realized',money(D.performance.realized_pnl_usd),D.performance.realized_pnl_usd>=0?'positive':'negative'],['已平仓 ROI / Closed ROI',pct(D.performance.closed_roi),D.performance.closed_roi>=0?'positive':'negative']]);
    h+='<div class="panel"><table><tr><th>比赛 / Match</th><th>市场 / Market</th><th>赔率 / Price</th><th>我的概率 / Fair</th><th>Book Consensus</th><th>Model-Book</th><th>Edge</th><th>EV</th><th>等级 / Grade</th><th>Max</th></tr>';
    h+=picks.map(x=>{const c=(D.sportsbook_consensus.items||[]).find(z=>z.pick_id===x.id)||{};return '<tr><td>'+x.match+'<br><span class="muted">'+x.competition+'</span></td><td>'+x.market+'</td><td>'+x.decimal_odds+'</td><td>'+pct(x.fair_probability)+'</td><td>'+pct(c.consensus_probability)+'</td><td>'+pct(c.model_vs_consensus_pp)+'</td><td>'+pct(x.edge_pp)+'</td><td class="'+(x.ev>=0?'positive':'negative')+'">'+pct(x.ev)+'</td><td class="'+x.grade+'">'+x.grade+'</td><td>'+x.max_units+'u</td></tr>'}).join('')+'</table></div>';
  }
  if(tab==='approval'){
    h='<div class="panel"><h2>人工审批 / Approval Queue</h2><p class="muted">Data Engine 只生成 paper signals。没有你的明确批准，不执行真钱交易 / No automatic real-money execution.</p><table><tr><th>Signal</th><th>Grade</th><th>建议仓位 / Size</th><th>最高入场 / Max Entry</th><th>Kalshi</th><th>状态 / Status</th></tr>'+(D.approval.items||[]).map(x=>'<tr><td>'+x.signal+'</td><td class="'+x.grade+'">'+x.grade+'</td><td>'+x.suggested_units+'u</td><td>'+x.max_entry+'</td><td>'+(x.kalshi_ticker||'待映射 / unmapped')+'</td><td><span class="pill">'+x.status+'</span></td></tr>').join('')+'</table></div>';
  }
  if(tab==='trades'){
    h='<div class="panel"><table><tr><th>日期 / Date</th><th>仓位 / Position</th><th>Stake</th><th>Payout / Exit</th><th>P&L</th><th>结果 / Status</th><th>执行复盘 / Execution</th></tr>'+(D.trades.trades||[]).map(x=>'<tr><td>'+x.date+'</td><td>'+x.position+'</td><td>'+money(x.stake_usd)+'</td><td>'+x.payout_display+'</td><td class="'+(x.pnl_usd>0?'positive':x.pnl_usd<0?'negative':'')+'">'+(x.pnl_usd==null?'OPEN':money(x.pnl_usd))+'</td><td>'+x.status+'</td><td>'+x.execution+'</td></tr>').join('')+'</table></div>';
  }
  if(tab==='performance'){
    let p=D.performance||{};h=cards([['已平仓本金 / Closed Stake',money(p.closed_stake_usd)],['已实现 P&L / Realized',money(p.realized_pnl_usd),p.realized_pnl_usd>=0?'positive':'negative'],['ROI',pct(p.closed_roi),p.closed_roi>=0?'positive':'negative'],['Cash-out P&L',money(p.cashout_realized_pnl_usd),'negative'],['Open Stake',money(p.open_stake_usd)],['交易数 / Trades',p.trade_count]]);
    h+='<div class="panel"><h2>研究指标 / Research Metrics</h2><p>CLV: '+(p.clv||'tracking prospectively')+'</p><p>Brier Score: '+(p.brier_score||'—')+'</p><p>EV Realization: '+(p.ev_realization||'—')+'</p></div>';
  }
  if(tab==='model'){
    let b=D.backtest||{},cp=D.calibrated_params||{};h=cards([['Backtest Status',b.status||'—'],['Holdout N',b.holdout?.n??'—'],['Holdout Log Loss',b.holdout?.log_loss??'—'],['Holdout Brier',b.holdout?.brier??'—'],['Calibration Active',cp.active?'YES':'NO']]);
    h+='<div class="panel"><h2>My Fair Probability / 模型拆解</h2><p class="muted">Sportsbook 与 Kalshi price 不进入 My Fair；只用于 sanity check / edge comparison。</p><table><tr><th>Pick</th><th>λ Home</th><th>λ Away</th><th>1</th><th>X</th><th>2</th><th>Fair</th><th>Status</th></tr>'+(D.model_fair.items||[]).map(x=>'<tr><td>'+x.pick_id+'</td><td>'+(x.lambda_home??'—')+'</td><td>'+(x.lambda_away??'—')+'</td><td>'+pct(x.home_win)+'</td><td>'+pct(x.draw)+'</td><td>'+pct(x.away_win)+'</td><td>'+pct(x.fair_probability)+'</td><td>'+x.status+'</td></tr>').join('')+'</table><h3>Walk-forward Calibration / 回测校准</h3><p>Params: '+(cp.params?JSON.stringify(cp.params):'等待回测 / waiting')+'</p><p>Method: '+(b.method||'—')+'</p><p class="muted">只有 holdout ≥500 predictions 才允许 calibrated params 自动进入 live model。</p></div>';
  }
  if(tab==='pit'){
    const s=D.clv.summary||{}, latest=D.pit_latest.items||[], closes=D.pit_closing.items||[];
    h=cards([['Hourly snapshots',latest.length],['Closing refs',closes.length],['CLV trades tracked',s.tracked_trades??0],['Mean Trade CLV',pct(s.mean_trade_clv_pp)]]);
    h+='<div class="panel"><h2>Point-in-Time / 时点快照</h2><p class="muted">每小时冻结 My Fair、sportsbook consensus、Kalshi probability、liquidity 和 kickoff horizon。历史快照不回写。</p><table><tr><th>Pick</th><th>Bucket</th><th>Minutes</th><th>My Fair</th><th>Book</th><th>Kalshi</th><th>Liquidity</th></tr>'+latest.map(x=>'<tr><td>'+x.pick_id+'</td><td>'+x.bucket+'</td><td>'+(x.minutes_to_kickoff??'—')+'</td><td>'+pct(x.my_fair)+'</td><td>'+pct(x.sportsbook_probability)+'</td><td>'+pct(x.kalshi_probability)+'</td><td>'+money(x.kalshi_liquidity_usd)+'</td></tr>').join('')+'</table></div>';
    h+='<div class="panel"><h2>Closing Line Value / 收盘线价值</h2><p class="muted">YES-side 定义：CLV = closing implied probability − entry implied probability。正值表示你买入后该 outcome 在收盘前变贵。</p><table><tr><th>Trade</th><th>Entry</th><th>Close Ref</th><th>CLV</th><th>Status</th></tr>'+(D.clv.trade_clv||[]).map(x=>'<tr><td>'+(x.position||x.trade_id||'—')+'</td><td>'+pct(x.entry_probability)+'</td><td>'+pct(x.closing_reference_probability)+'</td><td class="'+(x.clv_probability_points>0?'positive':x.clv_probability_points<0?'negative':'')+'">'+pct(x.clv_probability_points)+'</td><td>'+x.status+'</td></tr>').join('')+'</table></div>';
  }
  if(tab==='risk')h='<div class="panel"><h2>Portfolio 风控规则 / Risk Rules</h2><p><b>A</b>：真正高 edge 单腿 / genuine-edge single → 0.5–0.75u</p><p><b>B</b>：不同联赛两稳腿 / 2-leg safer combo → 0.25–0.5u</p><p><b>C</b>：2.5x–4x speculative combo → ≤0.25u</p><p>同场全部相关仓位 / correlated exposure per match → ≤1u</p><p>Data Engine gate：Edge ≥4pp、EV ≥5%、满足 liquidity 与 max-entry 才进入可审批状态。</p><p class="muted">不要因为 mark-to-market 下跌本身 cash out；只有红牌、核心伤退、首发/战术等新信息实质改变 thesis 才重估。Gambling involves risk of loss.</p></div>';
  $('#content').innerHTML=h;
}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;render()});load();
