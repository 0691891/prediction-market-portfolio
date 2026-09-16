# Prediction Market Portfolio

Football prediction-market research dashboard and trade ledger.

## Live workflow
Scheduled research → fair probability / EV → portfolio risk gate → paper signal → approval queue → execution only after explicit approval.

## Dashboard tabs
- Daily Board
- Approval Queue
- Trade Tracking
- Performance
- Risk Rules

## Portfolio rules
- A genuine-edge single: 0.5–0.75u
- B two-leg safer combo across different leagues: 0.25–0.5u
- C 2.5x–4x speculative combo: ≤0.25u
- Aggregate correlated exposure per match: ≤1u

## Analytics
The ledger stores numeric stake and P&L fields. Current closed-trade metrics are calculated only from confirmed records. CLV, Brier Score and EV realization are tracked prospectively as closing probabilities become available; historical values are not backfilled without evidence.

GitHub Pages deploys on pushes to main. Gambling involves risk of loss.