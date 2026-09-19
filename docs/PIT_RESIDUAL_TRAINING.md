# PIT residual-alpha training contract

Run `python src/train_residual_alpha.py`. Scheduled GitHub Actions: `.github/workflows/train-residual.yml`.

**Do not label an unavailable historical factor as trained.** Current Football-Data CSV has 1X2 opening/closing odds, scores, dates and basic match statistics; it does **not** provide verified point-in-time xG, lineup, injuries, tactical classifications or timestamped intra-day prices for 500 matches. Closing odds are future information for a T-1H strategy and must not be an input at T-1H.

## Required data

Create `data/pit_training/matches.jsonl` (one JSON object per match/snapshot), e.g.:

```json
{"match_id":"E0-2025-08-16-team-a-team-b","league":"Premier League","market_type":"1X2","kickoff_utc":"2025-08-16T14:00:00Z","snapshot_utc":"2025-08-16T13:00:00Z","market_observed_utc":"2025-08-16T12:59:00Z","market_odds_1x2":[1.85,3.6,4.4],"features":{"attack_xg":0.28,"defense_xga":-0.12,"lineup":0.3,"market_movement":0.015},"feature_observed_utc":{"attack_xg":"2025-08-15T18:00:00Z","defense_xga":"2025-08-15T18:00:00Z","lineup":"2025-08-16T12:45:00Z","market_movement":"2025-08-16T12:59:00Z"},"result_90m":"H"}
```

This is a **schema illustration only**, not a real match or training row. Every `features` value must be measured/derived using information observed by `snapshot_utc`. The trainer selects latest snapshot before kickoff per match, refuses post-snapshot features or odds, and refuses odds older than 1 hour. All match results must be 90-minute outcomes.

Feature names are in `src/residual_pricing.py` CAPS. Required evidence and derivations:
- xG/xGA, shot volume and xG/shot: historical match-by-match xG provider, timestamp/availability audit, rolling opponent-adjusted values using only matches strictly earlier than snapshot.
- lineup and injuries: lineup publication time, player availability, projected vs actual lineup, minutes/strength contributions based only on past games.
- tactical matchup: frozen coach/team tactical metrics (PPDA, buildup turnovers, transition xG, set-piece xG) with predeclared transforms; do not hand-score after seeing final result.
- market movement: at least two timestamped odds snapshots both preceding entry, same market/book/outcome mapping; opening-to-closing is **not** an acceptable prematch T-1H input if close is later than entry.
- human disagreement: documented user thesis timestamp strictly before entry; post-match recollection is excluded.

## Training / scoring

`p_i = softmax(log(p_market,i) + Σ_j w_ji z_j)`

`z_j = clip((x_j - mean_train_j)/sd_train_j,-2,2)`

Minimize train log loss plus L2 penalty, fixed train cutoff 2025-07-01. Evaluate 2025/26 holdout untouched. Report market-only baseline, residual model log loss/Brier/accuracy, ablation delta, feature coverage, paper-proxy ROI. Require ≥500 historical training fixtures and ≥300 holdout fixtures; **training and holdout counts are distinct**. Missing values are train-mean-imputed (zero standardized signal) and their coverage is reported. A factor with zero coverage cannot be called trained.

No candidate is activated into `data/config.json` automatically. Positive out-of-sample log-loss/Brier/ROI and enough data/CLV/fee tests are needed before considering live paper signal eligibility. Historical backtest P&L is separate from today's paper NAV.
