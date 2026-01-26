"""
Compute Seasonality Index and Rising Stars from Historical Data.

This script loads historical sales data, filters by Client Final,
and calculates:
1. Seasonality Index per product (upcoming months vs average)
2. Rising Stars (consistent >10% YoY growth for 3 years)
3. Hot/Cold classification

Output: data/seasonality_index.json
"""

import pandas as pd
import json
from datetime import datetime
from pathlib import Path

# Configuration
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "seasonality_index.json"
CLIENT_FILTER = "Vanzari Magazin_Client Final"

# Current month for seasonality calculation
CURRENT_MONTH = datetime.now().month
CURRENT_YEAR = datetime.now().year


def load_historical_data():
    """Load and concatenate all historical CSV files."""
    files = [
        DATA_DIR / "2019_2021.csv",
        DATA_DIR / "2022_2024.csv",
        DATA_DIR / "2025.csv"
    ]
    
    dfs = []
    for f in files:
        if f.exists():
            print(f"Loading {f.name}...")
            df = pd.read_csv(f, low_memory=False)
            dfs.append(df)
            print(f"  -> {len(df):,} rows")
    
    if not dfs:
        raise FileNotFoundError("No historical CSV files found in data/")
    
    combined = pd.concat(dfs, ignore_index=True)
    print(f"Total combined: {len(combined):,} rows")
    return combined


def filter_client_final(df):
    """Keep only Client Final sales."""
    if "CLIENT SPECIFIC" not in df.columns:
        print("WARNING: 'CLIENT SPECIFIC' column not found. Skipping filter.")
        return df
    
    before = len(df)
    df = df[df["CLIENT SPECIFIC"] == CLIENT_FILTER].copy()
    after = len(df)
    print(f"Filtered Client Final: {before:,} -> {after:,} rows ({after/before*100:.1f}%)")
    return df


def parse_dates(df):
    """Convert DATA column to datetime and extract month/year."""
    if "DATA" not in df.columns:
        raise ValueError("'DATA' column not found")
    
    # Try DD.MM.YYYY format
    df["DATA_DT"] = pd.to_datetime(df["DATA"], format="%d.%m.%Y", errors="coerce")
    df["MONTH"] = df["DATA_DT"].dt.month
    df["YEAR"] = df["DATA_DT"].dt.year
    
    valid = df["DATA_DT"].notna().sum()
    print(f"Parsed dates: {valid:,} valid out of {len(df):,}")
    return df


def compute_seasonality_index(df):
    """
    Calculate seasonality index per product.
    
    Seasonality Index = (Avg sales in upcoming 3 months historically) / (Overall monthly avg)
    
    > 1.0 = Peak season coming
    < 1.0 = Off-season coming
    """
    # Get upcoming 3 months
    upcoming_months = [(CURRENT_MONTH + i - 1) % 12 + 1 for i in range(1, 4)]
    print(f"Upcoming months for seasonality: {upcoming_months}")
    
    # Group by product and month
    monthly = df.groupby(["COD ARTICOL", "MONTH"])["CANTITATE FACTURATA"].sum().reset_index()
    
    # Calculate average per month per product
    monthly_avg = monthly.groupby("COD ARTICOL")["CANTITATE FACTURATA"].mean()
    
    # Calculate average for upcoming months
    upcoming_sales = monthly[monthly["MONTH"].isin(upcoming_months)]
    upcoming_avg = upcoming_sales.groupby("COD ARTICOL")["CANTITATE FACTURATA"].mean()
    
    # Seasonality index
    seasonality = (upcoming_avg / monthly_avg).fillna(1.0)
    seasonality = seasonality.clip(0.5, 2.0)  # Cap extremes
    
    return seasonality.to_dict()


def compute_rising_stars(df):
    """
    Identify Rising Stars: products with >10% growth in each of last 3 years.
    
    Returns dict: {cod_articol: True/False}
    """
    years = [2022, 2023, 2024]
    
    # Get yearly sales
    yearly = df[df["YEAR"].isin(years)].groupby(["COD ARTICOL", "YEAR"])["CANTITATE FACTURATA"].sum().unstack(fill_value=0)
    
    rising_stars = {}
    for cod in yearly.index:
        try:
            sales_2022 = yearly.loc[cod, 2022] if 2022 in yearly.columns else 0
            sales_2023 = yearly.loc[cod, 2023] if 2023 in yearly.columns else 0
            sales_2024 = yearly.loc[cod, 2024] if 2024 in yearly.columns else 0
            
            # Check consistent growth >10%
            growth_23 = (sales_2023 - sales_2022) / sales_2022 if sales_2022 > 0 else 0
            growth_24 = (sales_2024 - sales_2023) / sales_2023 if sales_2023 > 0 else 0
            
            is_rising = growth_23 > 0.10 and growth_24 > 0.10 and sales_2024 >= 10
            rising_stars[cod] = is_rising
        except:
            rising_stars[cod] = False
    
    count = sum(rising_stars.values())
    print(f"Rising Stars identified: {count} products")
    return rising_stars


def compute_hot_cold(df):
    """
    Hot/Cold classification based on recent trend.
    
    FIXED: Now requires minimum volume to classify (avoid false positives)
    Compares last 4 months vs same period last year.
    
    Returns dict: {cod_articol: "HOT" | "COLD" | "STABLE"}
    """
    # Minimum volume to classify (avoid +200% on 1 sale)
    MIN_VOLUME_FOR_TREND = 5  # Need at least 5 units in current or previous period
    
    # Get current period (last 4 months)
    current_year = CURRENT_YEAR
    current_months = [(CURRENT_MONTH - i - 1) % 12 + 1 for i in range(4)]
    
    # This year's sales
    this_year = df[(df["YEAR"] == current_year) & (df["MONTH"].isin(current_months))]
    this_year_sales = this_year.groupby("COD ARTICOL")["CANTITATE FACTURATA"].sum()
    
    # Last year same months
    last_year = df[(df["YEAR"] == current_year - 1) & (df["MONTH"].isin(current_months))]
    last_year_sales = last_year.groupby("COD ARTICOL")["CANTITATE FACTURATA"].sum()
    
    # Calculate trend
    hot_cold = {}
    all_products = set(this_year_sales.index) | set(last_year_sales.index)
    
    for cod in all_products:
        current = this_year_sales.get(cod, 0)
        previous = last_year_sales.get(cod, 0)
        
        # FIXED: Require minimum volume to classify as HOT/COLD
        max_volume = max(current, previous)
        if max_volume < MIN_VOLUME_FOR_TREND:
            # Low volume = STABLE (can't trust trend on small numbers)
            hot_cold[cod] = "STABLE"
            continue
        
        if previous == 0:
            # New product with decent volume
            hot_cold[cod] = "HOT" if current >= 10 else "STABLE"
        elif current == 0:
            # FIXED: Product that stopped selling is COLD, not ignored
            hot_cold[cod] = "COLD"
        else:
            change = (current - previous) / previous
            if change > 0.20:
                hot_cold[cod] = "HOT"
            elif change < -0.20:
                hot_cold[cod] = "COLD"
            else:
                hot_cold[cod] = "STABLE"
    
    hot_count = sum(1 for v in hot_cold.values() if v == "HOT")
    cold_count = sum(1 for v in hot_cold.values() if v == "COLD")
    print(f"Hot/Cold: {hot_count} HOT, {cold_count} COLD, {len(hot_cold) - hot_count - cold_count} STABLE")
    
    return hot_cold


def main():
    print("=" * 60)
    print("COMPUTE SEASONALITY INDEX & RISING STARS")
    print("=" * 60)
    
    # Load data
    df = load_historical_data()
    
    # Filter
    df = filter_client_final(df)
    
    # Parse dates
    df = parse_dates(df)
    
    # Compute indices
    print("\nCalculating seasonality index...")
    seasonality = compute_seasonality_index(df)
    
    print("\nIdentifying Rising Stars...")
    rising_stars = compute_rising_stars(df)
    
    print("\nClassifying Hot/Cold...")
    hot_cold = compute_hot_cold(df)
    
    # Combine results
    all_products = set(seasonality.keys()) | set(rising_stars.keys()) | set(hot_cold.keys())
    result = {}
    
    for cod in all_products:
        result[cod] = {
            "seasonality_index": round(float(seasonality.get(cod, 1.0)), 2),
            "is_rising_star": bool(rising_stars.get(cod, False)),
            "trend": str(hot_cold.get(cod, "STABLE"))
        }
    
    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved to {OUTPUT_FILE}")
    print(f"Total products indexed: {len(result):,}")
    
    # Sample output
    print("\nSample output (first 5):")
    for i, (k, v) in enumerate(list(result.items())[:5]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
