# Prediction Market Portfolio

Football prediction-market research dashboard + v0.3.4 Point-in-Time / CLV engine.

## 流程 / Workflow
Scheduled research → My Fair Probability → Sportsbook/Kalshi market snapshots → Point-in-Time archive → Edge/EV → Risk Gate → Paper Signal → Manual Approval → Execution (disabled for automatic real-money trading).

## Dashboard
中英混杂 / bilingual mixed UI:
- 今日机会 / Daily Board
- 审批队列 / Approval Queue
- 交易记录 / Trade Tracking
- 业绩 / Performance
- 模型 / Model Lab
- 时点数据 & CLV / PIT + CLV
- 风控 / Risk Rules

## v0.3 Data Engine
`src/data_engine.py` refreshes verified Kalshi tickers, recalculates market probability / decimal odds / edge / EV, then generates the approval queue. Missing tickers are never guessed. GitHub Actions runs the public-data refresh hourly.

Hard gates: Edge ≥4pp, EV ≥5%, liquidity threshold, match exposure ≤1u. **Real-money auto execution is OFF.**

## v0.3.1 Sportsbook Consensus
Optional The Odds API v4 adapter de-vigs bookmaker prices and computes a median consensus. Add repository secret `ODDS_API_KEY` to activate it. Large model-vs-consensus disagreements are sent to manual review.

## v0.3.2 Football Intelligence
Adds a football-data.org adapter plus a transparent expected-goals/Poisson fair-probability model. Market prices are excluded from My Fair. Machine factors currently include scoring environment, attack/defense strength, recency decay, home advantage and rest. Lineup/injury/tactical/motivation/weather adjustments are explicit bounded research overrides until dedicated feeds are connected. Add GitHub secret `FOOTBALL_DATA_API_KEY` to activate the automated match-history layer.

## v0.3.3 Backtesting & Calibration
Adds chronological no-lookahead backtesting, training-only grid search, untouched 30% holdout evaluation, calibration buckets, and per-league diagnostics. Calibrated parameters activate in the live model only after at least 500 holdout predictions. No historical CLV or ROI is invented when historical odds are unavailable. See `docs/BACKTEST.md`.

## v0.3.4 Point-in-Time Dataset + CLV
`src/point_in_time.py` freezes one snapshot per pick per UTC hour, including My Fair, sportsbook consensus, Kalshi implied probability/liquidity, kickoff horizon and model/intelligence status. Daily immutable archives live under `data/pit/YYYY-MM-DD.json`; `closing.json` maintains the closest pre-kickoff snapshot observed.

`src/clv_engine.py` computes prospective trade CLV and signal CLV. For YES-side trades, positive CLV means the selected outcome closed at a higher implied probability than the entry price. Historical CLV is not fabricated when entry probability or pick mapping is missing. See `docs/POINT_IN_TIME_CLV.md`.

Gambling involves risk of loss.
