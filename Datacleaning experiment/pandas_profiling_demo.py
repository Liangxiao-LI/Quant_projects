"""
pandas-profiling 3.6.6 — EDA report on raw_quant_dataset.csv
=============================================================
Generates three HTML reports into profiling_outputs/:

  profile_minimal.html    – lightweight overview (fast)
  profile_full.html       – full report with correlations, interactions,
                            missing-value heatmap, and distribution plots
  profile_comparison.html – side-by-side comparison of raw vs cleaned dataset

Run with:
  /opt/anaconda3/envs/myenv/bin/python pandas_profiling_demo.py
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
from pandas_profiling import ProfileReport   # noqa: E402 (3.6.6 shim over ydata)


# ── load datasets ─────────────────────────────────────────────────────────────
raw     = pd.read_csv("raw_quant_dataset.csv",     parse_dates=["trade_timestamp"])
cleaned = pd.read_csv("autoclean_outputs/cleaned_auto.csv", parse_dates=["trade_timestamp"])

print(f"Raw     shape : {raw.shape}")
print(f"Cleaned shape : {cleaned.shape}")

# ─────────────────────────────────────────────────────────────────────────────
# REPORT 1 — minimal (fast overview)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/3] Generating minimal profile...")

profile_minimal = ProfileReport(
    raw,
    title="Quant Dataset — Minimal Profile (Raw)",
    minimal=True,              # skips correlations & interactions for speed
    explorative=False,
)
profile_minimal.to_file("profiling_outputs/profile_minimal.html")
print("      → profiling_outputs/profile_minimal.html")

# ─────────────────────────────────────────────────────────────────────────────
# REPORT 2 — full (all analytics enabled)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/3] Generating full profile (this takes ~30 s)...")

profile_full = ProfileReport(
    raw,
    title="Quant Dataset — Full Profile (Raw)",
    minimal=False,
    explorative=True,          # enables extra checks (e.g. high-cardinality warnings)
    # ── overview ──────────────────────────────────────────────────────────────
    dataset={
        "description": "Synthetic stock market dataset with injected data quality issues.",
        "creator":     "AutoClean Demo",
        "url":         "https://github.com/elisemercury/AutoClean",
    },
    # ── variables ─────────────────────────────────────────────────────────────
    vars={
        "num": {
            "quantiles": [0.05, 0.25, 0.5, 0.75, 0.95],  # extra percentiles
        },
        "cat": {
            "n_obs": 10,        # show top-10 frequent categories
            "chi_squared_threshold": 0.999,
        },
    },
    # ── missing values ────────────────────────────────────────────────────────
    missing_diagrams={
        "bar":    True,    # bar chart of missing counts per column
        "matrix": True,    # missingness pattern matrix
        "heatmap": True,   # correlation of missingness between columns
        "dendrogram": True,
    },
    # ── correlations ─────────────────────────────────────────────────────────
    correlations={
        "pearson":  {"calculate": True},
        "spearman": {"calculate": True},
        "kendall":  {"calculate": True},
        "phi_k":    {"calculate": True},   # works for mixed numerical+categorical
        "cramers":  {"calculate": True},   # Cramér's V for categorical pairs
    },
    # ── interactions ─────────────────────────────────────────────────────────
    interactions={
        "continuous": True,    # scatter-plot matrix for numeric pairs
        "targets":    ["price", "daily_return", "pe_ratio"],
    },
    # ── duplicates ────────────────────────────────────────────────────────────
    duplicates={"head": 10},   # show first 10 duplicate rows
    # ── samples ───────────────────────────────────────────────────────────────
    samples={"head": 10, "tail": 10, "random": 5},
)
profile_full.to_file("profiling_outputs/profile_full.html")
print("      → profiling_outputs/profile_full.html")

# ─────────────────────────────────────────────────────────────────────────────
# REPORT 3 — side-by-side comparison: raw vs auto-cleaned
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/3] Generating comparison report (raw vs cleaned)...")

profile_raw_cmp = ProfileReport(
    raw,
    title="Raw",
    minimal=True,
)
profile_cleaned_cmp = ProfileReport(
    cleaned,
    title="Cleaned (auto mode)",
    minimal=True,
)

comparison = profile_raw_cmp.compare(profile_cleaned_cmp)
comparison.to_file("profiling_outputs/profile_comparison.html")
print("      → profiling_outputs/profile_comparison.html")

# ─────────────────────────────────────────────────────────────────────────────
# CONSOLE SUMMARY — key statistics
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  Console summary from full profile")
print("=" * 60)

desc = profile_full.get_description()   # returns a plain dict

tbl  = desc["table"]
vrs  = desc["variables"]
cors = desc.get("correlations", {})

print(f"\nOverview")
print(f"  Rows          : {tbl['n']}")
print(f"  Columns       : {tbl['n_var']}")
print(f"  Missing cells : {tbl['n_cells_missing']}  "
      f"({tbl['p_cells_missing']:.1%})")
print(f"  Duplicate rows: {tbl['n_duplicates']}")
print(f"  Numeric cols  : {tbl['types'].get('Numeric', 0)}")
print(f"  Categorical   : {tbl['types'].get('Categorical', 0)}")
print(f"  DateTime      : {tbl['types'].get('DateTime', 0)}")

print(f"\nPer-column missing values:")
for col, var in vrs.items():
    n_miss = var.get("n_missing", 0)
    if n_miss > 0:
        p_miss = var.get("p_missing", 0)
        print(f"  {col:20s}  {n_miss:4d}  ({p_miss:.1%})")

print(f"\nOutlier-prone columns (IQR method):")
num_cols = ["price", "volume", "daily_return", "market_cap_M", "beta", "pe_ratio"]
for col in num_cols:
    v  = vrs[col]
    mn = v.get("min", 0)
    mx = v.get("max", 0)
    q1 = v.get("25%", v.get("quantile_25", 0))
    q3 = v.get("75%", v.get("quantile_75", 0))
    print(f"  {col:15s}  min={mn:>12.2f}  max={mx:>12.2f}  "
          f"Q1={q1:.2f}  Q3={q3:.2f}")

print(f"\nTop correlations (Pearson, |r| > 0.3):")
try:
    pearson = cors.get("pearson")
    if pearson is not None:
        pairs = (
            pearson
            .abs()
            .where(lambda x: x < 1.0)
            .stack()
            .sort_values(ascending=False)
        )
        shown = 0
        for (c1, c2), r in pairs.items():
            if r > 0.3 and shown < 10:
                print(f"  {c1:20s} ↔ {c2:20s}  r={r:.3f}")
                shown += 1
        if shown == 0:
            print("  (no pairs above 0.3 — expected for this synthetic dataset)")
except Exception:
    print("  (correlation matrix not available)")

print("\nAll three HTML reports generated successfully.")
print("Open any of them in a browser to explore the interactive dashboard.")
