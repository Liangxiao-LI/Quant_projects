# AutoClean + pandas-profiling Demo

A complete feature showcase of [py-AutoClean](https://github.com/elisemercury/AutoClean) and [pandas-profiling](https://github.com/ydataai/ydata-profiling) applied to a synthetic quantitative finance dataset.

---

## pandas-profiling vs py-AutoClean

These two tools address the same dataset, but at opposite ends of the data pipeline.

| | pandas-profiling 3.6.6 | py-AutoClean 1.1.3 |
|---|---|---|
| **Purpose** | Exploratory Data Analysis (EDA) — *understand* your data | Data cleaning — *fix* your data |
| **Output** | Interactive HTML report for human review | Cleaned pandas DataFrame |
| **Action taken on data** | None — read-only diagnostic | Modifies the data (imputation, encoding, etc.) |
| **Missing values** | Reports count, heatmap, and missingness patterns | Fills or removes them via KNN, regression, mean, etc. |
| **Outliers** | Highlights them with distribution plots and alerts | Caps (winsorization) or deletes them |
| **Duplicates** | Reports and shows duplicate rows | Removes duplicate rows |
| **Correlations** | Pearson, Spearman, Kendall, Phi-k, Cramér's V matrices | Not computed |
| **Categorical features** | Frequency counts, chi-square, unique-value analysis | Encodes them (one-hot, label) |
| **Datetime features** | Parsed and visualised as a time series | Decomposed into numeric columns (year, month, day, …) |
| **When to use** | Before cleaning — to decide *what* to clean and *how* | After profiling — to apply the cleaning decisions |

**Typical workflow:**
```
raw data → pandas-profiling (understand) → py-AutoClean (fix) → model / analysis
```

pandas-profiling answers questions like: *"How many values are missing? Are price and volume correlated? Are there category imbalances?"*

py-AutoClean answers questions like: *"Fill those missing prices with KNN. Winsorize the outlier PE ratios. One-hot encode the sector column."*

---

## Folder Structure

```
Datacleaning experiment/
├── generate_dataset.py          # generates raw_quant_dataset.csv
├── autoclean_demo.py            # 14-run py-AutoClean feature showcase
├── pandas_profiling_demo.py     # generates the three EDA reports
├── raw_quant_dataset.csv        # synthetic messy dataset (shared input)
├── README.md
├── autoclean_outputs/
│   ├── cleaned_auto.csv         # output from Run 1 (auto mode)
│   └── cleaned_full_manual.csv  # output from Run 14 (full manual pipeline)
└── profiling_outputs/
    ├── profile_minimal.html     # lightweight EDA overview
    ├── profile_full.html        # full report with correlations & interactions
    └── profile_comparison.html  # raw vs cleaned side-by-side
```

---

## Dataset

`raw_quant_dataset.csv` simulates daily stock observations for 10 tickers over ~2 years. The following problems are intentionally injected to stress-test both tools:

| Problem | Detail |
|---------|--------|
| Duplicate rows | ~3% of rows duplicated |
| Numerical NaNs | 6–9% missing rate across `price`, `volume`, `daily_return`, `market_cap_M`, `beta`, `pe_ratio` |
| Categorical NaNs | 5–7% missing in `sector` and `analyst_rating` |
| Outliers | Extreme price spikes (−9070 to +9511 vs. normal 50–500), negative volume, absurd PE ratios |
| Datetime column | `trade_timestamp` spanning Jan 2023 – Dec 2024 |

**Stats confirmed by pandas-profiling:**
- 618 rows, 10 columns, 343 missing cells (5.6%)
- 5 duplicate rows
- 6 numeric, 3 categorical, 1 datetime column

---

## pandas-profiling Reports

Run with:
```bash
/opt/anaconda3/envs/myenv/bin/python pandas_profiling_demo.py
```

### profile_minimal.html — Lightweight overview
A fast summary of every column: type, missing count, distinct values, and basic distribution. Generated with `minimal=True` — skips correlation and interaction matrices. Good for a quick sanity check on large datasets.

### profile_full.html — Full EDA report
The complete analysis, including:

- **Overview** — row/column counts, missing cell %, duplicate count, memory usage
- **Per-variable** — histograms, box plots, value counts, quantile table, skewness/kurtosis, number of zeros/infinities
- **Missing values** — bar chart, missingness pattern matrix, missingness heatmap (which columns tend to be missing together), dendrogram
- **Correlations** — five matrices computed in parallel:
  - Pearson (linear, numeric pairs)
  - Spearman (rank-based, numeric pairs)
  - Kendall's τ (rank-based, more robust to outliers)
  - Phi-k (works for mixed numeric + categorical pairs)
  - Cramér's V (categorical pair associations)
- **Interactions** — scatter-plot matrix targeting `price`, `daily_return`, `pe_ratio`
- **Duplicates** — lists the duplicate rows
- **Samples** — first 10, last 10, and 5 random rows

Key findings from `profile_full.html` on the raw dataset:
```
price     : min=-9070.80  max=9511.24  Q1=152.89   Q3=394.10
volume    : min=-272,856,630  max=263,373,390  Q1=2.4M  Q3=7.6M
pe_ratio  : min=-2245.84  max=426.08   Q1=15.95   Q3=37.33
```

### profile_comparison.html — Raw vs Cleaned side-by-side
Runs two minimal profiles and renders them in a split-column layout so you can see exactly what changed after AutoClean: missing values eliminated, column distributions narrowed by winsorization, and new one-hot columns added.

---

## py-AutoClean Runs

### Run 1 — `mode='auto'`
Fully automated pipeline. Sets all parameters to `'auto'` automatically:
duplicates, missing values, outlier winsorization, categorical encoding, and datetime extraction.
Result: 618 rows → 613, 10 cols → 34, 343 missing → 0.

### Run 2 — `duplicates='auto'`
Removes duplicate rows only. Drops all but one copy of each duplicated row.
Result: 5 duplicates removed.

### Run 3 — `missing_num='knn'`
K-Nearest Neighbours imputation for numerical columns. Fills each missing value with the weighted average of its k nearest neighbours in feature space — preserves local structure better than mean/median.

### Run 4 — `missing_num='delete'`
Drops every row that contains at least one missing numerical value. Aggressive (214 rows removed) but leaves zero NaNs.

### Run 5 — `missing_num` ∈ `{'mean', 'median', 'most_frequent'}`
Simple univariate imputation via `sklearn.SimpleImputer`. Compares all three strategies side by side.

### Run 6 — `missing_categ='logreg'`
Logistic Regression imputation for categorical columns. Trains a per-column classifier on complete rows to predict missing labels.
> Note: requires numerical NaNs to be pre-filled; logreg cannot train when feature rows also contain NaNs.

### Run 7 — `missing_categ='knn'`
KNN imputation for categorical columns. Encodes categories to integers, imputes in that space, then decodes back to original labels.
Result: all 77 categorical NaNs filled; original label sets fully restored.

### Run 8 — `outliers='winz'` with `outlier_param=1.5` and `1.0`
Winsorization caps values at IQR fences:
```
lower = Q1 − outlier_param × IQR
upper = Q3 + outlier_param × IQR
```
Values outside the fence are replaced by the fence value (not deleted). Two multipliers are compared:
- `param=1.5` (default): price capped to [−170, +722]
- `param=1.0` (strict): price capped to [−59, +610]

### Run 9 — `outliers='delete'`
Drops any row that contains a value outside IQR bounds. 68 rows removed; price range shrinks to [50, 499].

### Run 10 — `encode_categ=['onehot']`
One-hot encodes all categorical columns. Creates 18 new binary columns for `ticker` (10), `sector` (5), and `analyst_rating` (3).

### Run 11 — `encode_categ=['label']`
Label encodes all categorical columns. Maps each unique value to an integer (0, 1, 2, …). Adds `ticker_lab`, `sector_lab`, `analyst_rating_lab` columns alongside the originals.

### Run 12 — `encode_categ=['onehot', ['sector']]`
Selective encoding. One-hot encodes `sector` only, leaving `ticker` and `analyst_rating` as strings. Adds 5 `sector_*` boolean columns.

### Run 13 — `extract_datetime` (all granularities)
Expands the `trade_timestamp` datetime column into numeric components. Each granularity adds all components up to that level:

| Setting | New columns |
|---------|-------------|
| `'D'` | Day |
| `'M'` | Day, Month |
| `'Y'` | Day, Month, Year |
| `'h'` | Day, Month, Year, Hour |
| `'m'` | Day, Month, Year, Hour, Minute |
| `'s'` | Day, Month, Year, Hour, Minute, Sec |

### Run 14 — Full manual pipeline
Every feature combined in manual mode:
```python
AutoClean(
    raw,
    mode="manual",
    duplicates="auto",
    missing_num="knn",
    missing_categ="logreg",
    outliers="winz",
    outlier_param=1.5,
    encode_categ=["onehot", ["sector", "analyst_rating"]],
    extract_datetime="D",
)
```
Result: 618 → 613 rows, 10 → 19 columns, 343 → 0 numerical NaNs, 5 → 0 duplicates, price winsorized to [−171, +722].

---

## Library Bugs Found (py-AutoClean v1.1.3)

Five bugs were discovered during this demo. All are patched at runtime in `autoclean_demo.py` via monkey-patching without modifying the installed library.

| # | Location | Bug | Affected runs |
|---|----------|-----|---------------|
| BUG-1 | `modules.py:58` | `_impute_missing` called but method is named `_impute` | Run 5 |
| BUG-2 | `modules.py:479,482` | `EncodeCateg.handle` omits `self` when calling `_to_onehot`/`_to_label` | Runs 10–11 |
| BUG-3 | `autoclean.py:114` | `'logreg'` is handled by the code but absent from `_validate_params` allowlist | Run 6 |
| BUG-4 | `modules.py:295` | Winsorization assigns float fence values to `Int64` columns, rejected by pandas | Runs 8–9 |
| BUG-5 | `modules.py:350` | `infer_datetime_format` argument was removed in pandas 3.0; call crashes silently | Run 13 |

---

## Usage

```bash
# Step 1: generate the messy dataset
/opt/anaconda3/bin/python3 generate_dataset.py

# Step 2: clean with AutoClean (must run before profiling comparison)
/opt/anaconda3/bin/python3 autoclean_demo.py
# → autoclean_outputs/cleaned_auto.csv
# → autoclean_outputs/cleaned_full_manual.csv

# Step 3: EDA with pandas-profiling (Python 3.10 env required)
/opt/anaconda3/envs/myenv/bin/python pandas_profiling_demo.py
# → profiling_outputs/profile_minimal.html
# → profiling_outputs/profile_full.html
# → profiling_outputs/profile_comparison.html
```

---

## Requirements

### AutoClean (`/opt/anaconda3/bin/python3` — Python 3.12)
- py-AutoClean 1.1.3
- pandas 3.0.2
- scikit-learn, numpy, loguru

### pandas-profiling (`/opt/anaconda3/envs/myenv/bin/python` — Python 3.10)
- pandas-profiling 3.6.6
- pydantic 1.10.x (v2 breaks the import)
- typeguard 2.13.x (v4 breaks the constructor)
- matplotlib 3.7.x (v3.8+ removed `mplDeprecation`)
- htmlmin, visions, phik, statsmodels, wordcloud, imagehash

> pandas-profiling 3.6.6 requires Python <3.11 and a specific set of pinned dependencies that conflict with its successor `ydata-profiling 4.x`. The `myenv` conda environment isolates these pins from the base environment.
