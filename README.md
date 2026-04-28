# Quant Projects

A collection of quantitative finance, venture-capital analytics, and market-data engineering projects.

This repository is organised as a portfolio of standalone projects. Each folder contains its own code, data assumptions, and local README where appropriate.

## Project Index

| Folder | Project | Focus |
|---|---|---|
| `Proj1_DualMovingAverage/` | NVIDIA Dual Moving Average Backtest | Equity strategy research, backtesting, transaction costs, and performance reporting |
| `QuantLib_Demo/` | QuantLib Python Demo | Fixed-rate bond pricing using QuantLib, yield curves, clean/dirty price, accrued interest |
| `VCAnalysis/Fund_performance/` | Fund Performance Analysis | Large-scale fund performance cleaning, EDA, IRR/DPI/TVPI/RVPI analysis |
| `VCAnalysis/MEIF_Dashboard/` | MEIF VC Dashboard | Investor-facing fund dashboard, deal filtering, concentration risk, deployment pace, data-quality memo |
| `polymarket-bedrock-agents/` | Polymarket Bedrock Multi-Agent | FastAPI service for Polymarket data ingestion, Amazon Bedrock enrichment, and event relationship analysis |

## Quick Start

Clone the repository and enter the project you want to run:

```bash
git clone <repo-url>
cd Quant_projects
```

Each subproject manages its own dependencies. Read the README inside the target folder before running scripts.

## Featured Projects

### `Proj1_DualMovingAverage`

Backtests a dual moving average strategy on NVIDIA CRSP daily data.

```bash
cd Proj1_DualMovingAverage
python3 -m pip install -r requirements.txt
python3 backtest.py
```

Outputs include performance summaries, equity curves, grid search results, and walk-forward validation artifacts.

### `QuantLib_Demo`

Demonstrates QuantLib in Python by pricing a fixed-rate bond with a flat yield curve.

```bash
cd QuantLib_Demo
./.venv/bin/python bond_pricing_demo.py
```

The demo prints clean price, dirty price, accrued interest, and yield to maturity.

### `VCAnalysis/MEIF_Dashboard`

Builds a concise investor-facing dashboard for MEIF-related VC deals using company-level and deal-level CSV files.

```bash
cd VCAnalysis/MEIF_Dashboard
python3 generate_dashboard.py
```

The script regenerates `README.md`, cleaned datasets, and `DATA_CLEANING_MEMO.md`.

### `VCAnalysis/Fund_performance`

Cleans and analyses a large fund-performance dataset with IRR, DPI, TVPI, and RVPI fields.

```bash
cd VCAnalysis/Fund_performance
python3 analyze_fund_performance.py
```

The project focuses on data cleaning, sample quality, descriptive statistics, annual trends, and top-fund identification.

### `polymarket-bedrock-agents`

Production-oriented Python service for Polymarket event discovery, Amazon Bedrock enrichment, graph storage, and FastAPI querying.

```bash
cd polymarket-bedrock-agents
```

See the project README for environment variables, database setup, and API workflow.

## Repository Notes

- Python is the main language across the repository.
- Some projects require local CSV files or external services.
- Generated outputs are project-specific and documented in each subfolder.
- Avoid committing secrets such as `.env` files or API credentials.

## Suggested Reading Order

1. Start with `Proj1_DualMovingAverage/` for classic quant backtesting.
2. Review `QuantLib_Demo/` for fixed-income pricing basics.
3. Explore `VCAnalysis/MEIF_Dashboard/` for investor-facing analytics.
4. Use `VCAnalysis/Fund_performance/` for large-scale fund data cleaning.
5. Read `polymarket-bedrock-agents/` for event-data engineering and agent architecture.