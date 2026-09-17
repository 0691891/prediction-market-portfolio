# v0.3.6 Football Intelligence + My Fair Model

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
9. Cross-division / competition tier gap
10. Squad depth and rotation resilience
11. Injuries/suspensions
12. Tactical matchup
13. Motivation/competition context
14. Weather/venue exceptional effects

The first six are machine-computable in the current adapter. Factors 7–14 are explicit research overrides until dedicated data providers are connected.

## Cup rotation: relative quality, not first-XI names
A major cup-specific rule is that rotation is evaluated **relative to the opponent actually faced**, not only relative to the rotating club's own strongest XI.

A deep elite squad can make 8–10 changes and still field a lineup whose underlying technical quality, athleticism, coaching-system familiarity and bench options are materially above a lower-division opponent. Therefore the model must not automatically translate "many changes" into a large negative expected-goals adjustment.

For a negative raw lineup adjustment, v0.3.5 can apply:

`effective_lineup_penalty = raw_lineup_penalty × (1 - rotation_depth_resilience × depth_mismatch)`

`depth_mismatch` is a pre-match research input from 0 to 1. The initial `rotation_depth_resilience` prior is 0.65. A larger mismatch means more of the rotation penalty is absorbed by elite squad depth. This interaction only softens negative rotation penalties; it does not create an automatic positive bonus.

Two additional bounded terms are available:
- `tier_gap`: structural quality difference across divisions/competition levels, cap ±0.16 log λ.
- `squad_depth`: quality of the available second unit and bench relative to the opponent, cap ±0.12 log λ.

For handicap markets such as -2.5, the model still distinguishes **win probability from margin probability**. A large tier/depth edge can support a high win probability without automatically implying a three-goal cover.

### Sep 17 learning note: Manchester City vs Norwich
The City–Norwich cup match is recorded as a model-learning example: City made extreme rotation, including academy/second-unit players, yet the structural squad and tier gap remained large. City won 5–0. This result supports testing the relative-depth hypothesis, but it is **one observation, not calibration evidence by itself**. Coefficients must be estimated from a historical sample of rotated elite-vs-lower-tier cup matches with point-in-time lineups.

## Quantification
Manual factors are not vague percentage-point bumps. They are bounded changes to log expected goals. A +0.10 log-lambda adjustment multiplies expected goals by exp(0.10)=1.105. A -0.10 adjustment multiplies them by 0.905.

Initial caps:
- recent form ±0.12 log λ
- lineup ±0.18
- tier gap ±0.16
- squad depth ±0.12
- injuries ±0.15
- rest ±0.08
- tactical ±0.10
- motivation ±0.06
- weather ±0.04

These are **initial priors**, not claimed calibrated coefficients. They must be fitted/revised through historical backtests and out-of-sample calibration.

## What is deliberately low/zero weight
Historical H2H is not a direct model input because squads/coaches change and it overlaps with team strength. "Market heat", public narratives and reverse-thinking are not inputs to My Fair; they belong in the post-model market-pricing analysis. A single match result is never used to retroactively set a coefficient.

## Validation
Track log loss, Brier score, calibration buckets, CLV, ROI, and model-vs-book consensus. Backtest by date with no look-ahead. Tune coefficients on training windows and validate on later seasons. For the new cup-rotation terms, maintain a separate slice for top-tier elite/deep squads versus lower-tier opponents and compare calibration for ML, -1.5, -2.5 and totals.

## v0.3.6 Probability-first Core Parlay construction
My Fair remains independent of market price. Portfolio construction happens only **after** My Fair is produced.

Core Parlay is now a separate bucket, not a synonym for "favorite":
- current market probability >= 65%
- My Fair >= 68% (preferred 68-82%)
- My Fair minus market probability >= 3 percentage points
- exactly two legs; different matches required and different competitions preferred
- estimated combined My Fair >= 50%
- exclude fragile favorites when lineup, motivation, injury or relative squad-depth uncertainty is unresolved

A 58% leg can still be a positive-EV Value Single, but it is **not** a Core/"safe" parlay leg. This prevents a 58% × 64% structure from being described as high-hit-rate simply because both legs individually look plausible.

The objective is not to maximize hit rate at any price. It is: **high probability first -> remove fragile favorites -> require positive edge -> combine only the best two survivors.** Short-priced favorites with no edge remain PASS.
