# Football Alpha Engine v0.4 — implementation and activation gates

## What is implemented

- `src/v04_engine.py`: prospective fixture discovery (ESPN; Football-Data.co.uk fixture CSV fallback; community openfootball fallback), five major league historical scores, 1X2/O2.5/U2.5/BTTS YES/NO independent Poisson probabilities, all candidates including UNRATED/PASS. Never uses Kalshi prices or grades to fit probabilities. Fails closed for missing history or ambiguous team aliases.
- `src/v04_mapping.py`: review-only match/event candidate queue. Does not conflate one team's name with an event or approve settlement rules from string similarities.
- `src/kalshi_research.py`: public market GET, manually verified mapping, pre-kickoff PIT, same-contract-side quote movement, exchange-settled hypothetical research P&L. Does not read account secrets or place orders. The BUY price is ASK, not bid/last.
- `src/fixture_ingest.py`: match-score observations plus source-stamped completed league scores (not fictional paper fills).
- `dashboard/app.py`: current independent model board, Kalshi public quotes, mapping review, edge/EV, CLV and separate research P&L.
- `.github/workflows/data-engine.yml`: scheduled hourly P0 stages and v0.4 model invariants.

## Why zero model/EV rows may be honest

1. ESPN public scoreboard returned HTTP 403 for 27 league/date requests on GitHub Actions 2026-09-20 02:13 UTC. The v0.4 engine now tries Football-Data.co.uk weekly fixture CSV, then openfootball 2026/27 community league fixture JSON. A source may be stale or unavailable, and schedule time is not independently cross-checked; do not force a quote against an unverified fixture.
2. football-data.org key and ODDS_API_KEY were still absent in the latest observed reports. The independent model uses the existing accessible Football-Data.co.uk results CSV, not Kalshi; historical scores had no fetch errors at that time.
3. `data/kalshi_mappings.json` has zero manually approved mappings. `data/kalshi_research.json` must not display verified fair or EV until exact market selection, YES/NO, match date, ninety-minute rule and fee are checked.
4. No historical hypothetical BUY is backfilled. Latest data can legitimately show 0 priced observations.

## Historical validation warning — do not suppress

`data/backtest.json` (2024/25 train, 2025/26 holdout, 500 matches) found the standalone goals-model historical closing-odds proxy strategy placed 383 trades, **lost $7,810 on $38,300 stake (~-20.39% ROI)**, without fees. It is **not an acceptable production A/A- system**.

`data/backtest_v04.json` market-prior residual proxy chose football residual weight **0**, meaning the market-only model beat the standalone goals model on training log loss; the holdout market log loss was ~0.9627 versus the football model ~0.99992. The v0.4 goals output is exploratory independent probability, not proven edge. The user's retrospective September 19 three Bundesliga O2.5 wins are separate and not evidence this v0.4 model traded profitably.

## Activation requirements

1. Prospectively generate timestamped fixtures and seven score-distribution-based markets, including PASS, with no post-kickoff reconstructed fair values.
2. Determine canonical team-ID and fixture-ID across sources; verify timestamp and league-local timezone. In ambiguous fixtures use `INSUFFICIENT_DATA` rather than guessed results.
3. Fetch authoritative Kalshi Event + market detail and rules; link exact ticker, YES/NO selection, kickoff/settlement rule and fee. Save approved mapping only after check; never infer 90-minute contract solely from `GAME` series ticker.
4. Decompose past-only xG, lineup, tactical and other factors when a real point-in-time source exists; do not label those factors trained before coverage and separate holdout calibration.
5. Compare proper independent Fair to ASK and incorporate fees and size-weighted orderbook depth. Persist both quote fetch time and market update time. No automatic A/A- recommendation/virtual fill on an unvalidated raw prior.
6. For settlement, use exchange-reported YES/NO outcome and original archived pre-kickoff BUY quote; report net hypothetical P&L only when fee is known. Full-time football score reviews and Kalshi settlement are distinct where match rules differ.
7. Evaluate 300–500+ frozen samples with log loss/Brier/reliability and true same-contract CLV, fee-adjusted out-of-sample P&L and capacity; predeclare A/A- rules and record losses.

## Useful commands

```sh
python -m unittest discover -s tests -p test_v04_engine.py
python src/v04_engine.py
python src/kalshi_research.py
python src/v04_mapping.py
```

No Streamlit Cloud setup or private Kalshi account credentials required for this pipeline.
