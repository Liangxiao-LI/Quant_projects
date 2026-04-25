from __future__ import annotations

from datetime import datetime
from itertools import product
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
    fixed_cost_one_way: float = 0.0005,
    market_impact_one_way: float = 0.0002,
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
    # More realistic cost model = fixed fee + half-spread slippage + market impact.
    # 更真实的成本模型 = 固定费用 + 半价差滑点 + 市场冲击。
    spread_ratio = ((out["ASK"] - out["BID"]).abs() / out["PRC"]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    out["half_spread_one_way"] = 0.5 * spread_ratio
    out["one_way_total_cost"] = fixed_cost_one_way + out["half_spread_one_way"] + market_impact_one_way
    out["strategy_return_tc"] = out["strategy_return"] - out["trade"] * out["one_way_total_cost"]

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


def run_single_strategy(
    df: pd.DataFrame,
    short_window: int,
    long_window: int,
    fixed_cost_one_way: float,
    market_impact_one_way: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    result = generate_signals(
        df=df,
        short_window=short_window,
        long_window=long_window,
        fixed_cost_one_way=fixed_cost_one_way,
        market_impact_one_way=market_impact_one_way,
    )
    metrics = calculate_performance_metrics(result["strategy_return_tc"], result["lagged_signal"])
    return result, metrics


def run_grid_search(
    df: pd.DataFrame,
    short_grid: list[int],
    long_grid: list[int],
    fixed_cost_one_way: float,
    market_impact_one_way: float,
    trade_penalty_lambda: float,
    drawdown_penalty_lambda: float,
) -> pd.DataFrame:
    records: list[dict[str, float]] = []
    sample_years = max(len(df) / 252.0, 1e-9)
    for short_window, long_window in product(short_grid, long_grid):
        if short_window >= long_window:
            continue
        _, metrics = run_single_strategy(
            df=df,
            short_window=short_window,
            long_window=long_window,
            fixed_cost_one_way=fixed_cost_one_way,
            market_impact_one_way=market_impact_one_way,
        )
        trades_per_year = float(metrics["number_of_trades"]) / sample_years
        max_drawdown_penalty = abs(min(float(metrics["max_drawdown"]), 0.0))
        objective_score = (
            float(metrics["sharpe_ratio"])
            - trade_penalty_lambda * trades_per_year
            - drawdown_penalty_lambda * max_drawdown_penalty
        )
        record: dict[str, float] = {"short_window": float(short_window), "long_window": float(long_window)}
        record.update(metrics)
        record["trades_per_year"] = trades_per_year
        record["max_drawdown_penalty"] = max_drawdown_penalty
        record["objective_score"] = objective_score
        records.append(record)

    grid_df = pd.DataFrame(records).sort_values("objective_score", ascending=False).reset_index(drop=True)
    return grid_df


def run_walk_forward_validation(
    df: pd.DataFrame,
    short_grid: list[int],
    long_grid: list[int],
    train_window: int,
    test_window: int,
    fixed_cost_one_way: float,
    market_impact_one_way: float,
    trade_penalty_lambda: float,
    drawdown_penalty_lambda: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    oos_chunks: list[pd.DataFrame] = []
    fold_rows: list[dict[str, float]] = []
    start = 0
    fold_id = 0

    while start + train_window + test_window <= len(df):
        train_df = df.iloc[start : start + train_window].copy()
        test_df = df.iloc[start + train_window : start + train_window + test_window].copy()

        grid_train = run_grid_search(
            df=train_df,
            short_grid=short_grid,
            long_grid=long_grid,
            fixed_cost_one_way=fixed_cost_one_way,
            market_impact_one_way=market_impact_one_way,
            trade_penalty_lambda=trade_penalty_lambda,
            drawdown_penalty_lambda=drawdown_penalty_lambda,
        )
        if grid_train.empty:
            break

        best_row = grid_train.iloc[0]
        best_short = int(best_row["short_window"])
        best_long = int(best_row["long_window"])

        test_result, test_metrics = run_single_strategy(
            df=test_df,
            short_window=best_short,
            long_window=best_long,
            fixed_cost_one_way=fixed_cost_one_way,
            market_impact_one_way=market_impact_one_way,
        )
        test_result["fold_id"] = fold_id
        test_result["selected_short"] = best_short
        test_result["selected_long"] = best_long
        oos_chunks.append(test_result)

        fold_rows.append(
            {
                "fold_id": float(fold_id),
                "train_start": train_df["date"].iloc[0].strftime("%Y-%m-%d"),
                "train_end": train_df["date"].iloc[-1].strftime("%Y-%m-%d"),
                "test_start": test_df["date"].iloc[0].strftime("%Y-%m-%d"),
                "test_end": test_df["date"].iloc[-1].strftime("%Y-%m-%d"),
                "selected_short": float(best_short),
                "selected_long": float(best_long),
                "oos_sharpe": float(test_metrics["sharpe_ratio"]),
                "oos_annualized_return": float(test_metrics["annualized_return"]),
                "oos_max_drawdown": float(test_metrics["max_drawdown"]),
            }
        )

        start += test_window
        fold_id += 1

    if not oos_chunks:
        return pd.DataFrame(), pd.DataFrame()

    oos_all = pd.concat(oos_chunks, ignore_index=True).sort_values("date").reset_index(drop=True)
    oos_all["wf_strategy_equity_tc"] = (1.0 + oos_all["strategy_return_tc"]).cumprod()
    oos_all["wf_buy_hold_equity"] = (1.0 + oos_all["buy_hold_return"]).cumprod()
    folds_df = pd.DataFrame(fold_rows)
    return oos_all, folds_df


def plot_equity_curves(df: pd.DataFrame, output_png: Path) -> None:
    # Visualization is critical for quick sanity checks and storytelling.
    # 可视化有助于快速做策略体检，也有助于项目展示与汇报。
    plt.figure(figsize=(11, 6))
    plt.plot(df["date"], df["buy_hold_equity"], label="Buy & Hold", linewidth=2.0, alpha=0.9)
    plt.plot(df["date"], df["strategy_equity"], label="MA20/MA60 (No TC)", linewidth=1.8)
    plt.plot(df["date"], df["strategy_equity_tc"], label="MA20/MA60 (Realistic TC+Slippage)", linewidth=1.8)
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


def plot_grid_heatmap(grid_df: pd.DataFrame, output_png: Path) -> None:
    pivot = grid_df.pivot(index="short_window", columns="long_window", values="objective_score")
    pivot = pivot.sort_index().sort_index(axis=1)
    data = pivot.values

    plt.figure(figsize=(9, 6))
    im = plt.imshow(data, cmap="viridis", aspect="auto", origin="lower")
    plt.colorbar(im, label="Objective Score (Sharpe - penalty)")
    plt.xticks(range(len(pivot.columns)), [int(v) for v in pivot.columns])
    plt.yticks(range(len(pivot.index)), [int(v) for v in pivot.index])
    plt.xlabel("Long Window")
    plt.ylabel("Short Window")
    plt.title("MA Parameter Grid Objective Heatmap")

    best_idx = np.unravel_index(np.nanargmax(data), data.shape)
    plt.scatter(best_idx[1], best_idx[0], marker="x", color="red", s=120, linewidths=2, label="Best")
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(output_png, dpi=150)
    plt.close()


def _is_pareto_efficient(points: np.ndarray) -> np.ndarray:
    # points columns: [maximize_metric, minimize_metric]
    efficient = np.ones(points.shape[0], dtype=bool)
    for i, p in enumerate(points):
        if not efficient[i]:
            continue
        dominated = (
            (points[:, 0] >= p[0]) & (points[:, 1] <= p[1]) & ((points[:, 0] > p[0]) | (points[:, 1] < p[1]))
        )
        dominated[i] = False
        if dominated.any():
            efficient[i] = False
    return efficient


def plot_pareto_like_frontier(grid_df: pd.DataFrame, output_png: Path) -> None:
    # Pareto-like view: maximize annualized return, minimize drawdown penalty.
    x = grid_df["max_drawdown_penalty"].values
    y = grid_df["annualized_return"].values
    points = np.column_stack([y, x])
    efficient_mask = _is_pareto_efficient(points)
    frontier = grid_df.loc[efficient_mask].sort_values("max_drawdown_penalty")

    plt.figure(figsize=(9, 6))
    scatter = plt.scatter(
        grid_df["max_drawdown_penalty"],
        grid_df["annualized_return"],
        c=grid_df["trades_per_year"],
        cmap="plasma",
        s=40 + 90 * (grid_df["sharpe_ratio"] - grid_df["sharpe_ratio"].min() + 1e-6),
        alpha=0.8,
        edgecolors="none",
    )
    plt.colorbar(scatter, label="Trades per Year")
    plt.plot(
        frontier["max_drawdown_penalty"],
        frontier["annualized_return"],
        color="lime",
        linewidth=2.0,
        marker="o",
        markersize=4,
        label="Pareto-like Frontier",
    )

    best_idx = int(grid_df["objective_score"].idxmax())
    best_row = grid_df.loc[best_idx]
    plt.scatter(
        [best_row["max_drawdown_penalty"]],
        [best_row["annualized_return"]],
        marker="X",
        color="red",
        s=140,
        label=f"Selected Best ({int(best_row['short_window'])}/{int(best_row['long_window'])})",
    )

    plt.xlabel("Max Drawdown Penalty (abs(MDD))")
    plt.ylabel("Annualized Return")
    plt.title("Parameter Stability Frontier (Pareto-like)")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_png, dpi=150)
    plt.close()


def plot_walk_forward_distribution(folds_df: pd.DataFrame, output_png: Path) -> None:
    plt.figure(figsize=(11, 5))
    plt.subplot(1, 2, 1)
    plt.hist(folds_df["oos_sharpe"], bins=min(8, max(3, len(folds_df))), alpha=0.8, edgecolor="black")
    plt.title("OOS Sharpe Distribution")
    plt.xlabel("OOS Sharpe")
    plt.ylabel("Count")
    plt.grid(alpha=0.2)

    plt.subplot(1, 2, 2)
    plt.hist(
        folds_df["oos_annualized_return"],
        bins=min(8, max(3, len(folds_df))),
        alpha=0.8,
        edgecolor="black",
    )
    plt.title("OOS Annualized Return Distribution")
    plt.xlabel("OOS Annualized Return")
    plt.ylabel("Count")
    plt.grid(alpha=0.2)

    plt.tight_layout()
    plt.savefig(output_png, dpi=150)
    plt.close()


def update_readme_results(
    readme_path: Path,
    performance_summary: pd.DataFrame,
    best_short: int,
    best_long: int,
    wf_summary: pd.DataFrame,
    trade_penalty_lambda: float,
    drawdown_penalty_lambda: float,
) -> None:
    def dataframe_to_markdown(df: pd.DataFrame) -> str:
        table = df.copy()
        table = table.reset_index()
        headers = list(table.columns)
        lines = []
        lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for _, row in table.iterrows():
            values = [str(row[h]) for h in headers]
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    main_table = dataframe_to_markdown(performance_summary.round(4))
    wf_table = dataframe_to_markdown(wf_summary.round(4))
    wf_sharpe = float(wf_summary.loc["sharpe_ratio", "wf_ma_tc"]) if "wf_ma_tc" in wf_summary.columns else np.nan
    bh_sharpe = float(wf_summary.loc["sharpe_ratio", "wf_buy_and_hold"]) if "wf_buy_and_hold" in wf_summary.columns else np.nan
    conclusion = (
        "滚动样本外中，MA 策略风险调整后表现优于基准。"
        if np.isfinite(wf_sharpe) and np.isfinite(bh_sharpe) and wf_sharpe > bh_sharpe
        else "滚动样本外中，MA 策略风险调整后未跑赢基准，需进一步优化。"
    )

    block = (
        f"<!-- AUTO_RESULTS_START -->\n"
        f"### 自动更新结果（Auto Updated Results）\n"
        f"- 更新时间：`{now}`\n"
        f"- 全样本网格搜索最优参数（按惩罚后目标）：`short={best_short}`, `long={best_long}`\n"
        f"- 目标函数（Objective）：`Sharpe - λ1*trades_per_year - λ2*max_drawdown_penalty`\n"
        f"- 其中：`λ1={trade_penalty_lambda}`, `λ2={drawdown_penalty_lambda}`\n\n"
        f"#### 主回测绩效（Main Backtest Summary）\n\n{main_table}\n\n"
        f"#### 滚动样本外绩效（Walk-Forward OOS Summary）\n\n{wf_table}\n"
        f"\n#### 稳健性图表（Robustness Plots）\n"
        f"![Parameter Heatmap](outputs/parameter_heatmap.png)\n\n"
        f"![Parameter Pareto-like Frontier](outputs/parameter_pareto_like.png)\n\n"
        f"![OOS Fold Distribution](outputs/oos_fold_distribution.png)\n\n"
        f"#### 自动结论（Auto Conclusion）\n"
        f"- {conclusion}\n"
        f"<!-- AUTO_RESULTS_END -->"
    )

    content = readme_path.read_text(encoding="utf-8")
    start_marker = "<!-- AUTO_RESULTS_START -->"
    end_marker = "<!-- AUTO_RESULTS_END -->"
    if start_marker in content and end_marker in content:
        start = content.index(start_marker)
        end = content.index(end_marker) + len(end_marker)
        content = content[:start] + block + content[end:]
    else:
        content = content + "\n\n---\n\n" + block + "\n"
    readme_path.write_text(content, encoding="utf-8")


def run_backtest(
    input_csv: Path,
    output_dir: Path,
    short_window: int = 20,
    long_window: int = 60,
    fixed_cost_one_way: float = 0.0005,
    market_impact_one_way: float = 0.0002,
    trade_penalty_lambda: float = 0.05,
    drawdown_penalty_lambda: float = 0.6,
) -> None:
    """
    End-to-end pipeline: load -> signal -> evaluate -> export.
    端到端流程：加载数据 -> 生成信号 -> 绩效评估 -> 导出结果。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_results_csv = output_dir / "backtest_results.csv"
    output_summary_csv = output_dir / "performance_summary.csv"
    output_chart_png = output_dir / "equity_curves.png"
    output_grid_csv = output_dir / "grid_search_summary.csv"
    output_wf_results_csv = output_dir / "walk_forward_results.csv"
    output_wf_folds_csv = output_dir / "walk_forward_folds.csv"
    output_wf_summary_csv = output_dir / "walk_forward_summary.csv"
    output_heatmap_png = output_dir / "parameter_heatmap.png"
    output_pareto_png = output_dir / "parameter_pareto_like.png"
    output_wf_dist_png = output_dir / "oos_fold_distribution.png"

    df = load_data(input_csv)
    short_grid = [10, 20, 30, 40]
    long_grid = [60, 90, 120, 150]

    grid_df = run_grid_search(
        df=df,
        short_grid=short_grid,
        long_grid=long_grid,
        fixed_cost_one_way=fixed_cost_one_way,
        market_impact_one_way=market_impact_one_way,
        trade_penalty_lambda=trade_penalty_lambda,
        drawdown_penalty_lambda=drawdown_penalty_lambda,
    )
    if grid_df.empty:
        raise RuntimeError("Grid search returned no valid parameter combinations.")

    best_short = int(grid_df.iloc[0]["short_window"])
    best_long = int(grid_df.iloc[0]["long_window"])

    results = generate_signals(
        df=df,
        short_window=best_short,
        long_window=best_long,
        fixed_cost_one_way=fixed_cost_one_way,
        market_impact_one_way=market_impact_one_way,
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
            "ma_20_60_realistic_cost": calculate_performance_metrics(
                daily_returns=results["strategy_return_tc"],
                position=results["lagged_signal"],
            ),
        }
    )
    summary.index.name = "metric"

    wf_results, wf_folds = run_walk_forward_validation(
        df=df,
        short_grid=short_grid,
        long_grid=long_grid,
        train_window=504,
        test_window=126,
        fixed_cost_one_way=fixed_cost_one_way,
        market_impact_one_way=market_impact_one_way,
        trade_penalty_lambda=trade_penalty_lambda,
        drawdown_penalty_lambda=drawdown_penalty_lambda,
    )
    wf_summary = pd.DataFrame()
    if not wf_results.empty:
        wf_summary = pd.DataFrame(
            {
                "wf_buy_and_hold": calculate_performance_metrics(
                    wf_results["buy_hold_return"], wf_results["buy_hold_position"]
                ),
                "wf_ma_tc": calculate_performance_metrics(
                    wf_results["strategy_return_tc"], wf_results["lagged_signal"]
                ),
            }
        )
        wf_summary.index.name = "metric"

    # Save machine-readable outputs for later analysis/reporting.
    # 保存结构化输出，方便后续分析与报告复用。
    results.to_csv(output_results_csv, index=False)
    summary.to_csv(output_summary_csv)
    grid_df.to_csv(output_grid_csv, index=False)
    plot_grid_heatmap(grid_df, output_heatmap_png)
    plot_pareto_like_frontier(grid_df, output_pareto_png)
    if not wf_results.empty:
        wf_results.to_csv(output_wf_results_csv, index=False)
        wf_folds.to_csv(output_wf_folds_csv, index=False)
        wf_summary.to_csv(output_wf_summary_csv)
        plot_walk_forward_distribution(wf_folds, output_wf_dist_png)
    plot_equity_curves(results, output_chart_png)

    readme_path = output_dir.parent / "README.md"
    update_readme_results(
        readme_path,
        summary,
        best_short,
        best_long,
        wf_summary if not wf_summary.empty else summary,
        trade_penalty_lambda,
        drawdown_penalty_lambda,
    )

    # Explicit paths make it easy for beginners to find artifacts.
    # 明确打印文件路径，方便初学者定位输出结果。
    print("Backtest complete.")
    print(f"Selected best parameters from grid search: short={best_short}, long={best_long}")
    print(f"Saved detailed backtest data: {output_results_csv}")
    print(f"Saved performance summary: {output_summary_csv}")
    print(f"Saved equity curve chart: {output_chart_png}")
    print(f"Saved grid search summary: {output_grid_csv}")
    print(f"Saved parameter heatmap: {output_heatmap_png}")
    print(f"Saved parameter Pareto-like frontier plot: {output_pareto_png}")
    if not wf_results.empty:
        print(f"Saved walk-forward results: {output_wf_results_csv}")
        print(f"Saved walk-forward fold details: {output_wf_folds_csv}")
        print(f"Saved walk-forward summary: {output_wf_summary_csv}")
        print(f"Saved OOS fold distribution plot: {output_wf_dist_png}")
    print(f"Updated README auto-results block: {readme_path}")
    print("\nPerformance summary:")
    print(summary)


if __name__ == "__main__":
    project_dir = Path(__file__).resolve().parent
    run_backtest(
        input_csv=project_dir / "NVDA_CRSP.csv",
        output_dir=project_dir / "outputs",
        short_window=20,
        long_window=60,
        fixed_cost_one_way=0.0005,
        market_impact_one_way=0.0002,
        trade_penalty_lambda=0.05,
        drawdown_penalty_lambda=0.6,
    )
