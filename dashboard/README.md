# Football Alpha Terminal — Streamlit Dashboard

Read-only $1,000,000 PAPER research terminal, styled as a dark prediction-market trading screen. No automatic real-money trading, no order placement.

## Run locally

From the repository root:

```bash
python -m pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

The app defaults to **Local repository** and reads paper/account.json, paper/state.json, paper/signals.json, paper/results.json, data/board.json, model_fair.json, market_snapshot.json, sportsbook_consensus.json and PIT/CLV files. Switch on **GitHub data mode** in the sidebar to read the latest public main branch remotely.

## Host on Streamlit Community Cloud

Choose this GitHub repository and main branch; entrypoint `dashboard/app.py`; dependencies `dashboard/requirements.txt`. In sidebar switch on **GitHub data mode**. Do not publish a private GitHub paper ledger using a public raw URL: deploy privately or use a secure authenticated data adapter. The app is read-only; it doesn't need your sportsbook/Kalshi API keys.

## What is and isn't live

Auto-refresh checks for changes every 30 seconds, but does not cause new upstream data to arrive. In particular, the current `data/sportsbook_consensus.json` reports `NO_ODDS_API_KEY` and `data/model_fair.json` has zero items. GitHub data may be updated only hourly and cannot promise seconds-fresh executable in-play quotes. UI shows missing data rather than invented positions/odds/fills. Hook in a licensed scores+odds event/market feed and a verified `paper/observations.json` writer to obtain meaningful in-play coverage.

Suggested `paper/observations.json` schema: `{"observations":[{"match_id":"...","competition":"Premier League","match":"...","market":"...","entry_phase":"LIVE","status":"WATCH","kickoff_utc":"...","quote_timestamp_utc":"...","market_probability":0.42,"decimal_odds":2.38,"fair_probability":0.47,"ev":0.1186,"risk_flags":[],"pass_reason":"..."}]}`. Fields must come from real frozen source data. Do not populate sample observations with fabricated prices.

PAPER NAV excludes unverified mark-to-market of open contracts. CLV and model-calibration panels intentionally show no metrics without valid observations. Real ledger `data/trades.json` is never read or changed by this app.

Football betting and parlays can lose all capital committed.
