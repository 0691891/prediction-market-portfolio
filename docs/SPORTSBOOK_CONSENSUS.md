# Sportsbook Consensus Engine v0.3.1

Purpose: compare **My Fair Probability** with a de-vigged bookmaker consensus before a signal reaches Approval.

Provider adapter: The Odds API v4. The engine requests h2h, spreads and totals, then removes bookmaker margin per market and takes the median fair probability across available books.

Output: `data/sportsbook_consensus.json`.

Safety:
- Read-only; it never places bets.
- Missing API key produces `NO_ODDS_API_KEY`, not fake data.
- Unmatched sport/event/market is explicitly flagged.
- Model-vs-consensus gaps above 12pp are routed to **MODEL/CONSENSUS REVIEW**, not automatically approved.

GitHub secret required: `ODDS_API_KEY`.
