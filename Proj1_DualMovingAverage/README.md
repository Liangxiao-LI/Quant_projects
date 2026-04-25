# NVIDIA MA20/MA60 回测项目（Backtest Project）

## Executive Summary（执行摘要）
本项目使用 CRSP 日频数据（Daily Data）对 NVIDIA（`PERMNO 86580`）进行双均线策略（Dual Moving Average Strategy）回测（Backtest）。  
核心规则是：当 `MA20 > MA60` 时做多（Long），否则空仓（Cash / No Position）。  
项目同时比较了三类策略（Strategies）：买入持有（Buy-and-Hold）、双均线无交易成本（No Transaction Cost）、双均线含交易成本（With Transaction Cost, 5 bps one-way），并输出净值曲线图（Equity Curves）与绩效汇总（Performance Summary）。

## Motivation（研究动机）
趋势跟踪（Trend Following）是量化研究（Quant Research）中最常见的基线方法（Baseline）。  
该项目强调可复现（Reproducibility）、无前视偏差（Look-Ahead Bias Control）、交易成本敏感性（Transaction Cost Sensitivity）与风险调整后评估（Risk-Adjusted Evaluation），适合作为 CV 展示项目。

## Dataset Overview（数据集概览）
- 数据文件（Source File）：`NVDA_CRSP.csv`
- 频率（Frequency）：日频（Daily）
- 时间区间（Date Span）：2019-01-02 至 2024-12-31
- 样本数（Observations）：1510
- 标的范围（Coverage）：单一股票（Single Equity，NVIDIA CORP）

### Variable Dictionary（变量字典）
- `PERMNO`：CRSP 永久证券标识（Permanent Security Identifier）
- `date`：交易日期（Trading Date）
- `COMNAM`：公司名称（Company Name）
- `PRC`：日度价格（Daily Price，本项目用于均线计算）
- `VOL`：成交量（Trading Volume）
- `RET`：总收益率（Total Return，用于策略与基准收益）
- `BID`：买价（Bid Quote）
- `ASK`：卖价（Ask Quote）
- `RETX`：不含分红收益率（Return Excluding Distributions）

## Strategy Introduction（策略介绍）
本项目包含 3 个“可比较策略”（Comparable Strategies）：

- `Buy-and-Hold`（买入并持有，基准策略 Benchmark）
  - 仓位（Position）恒为 1，始终持有 NVIDIA。
  - 用于衡量主动策略是否优于被动持有。

- `MA20/MA60 (No Transaction Cost)`（双均线策略，未计交易成本）
  - 当短期均线（Short Moving Average）`MA20` 高于长期均线（Long Moving Average）`MA60` 时持有；
  - 否则空仓。
  - 信号滞后一天执行（One-Day Signal Lag），避免前视偏差（Look-Ahead Bias）。

- `MA20/MA60 (5 bps One-Way Transaction Cost)`（双均线策略，计入单边 5bps 交易成本）
  - 在无成本策略基础上，每次仓位变化扣除单边成本（One-Way Cost）0.05%。
  - 更接近真实交易落地（Implementation Realism）。

## Strategy Methodology（策略方法）
1. 日期解析（Date Parsing）：将 `date` 转为 `datetime` 并按时间排序（Chronological Sorting）。
2. 指标计算（Indicator Calculation）：基于 `PRC` 计算 `MA20` 和 `MA60`。
3. 信号生成（Signal Generation）：`MA20 > MA60` 则做多（Long=1），否则空仓（Cash=0）。
4. 信号滞后（Signal Lagging）：`lagged_signal = signal.shift(1)`。
5. 收益计算（Return Calculation）：
   - `strategy_return = lagged_signal * RET`
   - `buy_hold_return = RET`
6. 成本调整（Cost Adjustment）：
   - `trade = 1` 当仓位变化，否则 0
   - `strategy_return_tc = strategy_return - trade * 0.0005`

## Backtest Assumptions（回测假设）
- 仅做多（Long-Only），二元仓位（Binary Exposure：1 或 0）。
- 不使用杠杆（No Leverage），不做空（No Shorting）。
- 年化使用 252 个交易日（252 Trading Days Convention）。
- 夏普比率（Sharpe Ratio）默认无风险利率（Risk-Free Rate）为 0。
- 本项目使用 `PRC` 作为价格输入（Price Input）用于原型验证（Prototype）。
- 更严谨的 CRSP 回测应考虑复权因子（Adjustment Factors），例如 `CFACPR`，但当前数据不包含该字段。

## Transaction Cost Model（交易成本模型）
- 单边交易成本（One-Way Transaction Cost）：**5 bps**（`0.0005`）
- 交易触发（Trade Trigger）：当滞后仓位（Lagged Position）变化时记为一次交易（`trade=1`）
- 成本后收益（After-Cost Return）：
  - `strategy_return_tc = strategy_return - trade * 0.0005`

## Performance Metrics（绩效指标说明）
每个策略都计算以下指标：
- 累计收益（Cumulative Return）
- 年化收益（Annualized Return）
- 年化波动（Annualized Volatility）
- 夏普比率（Sharpe Ratio）
- 最大回撤（Maximum Drawdown）
- 交易次数（Number of Trades）
- 日均换手（Average Daily Turnover）

## Key Results（关键结果）
最新运行（Latest Run，`python3 backtest.py`）结果如下：

| 指标 (Metric) | 买入持有 (Buy & Hold) | 双均线无成本 (MA20/MA60 No TC) | 双均线含成本 (MA20/MA60 5bps TC) |
|---|---:|---:|---:|
| 累计收益 (Cumulative Return) | 39.5633 | 9.1851 | 9.0441 |
| 年化收益 (Annualized Return) | 0.8551 | 0.4730 | 0.4696 |
| 年化波动 (Annualized Volatility) | 0.5187 | 0.4025 | 0.4024 |
| 夏普比率 (Sharpe Ratio) | 1.6485 | 1.1754 | 1.1669 |
| 最大回撤 (Maximum Drawdown) | -0.6634 | -0.6426 | -0.6437 |
| 交易次数 (Number of Trades) | 1 | 28 | 28 |
| 日均换手 (Avg Daily Turnover) | 0.000662 | 0.018543 | 0.018543 |

## 图片解析（Chart Interpretation）
下图文件位于 `outputs/equity_curves.png`，展示三条净值曲线（Equity Curves）：

- `Buy & Hold`（买入持有）：
  - 对应全程持有 NVIDIA 的累计收益路径；
  - 通常在强趋势年份收益最高，但回撤（Drawdown）也可能更深。
- `MA20/MA60 (No TC)`（双均线无成本）：
  - 在趋势明确时参与上涨，在趋势弱化时退出；
  - 相比买入持有，通常波动和回撤更可控，但可能牺牲部分上涨收益。
- `MA20/MA60 (5bps TC)`（双均线含成本）：
  - 与无成本曲线方向一致，但因交易成本累积略低；
  - 两条曲线之间的差距直观体现策略对交易成本的敏感性（Cost Sensitivity）。

阅读图片时建议重点关注：
- 终值差异（Terminal Wealth Difference）：最终净值高低；
- 回撤深度（Drawdown Depth）：下跌阶段最大亏损；
- 平滑程度（Path Smoothness）：净值路径稳定性与波动特征。

## How to Read This Project
建议按以下路径学习（Learning Path）：

1. **Step 1: Read the Executive Summary（先看执行摘要）**  
   理解项目目标（Objective）和被测试策略（Strategy）。
2. **Step 2: Read the Dataset Overview and Variable Dictionary（看数据与字段）**  
   明确 `NVDA_CRSP.csv` 每一列的金融含义（Financial Meaning）。
3. **Step 3: Read the Strategy Methodology（看策略逻辑）**  
   理解为什么用 `MA20/MA60` 做趋势过滤（Trend Filter）。
4. **Step 4: Read the Backtest Assumptions（看回测假设）**  
   理解长仓、日频、无杠杆、信号滞后等假设对结果解释的影响。
5. **Step 5: Read the Python Script from Top to Bottom（从上到下读代码）**  
   按研究流程（Research Workflow）依次理解：加载 -> 清洗 -> 信号 -> 收益 -> 成本 -> 指标 -> 可视化。
6. **Step 6: Read the Results and Performance Summary（看结果）**  
   解释收益、波动、夏普、回撤、交易次数和成本影响。
7. **Step 7: Read the Limitations and Extensions（看局限和扩展）**  
   明确原型简化点（Simplifications）和下一步研究方向（Next Steps）。

## Real-World Quant Research Workflow（真实量化研究流程映射）
本项目对应现实中的策略研发流程（Strategy Research Lifecycle）：

1. 提出市场假设（Market Hypothesis）
2. 选择并理解数据（Data Selection & Understanding）
3. 定义交易信号（Signal Definition）
4. 避免前视偏差（Look-Ahead Bias Prevention）
5. 建立基线回测（Baseline Backtest）
6. 引入交易成本（Transaction Cost Modeling）
7. 对比基准策略（Benchmark Comparison）
8. 做风险调整后评估（Risk-Adjusted Evaluation）
9. 识别局限（Limitations Identification）
10. 提出后续扩展（Research Extensions）

## How to Run（运行方式）
在 `Proj1_DualMovingAverage` 目录执行：

```bash
python3 -m pip install -r requirements.txt
python3 backtest.py
```

## Project Structure（项目结构）
- `NVDA_CRSP.csv`：输入数据（Input Dataset）
- `backtest.py`：回测脚本（Modular Backtest Script）
- `requirements.txt`：依赖列表（Dependencies）
- `outputs/backtest_results.csv`：逐日结果（Daily Backtest Table）
- `outputs/performance_summary.csv`：绩效汇总（Performance Summary）
- `outputs/equity_curves.png`：净值曲线图（Equity Curve Chart）

## Limitations（局限性）
- 单资产（Single Asset）、单信号（Single Signal）原型。
- 使用 `PRC` 而非完整复权价格（Fully Adjusted Price）。
- 假设收盘到收盘执行（Close-to-Close Execution），未建模市场冲击（Market Impact）。
- 未进行滚动样本外检验（Walk-Forward / Out-of-Sample Validation）。

## Possible Extensions（可扩展方向）
- 多资产横截面策略（Multi-Asset Cross-Sectional Testing）
- 波动率目标（Volatility Targeting）与风险预算（Risk Budgeting）
- 参数敏感性分析（Parameter Sensitivity Grid）
- 更丰富的成本与滑点模型（Slippage & Execution Cost Modeling）

## CV Bullet Point Example（简历描述示例）
- Built a Python-based dual moving average backtesting framework using CRSP daily equity data, incorporating look-ahead-bias control, transaction cost sensitivity analysis, equity curve visualization, and performance metrics including Sharpe ratio and maximum drawdown.  
（基于 CRSP 日频股票数据构建 Python 双均线回测框架，包含前视偏差控制、交易成本敏感性分析、净值曲线可视化，以及夏普比率与最大回撤等绩效指标评估。）

## 面试问答准备（Interview Q&A Prep）
- **为什么要信号滞后一天（Why one-day signal lag）？**  
  因为当天收盘价计算出的信号在当天收盘前不可得，若直接用当天信号乘当天收益会产生前视偏差（Look-Ahead Bias）。滞后一天是最基础的可交易性约束（Tradability Constraint）。
- **为什么要加交易成本（Why include transaction cost）？**  
  无成本回测通常高估策略表现。加入 5 bps 单边成本后，可评估策略在真实执行环境中的鲁棒性（Robustness）与可落地性（Implementability）。
- **为什么不仅看累计收益（Why not only cumulative return）？**  
  单看收益会忽略风险。量化研究通常同时看年化波动（Volatility）、夏普比率（Sharpe Ratio）、最大回撤（Maximum Drawdown）来评估收益质量（Return Quality）。
- **为什么要和买入持有对比（Why benchmark against buy-and-hold）？**  
  买入持有是最直接基准（Benchmark）。若主动策略无法在风险或收益维度相对基准提供增量价值（Alpha/风险改善），其研究意义有限。
- **这个项目的最大局限是什么（Main limitation）？**  
  单资产+简化成本模型+未做样本外检验（Out-of-Sample）。因此更适合作为研究原型（Research Prototype），而非实盘策略（Production Strategy）。

## 30 秒项目陈述（30-Second Pitch）
我做了一个基于 CRSP 日频数据的 NVIDIA 双均线回测项目。策略使用 `PRC` 计算 `MA20/MA60`，当 `MA20 > MA60` 时做多，否则空仓，并通过信号滞后一天控制前视偏差。  
在回测中我同时对比了买入持有、无交易成本策略和含单边 5bps 交易成本策略，输出了净值曲线与完整绩效指标，包括年化收益、夏普和最大回撤。  
这个项目重点体现了我在数据清洗、回测规范、交易成本建模和风险调整后评估方面的量化研究能力。
