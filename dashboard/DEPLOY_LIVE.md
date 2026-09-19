# Light-mode live dashboard (v1.1)

Start from repo root:
```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```
Cloud: set entrypoint dashboard/app.py; set Theme to Light if a user-level Streamlit theme overrides repo config. GitHub data mode is ON by default for hosted deployments.

### Current data wiring
- ESPN public soccer scoreboard endpoint polled server-side every ~25 seconds while app has a viewer; nine leagues/cups. This is a **scoreboard**, not a licensed match event stream. League coverage may vary and provider errors are shown. Shows scoreboard fetch timestamp, statuses and kickoff; do not assume score updates are instant.
- Optional The Odds API v4 sportsbook h2h/spreads/totals, cached 60s to control quotas; enable by adding `ODDS_API_KEY = "your-key"` in **Streamlit Cloud app secrets** (not code/GitHub), or setting environment variable ODDS_API_KEY. The Odds API plans/league keys may vary. If no key, odds panel is explicitly unavailable.
- `paper/state.json` and PIT come from local checkout or public GitHub raw main in GitHub mode. These are snapshot data, potentially hourly, **not live NAV marks**.
- Kalshi quote integration has not been authenticated/implemented in this dashboard; do not infer Kalshi from sportsbook prices.
- A visible quote is indicative, not confirmed executable. The paper engine requires archived synchronous score state + actual ask/liquidity evidence and conditional fair with timestamps. This scoreboard+odds read-only screen alone is not a paper execution signal.

### Operational next step
To run 24/7 independent of viewer sessions, add a server-side fixture/event/odds ingest job with persistent timestamped archives, provider SLA, event-ID mappings, red/yellow cards/confirmed XI, order-book depth, and verified paper fill rules. Streamlit reruns by themselves do not persist every refresh or provide seconds-fresh market states.

Avoid exposing private keys in the public HTML file or browser JavaScript.
