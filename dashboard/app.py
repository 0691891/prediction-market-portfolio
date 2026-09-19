#!/usr/bin/env python3
"""Football Alpha Terminal — READ-ONLY $1m paper-trading dashboard.

Run: pip install -r dashboard/requirements.txt && streamlit run dashboard/app.py
Local files by default; select GitHub mode in sidebar for a remote deployment.
No order entry, no modification of real trade ledger.
"""
import json
import pathlib
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from live_feed import scores as get_live_scores, odds as get_live_odds

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
.stApp{background:#f5f8fc;color:#142c47}
[data-testid="stSidebar"]{background:#ecf3fb}
h1,h2,h3{color:#18324e!important}
[data-testid="stMetric"]{background:#fff;border:1px solid #dbe5f0;
 border-radius:13px;padding:15px;box-shadow:0 2px 8px #24456609}
[data-testid="stMetricLabel"]{color:#536981}
div.stButton>button{border-radius:9px}
.signal{padding:12px 16px;background:#eaf8f2;border-left:3px solid #12a67c;
 border-radius:9px;margin-bottom:12px;color:#245344}
.muted{color:#607991;font-size:13px}
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
    remote=st.toggle("GitHub data mode",value=True,help="Enable for Streamlit Cloud or when repo data are not mounted locally.")
    auto=st.toggle("Auto-refresh / 30s",value=True,
                   help="Refreshes display; underlying upstream data may be hourly, not real-time.")
    if st.button("↻ Refresh now",use_container_width=True):
        fetch.clear()
        st.rerun()
    st.divider()
    st.markdown("**Live feeds / 数据源**")
    live_scores_enabled=st.toggle("Live scores / 全赛事比分",value=True)
    sportsbook_enabled=st.toggle("Sportsbook current quotes",value=True,
        help="Needs ODDS_API_KEY in Streamlit Secrets or environment. Quota applies.")
    configured_key=st.secrets.get("ODDS_API_KEY") if "ODDS_API_KEY" in st.secrets else os.getenv("ODDS_API_KEY")
    if sportsbook_enabled and not configured_key:
        st.warning("No ODDS_API_KEY — odds feed inactive. Never interpret GitHub snapshots as live prices.")
    st.divider()
    st.markdown("**Coverage**")
    st.caption("PL · La Liga · Serie A · Bundesliga · Ligue 1 · UCL · UEL · EFL · FA Cup")
    st.divider()
    st.caption("Read-only research. No betting execution. A stale quote is not a tradable opportunity.")

if auto:
    st_autorefresh(interval=30_000, limit=None, key="paper-refresh")

@st.cache_data(ttl=25, show_spinner=False)
def live_scores_data():
    return get_live_scores()

@st.cache_data(ttl=60, show_spinner=False)
def live_odds_data(key):
    return get_live_odds(key)

score_rows, score_errors, scores_at = live_scores_data() if live_scores_enabled else ([],{},None)
live_quotes, odds_errors, odds_at = live_odds_data(configured_key) if sportsbook_enabled and configured_key else ([],{},None)

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

tabs=st.tabs(["● LIVE SCORES","◉ MARKET WATCH","▣ PAPER POSITIONS","⌁ ALPHA LAB","⇄ ARB SCANNER","◷ PIT / CLV","⚑ RISK & DATA HEALTH"])

with tabs[0]:
    st.subheader("Live scoreboard / 今日全赛事")
    st.caption("ESPN public scoreboard • fetched "+stamp(scores_at)+
               " • display refresh 30s; provider delays possible. Scores are NOT executable odds.")
    if score_rows:
        s=pd.DataFrame(score_rows)
        s["Score"]=s["home_score"].fillna("–").astype(str)+" : "+s["away_score"].fillna("–").astype(str)
        show=[x for x in ["competition","home_team","Score","away_team","status","clock","kickoff_utc","match_id"] if x in s]
        st.dataframe(s[show].sort_values(["competition","kickoff_utc"]),hide_index=True,use_container_width=True)
    else:st.info("No score rows received. Check provider/API status before inferring no matches.")
    if score_errors:
        with st.expander("Scoreboard provider errors"):st.json(score_errors)
    st.subheader("Current sportsbook prices / 当前盘口")
    st.caption("The Odds API • fetched "+stamp(odds_at)+
               " • quote timestamps are book timestamps. Prices are indicative, NOT confirmed paper fills.")
    if live_quotes:
        o=pd.DataFrame(live_quotes)
        league_options=sorted(o["competition"].dropna().unique())
        choose=st.multiselect("Quote league",league_options,default=league_options,key="live-league")
        o=o[o["competition"].isin(choose)]
        o["quote_age_seconds"]=pd.to_datetime(odds_at,utc=True).timestamp()-pd.to_datetime(o["quote_timestamp_utc"],utc=True,errors="coerce").apply(
            lambda z: z.timestamp() if pd.notna(z) else float("nan"))
        o["freshness"]=o["quote_age_seconds"].apply(lambda age:"FRESH <30s" if pd.notna(age) and 0<=age<=30 else "STALE / UNKNOWN")
        show=["competition","home_team","away_team","market","selection","point","bookmaker",
              "decimal_odds","break_even","quote_timestamp_utc","freshness","status"]
        st.dataframe(o[show],hide_index=True,use_container_width=True,
            column_config={"break_even":st.column_config.NumberColumn(format="%.3f"),
                           "decimal_odds":st.column_config.NumberColumn(format="%.3f")})
    else:st.info("No current sportsbook quotes. Connect ODDS_API_KEY via Streamlit secrets and verify API plan/league coverage.")
    if odds_errors:
        with st.expander("Odds feed / quota / coverage errors"):st.json(odds_errors)
    st.warning("Live scoreboard and odds are separate provider feeds; event-name matching is NOT a verified synchronized event state. Do not paper-fill on this display alone.")

with tabs[1]:
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

with tabs[2]:
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
            fig.update_layout(template="plotly_white",paper_bgcolor="#ffffff",plot_bgcolor="#ffffff",
                              title="Realized NAV by settlement",height=330)
            st.plotly_chart(fig,use_container_width=True)
    else:st.info("No verified virtual orders. Account remains at $1,000,000; research/PASS rows are not fills.")
    st.subheader("Paper order audit / Signal log")
    if signals:st.dataframe(pd.DataFrame(signals),hide_index=True,use_container_width=True)
    else:st.caption("Signals file is empty.")
    if state.get("rejections"):
        with st.expander("Rejected paper signals"):
            st.dataframe(pd.DataFrame(state["rejections"]),hide_index=True)

with tabs[3]:
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

with tabs[4]:
    st.subheader("Cross-venue arbitrage / 跨平台价差")
    st.caption("Screen only — NOT an executable arbitrage claim. Requires every mutually exclusive and exhaustive outcome, same settlement rule, fees, timestamp and fillable depth.")
    groups={}
    for o in observations:
        if not (o.get("executable_verified") is True and o.get("settlement_rule") and
                o.get("market_group_id") and o.get("outcome_id") and o.get("expected_outcomes")):
            continue
        if not o.get("quote_timestamp_utc") or not o.get("decimal_odds"):continue
        try:
            age=(now-datetime.fromisoformat(o["quote_timestamp_utc"].replace("Z","+00:00")).astimezone(timezone.utc)).total_seconds()
            if not (0 <= age <= 30):continue
            if float(o["decimal_odds"]) <= 1:continue
        except (ValueError,TypeError,KeyError):continue
        key=(o["market_group_id"],o["settlement_rule"])
        groups.setdefault(key,[]).append(o)
    arbs=[]
    for (mid,rule),quotes in groups.items():
        expected=set(str(i) for i in quotes[0].get("expected_outcomes",[]))
        if not expected or any(set(str(i) for i in q.get("expected_outcomes",[]))!=expected for q in quotes):
            continue
        best={}
        for q in quotes:
            oid=str(q["outcome_id"])
            if oid not in expected:continue
            cost=1/float(q["decimal_odds"])+float(q.get("fee_per_dollar_payout",0))
            if oid not in best or cost<best[oid][0]:best[oid]=(cost,q)
        if set(best)!=expected:continue
        sumcost=sum(v[0] for v in best.values())
        if sumcost<1:
            arbs.append({"Market":mid,"Settlement":rule,
                         "All-in implied sum":round(sumcost,5),
                         "Gross margin (before slippage)":round(1-sumcost,5),
                         "Outcomes":", ".join(sorted(best)),
                         "Venues":", ".join(str(best[x][1].get("quote_source","?")) for x in sorted(best)),
                         "Caveat":"Check depth / partial fills / fees / venue payout and suspension"})
    if arbs:
        st.dataframe(pd.DataFrame(arbs),hide_index=True,use_container_width=True)
    else:
        st.info("No verified, fresh, complete cross-venue arb baskets. A disagreement in quotes alone is not guaranteed profit.")
    st.warning("For Kalshi YES/NO and sportsbook ML, settlement definitions may differ (90 min vs extra time, voids, commission). Do not match incompatible contracts.")

with tabs[5]:
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

with tabs[6]:
    st.subheader("Risk engine / Operational status")
    r1,r2,r3=st.columns(3)
    matchcap=float(account.get("maximum_exposure_per_match_usd",5000))
    bookcap=float(account.get("maximum_total_open_exposure_usd",50000))
    r1.metric("Per-match cap",money(matchcap))
    r2.metric("Book open cap",money(bookcap))
    r3.metric("Remaining book capacity",money(max(0,bookcap-open_exposure)))
    st.progress(min(1,open_exposure/bookcap) if bookcap else 0)
    st.subheader("Upstream data & freshness")
    st.write("ESPN scoreboard: "+stamp(scores_at)+" | Odds provider: "+stamp(odds_at))
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
