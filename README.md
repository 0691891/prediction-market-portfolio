# Prediction Market Portfolio

Football prediction-market dashboard and research ledger.

## Dashboard
GitHub Pages serves `index.html`. Data lives in `data/*.json` so scheduled research can update the board and trade ledger without rewriting the UI.

## Modes
Paper trading → approval mode → execution only after validation.

## Portfolio rules
- A: genuine edge single: 0.5–0.75u
- B: two-leg safer combo across different leagues: 0.25–0.5u
- C: 2.5x–4x speculative combo: ≤0.25u
- Aggregate correlated exposure per match: ≤1u

Gambling involves risk of loss.