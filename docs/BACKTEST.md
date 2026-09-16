# v0.3.3 Backtesting & Calibration

## Objective
Prove or reject the model with out-of-sample probability quality before scaling execution.

## No-lookahead design
For each league, matches are sorted chronologically. Every predicted match uses only earlier completed matches. The first 70% of each league is the training window; the final 30% is untouched holdout.

A global grid search fits only three machine hyperparameters on training log loss:
- recency half-life: 30 / 60 / 90 / 120 days
- shrinkage: 4 / 8 / 12 / 16 pseudo-matches
- home-advantage log-lambda: 0.04 / 0.08 / 0.12 / 0.16

The winning training parameters are frozen and evaluated on the holdout.

## Metrics
- Multiclass Log Loss: primary fitting objective
- Multiclass Brier Score: probability accuracy
- Accuracy: diagnostic only, not optimization target
- Calibration buckets: predicted probability vs actual frequency
- Per-league holdout metrics
- CLV/ROI: explicitly unavailable until historical closing/entry odds are stored

## Activation rule
Calibrated parameters are marked active only with at least 500 holdout predictions. A small sample never silently becomes production calibration.

## Important limitation
This backtest currently validates the machine core (team scoring strength, recency, shrinkage, home advantage). It does **not** backtest discretionary lineup/injury/tactical overrides because historical point-in-time versions of those inputs are not yet stored. Adding today's injury status to old matches would create look-ahead bias.

## Next
Store point-in-time pre-match snapshots and closing odds prospectively; then test incremental value of each factor with ablation studies.
