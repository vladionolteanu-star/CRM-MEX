"""
Script pentru importul datelor complete (master + istoric) în PostgreSQL
Include: sales_history (JSONB) și sales_last_3m pentru trend analysis

Rulează cu: python scripts/import_full_data.py
"""
import pandas as pd
from sqlalchemy import create_engine, text
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

# ============================================================
# CONFIGURARE CONEXIUNE PostgreSQL
# ============================================================
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "indomex_aprovizionare",
    "user": "postgres",
    "password": "123"
}

DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

# ============================================================
# FISIERE
# ============================================================
MASTER_CSV = "data/Tcioara Forecast_.csv"
HISTORY_FILES = [
    "data/2019_2021.csv",
    "data/2022_2024.csv",
    "data/2025.csv"
]

# Filtru pentru vânzări (doar Client Final, nu B2B)
CLIENT_FILTER = "Vanzari Magazin_Client Final"

# ============================================================
# MAPPING COLOANE MASTER -> SQL
# ============================================================
COLUMN_MAPPING = {
    'COD ARTICOL': 'cod_articol',
    'DENUMIRE ARTICOL': 'denumire',
    'FURNIZOR EXT': 'furnizor',
    'CLASA DENUMIRE': 'clasa',
    'SUBCLASA DENUMIRE': 'subclasa',
    'STARE PM': 'stare_pm',
    # CORECTIE: Stoc Furnizor = Stoc Indomex, Stoc Magazine = stoc pe raft
    'Stoc Disponibil Cantitativ Furnizor': 'stoc_total',
    'CAFE cantitativ nereceptionat Furnizor': 'stoc_tranzit',
    'Stoc Disponibil Cantitativ Magazine': 'stoc_magazine',
    'Vanzari Cantitative Magazine_client final ult. 4 Luni': 'vanzari_4luni',
    'Vanzari Cantitative Magazine 360z (client final)': 'vanzari_360z',
    'Vanzari Cantitative Magazine 2024 (client final)': 'vanzari_2024',
    'Vanzari Cantitative Magazine 2025 (client final)': 'vanzari_2025',
    'Vanzari Cantitative Furnizor 360z catre M16': 'vanzari_m16',
    'Cost Achizitie Furnizor (ultimul NIR_cronologic)': 'cost_achizitie',
    'Pret Vanzare cu TVA (magazin _client final)': 'pret_vanzare',
    'Pret de Catalog cu TVA': 'pret_catalog',
    # Store Stocks
    'Stoc Disponibil Cantitativ Baneasa': 'stoc_baneasa',
    'Stoc Disponibil Cantitativ Pipera': 'stoc_pipera',
    'Stoc Disponibil Cantitativ Militari': 'stoc_militari',
    'Stoc Disponibil Cantitativ Pantelimon': 'stoc_pantelimon',
    'Stoc Disponibil Cantitativ Iasi': 'stoc_iasi',
    'Stoc Disponibil Cantitativ Brasov': 'stoc_brasov',
    'Stoc Disponibil Cantitativ Pitesti': 'stoc_pitesti',
    'Stoc Disponibil Cantitativ Sibiu': 'stoc_sibiu',
    'Stoc Disponibil Cantitativ Oradea': 'stoc_oradea',
    'Stoc Disponibil Cantitativ Constanta': 'stoc_constanta',
    'Stoc Disponibil Cantitativ Constanta Outlet': 'stoc_outlet_constanta',
    'Stoc Disponibil Cantitativ Pipera Outlet': 'stoc_outlet_pipera',
    'Vanzari Cantitative Furnizor 360z exclus M16': 'vanzari_fara_m16',
}


def load_supplier_config():
    """Load supplier config for lead_time, safety_stock, moq"""
    config_path = "data/supplier_config.json"
    default_cfg = {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1}
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {"default": default_cfg}


def load_master_data():
    """Load master product data from CSV"""
    print(f"\n[1/5] Incarc master data: {MASTER_CSV}")
    df = pd.read_csv(MASTER_CSV, low_memory=False)
    print(f"      {len(df):,} produse incarcate")
    return df


def load_historical_data():
    """Load and concatenate historical sales data"""
    print(f"\n[2/5] Incarc date istorice...")
    
    all_dfs = []
    for fpath in HISTORY_FILES:
        if os.path.exists(fpath):
            print(f"      Loading: {fpath}")
            df = pd.read_csv(fpath, low_memory=False)
            all_dfs.append(df)
            print(f"      -> {len(df):,} rows")
        else:
            print(f"      SKIP (nu exista): {fpath}")
    
    if not all_dfs:
        print("      ATENTIE: Nu s-au gasit fisiere istorice!")
        return pd.DataFrame()
    
    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"      TOTAL istoric: {len(combined):,} rows")
    return combined


def aggregate_monthly_sales(df_history):
    """
    Aggregate sales by COD ARTICOL and month.
    Filter only for Client Final sales.
    """
    print(f"\n[3/5] Agregare vanzari lunare (filtru: {CLIENT_FILTER})...")
    
    if df_history.empty:
        return {}
    
    # Filter by client type
    if 'CLIENT SPECIFIC' in df_history.columns:
        df_filtered = df_history[df_history['CLIENT SPECIFIC'] == CLIENT_FILTER].copy()
        print(f"      Dupa filtru Client Final: {len(df_filtered):,} rows")
    else:
        print("      ATENTIE: Coloana 'CLIENT SPECIFIC' nu exista, folosesc tot")
        df_filtered = df_history.copy()
    
    if df_filtered.empty:
        print("      ATENTIE: Nu sunt date dupa filtrare!")
        return {}
    
    # Parse date - column is 'DATA'
    if 'DATA' in df_filtered.columns:
        df_filtered['date_parsed'] = pd.to_datetime(df_filtered['DATA'], errors='coerce')
    else:
        print("      EROARE: Coloana 'DATA' nu exista!")
        return {}
    
    # Extract YYYY-MM
    df_filtered['year_month'] = df_filtered['date_parsed'].dt.strftime('%Y-%m')
    
    # Aggregate: sum CANTITATE FACTURATA per COD ARTICOL + year_month
    qty_col = 'CANTITATE FACTURATA'
    if qty_col not in df_filtered.columns:
        print(f"      EROARE: Coloana '{qty_col}' nu exista!")
        return {}
    
    agg = df_filtered.groupby(['COD ARTICOL', 'year_month'])[qty_col].sum().reset_index()
    agg.rename(columns={qty_col: 'qty'}, inplace=True)
    
    # Build dict: {cod_articol: {"2024-10": 50, "2024-11": 45, ...}}
    sales_history = {}
    for _, row in agg.iterrows():
        cod = str(row['COD ARTICOL'])
        ym = row['year_month']
        qty = float(row['qty'])
        
        if cod not in sales_history:
            sales_history[cod] = {}
        sales_history[cod][ym] = qty
    
    print(f"      Produse cu istoric: {len(sales_history):,}")
    
    # Sample output
    sample_codes = list(sales_history.keys())[:3]
    for code in sample_codes:
        months = list(sales_history[code].keys())[-3:]
        print(f"      Sample {code}: ultimele luni = {months}")
    
    return sales_history


def calculate_sales_last_3m(sales_history):
    """
    Calculate sum of last 3 complete months sales for each product.
    Uses current date to determine which months are "complete".
    """
    print(f"\n[4/5] Calculez sales_last_3m...")
    
    today = datetime.now()
    # Last 3 COMPLETE months (exclude current month)
    complete_months = []
    for i in range(1, 4):
        m = today - relativedelta(months=i)
        complete_months.append(m.strftime('%Y-%m'))
    
    print(f"      Luni complete considerate: {complete_months}")
    
    sales_3m = {}
    for cod, history in sales_history.items():
        total = sum(history.get(m, 0) for m in complete_months)
        sales_3m[cod] = total
    
    # Stats
    non_zero = sum(1 for v in sales_3m.values() if v > 0)
    print(f"      Produse cu sales_3m > 0: {non_zero:,}")
    
    return sales_3m


def import_to_postgres(df_master, sales_history, sales_3m, supplier_config):
    """Import merged data to PostgreSQL"""
    print(f"\n[5/5] Import in PostgreSQL...")
    
    # Select and rename columns from master
    available_cols = [col for col in COLUMN_MAPPING.keys() if col in df_master.columns]
    df = df_master[available_cols].copy()
    df.rename(columns=COLUMN_MAPPING, inplace=True)
    
    # Clean data
    for col in df.select_dtypes(include=['float64', 'int64']).columns:
        df[col] = df[col].fillna(0)
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].fillna('')
    
    # Remove duplicates
    df = df.drop_duplicates(subset=['cod_articol'], keep='first')
    print(f"      Produse unice: {len(df):,}")
    
    # Add sales_history (JSON string) and sales_last_3m
    default_cfg = supplier_config.get("default", {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1})
    
    def get_sales_history_json(cod):
        h = sales_history.get(str(cod), {})
        return json.dumps(h) if h else '{}'
    
    def get_sales_3m(cod):
        return sales_3m.get(str(cod), 0.0)
    
    def get_supplier_param(row, param, default_val):
        furn = str(row.get('furnizor', ''))
        cfg = supplier_config.get(furn, default_cfg)
        return cfg.get(param, default_val)
    
    df['sales_history'] = df['cod_articol'].apply(get_sales_history_json)
    df['sales_last_3m'] = df['cod_articol'].apply(get_sales_3m)
    
    # Add supplier config columns
    df['lead_time_days'] = df.apply(lambda r: get_supplier_param(r, 'lead_time_days', 30), axis=1)
    df['safety_stock_days'] = df.apply(lambda r: get_supplier_param(r, 'safety_stock_days', 7), axis=1)
    df['moq'] = df.apply(lambda r: get_supplier_param(r, 'moq', 1), axis=1)
    
    # Stats
    has_history = df[df['sales_history'] != '{}'].shape[0]
    has_3m = df[df['sales_last_3m'] > 0].shape[0]
    print(f"      Cu sales_history: {has_history:,}")
    print(f"      Cu sales_last_3m > 0: {has_3m:,}")
    
    # Connect and import
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Test connection
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"      Conectat: {version[:50]}...")
            
            # Import (replace table)
            print(f"      Se importa {len(df):,} produse (DROP & CREATE)...")
            df.to_sql('products', engine, if_exists='replace', index=False, method='multi', chunksize=1000)
            
            # Verify
            result = conn.execute(text("SELECT COUNT(*) FROM products"))
            count = result.fetchone()[0]
            
            # Verify sales_history column type and content
            result2 = conn.execute(text("""
                SELECT cod_articol, sales_history, sales_last_3m 
                FROM products 
                WHERE sales_history != '{}' 
                LIMIT 3
            """))
            samples = result2.fetchall()
            
            print(f"\n      SUCCES! {count:,} produse in baza de date.")
            print(f"\n      Sample cu istoric:")
            for s in samples:
                h = json.loads(s[1]) if s[1] else {}
                months = list(h.keys())[-3:] if h else []
                print(f"        {s[0]}: 3m={s[2]}, luni={months}")
                
    except Exception as e:
        print(f"\n      EROARE: {e}")
        return False
    
    return True


def main():
    print("=" * 60)
    print("IMPORT COMPLET: Master Data + Istoric Vanzari")
    print("=" * 60)
    
    # Load configs
    supplier_config = load_supplier_config()
    
    # Step 1: Load master
    df_master = load_master_data()
    
    # Step 2: Load history
    df_history = load_historical_data()
    
    # Step 3: Aggregate monthly
    sales_history = aggregate_monthly_sales(df_history)
    
    # Step 4: Calculate last 3 months
    sales_3m = calculate_sales_last_3m(sales_history)
    
    # Step 5: Import
    success = import_to_postgres(df_master, sales_history, sales_3m, supplier_config)
    
    if success:
        print("\n" + "=" * 60)
        print("IMPORT COMPLET!")
        print("Acum poti rula: streamlit run src/ui/app.py")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("IMPORT ESUAT - Verifica erorile de mai sus")
        print("=" * 60)


if __name__ == "__main__":
    main()
