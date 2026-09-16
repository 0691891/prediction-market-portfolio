# Trade Ledger Schema for CLV

For future trades, add these fields prospectively when known.

## Single-leg trade
```json
{
  "trade_id": "2026-09-16-001",
  "pick_id": "arsenal-ipswich-90m",
  "position": "Arsenal 90-min win",
  "placed_at_utc": "2026-09-16T18:05:00Z",
  "entry_probability": 0.71,
  "entry_decimal_odds": 1.4085,
  "stake_usd": 25.0,
  "status": "OPEN"
}
```

## Combo trade
Store each leg separately under `legs` so CLV can be attributed leg by leg.
```json
{
  "trade_id": "2026-09-16-002",
  "position": "2-leg combo",
  "placed_at_utc": "2026-09-16T18:10:00Z",
  "stake_usd": 20.0,
  "legs": [
    {"pick_id":"pick-a","position":"Team A win","entry_probability":0.62},
    {"pick_id":"pick-b","position":"Under 3.5","entry_probability":0.68}
  ],
  "status": "OPEN"
}
```

The CLV engine never backfills unsupported historical entry probabilities. Combo CLV is reported per leg unless a separately quoted combo market itself is mapped and recorded.
