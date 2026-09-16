# v0.3.4 Point-in-Time Dataset + CLV Engine

## Purpose
Freeze what the model and markets knew **at the time**, so later evaluation is not contaminated by hindsight.

## Snapshot cadence
The hourly Data Engine stores one immutable record per pick per UTC hour. Each record includes:
- My Fair Probability + model source
- sportsbook de-vig consensus + book count
- Kalshi implied probability + liquidity when a verified ticker exists
- kickoff time and minutes to kickoff
- football-intelligence/model status

Snapshots are labeled by horizon:
- EARLY: >36h
- T-24H: 9h–36h
- T-6H: 2h–9h
- T-1H: 45m–2h
- CLOSE: 0–45m
- POST_KICKOFF: after kickoff

The daily archive is stored under `data/pit/YYYY-MM-DD.json`. `closing.json` keeps the closest pre-kickoff snapshot seen so far for each pick.

## CLV definitions
### Trade CLV
For a YES-side trade:
`CLV_pp = closing_probability - entry_probability`

Positive CLV means the chosen outcome became more expensive / more likely by the close. The preferred closing reference is Kalshi. If unavailable, the engine falls back to de-vig sportsbook consensus.

Historical trades are **not** assigned CLV unless entry probability and pick mapping are supported by evidence.

### Signal CLV
Separately, the engine compares the earliest archived model signal with the closest pre-kickoff market snapshot. This measures market timing even if no actual trade was placed.

## Required prospective trade fields
New tracked trades should include, when known:
- `trade_id`
- `pick_id`
- `placed_at_utc`
- `entry_probability` (preferred) or `entry_decimal_odds`
- `stake_usd`
- result/P&L fields after settlement

## Why this matters
P&L alone cannot distinguish model skill from timing and execution. Point-in-time data allows attribution into:
1. selection/model edge,
2. market timing,
3. execution quality,
4. realized outcome variance.

This engine is analytics-only and never sends an order.
