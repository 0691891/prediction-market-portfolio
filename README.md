# Prediction Market Portfolio

Football prediction-market research dashboard + v0.3.2 Football Intelligence Data Engine.

## 流程 / Workflow
Scheduled research → My Fair Probability → Kalshi public market snapshot → Edge/EV → Risk Gate → Paper Signal → Manual Approval → Execution (disabled in v0.3).

## Dashboard
中英混杂 / bilingual mixed UI:
- 今日机会 / Daily Board
- 审批队列 / Approval Queue
- 交易记录 / Trade Tracking
- 业绩 / Performance
- 风控 / Risk Rules

## v0.3
`src/data_engine.py` refreshes verified Kalshi tickers, recalculates market probability / decimal odds / edge / EV, then generates the approval queue. Missing tickers are never guessed. GitHub Actions runs the public-data refresh hourly.

Hard gates: Edge ≥4pp, EV ≥5%, liquidity threshold, match exposure ≤1u. **Real-money auto execution is OFF.**

See `docs/DATA_ENGINE.md`.

Gambling involves risk of loss.\n\n## v0.3.1 Sportsbook Consensus\nOptional The Odds API v4 adapter de-vigs bookmaker prices and computes a median consensus. Add repository secret `ODDS_API_KEY` to activate it. Large model-vs-consensus disagreements are sent to manual review.\n

## v0.3.2 Football Intelligence
Adds a football-data.org adapter plus a transparent expected-goals/Poisson fair-probability model. Market prices are excluded from My Fair. Machine factors currently include scoring environment, attack/defense strength, recency decay, home advantage and rest. Lineup/injury/tactical/motivation/weather adjustments are explicit bounded research overrides until dedicated feeds are connected. Add GitHub secret `FOOTBALL_DATA_API_KEY` to activate the automated match-history layer.
