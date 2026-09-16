# v0.3 Data Engine / 数据引擎

## Current pipeline
1. **Research layer / 研究层** writes `data/board.json` with fair probabilities.
2. **Market adapter / 市场适配器** reads public Kalshi market data when a `kalshi_ticker` is mapped.
3. **Pricing engine / 定价引擎** calculates market probability, decimal odds, edge and expected ROI.
4. **Risk gate / 风控闸门** requires Edge ≥4pp, EV ≥5%, liquidity threshold, and portfolio limits.
5. **Approval Queue / 人工审批** is generated in `data/approval.json`.
6. **Execution / 执行** remains disabled. v0.3 never sends an order.

## Mapping
Each board pick has `kalshi_ticker` and `kalshi_side`. Until a ticker is verified, the signal is marked **NEEDS TICKER MAP** rather than guessed.

## Next adapters
- Sportsbook consensus / de-vig reference price
- Fixtures + injuries + confirmed lineups
- Closing-price recorder for CLV
- Kalshi demo authenticated execution (v0.4)

Public Kalshi market endpoints are used without credentials. Real-money execution is intentionally disabled.
