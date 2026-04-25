from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_data(input_csv: Path) -> pd.DataFrame:
    """
    Load and clean the input dataset.
    加载并清洗输入数据。

    Why this matters / 为什么重要:
    A backtest is only as reliable as its input data. We enforce required columns,
    parse time correctly, and remove rows that cannot produce valid returns.
    回测质量高度依赖数据质量。这里会检查关键字段、正确解析时间，
    并剔除无法用于收益计算的无效行。
    """
    df = pd.read_csv(input_csv)
    # We validate schema first so errors are explicit and reproducible.
    # 先校验字段结构，避免后面静默报错，保证可复现。
    required_columns = ["PERMNO", "date", "COMNAM", "PRC", "VOL", "RET", "BID", "ASK", "RETX"]
    missing_columns = [c for c in required_columns if c not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    # Convert date strings to datetime so sorting and plotting are truly time-aware.
    # 将日期字符串转为 datetime，确保排序和绘图按真实时间进行。
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    # Coerce non-numeric values to NaN; this prevents accidental string math.
    # 把非数值内容转成 NaN，避免字符串参与计算导致错误结果。
    for col in ["PRC", "VOL", "RET", "BID", "ASK", "RETX"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # We only keep rows where core backtest inputs are valid.
    # 回测核心输入是 date/PRC/RET，缺失则无法可靠计算信号和收益。
    df = df.dropna(subset=["date", "PRC", "RET"]).copy()
    # Chronological order is essential for any time-series strategy.
    # 时间序列策略必须按时间排序，否则会引入错误的先后关系。
    df = df.sort_values("date").reset_index(drop=True)
    return df


def generate_signals(
    df: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 60,
    transaction_cost_one_way: float = 0.0005,
) -> pd.DataFrame:
    """
    Generate indicators, positions, and return series.
    生成技术指标、仓位与收益序列。

    Why this matters / 为什么重要:
    This function is the core strategy engine: signal -> tradable position -> PnL.
    这是策略核心流程：信号 -> 可交易仓位 -> 收益。
    """
    out = df.copy()
    # MA20/MA60 are trend filters: short-term trend vs medium-term trend.
    # MA20/MA60 用于趋势过滤：短期趋势相对中期趋势。
    out["ma20"] = out["PRC"].rolling(window=short_window, min_periods=short_window).mean()
    out["ma60"] = out["PRC"].rolling(window=long_window, min_periods=long_window).mean()

    # Trading rule: long when MA20 > MA60, else stay in cash.
    # 交易规则：MA20 > MA60 时做多，否则空仓。
    out["signal"] = (out["ma20"] > out["ma60"]).astype(int)
    # Shift by one day to avoid look-ahead bias.
    # 向后滞后一天，避免“未来函数”（前视偏差）。
    # Today we can only trade using information known at yesterday's close.
    # 今天的交易只能使用昨天收盘时已知的信息。
    out["lagged_signal"] = out["signal"].shift(1).fillna(0).astype(int)

    # Benchmark is always invested in the stock.
    # 基准策略始终持有股票（满仓买入并持有）。
    out["buy_hold_position"] = 1
    # Strategy return is position exposure times asset return.
    # 策略收益 = 仓位暴露 * 当日资产收益。
    out["strategy_return"] = out["lagged_signal"] * out["RET"]
    out["buy_hold_return"] = out["RET"]

    # Trade occurs when position changes (entry or exit).
    # 当仓位发生变化（进场/离场）时记为一次交易。
    # This is a simple but practical turnover proxy for transaction costs.
    # 这是一个简单且实用的换手代理，用于估算交易成本。
    out["trade"] = out["lagged_signal"].diff().abs().fillna(out["lagged_signal"]).astype(int)
    # Apply one-way transaction cost (e.g., 5 bps per trade).
    # 应用单边交易成本（例如每次交易 5bps）。
    out["strategy_return_tc"] = out["strategy_return"] - out["trade"] * transaction_cost_one_way

    # Equity curve shows cumulative growth of $1 over time.
    # 净值曲线表示 1 美元初始资金随时间的累计增长。
    out["buy_hold_equity"] = (1.0 + out["buy_hold_return"]).cumprod()
    out["strategy_equity"] = (1.0 + out["strategy_return"]).cumprod()
    out["strategy_equity_tc"] = (1.0 + out["strategy_return_tc"]).cumprod()
    return out


def max_drawdown(equity_curve: pd.Series) -> float:
    # Max drawdown measures worst peak-to-trough loss.
    # 最大回撤衡量从历史高点到低点的最大亏损幅度。
    rolling_max = equity_curve.cummax()
    drawdown = equity_curve / rolling_max - 1.0
    return float(drawdown.min())


def count_trades(position: pd.Series) -> int:
    # Sum of absolute position changes = number of entry/exit events.
    # 仓位变化绝对值之和 = 进出场事件总数。
    return int(position.diff().abs().fillna(position).sum())


def average_daily_turnover(position: pd.Series) -> float:
    # Binary turnover proxy: average absolute daily position change.
    # 二元仓位的日均换手代理：仓位日变化绝对值的均值。
    return float(position.diff().abs().fillna(position).mean())


def calculate_performance_metrics(
    daily_returns: pd.Series,
    position: pd.Series,
    trading_days: int = 252,
) -> dict[str, float]:
    """
    Compute standard backtest metrics for one strategy.
    计算单个策略的常用回测指标。
    """
    # Fill NaN with 0 to keep cumulative return path continuous.
    # 用 0 填补缺失收益，保证累计净值路径可连续计算。
    daily_returns = daily_returns.fillna(0.0)
    equity_curve = (1.0 + daily_returns).cumprod()
    total_periods = len(daily_returns)

    if total_periods == 0:
        return {
            "cumulative_return": np.nan,
            "annualized_return": np.nan,
            "annualized_volatility": np.nan,
            "sharpe_ratio": np.nan,
            "max_drawdown": np.nan,
            "number_of_trades": np.nan,
            "avg_daily_turnover": np.nan,
        }

    # Key performance indicators used in quant research.
    # 量化研究中常用的关键绩效指标。
    cumulative_return = float(equity_curve.iloc[-1] - 1.0)
    annualized_return = float((equity_curve.iloc[-1] ** (trading_days / total_periods)) - 1.0)
    annualized_volatility = float(daily_returns.std(ddof=1) * np.sqrt(trading_days))
    # Sharpe here assumes risk-free rate = 0 for simplicity.
    # 这里的 Sharpe 为简化版本，默认无风险利率为 0。
    sharpe_ratio = np.nan if annualized_volatility == 0 else float(annualized_return / annualized_volatility)

    return {
        "cumulative_return": cumulative_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown(equity_curve),
        "number_of_trades": float(count_trades(position)),
        "avg_daily_turnover": average_daily_turnover(position),
    }


def plot_equity_curves(df: pd.DataFrame, output_png: Path) -> None:
    # Visualization is critical for quick sanity checks and storytelling.
    # 可视化有助于快速做策略体检，也有助于项目展示与汇报。
    plt.figure(figsize=(11, 6))
    plt.plot(df["date"], df["buy_hold_equity"], label="Buy & Hold", linewidth=2.0, alpha=0.9)
    plt.plot(df["date"], df["strategy_equity"], label="MA20/MA60 (No TC)", linewidth=1.8)
    plt.plot(df["date"], df["strategy_equity_tc"], label="MA20/MA60 (5 bps One-Way TC)", linewidth=1.8)
    plt.title("NVIDIA Dual Moving Average Backtest: Equity Curves")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Growth of $1")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    # Save chart for reproducibility and CV/portfolio usage.
    # 保存图片以便复现实验和作品集展示。
    plt.savefig(output_png, dpi=150)
    plt.close()


def run_backtest(
    input_csv: Path,
    output_dir: Path,
    short_window: int = 20,
    long_window: int = 60,
    transaction_cost_one_way: float = 0.0005,
) -> None:
    """
    End-to-end pipeline: load -> signal -> evaluate -> export.
    端到端流程：加载数据 -> 生成信号 -> 绩效评估 -> 导出结果。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_results_csv = output_dir / "backtest_results.csv"
    output_summary_csv = output_dir / "performance_summary.csv"
    output_chart_png = output_dir / "equity_curves.png"

    df = load_data(input_csv)
    results = generate_signals(
        df=df,
        short_window=short_window,
        long_window=long_window,
        transaction_cost_one_way=transaction_cost_one_way,
    )

    summary = pd.DataFrame(
        {
            "buy_and_hold": calculate_performance_metrics(
                daily_returns=results["buy_hold_return"],
                position=results["buy_hold_position"],
            ),
            "ma_20_60_no_tc": calculate_performance_metrics(
                daily_returns=results["strategy_return"],
                position=results["lagged_signal"],
            ),
            "ma_20_60_tc_5bps": calculate_performance_metrics(
                daily_returns=results["strategy_return_tc"],
                position=results["lagged_signal"],
            ),
        }
    )
    summary.index.name = "metric"

    # Save machine-readable outputs for later analysis/reporting.
    # 保存结构化输出，方便后续分析与报告复用。
    results.to_csv(output_results_csv, index=False)
    summary.to_csv(output_summary_csv)
    plot_equity_curves(results, output_chart_png)

    # Explicit paths make it easy for beginners to find artifacts.
    # 明确打印文件路径，方便初学者定位输出结果。
    print("Backtest complete.")
    print(f"Saved detailed backtest data: {output_results_csv}")
    print(f"Saved performance summary: {output_summary_csv}")
    print(f"Saved equity curve chart: {output_chart_png}")
    print("\nPerformance summary:")
    print(summary)


if __name__ == "__main__":
    project_dir = Path(__file__).resolve().parent
    run_backtest(
        input_csv=project_dir / "NVDA_CRSP.csv",
        output_dir=project_dir / "outputs",
        short_window=20,
        long_window=60,
        transaction_cost_one_way=0.0005,
    )
