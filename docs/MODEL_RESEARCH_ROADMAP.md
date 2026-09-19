# Football Intelligence vNext — pricing-model research design

The production repo's current src/fair_model.py is a Poisson goal model with bounded expert log-lambda adjustments, NOT a fitted deep neural network or a proven calibrated production estimator. data/model_fair.json had 0 items and calibrated_params_active=false in the 2026-09-19 morning audit. Existing coefficients are priors awaiting out-of-time validation.

## Layer A: baseline distribution
Hierarchical team attack/defense strengths with recency, opponent and league strength, venue, fixture importance, and per-team shrinkage. Prefer regularized Poisson / negative binomial when dispersion tests justify it; evaluate Dixon–Coles low-score correction or a bivariate Poisson for dependence. Estimate home/away expected goals from strictly pre-event inputs and derive 1X2, Asian handicap, BTTS, totals **from one coherent score distribution**, not unrelated regressions. Book market consensus is a separate comparator, not silently an explanatory variable in My Fair.

For a simple baseline:
log(lambda_home)=league_home_intercept+attack_home-defense_away+home_advantage+adjustments.
log(lambda_away)=league_away_intercept+attack_away-defense_home+adjustments.
Predicted score P(H=h,A=a) yields all coherent prematch contracts by summation.

## Layer B: football intelligence
Features with evidence timestamp and missingness: confirmed XI, player minutes/quality and chemistry measured by shared starts, absences, positional replacement, formation/coach changes, fatigue/rest/travel, squad-depth quality *relative to opponent*, press/build-up and transition matchup, xG and shot quality/volume, set-piece profile, weather, motivation. Avoid literal transfer-market value as a deterministic win score; use lagged values as weak prior with league normalization, regression shrinkage and regularization. More data required before fitting dozens of free interaction coefficients.

Use regularized generalized linear/partial pooling for interpretable base; experiment with gradient boosting (CatBoost/LightGBM) for nonlinear interactions (tier_gap × rotation, press × buildup, time × red cards), constrained and calibrated out-of-time. Blend only if it reduces holdout log loss/Brier and improves reliability. Models output *distributions* and uncertainty, not single-point certainty.

## Layer C: live conditional model
Model goal hazard per team conditional on minute, current score, on-field XI, substitutions, cards/player positional value, xG pace and possession state. Recompute remainder-game score distribution after each verified event (survival/hazard, time-varying Poisson, Monte Carlo). Goal/red card updates materially alter both market and fair; a cheaper favorite price is not sufficient reason to buy. Use source timestamps and stale/paused market gates. In-play closing-value comparisons must be like-for-like same-contract, same event horizon (never compare postgoal price to prematch close).

## Layer D: decision engine
For contract cost c and conditional fair probability p, net expected return per dollar cost (ignoring fees) = p/c - 1 = p*decimal_odds - 1. Incorporate fee and slippage, observed executable depth, stale quote, worst-case exposure, correlation and model uncertainty. Positive independent EV is a candidate, not arbitrage; genuine arbitrage needs exhaustive outcomes, harmonized settlement/void rules, synchronously executable offers and fees+slippage netted. Use conservative fraction-of-Kelly with hard per-match and whole-book caps only AFTER calibration; during pilot use the existing fixed A/B/C maximum caps.

## Validation and learning loop
Persist all fixtures and PASS observations, independent quote/fair/model version/known information timestamp BEFORE kickoff or in-play fill; never reconstruct an entry after seeing final result. Chronological rolling/expanding training, contiguous out-of-time evaluation, league/season grouped diagnostics, never leakage from closing market/result after decision point. Evaluate multiclass log loss, Brier, reliability/ECE, scoreline/totals calibration, by-competition and by price bucket, CLV, ROI with confidence intervals, fees, slippage, max drawdown, and opportunity selection bias. Correct for multiple testing and uncertainty. Track interpretation/override disagreements prospectively. Stage introduction: baseline GLM -> score distribution -> hierarchical player covariates -> boosted residual correction -> in-play hazard; do not jump straight to deep learning on a small unclean dataset.

## 2026-09-19 match audit
T-1H Gladbach–Mainz Over2.5 @1.55 fair70% won; Frankfurt–Freiburg O2.5 @1.60 fair70% won; Bremen–Augsburg O2.5 @1.53 fair68% won. Hamburg–Köln O2.5 @1.57 fair59% was negative EV and passed even though it won. Mainz ML was a lean without original odds/fair/stake, so no dollar what-if. $4,622.50 what-if positive from three recorded T-1H picks on $8,250 stake, but no proven executed paper fills and no change to $1m virtual NAV. One 3/3 result set is insufficient for coefficient fitting or claim of alpha. Source: data/reviews/2026-09-19-morning.json.
