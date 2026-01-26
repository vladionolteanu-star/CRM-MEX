"""
Script pentru importul datelor din CSV în PostgreSQL
Rulează o singură dată pentru a popula baza de date
"""
import pandas as pd
from sqlalchemy import create_engine, text
import os

# ============================================================
# CONFIGURARE CONEXIUNE PostgreSQL
# ============================================================
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "indomex_aprovizionare",
    "user": "postgres",
    "password": "123"  # Schimbă dacă ai altă parolă
}

# Crează connection string
DATABASE_URL = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

# CSV path
CSV_PATH = "data/Tcioara Forecast_.csv"

# ============================================================
# MAPPING COLOANE CSV -> TABEL SQL
# ============================================================
COLUMN_MAPPING = {
    'COD ARTICOL': 'cod_articol',
    'DENUMIRE ARTICOL': 'denumire',
    'FURNIZOR EXT': 'furnizor',
    'CLASA DENUMIRE': 'clasa',
    'SUBCLASA DENUMIRE': 'subclasa',
    'STARE PM': 'stare_pm',
    'Stoc Disponibil Cantitativ Magazine Dep+Acc+Outlet': 'stoc_total',
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
    # Store Stocks - CORRECTED KEYS
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
    # Other sales
    'Vanzari Cantitative Furnizor 360z exclus M16': 'vanzari_fara_m16',
}

def import_csv_to_postgres():
    print("=" * 50)
    print("IMPORT CSV -> PostgreSQL")
    print("=" * 50)
    
    # 1. Încarcă CSV
    print(f"\n📂 Se încarcă CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    print(f"   ✓ {len(df)} rânduri încărcate")
    
    # 2. Selectează și redenumește coloanele
    print("\n🔄 Se procesează coloanele...")
    available_cols = [col for col in COLUMN_MAPPING.keys() if col in df.columns]
    df_filtered = df[available_cols].copy()
    df_filtered.rename(columns=COLUMN_MAPPING, inplace=True)
    
    # 3. Curăță datele
    print("🧹 Se curăță datele...")
    # Completează valorile lipsă
    for col in df_filtered.select_dtypes(include=['float64', 'int64']).columns:
        df_filtered[col] = df_filtered[col].fillna(0)
    for col in df_filtered.select_dtypes(include=['object']).columns:
        df_filtered[col] = df_filtered[col].fillna('')
    
    # Elimină duplicatele pe cod_articol
    df_filtered = df_filtered.drop_duplicates(subset=['cod_articol'], keep='first')
    print(f"   ✓ {len(df_filtered)} produse unice")
    
    # 4. Conectează la PostgreSQL
    print(f"\n🐘 Se conectează la PostgreSQL...")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Verifică conexiunea
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"   ✓ Conectat: {version[:50]}...")
            
            # 5. Importă datele (Recreates table with new schema)
            print(f"\n📥 Se importă {len(df_filtered)} produse (DROP & CREATE)...")
            df_filtered.to_sql('products', engine, if_exists='replace', index=False, method='multi', chunksize=1000)
            print("   ✓ Import complet!")
            
            # 7. Verifică
            result = conn.execute(text("SELECT COUNT(*) FROM products"))
            count = result.fetchone()[0]
            print(f"\n✅ SUCCES! {count} produse în baza de date.")
            
    except Exception as e:
        print(f"\n❌ EROARE: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = import_csv_to_postgres()
    if success:
        print("\n" + "=" * 50)
        print("🎉 Datele sunt acum în PostgreSQL!")
        print("   Acum poți modifica app.py să citească din DB")
        print("=" * 50)
