"""
Generates a synthetic, intentionally messy quantitative finance dataset.

Problems injected:
  - Duplicate rows
  - Missing values in numerical columns (price, volume, returns, market_cap, beta, pe_ratio)
  - Missing values in categorical columns (sector, rating)
  - Outliers (extreme price spikes, negative volume, absurd PE ratios)
  - A datetime column (trade_timestamp) for datetime extraction demo
  - Mixed-type categorical columns for encoding demo
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
N = 600

TICKERS   = ["AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA", "JPM", "GS", "BAC"]
SECTORS   = ["Technology", "Finance", "Consumer", "Energy", "Healthcare"]
RATINGS   = ["Buy", "Hold", "Sell"]
START_DATE = pd.Timestamp("2023-01-01")

def inject_nulls(arr, frac=0.08):
    mask = RNG.random(len(arr)) < frac
    arr = arr.astype(float)
    arr[mask] = np.nan
    return arr

def inject_outliers(arr, n=8, scale=15):
    arr = arr.copy()
    idx = RNG.choice(len(arr), n, replace=False)
    arr[idx] = arr[idx] * scale * RNG.choice([-1, 1], n)
    return arr


def build_raw_dataset() -> pd.DataFrame:
    tickers = RNG.choice(TICKERS, N)
    sectors = RNG.choice(SECTORS, N)
    ratings = RNG.choice(RATINGS, N)

    base_prices  = RNG.uniform(50, 500, N)
    volumes      = RNG.integers(100_000, 10_000_000, N).astype(float)
    returns      = RNG.normal(0.001, 0.025, N)
    market_caps  = base_prices * volumes * RNG.uniform(0.8, 1.2, N) / 1e6
    beta_vals    = RNG.normal(1.0, 0.4, N)
    pe_ratios    = RNG.uniform(5, 50, N)

    # datetime: one timestamp per row, spread over ~2 years
    seconds_range = int(pd.Timedelta("730 days").total_seconds())
    timestamps = [
        START_DATE + pd.Timedelta(seconds=int(s))
        for s in RNG.integers(0, seconds_range, N)
    ]

    df = pd.DataFrame({
        "trade_timestamp": timestamps,
        "ticker":          tickers,
        "sector":          sectors,
        "price":           base_prices,
        "volume":          volumes,
        "daily_return":    returns,
        "market_cap_M":    market_caps,
        "beta":            beta_vals,
        "pe_ratio":        pe_ratios,
        "analyst_rating":  ratings,
    })

    # --- inject problems ---

    # 1. duplicate rows (~3 %)
    dup_idx = RNG.choice(N, int(N * 0.03), replace=False)
    df = pd.concat([df, df.iloc[dup_idx]], ignore_index=True)

    # 2. numerical NaNs
    for col, frac in [("price", 0.06), ("volume", 0.05), ("daily_return", 0.07),
                      ("market_cap_M", 0.09), ("beta", 0.08), ("pe_ratio", 0.06)]:
        df[col] = inject_nulls(df[col].values, frac)

    # 3. categorical NaNs
    for col, frac in [("sector", 0.05), ("analyst_rating", 0.07)]:
        mask = RNG.random(len(df)) < frac
        df.loc[mask, col] = np.nan

    # 4. numerical outliers
    df["price"]    = inject_outliers(df["price"].values,    n=10, scale=20)
    df["volume"]   = inject_outliers(df["volume"].values,   n=8,  scale=30)
    df["pe_ratio"] = inject_outliers(df["pe_ratio"].values, n=6,  scale=50)

    # 5. a few completely blank rows to stress-test
    blank_idx = RNG.choice(len(df), 4, replace=False)
    df.loc[blank_idx, ["price", "volume", "daily_return", "market_cap_M"]] = np.nan

    df = df.sample(frac=1, random_state=0).reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = build_raw_dataset()
    out_path = "raw_quant_dataset.csv"
    df.to_csv(out_path, index=False)

    print(f"Dataset saved → {out_path}")
    print(f"Shape          : {df.shape}")
    print(f"Duplicates     : {df.duplicated().sum()}")
    print(f"\nMissing values per column:")
    print(df.isnull().sum().to_string())
    print(f"\nData types:")
    print(df.dtypes.to_string())
    print(f"\nBasic stats (numerics):")
    print(df.describe().round(2).to_string())
