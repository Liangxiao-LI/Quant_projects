# NVIDIA MA20/MA60 回测

<div align="center">

**<PROJECT_TAGLINE>**  
一个面向量化研究学习与作品集展示的双均线回测项目（Dual Moving Average Backtest）。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](#)
[![License](https://img.shields.io/badge/License-<LICENSE_TYPE>-green)](#license)
[![Status](https://img.shields.io/badge/Status-Prototype-orange)](#)

</div>

## 项目简介（Project Description）
`<PROJECT_DESCRIPTION>`

本项目基于 CRSP 日频数据 `NVDA_CRSP.csv`，实现了一个清晰、可复现的双均线策略回测框架：
- 使用 `PRC` 计算 `MA20` 与 `MA60`
- 信号规则：`MA20 > MA60` 做多，否则空仓
- 使用信号滞后（Signal Lag）避免前视偏差（Look-Ahead Bias）
- 对比三类策略：买入持有、无成本双均线、含交易成本双均线
- 输出净值曲线图与绩效汇总表，便于研究复盘与展示

> 仓库地址（Repository URL）：`<REPO_URL>`  
> 在线演示（Deployment URL，可选）：`<DEPLOYMENT_URL>`

---

## 目录（Table of Contents）
- [项目亮点（Highlights）](#项目亮点highlights)
- [快速开始（Quick Start）](#快速开始quick-start)
- [策略介绍（Strategies）](#策略介绍strategies)
- [数据集说明（Dataset）](#数据集说明dataset)
- [结果与图像解析（Results \& Chart Interpretation）](#结果与图像解析results--chart-interpretation)
- [配置说明（Configuration）](#配置说明configuration)
- [项目结构（Project Structure）](#项目结构project-structure)
- [工程实践说明（Engineering Notes）](#工程实践说明engineering-notes)
- [常见问题（FAQ）](#常见问题faq)
- [路线图（Roadmap）](#路线图roadmap)
- [贡献指南（Contributing）](#贡献指南contributing)
- [许可证（License）](#许可证license)
- [作者信息（Author）](#作者信息author)

---

## 项目亮点（Highlights）
- ✅ 简洁可复现（Reproducible）：`requirements.txt + 一键运行`
- ✅ 回测规范（Backtest Hygiene）：时间排序、缺失处理、信号滞后
- ✅ 交易成本敏感性（Transaction Cost Sensitivity）：5 bps 单边成本
- ✅ 风险收益并重（Risk-Adjusted Evaluation）：Sharpe、回撤、换手、交易次数
- ✅ 输出完整（Research Artifacts）：`performance_summary.csv` + `equity_curves.png`

---

## 快速开始（Quick Start）

### 1) 克隆仓库（Clone）
```bash
git clone <REPO_URL>
cd Quant_projects/Proj1_DualMovingAverage
```

### 2) 安装依赖（Install Dependencies）
```bash
python3 -m pip install -r requirements.txt
```

### 3) 运行回测（Run Backtest）
```bash
python3 backtest.py
```

### 4) 查看输出（Check Outputs）
```text
outputs/backtest_results.csv
outputs/performance_summary.csv
outputs/equity_curves.png
```

---

## 策略介绍（Strategies）

| 策略名称 | 中文说明 | 核心逻辑 | 作用 |
|---|---|---|---|
| `Buy-and-Hold` | 买入并持有（基准） | 始终持仓（Position=1） | 作为基准（Benchmark）比较主动策略是否有增益 |
| `MA20/MA60 (No TC)` | 双均线无交易成本 | `MA20 > MA60` 做多，否则空仓；信号滞后 1 天执行 | 观察纯信号效果 |
| `MA20/MA60 (5bps TC)` | 双均线含交易成本 | 在无成本策略基础上，每次仓位变化扣减 `0.0005` | 检验落地可交易性 |

---

## 数据集说明（Dataset）

### 数据概览
- 文件：`NVDA_CRSP.csv`
- 频率：日频（Daily）
- 标的：NVIDIA（`PERMNO 86580`）
- 时间范围：2019-01-02 至 2024-12-31

### 变量字典（Variable Dictionary）

| 字段 | 中文说明 | 英文术语 |
|---|---|---|
| `PERMNO` | CRSP 永久证券标识 | Permanent Security Identifier |
| `date` | 交易日期 | Trading Date |
| `COMNAM` | 公司名称 | Company Name |
| `PRC` | 日度价格（用于均线） | Daily Price |
| `VOL` | 成交量 | Trading Volume |
| `RET` | 总收益率（策略收益输入） | Total Return |
| `BID` | 买价 | Bid Quote |
| `ASK` | 卖价 | Ask Quote |
| `RETX` | 不含分红收益率 | Return Excluding Distributions |

---

## 结果与图像解析（Results & Chart Interpretation）

### 输出文件（Artifacts）
- `outputs/backtest_results.csv`：逐日回测明细（含信号、仓位、收益、净值）
- `outputs/performance_summary.csv`：策略绩效汇总
- `outputs/equity_curves.png`：三策略净值曲线对比图

### 图像预览（Screenshot）
![Equity Curves](outputs/equity_curves.png)

### 读图建议（How to Read the Chart）
- 看终值（Terminal Wealth）：最终累计收益谁更高
- 看回撤（Drawdown）：大跌阶段谁回撤更深
- 看路径平滑度（Path Smoothness）：策略波动是否更稳定
- 看成本影响（Cost Impact）：无成本与含成本曲线之间的差距

### 关键指标（示例）
运行后，`performance_summary.csv` 将包含：
- 累计收益（Cumulative Return）
- 年化收益（Annualized Return）
- 年化波动（Annualized Volatility）
- 夏普比率（Sharpe Ratio）
- 最大回撤（Maximum Drawdown）
- 交易次数（Number of Trades）
- 日均换手（Average Daily Turnover）

---

## 配置说明（Configuration）
当前项目无复杂配置，默认参数已写在 `backtest.py` 中：

```python
short_window = 20
long_window = 60
transaction_cost_one_way = 0.0005
```

如需扩展环境变量或外部配置，可使用占位符：

```text
API_KEY=<API_KEY>
DATABASE_URL=<DATABASE_URL>
```

---

## 项目结构（Project Structure）

```text
Proj1_DualMovingAverage/
├── NVDA_CRSP.csv
├── backtest.py
├── requirements.txt
├── README.md
└── outputs/
    ├── backtest_results.csv
    ├── performance_summary.csv
    └── equity_curves.png
```

---

## 工程实践说明（Engineering Notes）
- 数据处理：日期解析（Datetime Parsing）+ 时间排序（Chronological Sorting）
- 回测规范：信号滞后避免前视偏差（Look-Ahead Bias）
- 成本模型：仓位变化触发单边 5 bps 交易成本
- 可复现性：固定脚本入口 + 标准依赖文件

> 严谨 CRSP 研究通常会使用复权因子（如 `CFACPR`）做公司行为调整。  
> 当前数据未包含该字段，本项目使用 `PRC` 作为原型输入。

---

## 常见问题（FAQ）

### Q1: 为什么策略收益低于买入持有？
A: 样本期内 NVDA 趋势较强，趋势过滤可能会错过部分快速上涨区间；策略重点是控制风险并验证可执行性，不保证在每个样本期跑赢基准。

### Q2: 为什么要加入交易成本？
A: 无成本结果通常高估真实表现。加入成本后更接近实盘执行条件。

### Q3: 这个项目适合生产环境吗？
A: 当前更偏研究原型（Prototype）。生产化还需补充：样本外验证、参数稳健性、滑点模型、风险约束与监控。

---

## 路线图（Roadmap）
- [ ] 增加参数网格搜索（MA 参数敏感性）
- [ ] 增加样本外 / 滚动窗口验证（Walk-Forward）
- [ ] 增加多资产测试（Multi-Asset）
- [ ] 增加更真实交易成本与滑点模型
- [ ] 增加自动化测试与 CI

---

## 贡献指南（Contributing）
欢迎提交 Issue 和 Pull Request。

1. Fork 本仓库
2. 新建功能分支
3. 提交变更并附带说明
4. 发起 PR，描述动机、方案与验证结果

---

## 许可证（License）
本项目采用 `<LICENSE_TYPE>` 许可证。  
如仓库尚未添加许可证文件，请在根目录补充 `LICENSE`。

---

## 作者信息（Author）
- 作者：`<AUTHOR_NAME>`
- 邮箱：`<AUTHOR_EMAIL>`
- GitHub：`<GITHUB_PROFILE>`
