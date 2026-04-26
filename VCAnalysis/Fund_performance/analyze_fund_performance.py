from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


MIN_VALID_PERIODS = 4
INPUT_FILE = "Fund_performance_20260426.csv"


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    return df


def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    original_rows = len(df)
    original_funds = df["fundname"].nunique(dropna=True)

    df["fundname"] = df["fundname"].astype(str).str.strip()
    df.loc[df["fundname"].eq(""), "fundname"] = pd.NA
    df = df.dropna(subset=["fundname"])

    for col in ["irr", "dpi", "tvpi", "rvpi"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["asofyear", "asofquarter"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.drop_duplicates()

    perf_cols = ["irr", "dpi", "tvpi", "rvpi"]
    has_any_perf = df[perf_cols].notna().any(axis=1)
    df = df.loc[has_any_perf].copy()

    valid_quarter = df["asofquarter"].between(1, 4, inclusive="both")
    valid_year = df["asofyear"].between(1900, 2100, inclusive="both")
    period_str = (
        df.loc[valid_quarter & valid_year, "asofyear"].astype(int).astype(str)
        + "Q"
        + df.loc[valid_quarter & valid_year, "asofquarter"].astype(int).astype(str)
    )
    df.loc[valid_quarter & valid_year, "report_date"] = pd.PeriodIndex(period_str, freq="Q").to_timestamp(
        how="end"
    )

    fund_valid_periods = (
        df.groupby("fundname")[perf_cols]
        .apply(lambda x: x.notna().any(axis=1).sum())
        .rename("valid_periods")
    )

    eligible_funds = fund_valid_periods[fund_valid_periods >= MIN_VALID_PERIODS].index
    cleaned = df[df["fundname"].isin(eligible_funds)].copy()
    cleaned = cleaned.merge(
        fund_valid_periods.reset_index(), on="fundname", how="left", validate="many_to_one"
    )
    cleaned["asofyear"] = cleaned["asofyear"].astype("Int64")
    cleaned["asofquarter"] = cleaned["asofquarter"].astype("Int64")

    summary = {
        "original_rows": int(original_rows),
        "original_funds": int(original_funds),
        "rows_after_cleaning": int(len(cleaned)),
        "funds_after_cleaning": int(cleaned["fundname"].nunique()),
        "rows_removed": int(original_rows - len(cleaned)),
        "funds_removed": int(original_funds - cleaned["fundname"].nunique()),
        "row_retention_pct": round(len(cleaned) / original_rows * 100, 2),
        "fund_retention_pct": round(cleaned["fundname"].nunique() / original_funds * 100, 2),
        "min_valid_periods_threshold": MIN_VALID_PERIODS,
    }

    return cleaned, summary


def build_summary_tables(cleaned: pd.DataFrame) -> dict:
    perf_cols = ["irr", "dpi", "tvpi", "rvpi"]
    metric_stats = cleaned[perf_cols].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).T
    metric_stats = metric_stats.round(3)

    year_median = (
        cleaned.dropna(subset=["asofyear"])
        .groupby("asofyear")[perf_cols]
        .median()
        .dropna(how="all")
        .round(3)
    )

    latest_obs = (
        cleaned.sort_values(["fundname", "report_date", "asofyear", "asofquarter"])
        .groupby("fundname", as_index=False)
        .tail(1)
    )
    top_tvpi = latest_obs.nlargest(15, "tvpi")[["fundname", "tvpi", "irr", "dpi", "rvpi", "valid_periods"]]
    top_tvpi = top_tvpi.round(3)

    return {
        "metric_stats": metric_stats,
        "year_median": year_median,
        "top_tvpi": top_tvpi,
    }


def create_visualizations(cleaned: pd.DataFrame, output_dir: Path) -> None:
    sns.set_theme(style="whitegrid", context="talk")
    perf_cols = ["irr", "dpi", "tvpi", "rvpi"]

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    for ax, col in zip(axes.flatten(), perf_cols):
        plot_series = cleaned[col].dropna()
        if col in ["irr", "tvpi", "dpi", "rvpi"]:
            upper = plot_series.quantile(0.99)
            lower = plot_series.quantile(0.01)
            plot_series = plot_series.clip(lower=lower, upper=upper)
        sns.histplot(plot_series, bins=50, kde=True, ax=ax, color="#3366cc")
        ax.set_title(f"{col.upper()} Distribution (Winsorized 1%-99%)")
        ax.set_xlabel(col.upper())
    fig.tight_layout()
    fig.savefig(output_dir / "distribution_metrics.png", dpi=220)
    plt.close(fig)

    year_median = (
        cleaned.dropna(subset=["asofyear"])
        .groupby("asofyear")[perf_cols]
        .median()
        .dropna(how="all")
    )
    fig, ax = plt.subplots(figsize=(14, 7))
    for col, color in zip(perf_cols, ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]):
        ax.plot(year_median.index, year_median[col], marker="o", linewidth=2, label=col.upper(), color=color)
    ax.set_title("Median Fund Performance Metrics by Reporting Year")
    ax.set_xlabel("Reporting Year")
    ax.set_ylabel("Median Value")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "median_metrics_by_year.png", dpi=220)
    plt.close(fig)

    latest_obs = (
        cleaned.sort_values(["fundname", "report_date", "asofyear", "asofquarter"])
        .groupby("fundname", as_index=False)
        .tail(1)
    )
    top_tvpi = latest_obs.nlargest(15, "tvpi").sort_values("tvpi")
    fig, ax = plt.subplots(figsize=(14, 8))
    sns.barplot(
        data=top_tvpi, y="fundname", x="tvpi", hue="fundname", dodge=False, legend=False, ax=ax, palette="viridis"
    )
    ax.set_title("Top 15 Funds by Latest TVPI")
    ax.set_xlabel("TVPI")
    ax.set_ylabel("Fund Name")
    fig.tight_layout()
    fig.savefig(output_dir / "top15_latest_tvpi.png", dpi=220)
    plt.close(fig)


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    input_path = base_dir / INPUT_FILE
    output_dir = base_dir / "output"
    fig_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    raw_df = load_data(input_path)
    cleaned_df, summary = clean_data(raw_df)
    tables = build_summary_tables(cleaned_df)
    create_visualizations(cleaned_df, fig_dir)

    cleaned_df.to_csv(output_dir / "fund_performance_cleaned.csv", index=False)
    tables["metric_stats"].to_csv(output_dir / "metric_stats.csv")
    tables["year_median"].to_csv(output_dir / "median_metrics_by_year.csv")
    tables["top_tvpi"].to_csv(output_dir / "top15_latest_tvpi.csv", index=False)

    with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("Analysis complete.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
