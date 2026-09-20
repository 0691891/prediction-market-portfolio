# Prediction Market Quant Strategy — Sports Research & Paper Portfolio

**Independent quantitative research project** applying probability modeling, market pricing, point-in-time validation and portfolio risk controls to sports prediction markets. The implemented modeling pipeline is primarily **football/soccer**; basketball is an intended research extension, not a claim of equivalent live model coverage.

> Research and paper trading only. No automatic real-money order placement. A quoted price is not necessarily an executable fill, and simulated results are not audited investment performance.

## Research workflow / 研究流程

```text
Historical matches + pre-match information
    → football strength / expected-goals model
    → independent fair-probability estimates
    → sportsbook consensus (de-vig) + verified Kalshi market mapping
    → point-in-time snapshots and model/market disagreement review
    → calibrated residual pricing (only when trained weights exist)
    → executable-price EV, uncertainty and liquidity/risk gates
    → paper candidate / review / pass
    → closing-line value (CLV), settlement and factor attribution
    → chronological backtest, calibration and model iteration
```

**Two different pricing layers must not be confused:**

1. **Independent football baseline:** `src/football_intelligence.py` and `src/fair_model.py` use available historical scoring/strength information, recency, home advantage and rest to estimate expected goals and outcome probabilities. The initial goal-distribution approximation is Poisson. Market odds are not silently inserted into this independent `My Fair` estimate.
2. **Market-anchored residual research (v0.4):** `src/residual_pricing.py` starts from a de-vig sportsbook probability and models a bounded, standardized football-information residual in log-odds space, followed by calibration. Candidate factors include xG/xGA, chance quality, tactical matchups, lineups, rotation/depth, rest and market movement. **The repository's factor weights/calibration are not yet established as a validated production alpha model.** `src/data_engine.py` only allows this layer to produce an automatic paper-entry candidate when trained weights and calibration are present.

The factor specification, equations, limits and research status are in [docs/FACTOR_MODEL_V04.md](docs/FACTOR_MODEL_V04.md). The earlier independent Poisson backtest is a *baseline*, not evidence of profitable residual-model performance; its documented 500-match evaluation reports 383 trades, -$7,810 simulated P&L and -20.39% ROI. See the factor-model document for the scope of that result.

## Repository map / 文件用途

| Path | Purpose |
| --- | --- |
| `src/football_intelligence.py` | Historical football information and machine-readable match factors |
| `src/fair_model.py` | Independent model probabilities / fair-price baseline |
| `src/sportsbook_consensus.py` | Optional bookmaker quotes and de-vig consensus |
| `src/discover_markets.py` | Market discovery; do not invent tickers or contract mappings |
| `src/residual_pricing.py` | Market-prior residual model, factor contributions and conservative EV |
| `src/data_engine.py` | Verified market snapshots, pricing checks and paper-candidate risk gates |
| `src/point_in_time.py` | Timestamped pre-match model/market archives |
| `src/clv_engine.py` | Trade and signal closing-line value, where evidence exists |
| `src/alpha_attribution.py` | Research/model-factor attribution |
| `src/fixture_ingest.py`, `src/research_archive.py`, `src/kalshi_research.py` | Results ingestion, archived observations and read-only Kalshi research |
| `data/` | Configuration, model/market snapshots, PIT and CLV outputs |
| `paper/` | Paper observations, research archive and portfolio-related state |
| `dashboard/app.py` | Interactive, read-only Streamlit research terminal |
| `index.html`, `assets/` | Static GitHub Pages dashboard |
| `.github/workflows/data-engine.yml` | Scheduled data/model refresh |
| `.github/workflows/pages.yml` | Static dashboard deployment |

See [docs/BACKTEST.md](docs/BACKTEST.md), [docs/POINT_IN_TIME_CLV.md](docs/POINT_IN_TIME_CLV.md), [dashboard/README.md](dashboard/README.md) and [dashboard/DEPLOY_LIVE.md](dashboard/DEPLOY_LIVE.md) for deeper implementation notes.

## Quick start / 本地运行

Run these commands **from the repository root**. Python 3.12 is used by the scheduled GitHub workflow.

```bash
git clone https://github.com/0691891/prediction-market-portfolio.git
cd prediction-market-portfolio
python -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r dashboard/requirements.txt
```

The Streamlit requirements install the UI dependencies. Most research scripts use Python's standard library; inspect imports if a newly added research module requires further packages. A checkout can display **existing committed snapshots without API credentials**. Fresh bookmaker/football-provider data require the optional keys below.

### Refresh research data / 生成最新数据

The repository's scheduled pipeline runs these scripts **in this order**:

```bash
python src/football_intelligence.py
python src/fair_model.py
python src/sportsbook_consensus.py
python src/discover_markets.py
python src/data_engine.py
python src/point_in_time.py
python src/clv_engine.py
python src/alpha_attribution.py
python src/fixture_ingest.py
python src/research_archive.py
python src/kalshi_research.py
```

Typical generated artifacts include `data/football_intelligence.json`, `data/model_fair.json`, `data/sportsbook_consensus.json`, `data/market_snapshot.json`, `data/approval.json`, `data/pit/`, `data/clv.json`, `data/alpha_attribution.json` and Kalshi research snapshots. Missing provider access, absent matches or unverified tickers should produce missing-data/review states rather than synthetic prices or trades.

**Optional provider configuration:** Set `ODDS_API_KEY` for The Odds API sportsbook consensus and `FOOTBALL_DATA_API_KEY` for the football-data.org history adapter. For GitHub Actions, configure these as repository **Actions secrets**; for Streamlit Cloud, configure required dashboard-side secrets separately in that app. Never commit keys, account credentials or private paper ledgers. Public Kalshi research does not require real-money execution credentials.

### Launch the interactive dashboard / 打开 Streamlit

```bash
streamlit run dashboard/app.py
```

The Streamlit app reads local snapshots by default; its sidebar also offers GitHub data mode for a hosted deployment reading the public repository's snapshots. The UI can refresh frequently, **but the underlying scheduled research snapshots are generally hourly, not tick-by-tick or guaranteed live executable quotes**. Scoreboard/optional sportsbook widgets have their own fetch cadence and provider limits. The app is read-only and does not place orders.

For Streamlit Community Cloud: select this repository and `main`, set the entrypoint to `dashboard/app.py` and dependency file to `dashboard/requirements.txt`; select GitHub data mode as appropriate. See [dashboard/DEPLOY_LIVE.md](dashboard/DEPLOY_LIVE.md) for the light-theme and data-freshness caveats.

### Generate/deploy the static HTML dashboard / GitHub Pages

The **separate static dashboard** is already implemented in `index.html` with `assets/` JavaScript/CSS; it is not generated by exporting Streamlit. It reads the committed research/data artifacts. The [Deploy dashboard workflow](.github/workflows/pages.yml) runs on pushes to `main` or manually through GitHub Actions and publishes the repository as a GitHub Pages artifact. Enable GitHub Pages with **GitHub Actions** as the source in repository Settings → Pages if it is not enabled. Check the workflow run and its deployment URL rather than assuming a successful deployment.

The [data-engine workflow](.github/workflows/data-engine.yml) is scheduled at minute 17 of each hour (GitHub schedules may be delayed), can be manually dispatched, and commits changed snapshots back to `main`. Those pushes also trigger the Pages workflow. README-only changes do not themselves trigger the data-engine refresh.

## Signal logic and risk / 定价与风控

For decimal odds `O`, break-even probability is `1/O`. A basic gross expected return per unit stake is `p_fair × O − 1`; the residual layer uses a probability uncertainty haircut and fee/slippage assumptions for conservative net EV. Paper-entry gating additionally checks model eligibility, verified contract mapping, edge, liquidity and model-versus-consensus disagreement. Configured thresholds include **edge ≥4 percentage points and EV ≥5%**; match-level aggregate exposure is capped at **≤1u** under the research framework. A signal is not a fill.

The PIT engine archives model and market information at the observed time under `data/pit/YYYY-MM-DD.json` and retains the closest observed pre-kickoff quote. CLV compares supported entry/signal prices with the closing reference; absent timestamps, entry prices or mapping mean **no CLV claim**. A positive YES-side CLV indicates that the selected outcome's implied probability rose by close, not that the bet necessarily won.

## Backtesting and honest performance reporting

- Chronological, no-lookahead football baseline: first 70% of each league for training, last 30% untouched holdout; tune recency half-life, shrinkage and home-advantage parameters **on training only**. Track log loss, Brier score, calibration and per-league diagnostics.
- Activate fitted baseline parameters only after at least 500 holdout predictions, per [docs/BACKTEST.md](docs/BACKTEST.md).
- Evaluate new residual factors prospectively with frozen PIT features, ablation and out-of-time tests. Do not retroactively fill historical lineups, injuries, xG or closing odds from post-match knowledge.
- Separate **historical backtest**, **legacy research simulation**, **prospective paper trading** and **actual settled real-money trades**. Do not combine them into a single claimed strategy return. Do not infer CLV or executable ROI when historical prices/fills are unavailable.

## Scope and limitations

This is an evolving personal research system, not an audited fund strategy or a validated production trading model. Football/soccer has the substantive implemented intelligence/pricing pipeline; basketball is an expansion area. Public snapshots can be stale, data-provider coverage is incomplete, exact market contract wording matters, and sports prediction-market positions can lose the entire stake. No automatic real-money execution is enabled.
