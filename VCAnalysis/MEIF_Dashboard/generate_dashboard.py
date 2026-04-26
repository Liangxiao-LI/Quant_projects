from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


CSV_FILE = "MEIF West Midlands Equity Fund_investment.csv"
DEAL_FILE = "Deal_Info_20260426.csv"
README_FILE = "README.md"
TARGET_INVESTOR_PATTERNS = [
    "future planet capital",
    "midven",
    "midlands engine investment fund",
    "midlands engine",
    "meif",
]


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


def normalize_name(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.lower()
        .str.replace(r"[^a-z0-9]+", " ", regex=True)
        .str.strip()
    )


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


def extract_coinvestors(text: str) -> list[str]:
    """
    Extract rough co-investor names from deal synopsis snippets.
    We parse phrases like "from X, Y and Z on ...", then remove target investors
    and generic placeholders.
    """
    if not text:
        return []
    text_l = str(text).lower()
    match = re.search(r"\bfrom\s+(.+?)(?:\s+on\s+|\s+in\s+approximately|\.)", text_l)
    if not match:
        return []

    raw = match.group(1)
    chunks = re.split(r",| and | with participation from | led by ", raw)
    out: list[str] = []
    generic_tokens = {
        "other undisclosed investors",
        "other undisclosed investor",
        "undisclosed investors",
        "undisclosed investor",
        "other investors",
        "other",
    }
    for token in chunks:
        name = re.sub(r"[^a-z0-9& ]+", " ", token).strip()
        if not name:
            continue
        if any(p in name for p in TARGET_INVESTOR_PATTERNS):
            continue
        if name in generic_tokens:
            continue
        out.append(name.title())
    return out


def detect_relevant_deals(deals: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    candidate_text_cols = [
        c
        for c in [
            "dealsynopsis",
            "investor",
            "investors",
            "newinvestors",
            "followoninvestors",
            "fund",
            "fundname",
            "participant",
            "participants",
        ]
        if c in deals.columns
    ]

    if not candidate_text_cols:
        return deals.iloc[0:0].copy(), []

    combined_text = deals[candidate_text_cols].fillna("").astype(str).agg(" | ".join, axis=1).str.lower()
    mask = pd.Series(False, index=deals.index)
    for pat in TARGET_INVESTOR_PATTERNS:
        mask |= combined_text.str.contains(re.escape(pat), regex=True)
    return deals.loc[mask].copy(), candidate_text_cols


def attach_company_info(relevant_deals: pd.DataFrame, company_df: pd.DataFrame) -> pd.DataFrame:
    """
    Join filtered deals back to company-level attributes.
    Prefer companyid; fallback to normalized companyname if needed.
    """
    if "companyid" in relevant_deals.columns and "companyid" in company_df.columns:
        joined = relevant_deals.merge(
            company_df,
            on="companyid",
            how="left",
            suffixes=("_deal", "_company"),
        )
        if joined["companyname_company"].notna().any():
            return joined

    if "companyname" in relevant_deals.columns and "companyname" in company_df.columns:
        left = relevant_deals.copy()
        right = company_df.copy()
        left["_name_key"] = normalize_name(left["companyname"])
        right["_name_key"] = normalize_name(right["companyname"])
        joined = left.merge(right, on="_name_key", how="left", suffixes=("_deal", "_company"))
        return joined

    return relevant_deals.copy()


def generate_readme(base_dir: Path, brief: bool = False) -> str:
    company_path = base_dir / CSV_FILE
    deal_path = base_dir / DEAL_FILE
    if not company_path.exists():
        raise FileNotFoundError(f"Company CSV not found: {company_path}")
    if not deal_path.exists():
        raise FileNotFoundError(f"Deal CSV not found: {deal_path}")

    company_df = standardize_columns(pd.read_csv(company_path))
    deal_df = standardize_columns(pd.read_csv(deal_path))

    relevant_deals, matched_cols = detect_relevant_deals(deal_df)
    joined = attach_company_info(relevant_deals, company_df)

    amount_col = first_existing(joined, ["dealsize", "totalinvestedcapital", "nativeamountofdeal"])
    date_col = first_existing(joined, ["dealdate", "announceddate", "currentregistrationdate"])
    company_col = first_existing(joined, ["companyname_deal", "companyname_company", "companyname"])
    sector_col = first_existing(joined, ["primaryindustrysector", "primaryindustrygroup"])
    stage_col = first_existing(joined, ["dealclass", "dealtype", "firstfinancingdealclass"])
    geo_col = first_existing(joined, ["hqstate_province", "hqcity", "hqcountry", "hqglobalregion", "sitelocation"])
    deal_id_col = first_existing(joined, ["dealid", "dealno"])

    if company_col is None:
        raise ValueError("Required company name column not found after join.")

    if amount_col:
        joined[amount_col] = pd.to_numeric(joined[amount_col], errors="coerce")
    if date_col:
        joined[date_col] = pd.to_datetime(joined[date_col], errors="coerce")

    valid_amount = joined.dropna(subset=[amount_col]).copy() if amount_col else joined.iloc[0:0].copy()
    total_deals = len(joined)
    total_capital = valid_amount[amount_col].sum() if amount_col else None
    avg_ticket = valid_amount[amount_col].mean() if amount_col and not valid_amount.empty else None
    med_ticket = valid_amount[amount_col].median() if amount_col and not valid_amount.empty else None
    unique_companies = joined[company_col].dropna().nunique()

    largest_name = "N/A"
    largest_amount = None
    if amount_col and not valid_amount.empty:
        idx = valid_amount[amount_col].idxmax()
        largest_name = str(valid_amount.loc[idx, company_col])
        largest_amount = valid_amount.loc[idx, amount_col]

    recent_name = "N/A"
    recent_date = "N/A"
    if date_col and joined[date_col].notna().any():
        idx = joined[date_col].idxmax()
        recent_name = str(joined.loc[idx, company_col])
        recent_date = joined.loc[idx, date_col].date().isoformat()

    top_companies = pd.DataFrame()
    top5_share = None
    if amount_col and not valid_amount.empty:
        top_companies = (
            valid_amount.groupby(company_col, as_index=False)
            .agg(capital=(amount_col, "sum"), deals=(company_col, "size"))
            .sort_values("capital", ascending=False)
        )
        top_companies["share_pct"] = top_companies["capital"] / total_capital * 100 if total_capital else 0.0
        top5_share = top_companies.head(5)["capital"].sum() / total_capital * 100 if total_capital else None

    sector_breakdown = (
        make_breakdown(valid_amount, sector_col, amount_col) if sector_col and amount_col and not valid_amount.empty else pd.DataFrame()
    )
    stage_breakdown = (
        make_breakdown(valid_amount, stage_col, amount_col) if stage_col and amount_col and not valid_amount.empty else pd.DataFrame()
    )
    geo_breakdown = (
        make_breakdown(valid_amount, geo_col, amount_col) if geo_col and amount_col and not valid_amount.empty else pd.DataFrame()
    )

    yearly = pd.DataFrame()
    if date_col and amount_col and not valid_amount.empty:
        yearly = (
            valid_amount.assign(year=valid_amount[date_col].dt.year)
            .dropna(subset=["year"])
            .groupby("year", as_index=False)
            .agg(deals=("year", "size"), capital=(amount_col, "sum"))
            .sort_values("year")
        )

    largest_sector = sector_breakdown.iloc[0] if not sector_breakdown.empty else None
    largest_geo = geo_breakdown.iloc[0] if not geo_breakdown.empty else None

    unusually_large = pd.DataFrame()
    if amount_col and not valid_amount.empty and len(valid_amount) >= 4:
        q1 = valid_amount[amount_col].quantile(0.25)
        q3 = valid_amount[amount_col].quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            unusually_large = valid_amount[valid_amount[amount_col] > (q3 + 1.5 * iqr)]

    # Co-investors inferred from deal synopsis text.
    coinvestors = pd.Series(dtype=int)
    if "dealsynopsis" in relevant_deals.columns:
        parsed = relevant_deals["dealsynopsis"].fillna("").astype(str).apply(extract_coinvestors)
        counts: dict[str, int] = {}
        for arr in parsed:
            for name in set(arr):
                counts[name] = counts.get(name, 0) + 1
        if counts:
            coinvestors = pd.Series(counts).sort_values(ascending=False)

    missing_data_rows = []
    for label, col in [
        ("Deal size", amount_col),
        ("Deal date", date_col),
        ("Sector", sector_col),
        ("Stage", stage_col),
        ("Geography", geo_col),
        ("Deal ID", deal_id_col),
    ]:
        if not col or col not in joined.columns:
            missing_data_rows.append([label, "Column not available", "Metric skipped"])
            continue
        missing_n = int(joined[col].isna().sum())
        missing_pct = (missing_n / total_deals * 100) if total_deals else 0.0
        missing_data_rows.append([label, f"{missing_n}/{total_deals} ({missing_pct:.1f}%)", "OK" if missing_n == 0 else "Partial"])

    lines: list[str] = []
    lines.append("# MEIF Relevant Deals Dashboard")
    lines.append("")
    lines.append(
        f"> Sources: `{CSV_FILE}` + `{DEAL_FILE}` | Filtered by investor names: Future Planet Capital / Midven / Midlands Engine Investment Fund (+ MEIF variations)"
    )
    lines.append("")
    lines.append(
        f"> Relevant filtered deals: **{total_deals}** (matched using columns: {', '.join(matched_cols) if matched_cols else 'none'})"
    )
    lines.append("")
    lines.append("## Table of Contents")
    lines.append("")
    lines.append("- [1) Executive Fund Snapshot](#1-executive-fund-snapshot)")
    lines.append("- [2) Capital Allocation Breakdown](#2-capital-allocation-breakdown)")
    lines.append("- [3) Concentration and Risk Checks](#3-concentration-and-risk-checks)")
    lines.append("- [4) Practical Management Insights](#4-practical-management-insights)")
    lines.append("- [5) Data Quality and Coverage](#5-data-quality-and-coverage)")
    lines.append("- [Rebuild](#rebuild)")
    lines.append("- [Data Cleaning & Filtering Workflow (Audit Trail)](#data-cleaning--filtering-workflow-audit-trail)")
    lines.append("")
    lines.append("## 1) Executive Fund Snapshot")
    lines.append("")
    lines.append(
        md_table(
            ["Metric", "Value"],
            [
                ["Total relevant deals", str(total_deals)],
                ["Total invested capital", fmt_num(total_capital) if amount_col else "N/A"],
                ["Number of portfolio companies", str(unique_companies)],
                ["Average deal size", fmt_num(avg_ticket) if amount_col else "N/A"],
                ["Median deal size", fmt_num(med_ticket) if amount_col else "N/A"],
                ["Largest investment", f"{largest_name} ({fmt_num(largest_amount)})"],
                ["Most recent investment", f"{recent_name} ({recent_date})" if date_col else "N/A"],
            ],
        )
    )
    lines.append("")
    lines.append("Focus: only deal activity tied to target investors/funds for day-to-day monitoring.")
    lines.append("")

    lines.append("## 2) Capital Allocation Breakdown")
    lines.append("")
    lines.append("### Top Companies by Invested Amount")
    top_n = 3 if brief else 5
    lines.append(
        md_table(
            ["Company", "Capital", "Share of Total"],
            [
                [row[company_col], fmt_num(row["capital"]), f"{row['share_pct']:.1f}%"]
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
                ["Year", "# Deals", "Capital"],
                [
                    [str(int(r["year"])), str(int(r["deals"])), fmt_num(r["capital"])]
                    for _, r in yearly.iterrows()
                ],
            )
        )
        lines.append("")
        lines.append(mermaid_bar_year(yearly, amount_col))
        lines.append("Tracks deployment pace and vintage clustering.")
        lines.append("")

    if not coinvestors.empty:
        lines.append("### Top Co-Investors (in filtered deals)")
        rows = [[name, int(cnt)] for name, cnt in coinvestors.head(8).items()]
        lines.append(md_table(["Co-investor", "# Deals"], rows))
        lines.append("")

    lines.append("## 3) Concentration and Risk Checks")
    lines.append("")
    risk_rows = [
        ["Top 5 companies as % of total capital", f"{top5_share:.1f}%" if top5_share is not None else "N/A"],
        [
            "Largest sector exposure",
            f"{largest_sector['bucket']} ({largest_sector['share_pct']:.1f}%)" if largest_sector is not None else "N/A",
        ],
        [
            "Largest geography exposure",
            f"{largest_geo['bucket']} ({largest_geo['share_pct']:.1f}%)" if largest_geo is not None else "N/A",
        ],
        [
            "Unusually large deals (IQR rule)",
            ", ".join(
                f"{r[company_col]} ({fmt_num(r[amount_col])})" for _, r in unusually_large[[company_col, amount_col]].iterrows()
            )
            or "None flagged / insufficient data",
        ],
    ]
    lines.append(md_table(["Check", "Result"], risk_rows))
    lines.append("")

    lines.append("## 4) Practical Management Insights")
    lines.append("")
    insights: list[str] = []
    if top5_share is not None and top5_share >= 75:
        insights.append(
            f"- Capital concentration is high: top 5 companies represent **{top5_share:.1f}%** of tracked capital."
        )
    if largest_sector is not None and largest_sector["share_pct"] >= 50:
        insights.append(
            f"- Sector exposure is skewed to **{largest_sector['bucket']}** at **{largest_sector['share_pct']:.1f}%**."
        )
    if largest_geo is not None and largest_geo["share_pct"] >= 70:
        insights.append(
            f"- Geographic exposure is concentrated in **{largest_geo['bucket']}** ({largest_geo['share_pct']:.1f}%)."
        )
    if amount_col and int(joined[amount_col].isna().sum()) > 0:
        insights.append("- Some filtered deals have missing deal size; this reduces capital-based comparability.")
    if date_col and not yearly.empty and len(yearly) > 1:
        peak_year = int(yearly.loc[yearly["capital"].idxmax(), "year"])
        insights.append(f"- Deployment is concentrated by vintage; peak year is **{peak_year}**.")
    if coinvestors.empty:
        insights.append("- Co-investor ranking is limited because investor-name columns are sparse; synopsis parsing only gives partial coverage.")
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
    lines.append("## 5) Data Quality and Coverage")
    lines.append("")
    lines.append(md_table(["Field", "Missing", "Status"], missing_data_rows))
    lines.append("")
    lines.append("## Rebuild")
    lines.append("")
    lines.append("Run `python generate_dashboard.py` for full dashboard, or `python generate_dashboard.py --brief` for one-page mode.")
    lines.append("")
    lines.append("## Data Cleaning & Filtering Workflow (Audit Trail)")
    lines.append("")
    lines.append("### Step 1: Load and standardise both datasets")
    lines.append(
        md_table(
            ["Step 1 Item", "Details"],
            [
                ["Input", f"`{CSV_FILE}` and `{DEAL_FILE}` raw CSV exports"],
                ["Processing", "Standardize headers to lowercase `snake_case`; trim text; normalize key text fields (company, investor/fund, sector, stage, geography); parse date and deal-size fields with safe coercion"],
                ["Output", "Schema-consistent company-level and deal-level dataframes ready for filtering and join"],
                ["Impact on metrics", "Prevents casing/spacing mismatches and reduces parsing errors in date, amount, and grouping calculations"],
            ],
        )
    )
    lines.append("")
    lines.append("### Step 2: Identify relevant MEIF-related deals")
    lines.append(
        md_table(
            ["Step 2 Item", "Details"],
            [
                ["Input", "Standardized deal-level dataframe"],
                ["Processing", "Case-insensitive keyword matching across investor/fund-related text fields for `Future Planet Capital`, `Midven`, `Midlands Engine Investment Fund`, plus `MEIF` / `Midlands Engine` variations; drop non-matching rows; deduplicate repeated deal records where applicable"],
                ["Output", "Filtered relevant-deals dataframe containing only target-fund-linked transactions"],
                ["Impact on metrics", "Ensures all dashboard KPIs exclude unrelated investors/funds and reflect MEIF-relevant activity only"],
            ],
        )
    )
    lines.append("")
    lines.append("### Step 3: Join filtered deals to company-level information")
    lines.append(
        md_table(
            ["Step 3 Item", "Details"],
            [
                ["Input", "Filtered relevant-deals dataframe + standardized company-level dataframe"],
                ["Processing", "Join keys applied in priority order: `companyid` (preferred), then fallback to cleaned company-name matching when IDs are unavailable"],
                ["Output", "Final analytics dataset used for all summary metrics, breakdowns, concentration checks, and insights"],
                ["Impact on metrics", "Links deal activity to sector/stage/geography/company attributes and prevents leakage from unfiltered company universe"],
            ],
        )
    )
    lines.append("")
    lines.append("```mermaid")
    lines.append("flowchart LR")
    lines.append("    A[Load company-level investment file] --> C[Standardise and clean fields]")
    lines.append("    B[Load deal information file] --> C")
    lines.append("    C --> D[Filter for Future Planet Capital / Midven / MEIF deals]")
    lines.append("    D --> E[Join filtered deals to company-level data]")
    lines.append("    E --> F[Generate investor dashboard metrics]")
    lines.append("    F --> G[Update README dashboard]")
    lines.append("```")
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
