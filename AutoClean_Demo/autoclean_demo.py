"""
py-AutoClean Feature Demonstration
===================================
Showcases every major AutoClean parameter against the synthetic quant dataset.

py-AutoClean v1.1.3 has two known bugs that are transparently patched here:
  BUG-1  modules.py:58 — `_impute_missing` should be `_impute`
         (affects missing_num in {'mean','median','most_frequent'})
  BUG-2  modules.py:479/482 — EncodeCateg.handle drops `self` when calling
         _to_onehot/_to_label for explicit 'onehot'/'label' modes

  Runs 1–9 and 13–14 work without any patching.
  Runs 10–12 and Run 5 require the patches below.

Runs:
  Run 1  – auto mode            (fully automated pipeline)
  Run 2  – duplicates='auto'    (duplicate removal only)
  Run 3  – missing_num='knn'    (KNN imputation)
  Run 4  – missing_num='delete' (row deletion)
  Run 5  – missing_num ∈ {mean, median, most_frequent}  [patch applied]
  Run 6  – missing_categ='logreg'
  Run 7  – missing_categ='knn'
  Run 8  – outliers='winz'      (winsorization, default + strict multiplier)
  Run 9  – outliers='delete'    (row deletion)
  Run 10 – encode_categ=['onehot']   (one-hot, all columns)  [patch applied]
  Run 11 – encode_categ=['label']    (label encoding)         [patch applied]
  Run 12 – encode_categ=['onehot', ['sector']]  (selective)
  Run 13 – extract_datetime (all granularities)
  Run 14 – full manual pipeline
"""

import sys
import warnings
import textwrap

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ── ensure Anaconda site-packages is on path ─────────────────────────────────
ANACONDA_SITE = "/opt/anaconda3/lib/python3.12/site-packages"
if ANACONDA_SITE not in sys.path:
    sys.path.insert(0, ANACONDA_SITE)

from AutoClean import AutoClean           # noqa: E402
from AutoClean.modules import MissingValues, EncodeCateg  # noqa: E402

# ── BUG-1 patch: alias missing method name ───────────────────────────────────
MissingValues._impute_missing = MissingValues._impute

# ── BUG-2 patch: fix EncodeCateg.handle to pass self correctly ───────────────
def _patched_handle(self, df):
    if self.encode_categ:
        if not isinstance(self.encode_categ, list):
            self.encode_categ = ['auto']
        cols_categ = set(df.columns) ^ set(df.select_dtypes(include=np.number).columns)
        if len(self.encode_categ) == 1:
            target_cols = cols_categ
        else:
            target_cols = self.encode_categ[1]
        for feature in target_cols:
            if feature in cols_categ:
                feat = feature
            else:
                feat = df.columns[feature]
            try:
                pd.to_datetime(df[feat])
            except Exception:
                try:
                    if self.encode_categ[0] in ('auto',):
                        if df[feat].nunique() <= 10:
                            df = EncodeCateg._to_onehot(self, df, feat)
                        elif df[feat].nunique() <= 20:
                            df = EncodeCateg._to_label(self, df, feat)
                    elif self.encode_categ[0] == 'onehot':
                        df = EncodeCateg._to_onehot(self, df, feat)  # BUG-2 fix
                    elif self.encode_categ[0] == 'label':
                        df = EncodeCateg._to_label(self, df, feat)   # BUG-2 fix
                except Exception:
                    pass
    return df

EncodeCateg.handle = _patched_handle

# ── BUG-3 patch: 'logreg' missing from _validate_params allowlist ────────────
_orig_validate = AutoClean._validate_params

def _patched_validate(self, df, verbose, logfile):
    orig_categ = self.missing_categ
    if self.missing_categ == 'logreg':
        self.missing_categ = 'auto'   # temporarily satisfy validator
    _orig_validate(self, df, verbose, logfile)
    self.missing_categ = orig_categ   # restore for actual processing

AutoClean._validate_params = _patched_validate

# ── BUG-4 patch: winsorization tries to assign float fence to Int64 column ───
# When round_values converts whole-number floats to Int64, subsequent
# winsorization breaks on newer pandas (raises TypeError on float→int64).
from AutoClean.modules import Outliers  # noqa: E402

def _patched_winz(self, df):
    """
    Corrected winsorization: works on a float copy of each numeric column
    so that assigning fractional fence values never hits int dtype errors.
    """
    cols_num = df.select_dtypes(include=np.number).columns
    for feature in cols_num:
        lower_bound, upper_bound = Outliers._compute_bounds(self, df, feature)
        col = df[feature].astype(float)   # work on a float copy
        col = col.clip(lower=lower_bound, upper=upper_bound)
        df[feature] = col
    return df

Outliers._winsorization = _patched_winz

# ── BUG-5 patch: infer_datetime_format removed in pandas 3.0 ─────────────────
from AutoClean.modules import Adjust  # noqa: E402

def _patched_convert_datetime(self, df):
    if self.extract_datetime:
        cols = set(df.columns) ^ set(df.select_dtypes(include=np.number).columns)
        for feature in cols:
            try:
                dt_col = pd.to_datetime(df[feature])   # no infer_datetime_format
                df['Day'] = dt_col.dt.day
                if self.extract_datetime in ['auto', 'M', 'Y', 'h', 'm', 's']:
                    df['Month'] = dt_col.dt.month
                if self.extract_datetime in ['auto', 'Y', 'h', 'm', 's']:
                    df['Year'] = dt_col.dt.year
                if self.extract_datetime in ['auto', 'h', 'm', 's']:
                    df['Hour'] = dt_col.dt.hour
                if self.extract_datetime in ['auto', 'm', 's']:
                    df['Minute'] = dt_col.dt.minute
                if self.extract_datetime in ['auto', 's']:
                    df['Sec'] = dt_col.dt.second
            except Exception:
                pass
    return df

Adjust.convert_datetime = _patched_convert_datetime

# ── helpers ───────────────────────────────────────────────────────────────────
DIVIDER = "=" * 72


def section(title: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def summarise(label: str, raw: pd.DataFrame, cleaned: pd.DataFrame) -> None:
    print(f"\n{'─'*60}")
    print(f"  Result: {label}")
    print(f"{'─'*60}")
    print(f"  Rows        : {len(raw):>6}  →  {len(cleaned):>6}  (Δ {len(cleaned)-len(raw):+d})")
    print(f"  Columns     : {raw.shape[1]:>6}  →  {cleaned.shape[1]:>6}  (Δ {cleaned.shape[1]-raw.shape[1]:+d})")
    raw_miss   = int(raw.isnull().sum().sum())
    clean_miss = int(cleaned.isnull().sum().sum())
    print(f"  Missing vals: {raw_miss:>6}  →  {clean_miss:>6}  (Δ {clean_miss-raw_miss:+d})")
    raw_dups   = int(raw.duplicated().sum())
    clean_dups = int(cleaned.duplicated().sum())
    print(f"  Duplicates  : {raw_dups:>6}  →  {clean_dups:>6}  (Δ {clean_dups-raw_dups:+d})")


def col_list(df: pd.DataFrame) -> None:
    print(f"  Columns ({df.shape[1]}): {list(df.columns)}")


def stat(df: pd.DataFrame, col: str) -> str:
    return f"min={df[col].min():.2f}  max={df[col].max():.2f}  mean={df[col].mean():.2f}"


def load_raw() -> pd.DataFrame:
    return pd.read_csv("raw_quant_dataset.csv", parse_dates=["trade_timestamp"])


# ─────────────────────────────────────────────────────────────────────────────
# 0. RAW OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
section("0. Raw Dataset Overview")
raw = load_raw()
num_cols   = ["price", "volume", "daily_return", "market_cap_M", "beta", "pe_ratio"]
categ_cols = ["sector", "analyst_rating"]

print(f"\nShape          : {raw.shape}")
print(f"Duplicates     : {raw.duplicated().sum()}")
print(f"\nMissing values:\n{raw.isnull().sum().to_string()}")
print(f"\nDtypes:\n{raw.dtypes.to_string()}")
print(f"\nPrice (before clean) : {stat(raw.dropna(subset=['price']), 'price')}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 1 — AUTO MODE
# ─────────────────────────────────────────────────────────────────────────────
section("Run 1 — mode='auto'  (fully automated pipeline)")
print(textwrap.dedent("""
  mode='auto' activates all steps automatically:
    duplicates='auto', missing_num='auto', missing_categ='auto',
    outliers='winz', encode_categ=['auto'], extract_datetime='s'
"""))

p_auto = AutoClean(raw, mode="auto", logfile=False, verbose=False)
summarise("AUTO mode", raw, p_auto.output)
col_list(p_auto.output)
print("\nFirst 2 rows:")
print(p_auto.output.head(2).to_string())

# ─────────────────────────────────────────────────────────────────────────────
# RUN 2 — DUPLICATES ONLY
# ─────────────────────────────────────────────────────────────────────────────
section("Run 2 — duplicates='auto'  (duplicate removal only)")
print("  Drops all but one copy of each duplicated row.")

p_dup = AutoClean(raw, mode="manual", duplicates="auto", logfile=False, verbose=False)
summarise("Duplicates removed", raw, p_dup.output)
print(f"\n  Removed: {raw.duplicated().sum() - p_dup.output.duplicated().sum()} duplicate row(s)")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 3 — MISSING NUMERICAL — KNN
# ─────────────────────────────────────────────────────────────────────────────
section("Run 3 — missing_num='knn'  (K-Nearest Neighbours imputation)")
print(textwrap.dedent("""
  Fills each missing numeric value with the weighted average of its
  k nearest neighbours in feature space — preserves local structure.
"""))

p_knn = AutoClean(raw, mode="manual", missing_num="knn", logfile=False, verbose=False)
summarise("KNN numerical imputation", raw, p_knn.output)
print(f"\n  Numerical NaNs: {raw[num_cols].isnull().sum().sum()} → "
      f"{p_knn.output[num_cols].isnull().sum().sum()}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 4 — MISSING NUMERICAL — DELETE
# ─────────────────────────────────────────────────────────────────────────────
section("Run 4 — missing_num='delete'  (delete rows with missing numerics)")
print(textwrap.dedent("""
  Drops every row that has at least one missing numerical value.
  Aggressive — but guaranteed to leave zero NaNs.
"""))

p_del_num = AutoClean(raw, mode="manual", missing_num="delete", logfile=False, verbose=False)
summarise("Delete rows (missing numerics)", raw, p_del_num.output)
print(f"\n  Rows dropped          : {len(raw) - len(p_del_num.output)}")
print(f"  Numerical NaNs remain : {p_del_num.output[num_cols].isnull().sum().sum()}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 5 — MISSING NUMERICAL — MEAN / MEDIAN / MOST_FREQUENT
# ─────────────────────────────────────────────────────────────────────────────
section("Run 5 — missing_num ∈ {'mean', 'median', 'most_frequent'}  [BUG-1 patch applied]")
print(textwrap.dedent("""
  Simple univariate imputation via sklearn.SimpleImputer.
  NOTE: v1.1.3 calls a non-existent method `_impute_missing`; patched above.
"""))

for strategy in ("mean", "median", "most_frequent"):
    p = AutoClean(raw, mode="manual", missing_num=strategy, logfile=False, verbose=False)
    nans = p.output[num_cols].isnull().sum().sum()
    print(f"  [{strategy:>13}]  NaN→0: {nans==0}  |  price mean={p.output['price'].mean():.2f}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 6 — MISSING CATEGORICAL — LOGISTIC REGRESSION
# ─────────────────────────────────────────────────────────────────────────────
section("Run 6 — missing_categ='logreg'  (Logistic Regression imputation)")
print(textwrap.dedent("""
  Trains a per-column logistic regression on complete rows to predict
  missing category labels — good for structured low-cardinality features.
"""))

p_logreg = AutoClean(raw, mode="manual", missing_categ="logreg", logfile=False, verbose=False)
summarise("LogReg categorical imputation", raw, p_logreg.output)
print(f"\n  Categorical NaNs: {raw[categ_cols].isnull().sum().sum()} → "
      f"{p_logreg.output[categ_cols].isnull().sum().sum()}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 7 — MISSING CATEGORICAL — KNN
# ─────────────────────────────────────────────────────────────────────────────
section("Run 7 — missing_categ='knn'  (KNN categorical imputation)")
print(textwrap.dedent("""
  Encodes categories to integers, applies KNN imputation in that space,
  then decodes back to the original labels.
"""))

p_categ_knn = AutoClean(raw, mode="manual", missing_categ="knn", logfile=False, verbose=False)
summarise("KNN categorical imputation", raw, p_categ_knn.output)
print(f"\n  Categorical NaNs: {raw[categ_cols].isnull().sum().sum()} → "
      f"{p_categ_knn.output[categ_cols].isnull().sum().sum()}")
print(f"  Unique values restored:")
for col in categ_cols:
    print(f"    {col}: {sorted(p_categ_knn.output[col].dropna().unique())}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 8 — OUTLIERS — WINSORIZATION (default + strict)
# ─────────────────────────────────────────────────────────────────────────────
section("Run 8 — outliers='winz'  (Winsorization, default + strict outlier_param)")
print(textwrap.dedent("""
  Caps values at IQR fences:
    lower = Q1 − outlier_param × IQR
    upper = Q3 + outlier_param × IQR
  Values beyond fences are replaced by the fence value (not deleted).
  Default param = 1.5; smaller values create tighter fences.
"""))

# pre-fill NaNs so only outlier behaviour is visible
# cast all numeric cols to float64 to avoid pandas int64 ↔ float fence clash
df_filled = raw.copy()
df_filled[num_cols] = (
    df_filled[num_cols]
    .fillna(df_filled[num_cols].median())
    .astype(float)
)

print(f"  Price BEFORE          : {stat(df_filled, 'price')}")
for param in (1.5, 1.0):
    p = AutoClean(df_filled, mode="manual", outliers="winz",
                  outlier_param=param, logfile=False, verbose=False)
    print(f"  Price AFTER (param={param}) : {stat(p.output, 'price')}")
    print(f"  PE    AFTER (param={param}) : {stat(p.output, 'pe_ratio')}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 9 — OUTLIERS — DELETE
# ─────────────────────────────────────────────────────────────────────────────
section("Run 9 — outliers='delete'  (delete rows containing outliers)")
print("  Any row with a value outside IQR bounds is dropped entirely.")

p_del_out = AutoClean(df_filled, mode="manual", outliers="delete",
                      outlier_param=1.5, logfile=False, verbose=False)
summarise("Outlier row deletion", df_filled, p_del_out.output)
print(f"\n  Price after deletion  : {stat(p_del_out.output, 'price')}")
print(f"  PE    after deletion  : {stat(p_del_out.output, 'pe_ratio')}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 10 — ENCODE CATEGORICAL — ONE-HOT (all columns)
# ─────────────────────────────────────────────────────────────────────────────
section("Run 10 — encode_categ=['onehot']  (one-hot, all categorical)  [BUG-2 patch applied]")
print(textwrap.dedent("""
  Creates a binary column for every unique category value.
  NOTE: v1.1.3 omits `self` when calling _to_onehot/_to_label for
  explicit 'onehot'/'label' modes; the patch above corrects this.
"""))

# start from deduped + KNN-imputed base (no encoding yet) for clean encoding demos
df_clean = p_knn.output.copy()
df_clean[categ_cols] = df_clean[categ_cols].fillna(
    df_clean[categ_cols].mode().iloc[0]
)

p_onehot = AutoClean(df_clean, mode="manual", encode_categ=["onehot"],
                     logfile=False, verbose=False)
new_cols = sorted(set(p_onehot.output.columns) - set(df_clean.columns))
summarise("One-hot encoding (all)", df_clean, p_onehot.output)
print(f"\n  New binary columns ({len(new_cols)}): {new_cols}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 11 — ENCODE CATEGORICAL — LABEL
# ─────────────────────────────────────────────────────────────────────────────
section("Run 11 — encode_categ=['label']  (label encoding)  [BUG-2 patch applied]")
print(textwrap.dedent("""
  Maps each unique category to an integer (0, 1, 2, …).
  Compact, but introduces an implied ordinal relationship.
"""))

p_label = AutoClean(df_clean, mode="manual", encode_categ=["label"],
                    logfile=False, verbose=False)
summarise("Label encoding (all)", df_clean, p_label.output)
for col in ["ticker", "sector", "analyst_rating"]:
    lab_col = col + "_lab"
    if lab_col in p_label.output.columns:
        print(f"  {lab_col}: {sorted(p_label.output[lab_col].dropna().unique())[:8]}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 12 — ENCODE CATEGORICAL — SELECTIVE ONE-HOT
# ─────────────────────────────────────────────────────────────────────────────
section("Run 12 — encode_categ=['onehot', ['sector']]  (selective encoding)")
print(textwrap.dedent("""
  Pass a column list as the second element to encode only those columns.
  Here we one-hot-encode 'sector' only, leaving 'ticker' and
  'analyst_rating' as strings.
"""))

p_selective = AutoClean(df_clean, mode="manual",
                        encode_categ=["onehot", ["sector"]],
                        logfile=False, verbose=False)
sector_dummies = [c for c in p_selective.output.columns if "sector_" in c]
summarise("Selective one-hot (sector only)", df_clean, p_selective.output)
print(f"\n  Sector dummy columns : {sector_dummies}")
still_str = [c for c in ["ticker", "analyst_rating"]
             if pd.api.types.is_string_dtype(p_selective.output[c])]
print(f"  Still-string columns : {still_str}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 13 — EXTRACT DATETIME (all granularities)
# ─────────────────────────────────────────────────────────────────────────────
section("Run 13 — extract_datetime (all granularities: D / M / Y / h / m / s)")
print(textwrap.dedent("""
  AutoClean detects datetime columns and expands them into numeric parts.
  Granularity controls the maximum component extracted:
    'D' → Day
    'M' → Day + Month
    'Y' → Day + Month + Year
    'h' → Day + Month + Year + Hour
    'm' → Day + Month + Year + Hour + Minute
    's' → Day + Month + Year + Hour + Minute + Second
  (Original datetime column is retained alongside the new components.)
"""))

df_dt = raw[["trade_timestamp", "price", "volume"]].copy()
df_dt[["price", "volume"]] = df_dt[["price", "volume"]].fillna(
    df_dt[["price", "volume"]].median()
)

for g in ("D", "M", "Y", "h", "m", "s"):
    p = AutoClean(df_dt, mode="manual", extract_datetime=g, logfile=False, verbose=False)
    dt_new = [c for c in p.output.columns if c not in df_dt.columns]
    print(f"  '{g}'  →  {p.output.shape[1]} cols  |  new: {dt_new}")

# ─────────────────────────────────────────────────────────────────────────────
# RUN 14 — FULL MANUAL PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
section("Run 14 — Full manual pipeline  (all features combined)")
print(textwrap.dedent("""
  Explicit control over every step:
    duplicates       = 'auto'
    missing_num      = 'knn'
    missing_categ    = 'logreg'
    outliers         = 'winz'   (outlier_param=1.5)
    encode_categ     = ['onehot', ['sector', 'analyst_rating']]
    extract_datetime = 'D'
"""))

p_full = AutoClean(
    raw,
    mode="manual",
    duplicates="auto",
    missing_num="knn",
    missing_categ="logreg",
    outliers="winz",
    outlier_param=1.5,
    encode_categ=["onehot", ["sector", "analyst_rating"]],
    extract_datetime="D",
    logfile=False,
    verbose=False,
)

summarise("Full manual pipeline", raw, p_full.output)
print(f"\n  Missing values left : {p_full.output.isnull().sum().sum()}")
print(f"  Duplicates left     : {p_full.output.duplicated().sum()}")
print(f"  Price (winsorized)  : {stat(p_full.output, 'price')}")
print(f"\n  Final column list ({p_full.output.shape[1]} cols):")
for col in sorted(p_full.output.columns):
    print(f"    {col:40s}  {str(p_full.output[col].dtype)}")

# ─────────────────────────────────────────────────────────────────────────────
# SAVE OUTPUTS
# ─────────────────────────────────────────────────────────────────────────────
section("Saving outputs")
p_auto.output.to_csv("cleaned_auto.csv",        index=False)
p_full.output.to_csv("cleaned_full_manual.csv", index=False)
print("  cleaned_auto.csv          → auto mode output")
print("  cleaned_full_manual.csv   → full manual pipeline output")

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY TABLE
# ─────────────────────────────────────────────────────────────────────────────
section("Feature Coverage Summary")
print(textwrap.dedent("""
  ┌──────────────────────────────┬──────────────────────────────────────────┐
  │ Feature / Param              │ Options demonstrated                     │
  ├──────────────────────────────┼──────────────────────────────────────────┤
  │ mode                         │ 'auto', 'manual'                         │
  │ duplicates                   │ 'auto'                                   │
  │ missing_num                  │ 'knn', 'delete', 'mean', 'median',       │
  │                              │ 'most_frequent'                          │
  │ missing_categ                │ 'logreg', 'knn'                          │
  │ outliers                     │ 'winz', 'delete'                         │
  │ outlier_param                │ 1.5 (default), 1.0 (strict)              │
  │ encode_categ                 │ ['auto'], ['onehot'], ['label'],          │
  │                              │ ['onehot', ['col']]  (selective)         │
  │ extract_datetime             │ 'D', 'M', 'Y', 'h', 'm', 's'            │
  ├──────────────────────────────┼──────────────────────────────────────────┤
  │ Library bugs found (v1.1.3)  │ BUG-1: _impute_missing typo              │
  │                              │ BUG-2: EncodeCateg missing `self` arg    │
  │                              │ BUG-3: 'logreg' absent from validator    │
  │                              │ BUG-4: winz assigns float to Int64 col  │
  │                              │ BUG-5: infer_datetime_format removed in  │
  │                              │        pandas 3.0 (crashes silently)     │
  └──────────────────────────────┴──────────────────────────────────────────┘
"""))
