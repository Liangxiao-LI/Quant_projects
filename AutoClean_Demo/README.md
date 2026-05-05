# py-AutoClean Demo

A complete feature showcase of [py-AutoClean](https://github.com/elisemercury/AutoClean) applied to a synthetic quantitative finance dataset. Every major parameter is exercised across 14 runs, with before/after comparisons printed for each.

## Files

| File | Description |
|------|-------------|
| `generate_dataset.py` | Generates `raw_quant_dataset.csv` — a 618-row stock dataset with deliberately injected problems |
| `autoclean_demo.py` | 14-run demonstration covering every py-AutoClean parameter |
| `raw_quant_dataset.csv` | Synthetic messy dataset (input) |
| `cleaned_auto.csv` | Output from Run 1 — fully automated pipeline |
| `cleaned_full_manual.csv` | Output from Run 14 — full manual pipeline |

## Dataset

`raw_quant_dataset.csv` simulates daily stock observations for 10 tickers over ~2 years. The following problems are intentionally injected to stress-test the cleaner:

| Problem | Detail |
|---------|--------|
| Duplicate rows | ~3% of rows duplicated |
| Numerical NaNs | 6–9% missing rate across `price`, `volume`, `daily_return`, `market_cap_M`, `beta`, `pe_ratio` |
| Categorical NaNs | 5–7% missing in `sector` and `analyst_rating` |
| Outliers | Extreme price spikes (−9070 to +9511 vs. normal 50–500), negative volume, absurd PE ratios |
| Datetime column | `trade_timestamp` for datetime extraction demo |

## Runs

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

## Library Bugs Found (v1.1.3)

Five bugs were discovered in py-AutoClean v1.1.3 during this demo. All are patched at runtime in `autoclean_demo.py` via monkey-patching without modifying the installed library.

| # | Location | Bug | Affected runs |
|---|----------|-----|---------------|
| BUG-1 | `modules.py:58` | `_impute_missing` called but method is named `_impute` | Run 5 |
| BUG-2 | `modules.py:479,482` | `EncodeCateg.handle` omits `self` when calling `_to_onehot`/`_to_label` | Runs 10–11 |
| BUG-3 | `autoclean.py:114` | `'logreg'` is handled by the code but absent from `_validate_params` allowlist | Run 6 |
| BUG-4 | `modules.py:295` | Winsorization assigns float fence values to `Int64` columns, rejected by pandas | Runs 8–9 |
| BUG-5 | `modules.py:350` | `infer_datetime_format` argument was removed in pandas 3.0; call crashes silently | Run 13 |

## Usage

```bash
# Step 1: generate the messy dataset
python generate_dataset.py

# Step 2: run the full demo
python autoclean_demo.py
```

The demo uses Anaconda Python (`/opt/anaconda3/bin/python3`) because `py-AutoClean` is installed there.
If using a different environment, install the dependency first:
```bash
pip install py-AutoClean
```

## Requirements

- Python 3.12
- pandas ≥ 2.0 (tested on 3.0.2)
- numpy
- scikit-learn
- py-AutoClean 1.1.3
- loguru (installed automatically with py-AutoClean)
