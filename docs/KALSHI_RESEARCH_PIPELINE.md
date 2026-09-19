# Kalshi public quotes -> Football model research (READ ONLY)

## Status and scope

The hourly workflow runs `src/kalshi_research.py` after the independent football model and research archive. No authenticated Kalshi account reads are needed and none are written to GitHub; no real or virtual orders are sent. No Streamlit Cloud configuration is required.

1. `data/kalshi_public_snapshot.json` — open football markets discovered from Kalshi public Sports series. Sources, bid/ask, status and fetch timestamps; sampled series rather than exhaustive catalog. If no markets appear, inspect `errors`, series discovery and the `data_engine.kalshi_series_tickers` config. No odds are invented.
2. `data/kalshi_mappings.json` — APPROVED pick_id ↔ exact ticker, YES/NO side, verified kickoff and contract wording. All mappings must be manually reviewed; string similarity is a candidate hint, never contract verification.
3. `data/kalshi_research.json` — for explicit mappings only: independent v0.3.6 model fair, chosen side ask, gross edge and gross EV. Net EV is null unless an actual per-contract fee is available. If the existing `data/board.json` has no picks or `data/model_fair.json` has no `MODELLED` items, fair/EV remain absent; merely adding Kalshi quotes does not create a trained model.
4. `data/kalshi_pit/YYYY-MM-DD.json` — the first fetched, pre-kickoff mapped quote per pick/side/hour is frozen; no post-kickoff backfill. The hourly cadence can miss the actual close.
5. `data/kalshi_clv.json` — same ticker+side Kalshi ask movement from earliest to latest observed pre-kickoff snapshot. It is a quoted-price diagnostic, not a fill-to-true-close CLV unless timing and fill are independently validated.
6. `data/kalshi_whatif.json` — hypothetical P&L only for prospectively frozen `paper/research_archive.json` RECOMMEND/BUY entries with original timestamp and ask exactly matching Kalshi PIT and later exchange-confirmed YES/NO binary settlement. Missing fee => NET P&L null. No changes to `paper/state.json`, `data/trades.json` or a private Kalshi balance.

## Example mapping schema (illustrative field values only, NOT a valid ticker)

```json
{
  "mappings": [
    {
      "pick_id": "EXACT_EXISTING_BOARD_PICK_ID",
      "ticker": "EXACT_VERIFIED_KALSHI_TICKER",
      "side": "yes",
      "kickoff_utc": "UTC_FROM_VERIFIED_FIXTURE",
      "contract_verified": true,
      "fair_is_mapped_side": true,
      "fee_per_contract_usd": null
    }
  ]
}
```

Do not insert this example into production as a trading signal. For NO, independent model probability must be for that exact NO outcome, rather than mechanically flipping an unrelated 1X2 draw/no bet market. Ensure regulation-time vs extra-time, postponement/void and settlement rules align. Compare BUY cost to ASK; never use LAST or BID as hypothetical buy fill. Ask-size and book depth are not guaranteed by REST snapshot.

## Hourly job

`python src/kalshi_research.py` can also be run locally with only Python standard library. Public GET endpoints do not use the user's RSA private key or GitHub Actions Secrets. The original `ODDS_API_KEY` is a different third-party sportsbook key.

GitHub snapshot updates are approximately hourly — NOT a live streaming data product. For sub-minute quotes, use an independently hosted subscriber/service; GitHub Actions cannot guarantee 30-second polling. For now, keep prematch-only paper strategy; user-requested live analysis remains a separate read-only research workflow.

## Operational blockers

The last inspected `data/board.json` contained no picks; `data/model_fair.json` contained no modelled items; `data/kalshi_mappings.json` was initialized empty. Therefore do not claim the full model→market→CLV→P&L loop has live sample outputs yet. Next fill validated actual fixture IDs/picks and market mappings, activate independent historical team data and confirm workflow completed successfully.
