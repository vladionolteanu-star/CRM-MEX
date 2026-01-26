"""
Compute Advanced Trends from Historical Data.

Uses date-level and client-level data to calculate refined metrics:
1. YoY Growth (same months comparison)
2. Quarterly Acceleration (Q4/Q3)
3. Volatility (CV of monthly sales)
4. Client Mix (new vs repeat)
5. Monthly Profile (seasonality pattern per product)

Output: data/advanced_trends.json
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime

# Configuration
DATA_DIR = Path("data")
OUTPUT_FILE = DATA_DIR / "advanced_trends.json"
CLIENT_FILTER = "Vanzari Magazin_Client Final"

# Current context
CURRENT_MONTH = datetime.now().month
CURRENT_YEAR = datetime.now().year


def load_and_prepare_data():
    """Load all CSVs and prepare for analysis."""
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
    
    combined = pd.concat(dfs, ignore_index=True)
    
    # Filter Client Final
    if "CLIENT SPECIFIC" in combined.columns:
        combined = combined[combined["CLIENT SPECIFIC"] == CLIENT_FILTER].copy()
    
    # Parse dates
    combined["DATA_DT"] = pd.to_datetime(combined["DATA"], format="%d.%m.%Y", errors="coerce")
    combined["MONTH"] = combined["DATA_DT"].dt.month
    combined["YEAR"] = combined["DATA_DT"].dt.year
    combined["QUARTER"] = combined["DATA_DT"].dt.quarter
    
    # Convert quantities
    combined["CANTITATE FACTURATA"] = pd.to_numeric(combined["CANTITATE FACTURATA"], errors="coerce").fillna(0)
    
    print(f"Total rows after filter: {len(combined):,}")
    return combined


def compute_yoy_growth(df):
    """
    Year-over-Year growth comparing same months.
    
    Compares current year's months (so far) vs same months last year.
    """
    print("\n=== YoY Growth ===")
    
    # Get this year and last year data
    this_year = df[df["YEAR"] == CURRENT_YEAR]
    last_year = df[df["YEAR"] == CURRENT_YEAR - 1]
    
    # Only compare months that exist in current year
    months_this_year = this_year["MONTH"].unique()
    
    this_year_sales = this_year.groupby("COD ARTICOL")["CANTITATE FACTURATA"].sum()
    last_year_same_months = last_year[last_year["MONTH"].isin(months_this_year)]
    last_year_sales = last_year_same_months.groupby("COD ARTICOL")["CANTITATE FACTURATA"].sum()
    
    # Calculate YoY
    yoy = {}
    all_products = set(this_year_sales.index) | set(last_year_sales.index)
    
    for cod in all_products:
        current = this_year_sales.get(cod, 0)
        previous = last_year_sales.get(cod, 0)
        
        if previous > 0:
            yoy[cod] = round((current - previous) / previous * 100, 1)
        elif current > 0:
            yoy[cod] = 100.0  # New product
        else:
            yoy[cod] = 0.0
    
    print(f"Calculated YoY for {len(yoy):,} products")
    return yoy


def compute_acceleration(df):
    """
    Quarterly acceleration: Q4 vs Q3 (or last 3 months vs previous 3).
    
    Shows if product is accelerating or decelerating.
    """
    print("\n=== Acceleration ===")
    
    # Get last 6 months of data
    recent = df[df["YEAR"] >= CURRENT_YEAR - 1].copy()
    
    # Last 3 months vs previous 3 months
    recent["MONTH_KEY"] = recent["YEAR"] * 12 + recent["MONTH"]
    max_month_key = recent["MONTH_KEY"].max()
    
    last_3m = recent[recent["MONTH_KEY"] > max_month_key - 3]
    prev_3m = recent[(recent["MONTH_KEY"] <= max_month_key - 3) & (recent["MONTH_KEY"] > max_month_key - 6)]
    
    last_3m_sales = last_3m.groupby("COD ARTICOL")["CANTITATE FACTURATA"].sum()
    prev_3m_sales = prev_3m.groupby("COD ARTICOL")["CANTITATE FACTURATA"].sum()
    
    acceleration = {}
    all_products = set(last_3m_sales.index) | set(prev_3m_sales.index)
    
    for cod in all_products:
        current = last_3m_sales.get(cod, 0)
        previous = prev_3m_sales.get(cod, 0)
        
        if previous > 0:
            accel = (current - previous) / previous * 100
            acceleration[cod] = round(accel, 1)
        elif current > 0:
            acceleration[cod] = 100.0
        else:
            acceleration[cod] = 0.0
    
    accelerating = sum(1 for v in acceleration.values() if v > 10)
    decelerating = sum(1 for v in acceleration.values() if v < -10)
    print(f"Accelerating (>10%): {accelerating}, Decelerating (<-10%): {decelerating}")
    
    return acceleration


def compute_volatility(df):
    """
    Coefficient of Variation of monthly sales.
    
    CV = StdDev / Mean
    Low CV = stable/predictable, High CV = volatile/risky
    """
    print("\n=== Volatility ===")
    
    # Monthly sales per product
    monthly = df.groupby(["COD ARTICOL", "YEAR", "MONTH"])["CANTITATE FACTURATA"].sum().reset_index()
    
    # Calculate CV per product
    volatility = {}
    for cod, group in monthly.groupby("COD ARTICOL"):
        if len(group) >= 3:  # Need at least 3 months
            mean = group["CANTITATE FACTURATA"].mean()
            std = group["CANTITATE FACTURATA"].std()
            if mean > 0:
                cv = std / mean
                volatility[cod] = round(cv, 2)
            else:
                volatility[cod] = 0.0
        else:
            volatility[cod] = 1.0  # Not enough data = high uncertainty
    
    stable = sum(1 for v in volatility.values() if v < 0.5)
    volatile = sum(1 for v in volatility.values() if v > 1.0)
    print(f"Stable (CV<0.5): {stable}, Volatile (CV>1.0): {volatile}")
    
    return volatility


def compute_client_mix(df):
    """
    Analyze client patterns per product.
    
    - repeat_rate: % of clients who bought multiple times
    - avg_orders_per_client: loyalty indicator
    """
    print("\n=== Client Mix ===")
    
    # Count orders per client per product
    client_orders = df.groupby(["COD ARTICOL", "ID CLIENT"]).size().reset_index(name="orders")
    
    client_mix = {}
    for cod, group in client_orders.groupby("COD ARTICOL"):
        total_clients = len(group)
        repeat_clients = (group["orders"] > 1).sum()
        
        if total_clients > 0:
            repeat_rate = repeat_clients / total_clients * 100
            avg_orders = group["orders"].mean()
            client_mix[cod] = {
                "repeat_rate": round(repeat_rate, 1),
                "avg_orders": round(avg_orders, 2),
                "unique_clients": total_clients
            }
        else:
            client_mix[cod] = {"repeat_rate": 0, "avg_orders": 0, "unique_clients": 0}
    
    print(f"Analyzed client patterns for {len(client_mix):,} products")
    return client_mix


def compute_monthly_profile(df):
    """
    Product-specific seasonality pattern.
    
    Which months does THIS product sell best?
    """
    print("\n=== Monthly Profile ===")
    
    monthly = df.groupby(["COD ARTICOL", "MONTH"])["CANTITATE FACTURATA"].sum().reset_index()
    
    profiles = {}
    for cod, group in monthly.groupby("COD ARTICOL"):
        if len(group) >= 3:
            # Find peak month
            peak_month = group.loc[group["CANTITATE FACTURATA"].idxmax(), "MONTH"]
            
            # Calculate % in peak
            total = group["CANTITATE FACTURATA"].sum()
            peak_sales = group[group["MONTH"] == peak_month]["CANTITATE FACTURATA"].sum()
            peak_pct = peak_sales / total * 100 if total > 0 else 0
            
            profiles[cod] = {
                "peak_month": int(peak_month),
                "peak_pct": round(peak_pct, 1)
            }
        else:
            profiles[cod] = {"peak_month": 0, "peak_pct": 0}
    
    return profiles


def main():
    print("=" * 60)
    print("COMPUTE ADVANCED TRENDS")
    print("=" * 60)
    
    df = load_and_prepare_data()
    
    yoy = compute_yoy_growth(df)
    acceleration = compute_acceleration(df)
    volatility = compute_volatility(df)
    client_mix = compute_client_mix(df)
    monthly_profile = compute_monthly_profile(df)
    
    # Combine all metrics
    all_products = set(yoy.keys()) | set(acceleration.keys()) | set(volatility.keys())
    
    result = {}
    for cod in all_products:
        cm = client_mix.get(cod, {"repeat_rate": 0, "avg_orders": 0, "unique_clients": 0})
        mp = monthly_profile.get(cod, {"peak_month": 0, "peak_pct": 0})
        
        result[cod] = {
            "yoy_growth": float(yoy.get(cod, 0.0)),
            "acceleration": float(acceleration.get(cod, 0.0)),
            "volatility": float(volatility.get(cod, 1.0)),
            "repeat_rate": float(cm["repeat_rate"]),
            "avg_orders_per_client": float(cm["avg_orders"]),
            "unique_clients": int(cm["unique_clients"]),
            "peak_month": int(mp["peak_month"]),
            "peak_month_pct": float(mp["peak_pct"])
        }
    
    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved to {OUTPUT_FILE}")
    print(f"Total products: {len(result):,}")
    
    # Sample
    print("\nSample output (first 3):")
    for i, (k, v) in enumerate(list(result.items())[:3]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
