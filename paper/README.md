# Paper Portfolio v1.0 — $1,000,000 virtual capital

Purpose: collect **all covered football fixtures as observations** and simulate only reproducible positive-EV paper orders. This is completely separate from `data/trades.json` (real confirmed transactions). No real-money execution.

Coverage: Premier League, La Liga, Serie A, Bundesliga, Ligue 1, UEFA Champions League, UEFA Europa League, EFL/Carabao Cup, FA Cup.

## Two layers
- **Fixture / candidate dataset:** every fixture, kickoff UTC, match ID, provider, timestamp, model version, XI status, availability, tactical/rotation/rest/weather flags, risk factors, each observed 1X2/spread/total/BTTS price (where available), bid/ask, liquidity, fair probability, de-vig consensus, EV, no-bet reason. Record PASS matches too. Missing data must remain null, not estimated or retrospectively replaced.
- **Virtual orders:** only model-qualified markets with a contemporaneous, checkable executable sportsbook odds or Kalshi-side ask, sufficient liquidity, compatible market definitions, and no unresolved hard flags. Freeze the PIT fair/price/quote/source/size at virtual entry. If odds inaccessible or no real paper fill model, WATCH/PASS instead of invented entry.

Account: initial NAV $1,000,000 USD, cash funded virtually, open liability/reserved capital deducted from available cash. Default 1u = 0.5% starting NAV = $5,000; per-match exposure <= 1u ($5k); total simultaneous committed capital <= 5% starting NAV ($50k). Single grade A 0.5–0.75u; exploratory B 0.25–0.5u; C <=0.25u. Additional experimental tiers must be flagged, and grading should be based on modeled EV and uncertainty rather than win probability alone. Size limits are caps, not minimum wagers. Paper exposure includes overlapping singles and combos and must be counted against every affected match. No forced wagers.

Paper signal fields: `signal_id, match_id, competition, match, kickoff_utc, market, selection, quote_timestamp_utc, quote_source, quote_url, decimal_odds, fair_probability, model_version, grade, stake_usd, lineup_status, risk_flags, liquidity_usd, market_id, scenario, paper_eligible`. A repeated signal_id must not result in a second order; changed prices require a new timestamped signal ID. Paper lines are not real fills; for sportsbook use quoted decimal odds, for Kalshi convert actual side ask incl. fees/spread or record fees separately. Bookmaker execution assumptions must be documented.

Settlement results: independently verified final score and market rule/result, `match_id, market_id, selection, outcome (WIN/LOSS/VOID/PUSH), result_source, verified_at_utc`, with unambiguous grading for 90-minute regular time vs extra time. WIN net P&L = stake*(decimal_odds-1)-fees; LOSS = -stake-fees; VOID/PUSH = -fees. Mark outstanding trades OPEN until verified, never assume result. NAV = $1m + realized P&L + unrealized MTM if reliable executable mark exists (otherwise report realized NAV and reserved/open exposure separately).

Metrics: coverage %, total candidate signals, no-bet reasons, paper fill count, invested/exposed $, realized and unrealized P&L, ROI on settled stake, NAV return, win %, fair-probability bucket calibration, Brier/log loss on settled prediction universe, CLV (same market, same side), average EV, slippage/fees, by league/market/odds band/grade/lineup certainty/strategic thesis. Prevent leakage by freezing a pre-kickoff snapshot and never overwriting forecasts after kickoff.

Keep a distinct `paper/` namespace. Never write the confirmed real-money ledger from paper operations. Start at $1m with zero orders and zero P&L; never backfill simulated fills using old prices. Past actual bets can inform rules but must not be represented as new virtual bets.
