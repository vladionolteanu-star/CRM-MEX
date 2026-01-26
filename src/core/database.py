"""
Database connection and query module for PostgreSQL
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
import os
import streamlit as st

# ============================================================
# DATABASE CONFIGURATION
# ============================================================
DB_CONFIG_PATH = "data/db_config.json"

DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "indomex_aprovizionare",
    "user": "postgres",
    "password": "123"
}

def get_db_config():
    """Load database configuration from file or return defaults"""
    import json
    if os.path.exists(DB_CONFIG_PATH):
        with open(DB_CONFIG_PATH, 'r') as f:
            return json.load(f)
    return DEFAULT_DB_CONFIG

def save_db_config(config):
    """Save database configuration to file"""
    import json
    with open(DB_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def get_connection_string():
    """Build PostgreSQL connection string"""
    # DEBUG: Visual feedback
    try:
        # Check Env Var
        env_conn = os.getenv("DB_CONNECTION_STRING")
        if env_conn:
            # st.sidebar.success("✅ Found Env Var connection")
            return env_conn

        # Check Secrets
        if "DB_CONNECTION_STRING" in st.secrets:
            # st.sidebar.success("✅ Found Streamlit Secret connection")
            return st.secrets["DB_CONNECTION_STRING"]
        else:
            st.sidebar.warning("⚠️ No 'DB_CONNECTION_STRING' found in Secrets!")
            st.sidebar.info(f"Available secrets keys: {list(st.secrets.keys())}")
            
    except Exception as e:
        st.sidebar.error(f"⚠️ Error reading secrets: {e}")
        
    # 3. Fallback to Local Config (Localhost)
    st.sidebar.warning("⚠️ Falling back to Localhost (Default)")
    cfg = get_db_config()
    return f"postgresql://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['database']}"

def get_engine():
    """Create SQLAlchemy engine with connection pooling"""
    return create_engine(
        get_connection_string(),
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True  # Validates connections before use
    )

# ============================================================
# QUERY FUNCTIONS
# ============================================================

def load_products_from_db(furnizor=None, stare_pm=None, limit=None, offset=0, order_by="cod_articol", order_dir="ASC"):
    """
    Load products from PostgreSQL database
    
    Args:
        furnizor: Filter by supplier (None = all)
        stare_pm: Filter by PM status (None = all)
        limit: Max rows to return (None = all)
        offset: Starting row for pagination (default 0)
        order_by: Column to sort by (default cod_articol)
        order_dir: Sort direction ASC or DESC (default ASC)
    
    Returns:
        pandas DataFrame with product data
    """
    # Whitelist of allowed columns for ORDER BY (security)
    allowed_columns = [
        "cod_articol", "denumire", "furnizor", "stoc_total", "stoc_tranzit", 
        "stoc_magazine", "vanzari_4luni", "vanzari_360z", "vanzari_2024", 
        "vanzari_2025", "cost_achizitie", "pret_vanzare", "days_of_coverage",
        "avg_daily_sales", "segment"
    ]
    
    if order_by not in allowed_columns:
        order_by = "cod_articol"
    if order_dir not in ["ASC", "DESC"]:
        order_dir = "ASC"
    
    query = """
        SELECT 
            cod_articol,
            denumire,
            furnizor,
            clasa,
            subclasa,
            stare_pm,
            stoc_total,
            stoc_tranzit,
            stoc_magazine,
            stoc_baneasa,
            stoc_pipera,
            stoc_militari,
            stoc_pantelimon,
            stoc_iasi,
            stoc_brasov,
            stoc_pitesti,
            stoc_sibiu,
            stoc_oradea,
            stoc_constanta,
            stoc_outlet_constanta,
            stoc_outlet_pipera,
            vanzari_4luni,
            vanzari_360z,
            vanzari_2024,
            vanzari_2025,
            vanzari_m16,
            vanzari_fara_m16,
            cost_achizitie,
            pret_vanzare,
            pret_catalog,
            lead_time_days,
            safety_stock_days,
            moq,
            sales_history,
            sales_last_3m
        FROM products
        WHERE 1=1
    """
    params = {}
    
    if furnizor and furnizor != "ALL":
        query += " AND furnizor = :furnizor"
        params["furnizor"] = furnizor
    
    if stare_pm and stare_pm != "ALL":
        query += " AND stare_pm = :stare_pm"
        params["stare_pm"] = stare_pm
    
    query += f" ORDER BY {order_by} {order_dir}"
    
    if limit:
        query += f" LIMIT {int(limit)} OFFSET {int(offset)}"
    
    engine = get_engine()
    return pd.read_sql(text(query), engine, params=params)

def get_unique_suppliers():
    """Get list of unique suppliers from database"""
    engine = get_engine()
    query = "SELECT DISTINCT furnizor FROM products WHERE furnizor IS NOT NULL AND furnizor != '' ORDER BY furnizor"
    df = pd.read_sql(text(query), engine)
    return df["furnizor"].tolist()


@st.cache_data(ttl=300)  # Cache 5 minute
def get_supplier_priority_list() -> list:
    """
    Get list of suppliers sorted by urgency with segment counts.
    Uses EXISTING segment logic from precompute_segments.py.
    
    Returns:
        List of dicts sorted by priority (CRITICAL first):
        [{
            "furnizor": str,
            "critical_count": int,
            "urgent_count": int,
            "attention_count": int
        }]
    """
    engine = get_engine()
    
    query = """
        SELECT 
            furnizor,
            SUM(CASE WHEN segment = 'CRITICAL' THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN segment = 'URGENT' THEN 1 ELSE 0 END) as urgent_count,
            SUM(CASE WHEN segment = 'ATTENTION' THEN 1 ELSE 0 END) as attention_count
        FROM products
        WHERE furnizor IS NOT NULL AND furnizor != ''
        GROUP BY furnizor
        ORDER BY 
            SUM(CASE WHEN segment = 'CRITICAL' THEN 1 ELSE 0 END) DESC,
            SUM(CASE WHEN segment = 'URGENT' THEN 1 ELSE 0 END) DESC,
            SUM(CASE WHEN segment = 'ATTENTION' THEN 1 ELSE 0 END) DESC,
            furnizor ASC
    """
    
    df = pd.read_sql(text(query), engine)
    
    result = []
    for _, row in df.iterrows():
        result.append({
            "furnizor": row["furnizor"],
            "critical_count": int(row["critical_count"]),
            "urgent_count": int(row["urgent_count"]),
            "attention_count": int(row["attention_count"])
        })
    
    return result


def get_unique_statuses():
    """Get list of unique PM statuses from database"""
    engine = get_engine()
    query = "SELECT DISTINCT stare_pm FROM products WHERE stare_pm IS NOT NULL ORDER BY stare_pm"
    df = pd.read_sql(text(query), engine)
    return df["stare_pm"].tolist()

def get_product_count():
    """Get total product count"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM products"))
        return result.fetchone()[0]

def test_connection():
    """Test database connection, returns (success, message)"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM products"))
            count = result.fetchone()[0]
            return True, f"✅ Conectat! {count:,} produse în baza de date."
    except Exception as e:
        return False, f"❌ Eroare conexiune: {str(e)}"

def get_unique_families():
    """Get list of unique families from database"""
    engine = get_engine()
    # Extract unique families (assuming format 'COVOR NOMAD ...')
    # This is simplified - in reality we might need regex if family isn't a column
    # But since we don't have a 'familie' column in DB yet (it was computed in Python),
    # we might need to rely on 'denumire' parsing in SQL or Python.
    # For now, let's try to extract from 'denumire' if we can, or just return empty if needed.
    # Actually, the user script precompute_segments.py did NOT add 'familie' column.
    
    # Let's extract distinct first word after 'COVOR '
    query = """
        SELECT DISTINCT substring(denumire from 'COVOR ([^ ]+)') as fam
        FROM products 
        WHERE denumire LIKE 'COVOR %'
        ORDER BY fam
    """
    try:
        df = pd.read_sql(text(query), engine)
        return sorted([f for f in df["fam"].tolist() if f])
    except:
        return []

def load_family_products_from_db(family_name):
    """Load all products for a specific family"""
    engine = get_engine()
    # Load products where denumire contains family name
    query = """
        SELECT * FROM products 
        WHERE denumire LIKE :pattern
    """
    params = {"pattern": f"%{family_name}%"}
    return pd.read_sql(text(query), engine, params=params)

# ============================================================
# OPTIMIZED SEGMENT FUNCTIONS (pre-computed in DB)
# ============================================================

def get_segment_counts(furnizor=None, stare_pm=None):
    """Get product counts per segment - INSTANT"""
    engine = get_engine()
    
    query = """
        SELECT segment, COUNT(*) as cnt, 
               SUM(cost_achizitie * stoc_total) as value
        FROM products 
        WHERE segment IS NOT NULL
    """
    params = {}
    
    if furnizor and furnizor != "ALL":
        query += " AND furnizor = :furnizor"
        params["furnizor"] = furnizor
    
    if stare_pm and stare_pm != "ALL":
        query += " AND stare_pm = :stare_pm"
        params["stare_pm"] = stare_pm
    
    query += " GROUP BY segment ORDER BY segment"
    
    df = pd.read_sql(text(query), engine, params=params)
    
    # Convert to dict
    result = {}
    for _, row in df.iterrows():
        result[row["segment"]] = {
            "count": int(row["cnt"]),
            "value": float(row["value"] or 0)
        }
    return result

def load_segment_from_db(segment, furnizor=None, stare_pm=None, limit=500, offset=0):
    """
    Load products for a specific segment with pagination - FAST!
    
    Args:
        segment: CRITICAL, URGENT, ATTENTION, OK, OVERSTOCK
        furnizor: Filter by supplier (None = all)
        stare_pm: Filter by PM status (None = all)
        limit: Max rows per page (default 500)
        offset: Starting row for pagination
    
    Returns:
        pandas DataFrame with product data
    """
    query = """
        SELECT 
            cod_articol,
            denumire,
            furnizor,
            clasa,
            subclasa,
            stare_pm,
            stoc_total,
            stoc_tranzit,
            stoc_magazine,
            stoc_baneasa,
            stoc_pipera,
            stoc_militari,
            stoc_pantelimon,
            stoc_iasi,
            stoc_brasov,
            stoc_pitesti,
            stoc_sibiu,
            stoc_oradea,
            stoc_constanta,
            stoc_outlet_constanta,
            stoc_outlet_pipera,
            vanzari_4luni,
            vanzari_360z,
            vanzari_2024,
            vanzari_2025,
            vanzari_m16,
            vanzari_fara_m16,
            cost_achizitie,
            pret_vanzare,
            pret_catalog,
            lead_time_days,
            safety_stock_days,
            moq,
            avg_daily_sales,
            days_of_coverage,
            segment,
            sales_history,
            sales_last_3m
        FROM products
        WHERE segment = :segment
    """
    params = {"segment": segment}
    
    if furnizor and furnizor != "ALL":
        query += " AND furnizor = :furnizor"
        params["furnizor"] = furnizor
    
    if stare_pm and stare_pm != "ALL":
        query += " AND stare_pm = :stare_pm"
        params["stare_pm"] = stare_pm
    
    # Order by urgency (days_of_coverage ascending for CRITICAL/URGENT)
    if segment in ['CRITICAL', 'URGENT']:
        query += " ORDER BY days_of_coverage ASC"
    else:
        query += " ORDER BY cost_achizitie * stoc_total DESC"  # By value
    
    query += f" LIMIT {int(limit)} OFFSET {int(offset)}"
    
    engine = get_engine()
    return pd.read_sql(text(query), engine, params=params)

# ============================================================
# SUBCLASS ORDER BUILDER FUNCTIONS
# ============================================================

def get_unique_subclasses(furnizor: str = None) -> list:
    """
    Get list of unique subclasses, optionally filtered by supplier.
    
    Args:
        furnizor: Filter by supplier (None = all)
    
    Returns:
        List of subclass names
    """
    engine = get_engine()
    query = """
        SELECT DISTINCT subclasa 
        FROM products 
        WHERE subclasa IS NOT NULL AND subclasa != ''
    """
    params = {}
    
    if furnizor:
        query += " AND furnizor = :furnizor"
        params["furnizor"] = furnizor
    
    query += " ORDER BY subclasa"
    
    df = pd.read_sql(text(query), engine, params=params)
    return df["subclasa"].tolist()


@st.cache_data(ttl=300)  # Cache 5 minute
def get_subclass_summary(furnizor: str) -> list:
    """
    Get summary statistics per subclass for a supplier.
    Used for Order Builder subclass cards.
    
    Args:
        furnizor: Supplier name
    
    Returns:
        List of dicts with subclass summary:
        [{
            "subclasa": str,
            "article_count": int,
            "critical_count": int,
            "urgent_count": int,
            "attention_count": int,
            "total_value": float,
            "urgency_score": float
        }]
    """
    engine = get_engine()
    query = """
        SELECT 
            subclasa,
            COUNT(*) as article_count,
            SUM(CASE WHEN segment = 'CRITICAL' THEN 1 ELSE 0 END) as critical_count,
            SUM(CASE WHEN segment = 'URGENT' THEN 1 ELSE 0 END) as urgent_count,
            SUM(CASE WHEN segment = 'ATTENTION' THEN 1 ELSE 0 END) as attention_count,
            SUM(COALESCE(cost_achizitie, 0) * COALESCE(stoc_total, 0)) as total_value,
            -- Urgency score: CRITICAL=100, URGENT=50, ATTENTION=10 per article
            SUM(
                CASE WHEN segment = 'CRITICAL' THEN 100 
                     WHEN segment = 'URGENT' THEN 50 
                     WHEN segment = 'ATTENTION' THEN 10 
                     ELSE 0 END
            ) as urgency_score
        FROM products
        WHERE furnizor = :furnizor
          AND subclasa IS NOT NULL 
          AND subclasa != ''
        GROUP BY subclasa
        ORDER BY urgency_score DESC, subclasa
    """
    
    df = pd.read_sql(text(query), engine, params={"furnizor": furnizor})
    
    result = []
    for _, row in df.iterrows():
        result.append({
            "subclasa": row["subclasa"],
            "article_count": int(row["article_count"]),
            "critical_count": int(row["critical_count"]),
            "urgent_count": int(row["urgent_count"]),
            "attention_count": int(row["attention_count"]),
            "total_value": float(row["total_value"] or 0),
            "urgency_score": float(row["urgency_score"] or 0)
        })
    
    return result


@st.cache_data(ttl=300)  # Cache 5 minute
def load_subclass_products(furnizor: str, subclasa: str, limit: int = None, offset: int = 0) -> pd.DataFrame:
    """
    Load all products for a specific supplier + subclass combination.
    Returns full product data for Order Builder table.
    
    Args:
        furnizor: Supplier name
        subclasa: Subclass name
        limit: Optional limit for pagination
        offset: Offset for pagination (default 0)
    
    Returns:
        DataFrame with all product columns
    """
    query = """
        SELECT 
            cod_articol,
            denumire,
            furnizor,
            clasa,
            subclasa,
            stare_pm,
            stoc_total,
            stoc_tranzit,
            stoc_magazine,
            stoc_baneasa,
            stoc_pipera,
            stoc_militari,
            stoc_pantelimon,
            stoc_iasi,
            stoc_brasov,
            stoc_pitesti,
            stoc_sibiu,
            stoc_oradea,
            stoc_constanta,
            stoc_outlet_constanta,
            stoc_outlet_pipera,
            vanzari_4luni,
            vanzari_360z,
            vanzari_2024,
            vanzari_2025,
            vanzari_m16,
            vanzari_fara_m16,
            cost_achizitie,
            pret_vanzare,
            pret_catalog,
            lead_time_days,
            safety_stock_days,
            moq,
            avg_daily_sales,
            days_of_coverage,
            segment,
            suggested_qty,
            sales_history,
            sales_last_3m
        FROM products
        WHERE furnizor = :furnizor 
          AND subclasa = :subclasa
        ORDER BY 
            CASE segment 
                WHEN 'CRITICAL' THEN 1 
                WHEN 'URGENT' THEN 2 
                WHEN 'ATTENTION' THEN 3 
                WHEN 'OK' THEN 4 
                ELSE 5 
            END,
            days_of_coverage ASC
    """
    
    # Add pagination if limit specified
    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"
    
    engine = get_engine()
    return pd.read_sql(text(query), engine, params={"furnizor": furnizor, "subclasa": subclasa})

