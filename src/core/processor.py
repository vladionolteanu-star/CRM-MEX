import pandas as pd
import numpy as np
import json
from src.models.product import extract_family_dimension, DIMENSION_COEFFICIENTS

def process_products_vectorized(df: pd.DataFrame, config: dict, seasonality_data: dict = None, advanced_trends_data: dict = None, cubaj_data: dict = None) -> pd.DataFrame:
    """
    Process product DataFrame using vectorized operations (High Performance).
    Replaces the slow Pydantic generic parsing loop.
    
    Args:
        df: Raw DataFrame from SQL (columns: cod_articol, denumire, furnizor, stoc_total, etc.)
        config: Supplier configuration dict
        seasonality_data: Dict mapping cod_articol -> seasonality info
        advanced_trends_data: Dict mapping cod_articol -> trends info
        
    Returns:
        DataFrame with added calculated columns, ready for display.
    """
    if df.empty:
        return df

    # 1. Standardize Columns (ensure numeric types)
    numeric_cols = [
        "stoc_total", "stoc_tranzit", "stoc_magazin_total", 
        "vanzari_4luni", "vanzari_360z", "vanzari_2024", "vanzari_2025",
        "cost_achizitie", "pret_vanzare", "sales_last_3m",
        "stoc_baneasa", "stoc_pipera", "stoc_militari", "stoc_pantelimon",
        "stoc_iasi", "stoc_brasov", "stoc_pitesti", "stoc_sibiu", 
        "stoc_oradea", "stoc_constanta", "stoc_outlet_constanta", "stoc_outlet_pipera",
        "lead_time_days", "safety_stock_days", "moq", "days_of_coverage"
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 2. Extract Family/Dimension (Vectorized Apply - string ops are fast enough for 5k rows)
    # Cache extraction to avoid re-regexing
    def get_fam_dim(name):
        return extract_family_dimension(str(name))
        
    fam_dim = df["denumire"].apply(get_fam_dim)
    df["familie"] = fam_dim.apply(lambda x: x[0])
    df["dimensiune"] = fam_dim.apply(lambda x: x[1])
    
    # 3. Dimension Coefficients (Vectorized map)
    # Extract width from 080x150 -> 080
    df["width"] = df["dimensiune"].astype(str).str.split('x').str[0]
    df["dimension_coefficient"] = df["width"].map(DIMENSION_COEFFICIENTS).fillna(1.0)
    
    # 4. Supplier Parameters (Broadcast default if missing)
    default_cfg = config.get("default", {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1})
    
    # If columns missing in SQL result, fill them from config (simplified logic: assumes 1 supplier usually per view, or we map)
    # Since we can have mixed suppliers in "ALL", we should rely on SQL columns 'lead_time_days' etc which come from DB products table.
    # The DB columns are authoritative as per sync_supplier_to_db.
    
    # 5. Calculate Metrics
    
    # Avg Daily Sales
    # If 4 months > 0, use 4 months / 120. Else 360 days / 360.
    df["avg_daily_sales"] = np.where(
        df["vanzari_4luni"] > 0,
        df["vanzari_4luni"] / 120.0,
        np.where(
            df["vanzari_360z"] > 0,
            df["vanzari_360z"] / 360.0,
            0.0
        )
    )
    
    # Days of Coverage (Recalculate to be sure)
    df["total_stock"] = df["stoc_total"] + df["stoc_tranzit"]
    # Avoid div/0
    df["days_of_coverage"] = np.where(
        df["avg_daily_sales"] > 0,
        df["total_stock"] / df["avg_daily_sales"],
        999.0
    )
    # If total_stock <= 0 and sales <= 0 -> 0 coverage? No, DB logic says 999 or 0 if sales > 0.
    # Let's align with Product model: if sales <= 0: return 999 if stock > 0 else 0
    df["days_of_coverage"] = np.where(
        df["avg_daily_sales"] <= 0,
        np.where(df["total_stock"] > 0, 999.0, 0.0),
        df["days_of_coverage"]
    )
    
    # 6. Seasonality & Trends Integration
    # Map from seasonality_data dict
    if seasonality_data:
        # Create series from dict
        season_index_map = {k: v.get("seasonality_index", 1.0) for k, v in seasonality_data.items()}
        rising_star_map = {k: v.get("is_rising_star", False) for k, v in seasonality_data.items()}
        trend_map = {k: v.get("trend", "STABLE") for k, v in seasonality_data.items()}
        
        df["seasonality_index"] = df["cod_articol"].map(season_index_map).fillna(1.0)
        df["is_rising_star"] = df["cod_articol"].map(rising_star_map).fillna(False)
        df["trend_label"] = df["cod_articol"].map(trend_map).fillna("STABLE")
    else:
        df["seasonality_index"] = 1.0
        df["is_rising_star"] = False
        df["trend_label"] = "STABLE"

    # Map from advanced_trends_data
    if advanced_trends_data:
        yoy_map = {k: v.get("yoy_growth", 0.0) for k, v in advanced_trends_data.items()}
        vol_map = {k: v.get("volatility", 1.0) for k, v in advanced_trends_data.items()}
        
        df["yoy_growth"] = df["cod_articol"].map(yoy_map).fillna(0.0)
        df["volatility"] = df["cod_articol"].map(vol_map).fillna(1.0)
    else:
        df["yoy_growth"] = 0.0
        df["volatility"] = 1.0

    # 6.5 Cubaj & Logistics
    if cubaj_data:
        cubaj_map = {k: v.get("cubaj_m3") for k, v in cubaj_data.items()}
        masa_map = {k: v.get("masa_kg") for k, v in cubaj_data.items()}
        product_url_map = {k: v.get("product_url") for k, v in cubaj_data.items()}
        
        df["cubaj_m3"] = df["cod_articol"].map(cubaj_map).where(pd.notnull(df["cod_articol"].map(cubaj_map)), None)
        df["masa_kg"] = df["cod_articol"].map(masa_map).where(pd.notnull(df["cod_articol"].map(masa_map)), None)
        df["product_url"] = df["cod_articol"].map(product_url_map).where(pd.notnull(df["cod_articol"].map(product_url_map)), None)
        df["image_url"] = None  # Will be lazy-fetched from product_url
    else:
        df["cubaj_m3"] = None
        df["masa_kg"] = None
        df["product_url"] = None
        df["image_url"] = None

    # 7. Suggested Order Quantity (Simplified Formula - Matching Order Builder)
    # Formula: Need = (AvgDaily * (Lead + Frequency + Safety)) - TotalStock
    
    # 1. Constants matching Order Builder defaults
    review_period_days = 30.0  # Equivalent to 'sim_freq' = 30
    
    # 2. Target Days
    # Note: We use raw safety_stock_days without dimension coefficient to match Builder
    # If Builder uses raw, we use raw. If Builder uses coeff, we use coeff.
    # Builder code: df_calc["safety_stock_days"]. It comes from DB/Config.
    # Processor used: df["safety_stock_days"] * df["dimension_coefficient"].
    # We will stick to the simplest interpretation of "Same as Builder": Raw.
    target_days = df["lead_time_days"] + review_period_days + df["safety_stock_days"]
    
    # 3. Target Quantity
    # Builder: df_calc["sim_avg_daily"] * df_calc["target_days"]
    # We ignore seasonality here to match Builder simulation default (sim_factor=1.0)
    # BUT App usually wants seasonality?
    # User said "formula in builder sa fie peste tot". Builder defaults to sim_factor=1.0.
    # So we use raw avg_daily_sales.
    target_qty = df["avg_daily_sales"] * target_days
    
    # 4. Net Need
    net_needed = target_qty - df["total_stock"]
    
    # Ensure non-negative
    raw_qty = np.maximum(0, net_needed)
    
    # 5. MOQ Rounding
    df["suggested_qty"] = np.where(
        df["moq"] > 1,
        np.maximum(df["moq"], np.ceil(raw_qty / df["moq"]) * df["moq"]),
        np.round(raw_qty, 0)
    )
    
    # 6. Dead Stock Rule
    # If sales_360z < 3 -> 0 (simplified)
    # Builder logic: dead_mask = df_calc["vanzari_360z"] < 3 -> 0.
    is_dead = df["vanzari_360z"] < 3
    df["suggested_qty"] = np.where(is_dead, 0.0, df["suggested_qty"])
    
    # Final clamp to 0 if sales=0
    df["suggested_qty"] = np.where(df["avg_daily_sales"] <= 0, 0.0, df["suggested_qty"])

    # 8. Mapped Columns for UI (Compatible with render_interactive_table expectations)
    df["nr_art"] = df["cod_articol"]
    df["nume_produs"] = df["denumire"]
    df["stoc_indomex"] = df["stoc_total"] 
    df["stoc_magazin_total"] = df["stoc_magazine"]

    # Pydantic Compatibility Aliases
    col_map = {
        "vanzari_ultimele_4_luni": "vanzari_4luni",
        "vanzari_ultimele_360_zile": "vanzari_360z",
        "stoc_disponibil_total": "stoc_total",
        "stoc_in_tranzit": "stoc_tranzit",
        "suggested_order_qty": "suggested_qty"
    }
    
    for target, source in col_map.items():
        if source in df.columns:
            df[target] = df[source]
        else:
            df[target] = 0.0
    
    # Ensure sales_history is dict
    def parse_hist(x):
        if isinstance(x, str):
            try: return json.loads(x)
            except: return {}
        return x if isinstance(x, dict) else {}
        
    if "sales_history" in df.columns:
         df["sales_history"] = df["sales_history"].apply(parse_hist)
    else:
         df["sales_history"] = [{} for _ in range(len(df))]
    
    return df
