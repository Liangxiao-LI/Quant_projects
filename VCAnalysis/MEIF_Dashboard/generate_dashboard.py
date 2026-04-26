from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


CSV_FILE = "MEIF West Midlands Equity Fund_investment.csv"
README_FILE = "README.md"


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = (
        pd.Index(out.columns)
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )
    return out


def first_existing(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def fmt_num(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.{digits}f}"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def make_breakdown(df: pd.DataFrame, group_col: str, amount_col: str) -> pd.DataFrame:
    temp = pd.DataFrame(
        {
            "bucket": df[group_col].fillna("Unknown").astype(str).str.strip().replace("", "Unknown"),
            "amount": df[amount_col],
        }
    )
    agg = (
        temp.groupby("bucket", as_index=False)
        .agg(investments=("bucket", "size"), capital=("amount", "sum"))
        .sort_values(["capital", "investments"], ascending=[False, False])
    )
    total = agg["capital"].sum()
    agg["share_pct"] = (agg["capital"] / total * 100) if total > 0 else 0.0
    return agg


def mermaid_pie(title: str, breakdown: pd.DataFrame, top_n: int = 6) -> str:
    if breakdown.empty:
        return '```mermaid\npie showData\n    "No data" : 1\n```'
    top = breakdown.head(top_n).copy()
    other = breakdown.iloc[top_n:]["capital"].sum() if len(breakdown) > top_n else 0.0
    lines = ["```mermaid", "pie showData", f"    title {title}"]
    for _, row in top.iterrows():
        lines.append(f'    "{row["bucket"]}" : {float(row["capital"]):.4f}')
    if other > 0:
        lines.append(f'    "Other" : {float(other):.4f}')
    lines.append("```")
    return "\n".join(lines)


def mermaid_bar_year(yearly: pd.DataFrame, amount_col: str) -> str:
    if yearly.empty:
        return (
            "```mermaid\n"
            "xychart-beta\n"
            '    title "Investment by Year"\n'
            '    x-axis ["N/A"]\n'
            '    y-axis "Capital" 0 --> 1\n'
            "    bar [0]\n"
            "```"
        )
    years = ", ".join(f'"{int(v)}"' for v in yearly["year"])
    values = ", ".join(f"{float(v):.4f}" for v in yearly["capital"])
    ymax = max(float(yearly["capital"].max()) * 1.15, 1.0)
    return (
        "```mermaid\n"
        "xychart-beta\n"
        '    title "Capital Deployment by Year"\n'
        f"    x-axis [{years}]\n"
        f'    y-axis "Capital ({amount_col})" 0 --> {ymax:.2f}\n'
        f"    bar [{values}]\n"
        "```"
    )


def generate_readme(base_dir: Path, brief: bool = False) -> str:
    csv_path = base_dir / CSV_FILE
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    raw = pd.read_csv(csv_path)
    df = standardize_columns(raw)

    amount_col = first_existing(df, ["totalraised", "totalraisednativeamount"])
    company_col = first_existing(df, ["companyname", "companylegalname"])
    sector_col = first_existing(df, ["primaryindustrysector", "primaryindustrygroup"])
    stage_col = first_existing(df, ["firstfinancingdealclass", "firstfinancingdealtype"])
    geo_col = first_existing(df, ["hqstate_province", "hqcity", "hqcountry", "hqglobalregion"])
    date_col = first_existing(df, ["lastfinancingdate", "firstfinancingdate", "companyfinancingstatusdate"])

    if amount_col is None or company_col is None:
        raise ValueError("Required columns missing: need amount and company fields.")

    df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    valid = df.dropna(subset=[amount_col]).copy()
    total_rows = len(df)
    covered_rows = len(valid)
    coverage_pct = (covered_rows / total_rows * 100) if total_rows else 0.0

    total_capital = valid[amount_col].sum()
    avg_ticket = valid[amount_col].mean()
    med_ticket = valid[amount_col].median()
    largest_idx = valid[amount_col].idxmax() if not valid.empty else None
    largest_name = valid.loc[largest_idx, company_col] if largest_idx is not None else "N/A"
    largest_amount = valid.loc[largest_idx, amount_col] if largest_idx is not None else None

    recent_name = "N/A"
    recent_date = "N/A"
    if date_col and not valid[date_col].dropna().empty:
        recent_idx = valid[date_col].idxmax()
        recent_name = valid.loc[recent_idx, company_col]
        recent_date = valid.loc[recent_idx, date_col].date().isoformat()

    unique_companies = df[company_col].nunique(dropna=True)
    top_companies = (
        valid[[company_col, amount_col]]
        .sort_values(amount_col, ascending=False)
        .head(5)
        .assign(share_pct=lambda x: x[amount_col] / total_capital * 100 if total_capital > 0 else 0)
    )

    sector_breakdown = make_breakdown(valid, sector_col, amount_col) if sector_col else pd.DataFrame()
    stage_breakdown = make_breakdown(valid, stage_col, amount_col) if stage_col else pd.DataFrame()
    geo_breakdown = make_breakdown(valid, geo_col, amount_col) if geo_col else pd.DataFrame()

    yearly = pd.DataFrame()
    if date_col:
        yearly = (
            valid.assign(year=valid[date_col].dt.year)
            .dropna(subset=["year"])
            .groupby("year", as_index=False)
            .agg(investments=("year", "size"), capital=(amount_col, "sum"))
            .sort_values("year")
        )

    top5_share = top_companies[amount_col].sum() / total_capital * 100 if total_capital > 0 else 0.0
    largest_sector = sector_breakdown.iloc[0] if not sector_breakdown.empty else None
    largest_geo = geo_breakdown.iloc[0] if not geo_breakdown.empty else None

    q1 = valid[amount_col].quantile(0.25) if not valid.empty else 0.0
    q3 = valid[amount_col].quantile(0.75) if not valid.empty else 0.0
    iqr = q3 - q1
    high_threshold = q3 + 1.5 * iqr
    unusually_large = valid[valid[amount_col] > high_threshold] if iqr > 0 else pd.DataFrame()

    missing_amount = total_rows - covered_rows

    lines: list[str] = []
    lines.append("# MEIF West Midlands Equity Fund - Daily Management Dashboard")
    lines.append("")
    lines.append(
        f"> Source: `{CSV_FILE}` | Records: **{total_rows}** | Capital coverage: **{covered_rows}/{total_rows} ({coverage_pct:.1f}%)** using `{amount_col}`"
    )
    lines.append("")
    lines.append("## 1) Executive Fund Snapshot")
    lines.append("")
    lines.append(
        md_table(
            ["Metric", "Value"],
            [
                ["Total invested capital", fmt_num(total_capital)],
                ["Number of investments", str(total_rows)],
                ["Number of portfolio companies", str(unique_companies)],
                ["Average investment size", fmt_num(avg_ticket)],
                ["Median investment size", fmt_num(med_ticket)],
                ["Largest investment", f"{largest_name} ({fmt_num(largest_amount)})"],
                ["Most recent investment", f"{recent_name} ({recent_date})" if date_col else "N/A"],
            ],
        )
    )
    lines.append("")
    lines.append("Focus: compact view for daily portfolio monitoring and exception tracking.")
    lines.append("")

    lines.append("## 2) Capital Allocation Breakdown")
    lines.append("")
    lines.append("### Top Companies by Invested Amount")
    top_n = 3 if brief else 5
    lines.append(
        md_table(
            ["Company", "Capital", "Share of Total"],
            [
                [row[company_col], fmt_num(row[amount_col]), f"{row['share_pct']:.1f}%"]
                for _, row in top_companies.head(top_n).iterrows()
            ]
            or [["N/A", "N/A", "N/A"]],
        )
    )
    lines.append("")

    if not sector_breakdown.empty:
        lines.append("### Allocation by Sector")
        lines.append(
            md_table(
                ["Sector", "# Investments", "Capital", "Share"],
                [
                    [r["bucket"], str(int(r["investments"])), fmt_num(r["capital"]), f"{r['share_pct']:.1f}%"]
                    for _, r in sector_breakdown.iterrows()
                ],
            )
        )
        lines.append("")
        lines.append(mermaid_pie("Sector Allocation", sector_breakdown))
        lines.append("Shows where exposure is concentrated by industry theme.")
        lines.append("")

    if not brief and not stage_breakdown.empty:
        lines.append("### Allocation by Stage")
        lines.append(
            md_table(
                ["Stage", "# Investments", "Capital", "Share"],
                [
                    [r["bucket"], str(int(r["investments"])), fmt_num(r["capital"]), f"{r['share_pct']:.1f}%"]
                    for _, r in stage_breakdown.iterrows()
                ],
            )
        )
        lines.append("")
        lines.append(mermaid_pie("Stage Allocation", stage_breakdown))
        lines.append("Checks whether deployment stays aligned with stage mandate.")
        lines.append("")

    if not geo_breakdown.empty:
        lines.append("### Allocation by Geography")
        lines.append(
            md_table(
                ["Region", "# Investments", "Capital", "Share"],
                [
                    [r["bucket"], str(int(r["investments"])), fmt_num(r["capital"]), f"{r['share_pct']:.1f}%"]
                    for _, r in geo_breakdown.iterrows()
                ],
            )
        )
        lines.append("")
        lines.append(mermaid_pie("Geography Allocation", geo_breakdown))
        lines.append("Highlights location concentration and sourcing breadth.")
        lines.append("")

    if not yearly.empty:
        lines.append("### Allocation by Year")
        lines.append(
            md_table(
                ["Year", "# Investments", "Capital"],
                [
                    [str(int(r["year"])), str(int(r["investments"])), fmt_num(r["capital"])]
                    for _, r in yearly.iterrows()
                ],
            )
        )
        lines.append("")
        lines.append(mermaid_bar_year(yearly, amount_col))
        lines.append("Tracks deployment pace and vintage clustering.")
        lines.append("")

    lines.append("## 3) Concentration and Risk Checks")
    lines.append("")
    risk_rows = [
        ["Top 5 investments as % of total capital", f"{top5_share:.1f}%"],
        [
            "Largest sector exposure",
            f"{largest_sector['bucket']} ({largest_sector['share_pct']:.1f}%)" if largest_sector is not None else "N/A",
        ],
        [
            "Largest geography exposure",
            f"{largest_geo['bucket']} ({largest_geo['share_pct']:.1f}%)" if largest_geo is not None else "N/A",
        ],
        ["Missing investment amount rows", str(missing_amount)],
        ["Unusually large deals (IQR rule)", ", ".join(unusually_large[company_col].tolist()) or "None flagged"],
    ]
    lines.append(md_table(["Check", "Result"], risk_rows))
    lines.append("")

    lines.append("## 4) Practical Management Insights")
    lines.append("")
    insights: list[str] = []
    if top5_share >= 75:
        insights.append(
            f"- Concentration is high: top 5 holdings represent **{top5_share:.1f}%** of invested capital; prioritize diversification in upcoming deployments."
        )
    if largest_sector is not None and largest_sector["share_pct"] >= 50:
        insights.append(
            f"- Sector exposure is skewed to **{largest_sector['bucket']}** at **{largest_sector['share_pct']:.1f}%**; review target sector limits."
        )
    if largest_geo is not None and largest_geo["share_pct"] >= 70:
        insights.append(
            f"- Geographic exposure is concentrated in **{largest_geo['bucket']}** ({largest_geo['share_pct']:.1f}%); expand regional pipeline where mandate allows."
        )
    if missing_amount > 0:
        insights.append("- Data quality: some rows have missing investment amounts; close gaps before monthly reporting.")
    if date_col and not yearly.empty and len(yearly) > 1:
        peak_year = int(yearly.loc[yearly["capital"].idxmax(), "year"])
        insights.append(f"- Deployment pace is uneven; peak year is **{peak_year}**. Track whether new deals smooth vintage risk.")
    if not insights:
        insights.append("- Current allocation looks balanced on available fields; continue monitoring new deals against concentration thresholds.")

    lines.extend(insights)
    lines.append("")
    lines.append("### Suggested Daily Follow-Ups")
    if brief:
        lines.extend(
            [
                "- Compare each new deal against median ticket size before IC sign-off.",
                "- Keep top holdings and missing data fields on a weekly exception list.",
            ]
        )
    else:
        lines.extend(
            [
                "- Compare every new deal against median ticket size before IC sign-off.",
                "- Maintain watchlist of top holdings and expected follow-on capital needs.",
                "- Update missing data fields weekly to keep dashboard decision-ready.",
            ]
        )
    lines.append("")
    lines.append("## Rebuild")
    lines.append("")
    lines.append("Run `python generate_dashboard.py` for full dashboard, or `python generate_dashboard.py --brief` for one-page mode.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MEIF dashboard README from CSV.")
    parser.add_argument(
        "--brief",
        action="store_true",
        help="Generate a shorter one-page dashboard view.",
    )
    parser.add_argument(
        "--output",
        default=README_FILE,
        help="Output markdown filename (default: README.md).",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    readme_content = generate_readme(base_dir, brief=args.brief)
    output_path = base_dir / args.output
    output_path.write_text(readme_content, encoding="utf-8")
    mode = "brief" if args.brief else "full"
    print(f"Generated {output_path} ({mode} mode)")


if __name__ == "__main__":
    main()
