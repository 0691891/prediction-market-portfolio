#!/usr/bin/env python3
"""Streamlit page: Model factor odds/PnL attribution for Sep 19 morning what-if."""
import json
import pathlib
import urllib.request

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "https://raw.githubusercontent.com/0691891/prediction-market-portfolio/main/"
DATA_PATH = "data/reviews/2026-09-19-morning_factor_attribution.json"

st.set_page_config(page_title="Model Factor PnL", page_icon="🧠", layout="wide")


def money(x):
    try:
        return f"${float(x):,.2f}"
    except (TypeError, ValueError):
        return "—"


def pct(x):
    try:
        return f"{float(x):+.2%}"
    except (TypeError, ValueError):
        return "—"


@st.cache_data(ttl=30, show_spinner=False)
def load_data(remote=True):
    if remote:
        req = urllib.request.Request(BASE + DATA_PATH, headers={"User-Agent": "FootballAlphaTerminal/1.0"})
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.load(response)
    return json.loads((ROOT / DATA_PATH).read_text())

with st.sidebar:
    st.markdown("## 🧠 Factor PnL")
    remote = st.toggle("GitHub data mode", value=True)
    st.caption("What-if research only. No actual/paper fill.")

try:
    doc = load_data(remote)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load factor attribution data: {exc}")
    st.stop()

summary = doc.get("summary", {})
st.title("Model Factor Odds & PnL Attribution / 模型因子赔率与盈亏拆解")
st.caption(doc.get("mode", "WHAT_IF") + " · " + doc.get("date", ""))

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("What-if P&L", money(summary.get("realized_whatif_pnl_usd")))
c2.metric("Stake", money(summary.get("settled_stake_usd")))
c3.metric("ROI", pct(summary.get("roi_on_stake")))
c4.metric("Ex-ante model EV", money(summary.get("ex_ante_model_ev_usd")))
c5.metric("Actual fills", str(summary.get("actual_verified_fills", 0)))

trades = doc.get("trades", [])
trade_rows = []
factor_rows = []
for t in trades:
    trade_rows.append({
        "Match": t.get("short_match") or t.get("match"),
        "Market": t.get("market"),
        "Odds": t.get("decimal_odds"),
        "Break-even": t.get("market_break_even_probability"),
        "Model fair": t.get("model_fair_probability"),
        "Edge pp": t.get("total_edge_pp"),
        "Stake": t.get("stake_usd"),
        "Result": t.get("result"),
        "What-if P&L": t.get("realized_whatif_pnl_usd"),
        "Ex-ante EV": t.get("ex_ante_model_ev_usd"),
    })
    for f in t.get("factor_rows", []):
        factor_rows.append({
            "Match": t.get("short_match") or t.get("match"),
            "Market": t.get("market"),
            "Entry odds": t.get("decimal_odds"),
            "Factor": f.get("factor"),
            "Factor probability pp": f.get("probability_contribution_pp"),
            "Cumulative fair after factor": f.get("cumulative_fair_after_factor"),
            "Fair odds after factor": f.get("cumulative_fair_odds_after_factor"),
            "Factor ex-ante EV $": f.get("factor_ev_usd"),
            "Realized P&L attribution $": f.get("realized_pnl_factor_attribution_usd"),
        })

st.markdown("### Final per-match P&L / 每场最终盈亏")
st.dataframe(pd.DataFrame(trade_rows), hide_index=True, use_container_width=True,
    column_config={
        "Odds": st.column_config.NumberColumn(format="%.3f"),
        "Break-even": st.column_config.NumberColumn(format="%.2%"),
        "Model fair": st.column_config.NumberColumn(format="%.2%"),
        "Edge pp": st.column_config.NumberColumn(format="%.2%"),
        "Stake": st.column_config.NumberColumn(format="$%.2f"),
        "What-if P&L": st.column_config.NumberColumn(format="$%.2f"),
        "Ex-ante EV": st.column_config.NumberColumn(format="$%.2f"),
    })

st.markdown("### Factor-level odds & PnL / 因子级赔率与盈亏")
fd = pd.DataFrame(factor_rows)
match_filter = st.multiselect("Match filter", sorted(fd["Match"].unique()), default=sorted(fd["Match"].unique()))
fd_view = fd[fd["Match"].isin(match_filter)]
st.dataframe(fd_view, hide_index=True, use_container_width=True,
    column_config={
        "Entry odds": st.column_config.NumberColumn(format="%.3f"),
        "Factor probability pp": st.column_config.NumberColumn(format="%.2%"),
        "Cumulative fair after factor": st.column_config.NumberColumn(format="%.2%"),
        "Fair odds after factor": st.column_config.NumberColumn(format="%.3f"),
        "Factor ex-ante EV $": st.column_config.NumberColumn(format="$%.2f"),
        "Realized P&L attribution $": st.column_config.NumberColumn(format="$%.2f"),
    })

st.markdown("### Realized P&L attribution chart / 实现盈亏归因")
fig = px.bar(fd_view, x="Factor", y="Realized P&L attribution $", color="Match", barmode="group",
             hover_data=["Entry odds", "Factor probability pp", "Fair odds after factor", "Factor ex-ante EV $"])
fig.update_layout(height=520, xaxis_title="", yaxis_title="Attributed realized P&L ($)")
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Ex-ante EV by factor / 下注前EV因子拆解")
fig2 = px.bar(fd_view, x="Factor", y="Factor ex-ante EV $", color="Match", barmode="group",
              hover_data=["Entry odds", "Factor probability pp", "Fair odds after factor"])
fig2.update_layout(height=520, xaxis_title="", yaxis_title="Ex-ante model EV ($)")
st.plotly_chart(fig2, use_container_width=True)

with st.expander("Methodology / 方法说明", expanded=False):
    st.json(doc.get("methodology", {}))
    st.warning("Factor P&L is a model attribution layer, not causal proof. A single match result cannot prove which factor caused the win. Use this for audit, sizing, and future calibration only.")

st.caption("Actual paper NAV remains $1,000,000 with 0 verified fills. Football bets/parlays can lose 100% of committed stake.")
