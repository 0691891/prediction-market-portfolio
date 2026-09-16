# v0.3.2 Football Intelligence + My Fair Model

## Principle
**My Fair is independent of sportsbook and Kalshi prices.** Market prices are used only after the model produces a probability, for comparison, EV and sanity checks.

## Goal-space architecture
We model expected goals `lambda_home` and `lambda_away`, then convert them into a score distribution with a Poisson matrix.

Base rates come from the competition's observed home/away scoring environment. Team attack and defense multipliers come from exponentially recency-weighted finished matches, shrunk toward league average to reduce small-sample noise.

`lambda_home = league_home_rate × home_attack × away_defense × exp(adjustments)`
`lambda_away = league_away_rate × away_attack × home_defense × exp(adjustments)`

The score matrix gives P(Home win), P(Draw), P(Away win), totals and handicap cover probabilities.

## Factor families
1. League scoring environment
2. Team attacking strength
3. Team defensive strength
4. Recency/time decay
5. Home advantage
6. Rest/fatigue differential
7. Recent-form research override
8. Confirmed/projected lineup
9. Injuries/suspensions
10. Tactical matchup
11. Motivation/competition context
12. Weather/venue exceptional effects

The first six are machine-computable in the current adapter. Factors 7–12 are explicit research overrides until dedicated data providers are connected.

## Quantification
Manual factors are not vague percentage-point bumps. They are bounded changes to log expected goals. A +0.10 log-lambda adjustment multiplies expected goals by exp(0.10)=1.105. A -0.10 adjustment multiplies them by 0.905.

Initial caps:
- recent form ±0.12 log λ
- lineup ±0.18
- injuries ±0.15
- rest ±0.08
- tactical ±0.10
- motivation ±0.06
- weather ±0.04

These are **initial priors**, not claimed calibrated coefficients. They must be fitted/revised through historical backtests and out-of-sample calibration.

## What is deliberately low/zero weight
Historical H2H is not a direct model input because squads/coaches change and it overlaps with team strength. “Market heat”, public narratives and reverse-thinking are not inputs to My Fair; they belong in the post-model market-pricing analysis.

## Validation
Track log loss, Brier score, calibration buckets, CLV, ROI, and model-vs-book consensus. Backtest by date with no look-ahead. Tune coefficients on training windows and validate on later seasons.
