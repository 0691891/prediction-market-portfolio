#!/usr/bin/env python3
"""Football Alpha Terminal — READ-ONLY $1m paper-trading dashboard.

Run: pip install -r dashboard/requirements.txt && streamlit run dashboard/app.py
Local files by default; select GitHub mode in sidebar for a remote deployment.
No order entry, no modification of real trade ledger.
"""
import json
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/0691891/prediction-market-portfolio/main/"
FILES = {
    "account": "paper/account.json",
    "state": "paper/state.json",
    "signals": "paper/signals.json",
    "results": "paper/results.json",
    "observations": "paper/observations.json",
    "board": "data/board.json",
    "model": "data/model_fair.json",
    "markets": "data/market_snapshot.json",
    "sportsbook": "data/sportsbook_consensus.json",
    "pit": "data/pit/latest.json",
    "clv": "data/clv.json",
}
st.set_page_config(page_title="Football Alpha Terminal | PAPER", page_icon="⚽",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
.stApp{background:#080d16;color:#e9f1fa}
[data-testid="stSidebar"]{background:#101a2a}
h1,h2,h3{color:#eff7ff!important}
[data-testid="stMetric"]{background:#101b2d;border:1px solid #263a50;
 border-radius:13px;padding:15px}
[data-testid="stMetricLabel"]{color:#a3b8cc}
div.stButton>button{border-radius:9px}
.signal{padding:12px 16px;background:#122336;border-left:3px solid #22ceb3;
 border-radius:9px;margin-bottom:12px}
.muted{color:#9badc2;font-size:13px}
</style>""", unsafe_allow_html=True)

def money(x):
    try:return f"${float(x):,.2f}"
    except (TypeError,ValueError):return "—"

def pct(x):
    try:return f"{float(x):+.2%}"
    except (TypeError,ValueError):return "—"

def stamp(x):
    if not x:return "Not provided"
    try:return datetime.fromisoformat(str(x).replace("Z","+00:00")).astimezone(timezone.utc).strftime("%d %b %Y %H:%M:%S UTC")
    except (TypeError,ValueError):return str(x)

@st.cache_data(ttl=20, show_spinner=False)
def fetch(path, remote):
    try:
        if remote:
            req=urllib.request.Request(BASE+path,headers={"User-Agent":"FootballAlphaTerminal/1.0"})
            with urllib.request.urlopen(req,timeout=8) as response:
                return json.load(response), None
        p=ROOT/path
        return (json.loads(p.read_text()),None) if p.exists() else ({}, "File not found")
    except (OSError,ValueError,urllib.error.URLError) as e:
        return {}, str(e)[:140]

with st.sidebar:
    st.markdown("## ⚽ ALPHA / TERMINAL")
    st.caption("PAPER TRADING • NO REAL ORDERS")
    remote=st.toggle("GitHub data mode",value=False,help="Enable for Streamlit Cloud or when repo data are not mounted locally.")
    auto=st.toggle("Auto-refresh / 30s",value=False,
                   help="Refreshes display; underlying upstream data may be hourly, not real-time.")
    if st.button("↻ Refresh now",use_container_width=True):
        fetch.clear()
        st.rerun()
    st.divider()
    st.markdown("**Coverage**")
    st.caption("PL · La Liga · Serie A · Bundesliga · Ligue 1 · UCL · UEL · EFL · FA Cup")
    st.divider()
    st.caption("Read-only research. No betting execution. A stale quote is not a tradable opportunity.")

if auto:
    st_autorefresh(interval=30_000, limit=None, key="paper-refresh")

D={}; errors={}
for key,path in FILES.items():
    D[key],err=fetch(path,remote)
    if err:errors[key]=err

account=D["account"]; state=D["state"]; signals=D["signals"].get("signals",[])
observations=D["observations"].get("observations",[])
trades=state.get("trades",[])
initial=float(account.get("initial_capital_usd",1000000))
nav=float(state.get("realized_nav_usd",initial))
open_exposure=float(state.get("open_stake_usd",0))
cash=float(state.get("available_cash_usd",initial))
pnl=float(state.get("realized_pnl_usd",0))
now=datetime.now(timezone.utc)

st.title("FOOTBALL / ALPHA TERMINAL")
st.markdown('<div class="signal">● PAPER MODE &nbsp; $1,000,000 virtual bankroll &nbsp; | &nbsp; Pre-match + In-play mispricing research &nbsp; | &nbsp; Live execution disabled</div>',unsafe_allow_html=True)
if "state" in errors:
    st.error("PAPER STATE UNAVAILABLE — showing initial account fallback, not a verified NAV.")
a,b,c,d,e=st.columns(5)
a.metric("PAPER NAV",money(nav),pct(nav/initial-1))
b.metric("AVAILABLE CASH",money(cash))
c.metric("OPEN RISK",money(open_exposure),f"{open_exposure/initial:.2%} of initial NAV")
d.metric("REALIZED P&L",money(pnl))
e.metric("SETTLED TRADES",str(state.get("settled_orders",0)),f"{state.get('open_orders',0)} open")
st.caption(f"Data source: {'GitHub main' if remote else 'Local repository'} · Screen time {now:%Y-%m-%d %H:%M:%S} UTC · Market/model freshness shown below. Screen refresh ≠ real-time exchange feed.")

tabs=st.tabs(["◉ MARKET WATCH","▣ PAPER POSITIONS","⌁ ALPHA LAB","◷ PIT / CLV","⚑ RISK & DATA HEALTH"])

with tabs[0]:
    st.subheader("All-fixture market scanner / 全赛程观察")
    st.caption("PASS and missing-data matches belong in the research universe. No synthetic odds or inferred fills.")
    board=D["board"]
    picks=board.get("picks",[])
    model={str(x.get("pick_id") or x.get("id")):x for x in D["model"].get("items",[])}
    markets={str(x.get("pick_id") or x.get("id")):x for x in D["markets"].get("markets",[])}
    books={str(x.get("pick_id") or x.get("id")):x for x in D["sportsbook"].get("items",[])}
    src=observations or picks or board.get("watchlist",[])
    rows=[]
    for i,x in enumerate(src):
        pid=str(x.get("pick_id") or x.get("id") or i)
        m=markets.get(pid,{}); b=books.get(pid,{}); f=model.get(pid,{})
        fair=x.get("fair_probability",x.get("my_fair_probability",f.get("fair_probability")))
        ask=x.get("market_probability",m.get("market_probability"))
        decimal=x.get("decimal_odds",m.get("decimal_odds"))
        if not decimal and ask:
            try:decimal=1/float(ask)
            except (ValueError,ZeroDivisionError,TypeError):pass
        ev=x.get("ev",m.get("ev"))
        if ev is None and fair is not None and decimal:
            try:ev=float(fair)*float(decimal)-1
            except (ValueError,TypeError):pass
        rows.append({
            "Competition":x.get("competition","—"),"Match":x.get("match","—"),
            "Market":x.get("market","—"),"Phase":x.get("entry_phase",x.get("refresh","—")),
            "Status":x.get("status",x.get("decision","WATCH")),
            "Odds":decimal,"Break-even":(1/float(decimal) if decimal else None),
            "My Fair":fair,"EV":ev,"Liquidity $":m.get("liquidity_usd",x.get("liquidity_usd")),
            "Price timestamp":x.get("quote_timestamp_utc",m.get("updated_utc")),
            "Kickoff UTC":x.get("kickoff_utc",x.get("kickoff")),
            "Risk/why":x.get("pass_reason",x.get("thesis",x.get("note",""))),
        })
    if rows:
        df=pd.DataFrame(rows)
        comps=sorted(set(df["Competition"].dropna().astype(str)))
        selected=st.multiselect("League filter",comps,default=comps)
        q=st.text_input("Search match / market")
        view=df[df["Competition"].isin(selected)]
        if q:view=view[view["Match"].astype(str).str.contains(q,case=False,regex=False)|
                       view["Market"].astype(str).str.contains(q,case=False,regex=False)]
        st.dataframe(view,hide_index=True,use_container_width=True,
            column_config={"Break-even":st.column_config.NumberColumn(format="%.1f%%",help="Decimal implied probability; displayed as decimal fraction below if provider format differs."),
                           "EV":st.column_config.NumberColumn(format="%.3f"),
                           "Odds":st.column_config.NumberColumn(format="%.3f")})
        st.caption("Break-even / My Fair / EV are decimal fractions unless explicitly displayed otherwise. Only timestamped executable quotes qualify for paper fills.")
    else:
        st.info("No verified fixture observations or picks yet. Configure the upstream fixture + odds feed; this screen does not invent fixtures or prices.")
    st.subheader("Research queue / Watchlist")
    if board.get("watchlist"):
        st.dataframe(pd.DataFrame(board["watchlist"]),hide_index=True,use_container_width=True)
    else:st.caption("No watchlist rows in latest board.")
    st.caption("Model fair status: "+str(D["model"].get("model","UNAVAILABLE"))+
               " • Sportsbook feed: "+str(D["sportsbook"].get("status","UNAVAILABLE")))

with tabs[1]:
    st.subheader("Paper portfolio / 虚拟持仓")
    if trades:
        v=pd.DataFrame(trades)
        cols=[x for x in ["signal_id","competition","match","entry_phase","market","selection",
                          "decimal_odds","fair_probability_at_entry","entry_ev","stake_usd",
                          "status","outcome","realized_pnl_usd","quote_timestamp_utc"] if x in v]
        st.dataframe(v[cols],hide_index=True,use_container_width=True)
        settled=v[v.status=="SETTLED"] if "status" in v else pd.DataFrame()
        if not settled.empty:
            fig=go.Figure(go.Scatter(x=list(range(len(settled)+1)),
              y=[initial]+[initial+z for z in settled["realized_pnl_usd"].fillna(0).cumsum()],
              mode="lines+markers",name="Realized NAV",line_color="#20d4b5"))
            fig.update_layout(template="plotly_dark",paper_bgcolor="#080d16",plot_bgcolor="#080d16",
                              title="Realized NAV by settlement",height=330)
            st.plotly_chart(fig,use_container_width=True)
    else:st.info("No verified virtual orders. Account remains at $1,000,000; research/PASS rows are not fills.")
    st.subheader("Paper order audit / Signal log")
    if signals:st.dataframe(pd.DataFrame(signals),hide_index=True,use_container_width=True)
    else:st.caption("Signals file is empty.")
    if state.get("rejections"):
        with st.expander("Rejected paper signals"):
            st.dataframe(pd.DataFrame(state["rejections"]),hide_index=True)

with tabs[2]:
    st.subheader("Alpha Research / 模型迭代")
    settled=[t for t in trades if t.get("status")=="SETTLED"]
    s1,s2,s3,s4=st.columns(4)
    s1.metric("Fixture observations",len(observations))
    s2.metric("Signals",len(signals))
    s3.metric("Paper fills",len(trades))
    roi=state.get("settled_stake_roi")
    s4.metric("ROI on settled stake",pct(roi) if roi is not None else "N/A")
    if settled:
        f=pd.DataFrame(settled)
        for group in ["entry_phase","competition","market","grade","scenario"]:
            if group in f:
                g=f.groupby(group,dropna=False).agg(
                    trades=("signal_id","count"),stake=("stake_usd","sum"),
                    pnl=("realized_pnl_usd","sum"))
                g["ROI"]=g["pnl"]/g["stake"]
                st.markdown("**"+group.replace("_"," ").title()+" attribution**")
                st.dataframe(g,use_container_width=True)
    else:st.info("Alpha attribution awaits verified settlements. No win-rate, Brier score or CLV is imputed.")
    st.subheader("Model vs market / 预测校准")
    pit=D["pit"].get("items",[])
    if pit:
        pv=pd.DataFrame(pit)
        cols=[x for x in ["match","market","bucket","my_fair","sportsbook_probability",
                          "kalshi_probability","minutes_to_kickoff","snapshot_utc"] if x in pv]
        st.dataframe(pv[cols],hide_index=True,use_container_width=True)
    else:st.caption("No frozen PIT predictions in latest snapshot.")
    st.info("Proper calibration needs resolved predictions across ALL fixtures, including PASS. Event-level Brier/log loss must not be computed from selected wins alone.")

with tabs[3]:
    st.subheader("Point-in-time archive / Closing line")
    clv=D["clv"]
    st.caption("Latest PIT: "+stamp(D["pit"].get("updated_utc"))+
               " | CLV update: "+stamp(clv.get("updated_utc")))
    for name in ["trade_clv","signal_clv"]:
        if clv.get(name):
            st.markdown("**"+name.replace("_"," ").title()+"**")
            st.dataframe(pd.DataFrame(clv[name]),hide_index=True,use_container_width=True)
    st.warning("LIVE CLV requires later executable quotes on the SAME event + SAME contract. A pre-match closing price cannot be compared with a post-goal live entry.")
    if clv.get("summary"):st.json(clv["summary"])

with tabs[4]:
    st.subheader("Risk engine / Operational status")
    r1,r2,r3=st.columns(3)
    matchcap=float(account.get("maximum_exposure_per_match_usd",5000))
    bookcap=float(account.get("maximum_total_open_exposure_usd",50000))
    r1.metric("Per-match cap",money(matchcap))
    r2.metric("Book open cap",money(bookcap))
    r3.metric("Remaining book capacity",money(max(0,bookcap-open_exposure)))
    st.progress(min(1,open_exposure/bookcap) if bookcap else 0)
    st.subheader("Upstream data & freshness")
    for key,path in FILES.items():
        doc=D[key]
        ts=doc.get("updated_utc") or doc.get("updated")
        if not ts and key=="account":ts=doc.get("created_utc")
        if ts:
            try: age_h=(now-datetime.fromisoformat(str(ts).replace("Z","+00:00")).astimezone(timezone.utc)).total_seconds()/3600
            except (ValueError,TypeError):age_h=None
        else:age_h=None
        stale=age_h is not None and age_h>2
        st.write(f"{'🔴' if key in errors or stale else '🟢' if ts else '⚪'} {key}: {stamp(ts)}"+(f" • {age_h:.1f}h old" if age_h is not None else "")+
                 (f" • {errors[key]}" if key in errors else ""))
    st.error("Refresh of this screen does not increase data-source frequency. Current GitHub workflow/model may be hourly and sportsbook feed may be unconfigured. Do not treat data as live executable odds.")
st.caption("All values are PAPER ONLY. Football bets/parlays can lose 100% of capital committed. Arbitrage is not established without same-outcome coverage, net fees, execution and settlement-rule reconciliation.")
