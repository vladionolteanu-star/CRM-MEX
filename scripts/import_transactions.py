"""
Script pentru importul tranzactiilor zilnice în PostgreSQL.
Creează tabelul sales_transactions pentru query-uri pe intervale personalizate.

Rulează cu: python scripts/import_transactions.py
"""
import pandas as pd
from sqlalchemy import create_engine, text
import os
import sys

sys.path.append('.')
from src.core.database import get_connection_string

# ============================================================
# CONFIGURARE
# ============================================================
DATABASE_URL = get_connection_string()

HISTORY_FILES = [
    "data/2019_2021.csv",
    "data/2022_2024.csv",
    "data/2025.csv"
]

CLIENT_FILTER = "Vanzari Magazin_Client Final"


def create_transactions_table(engine):
    """Create sales_transactions table with indexes"""
    print("[1/3] Creez tabelul sales_transactions...")
    
    with engine.connect() as conn:
        # Drop if exists
        conn.execute(text("DROP TABLE IF EXISTS sales_transactions"))
        conn.commit()
        
        # Create table
        conn.execute(text("""
            CREATE TABLE sales_transactions (
                id SERIAL PRIMARY KEY,
                cod_articol VARCHAR(50) NOT NULL,
                data DATE NOT NULL,
                cantitate DECIMAL(10,2) DEFAULT 0,
                valoare DECIMAL(12,2) DEFAULT 0
            )
        """))
        conn.commit()
        
        # Create indexes for fast queries
        conn.execute(text("CREATE INDEX idx_trans_date ON sales_transactions(data)"))
        conn.execute(text("CREATE INDEX idx_trans_cod ON sales_transactions(cod_articol)"))
        conn.execute(text("CREATE INDEX idx_trans_cod_date ON sales_transactions(cod_articol, data)"))
        conn.commit()
        
    print("      ✅ Tabel creat cu indexuri")


def load_and_import_transactions(engine):
    """Load CSVs and import daily transactions"""
    print("[2/3] Încarc și import tranzacțiile zilnice...")
    
    all_dfs = []
    for fpath in HISTORY_FILES:
        if os.path.exists(fpath):
            print(f"      Loading: {fpath}")
            df = pd.read_csv(fpath, low_memory=False)
            all_dfs.append(df)
            print(f"      -> {len(df):,} rows")
        else:
            print(f"      SKIP: {fpath}")
    
    if not all_dfs:
        print("      ❌ Nu s-au găsit fișiere!")
        return 0
    
    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"      TOTAL brut: {len(combined):,} rows")
    
    # Filter by client type
    if 'CLIENT SPECIFIC' in combined.columns:
        df_filtered = combined[combined['CLIENT SPECIFIC'] == CLIENT_FILTER].copy()
        print(f"      După filtru Client Final: {len(df_filtered):,} rows")
    else:
        df_filtered = combined.copy()
    
    # Parse date
    df_filtered['data'] = pd.to_datetime(df_filtered['DATA'], errors='coerce', dayfirst=True)
    df_filtered = df_filtered.dropna(subset=['data'])
    
    # Prepare columns for insert
    df_insert = pd.DataFrame({
        'cod_articol': df_filtered['COD ARTICOL'].astype(str),
        'data': df_filtered['data'].dt.date,
        'cantitate': pd.to_numeric(df_filtered['CANTITATE FACTURATA'], errors='coerce').fillna(0),
        'valoare': pd.to_numeric(df_filtered['VALOARE FACTURATA'], errors='coerce').fillna(0)
    })
    
    # Aggregate duplicates (same product, same day)
    df_agg = df_insert.groupby(['cod_articol', 'data']).agg({
        'cantitate': 'sum',
        'valoare': 'sum'
    }).reset_index()
    
    print(f"      După agregare: {len(df_agg):,} rows unice (produs + zi)")
    
    # Insert in chunks
    print("[3/3] Import în PostgreSQL...")
    df_agg.to_sql('sales_transactions', engine, if_exists='append', index=False, 
                  method='multi', chunksize=5000)
    
    return len(df_agg)


def verify_import(engine):
    """Verify import and show stats"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM sales_transactions"))
        count = result.fetchone()[0]
        
        result2 = conn.execute(text("""
            SELECT MIN(data) as min_date, MAX(data) as max_date, 
                   COUNT(DISTINCT cod_articol) as products
            FROM sales_transactions
        """))
        stats = result2.fetchone()
        
        print(f"\n      ✅ IMPORT COMPLET!")
        print(f"      Total tranzacții: {count:,}")
        print(f"      Interval: {stats[0]} -> {stats[1]}")
        print(f"      Produse unice: {stats[2]:,}")
        
        # Sample query test
        result3 = conn.execute(text("""
            SELECT cod_articol, SUM(cantitate) as qty
            FROM sales_transactions
            WHERE data BETWEEN '2025-01-01' AND '2025-01-31'
            GROUP BY cod_articol
            ORDER BY qty DESC
            LIMIT 5
        """))
        samples = result3.fetchall()
        print(f"\n      Top 5 produse (Ian 2025):")
        for s in samples:
            print(f"        {s[0]}: {s[1]} buc")


def main():
    print("=" * 60)
    print("IMPORT TRANZACȚII ZILNICE (pentru Calendar Feature)")
    print("=" * 60)
    
    engine = create_engine(DATABASE_URL)
    
    create_transactions_table(engine)
    count = load_and_import_transactions(engine)
    
    if count > 0:
        verify_import(engine)
        print("\n" + "=" * 60)
        print("GATA! Acum poți folosi Calendar Feature în aplicație.")
        print("=" * 60)
    else:
        print("\n❌ Import eșuat!")


if __name__ == "__main__":
    main()
