# NVIDIA MA20/MA60 Backtest on CRSP Daily Data

## Executive summary
This project implements a clean, reproducible Python backtest for NVIDIA (`PERMNO 86580`) using a dual moving average rule on daily CRSP data. The strategy goes long when `MA20 > MA60`, stays in cash otherwise, applies a one-day signal lag to avoid look-ahead bias, and includes transaction cost sensitivity (5 bps one-way).

## Motivation
Trend-following rules are a common baseline in quant research. This project demonstrates core research engineering skills expected in asset management and quant roles: data handling, bias control, transaction cost modeling, risk-adjusted performance evaluation, and reproducible reporting.

## Dataset overview
- Source file: `NVDA_CRSP.csv`
- Frequency: daily
- Date span: 2019-01-02 to 2024-12-31
- Observations: 1510
- Coverage: single equity (NVIDIA CORP)

### Variable dictionary
- `PERMNO`: CRSP permanent security identifier
- `date`: trading date
- `COMNAM`: company name
- `PRC`: daily price (used for moving averages in this prototype)
- `VOL`: daily traded volume
- `RET`: total daily return (used for strategy and benchmark PnL)
- `BID`: daily bid quote
- `ASK`: daily ask quote
- `RETX`: daily return excluding distributions

## Strategy methodology
1. Parse `date` as `datetime`, coerce numeric fields, drop rows with missing `date`/`PRC`/`RET`, and sort chronologically.
2. Compute moving averages from `PRC`:
   - `MA20`: 20 trading days
   - `MA60`: 60 trading days
3. Generate signal:
   - Long (`1`) when `MA20 > MA60`
   - Cash (`0`) when `MA20 <= MA60`
4. Lag signal by one day:
   - `lagged_signal = signal.shift(1)`
5. Compute returns:
   - `strategy_return = lagged_signal * RET`
   - `buy_hold_return = RET`

## Backtest assumptions
- Long-only with binary exposure (fully invested or fully in cash).
- No leverage or shorting.
- 252 trading days per year for annualization.
- Sharpe ratio uses a 0% risk-free rate.
- Prototype intentionally keeps modeling simple for readability and portfolio demonstration.
- For a more rigorous CRSP backtest, prices should ideally be adjusted for corporate actions using adjustment factors such as `CFACPR`, but this dataset does not include that field.

## Transaction cost model
- One-way transaction cost: **5 bps** (`0.0005`) per trade.
- Trade indicator:
  - `trade = 1` when the lagged position changes from the previous day, else `0`.
- Net strategy return:
  - `strategy_return_tc = strategy_return - trade * 0.0005`

The project compares three equity curves:
- Buy-and-hold
- MA20/MA60 (no transaction costs)
- MA20/MA60 (with 5 bps one-way transaction costs)

## Performance metrics explanation
For each strategy, the script reports:
- Cumulative return
- Annualized return
- Annualized volatility
- Sharpe ratio
- Maximum drawdown
- Number of trades
- Average daily turnover (absolute daily position change)

## Key results
Latest run (`python3 backtest.py`) produced:

| Metric | Buy & Hold | MA20/MA60 (No TC) | MA20/MA60 (5bps TC) |
|---|---:|---:|---:|
| Cumulative return | 39.5633 | 9.1851 | 9.0441 |
| Annualized return | 0.8551 | 0.4730 | 0.4696 |
| Annualized volatility | 0.5187 | 0.4025 | 0.4024 |
| Sharpe ratio | 1.6485 | 1.1754 | 1.1669 |
| Maximum drawdown | -0.6634 | -0.6426 | -0.6437 |
| Number of trades | 1 | 28 | 28 |
| Avg daily turnover | 0.000662 | 0.018543 | 0.018543 |

## How to Read This Project
Use this order to learn both the finance logic and the coding workflow:

1. **Step 1: Read the Executive Summary**  
   Understand the project goal: test a dual moving average strategy (MA20/MA60) on NVIDIA CRSP daily data and compare it with buy-and-hold.
2. **Step 2: Read the Dataset Overview and Variable Dictionary**  
   Learn what each column in `NVDA_CRSP.csv` means and why fields such as `PRC`, `RET`, and `date` are central for backtesting.
3. **Step 3: Read the Strategy Methodology**  
   Focus on the signal intuition: when short-term trend (`MA20`) is above medium-term trend (`MA60`), hold the asset; otherwise hold cash.
4. **Step 4: Read the Backtest Assumptions**  
   Understand simplifications (daily frequency, long-only, no leverage) and why signal lagging is necessary to avoid look-ahead bias.
5. **Step 5: Read the Python Script from Top to Bottom**  
   Follow the exact quant workflow in code: load data -> clean data -> generate signals -> calculate returns -> apply transaction costs -> evaluate performance -> visualize results.
6. **Step 6: Read the Results and Performance Summary**  
   Interpret cumulative return, annualized return, volatility, Sharpe ratio, maximum drawdown, number of trades, and the impact of transaction costs.
7. **Step 7: Read the Limitations and Extensions**  
   Identify what is simplified in this prototype and how to evolve it into a stronger research pipeline.

## Real-World Quant Research Workflow
This project mirrors a realistic quant strategy development cycle:

1. **Start with a market hypothesis**  
   Hypothesis: medium-horizon trend-following may capture persistent upward moves in NVDA.
2. **Select and understand the dataset**  
   Use CRSP-style daily equity fields and validate their meaning before modeling.
3. **Define the trading signal**  
   Translate intuition into a rule: `MA20 > MA60` long, else cash.
4. **Avoid look-ahead bias**  
   Shift signals by one day so trading decisions only use information available at the time.
5. **Build a baseline backtest**  
   Compute daily strategy returns and compare against a transparent benchmark (`RET` buy-and-hold).
6. **Add transaction costs**  
   Penalize position changes with 5 bps one-way costs to test implementation realism.
7. **Compare against a benchmark**  
   Check whether the strategy improves return profile or risk control versus passive holding.
8. **Evaluate risk-adjusted performance**  
   Review Sharpe, volatility, and drawdown rather than returns alone.
9. **Identify limitations**  
   Acknowledge simplifications (single asset, simple costs, no walk-forward robustness).
10. **Propose next research extensions**  
   Expand to multi-asset tests, stronger cost models, and out-of-sample validation.

## How to run
From `Proj1_DualMovingAverage`:

```bash
python3 -m pip install -r requirements.txt
python3 backtest.py
```

## Project structure
- `NVDA_CRSP.csv`: input dataset
- `backtest.py`: modular backtest script
- `requirements.txt`: project dependencies
- `outputs/backtest_results.csv`: full daily backtest table
- `outputs/performance_summary.csv`: strategy performance summary
- `outputs/equity_curves.png`: equity curve comparison chart

## Limitations
- Single-asset, single-signal prototype.
- Uses `PRC` directly rather than fully corporate-action-adjusted prices.
- Assumes close-to-close execution with no market impact model.
- No walk-forward validation, hyperparameter tuning discipline, or out-of-sample robustness checks.

## Possible extensions
- Add multi-asset cross-sectional testing.
- Incorporate volatility targeting and risk budgeting.
- Add parameter sensitivity grids (e.g., MA pairs 10/50, 50/200).
- Introduce rolling out-of-sample / walk-forward evaluation.
- Include richer cost and slippage assumptions.

## CV bullet point example
- Built a Python-based dual moving average backtesting framework using CRSP daily equity data, incorporating look-ahead-bias control, transaction cost sensitivity analysis, equity curve visualization, and performance metrics including Sharpe ratio and maximum drawdown.
