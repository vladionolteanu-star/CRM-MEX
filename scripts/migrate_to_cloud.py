"""
Script INTERACTIV pentru migrarea datelor locale în Cloud (Supabase/PostgreSQL).
Rulează acest script pentru a popula baza de date din Cloud.

Usage:
    python scripts/migrate_to_cloud.py
"""
import os
import sys
import time

# Adaugă root-ul proiectului în path pentru a putea importa modulele
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

def main():
    print("\n" + "="*60)
    print("☁️  MIGRARE DATE CĂTRE CLOUD (SUPABASE) ")
    print("="*60)
    print("Acest script va:")
    print("1. Seta conexiunea către baza ta de date din Cloud")
    print("2. Importa produsele și istoricul vânzărilor (din CSV-urile locale)")
    print("3. Calcula segmentele și sugestiile de stoc pe server")
    print("-" * 60)

    # 1. Get Connection String
    print("\n[PASUL 1] Introdu Connection String-ul de la Supabase.")
    print("   (Format: postgresql://postgres.xxxx:[PAROLA]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres)")
    
    conn_str = input("\n🔗 Paste Connection String aici: ").strip()
    
    if not conn_str:
        print("❌ Nu ai introdus nimic. Anulare.")
        return
        
    if "postgres" not in conn_str or "@" not in conn_str:
        print("⚠️  ATENȚIE: Link-ul nu pare valid. Ar trebui să conțină 'postgres' și '@'.")
        confirm = input("Ești sigur că e corect? (da/nu): ").lower()
        if confirm != "da":
            return

    # Set Environment Variable for child scripts
    os.environ["DB_CONNECTION_STRING"] = conn_str
    
    # Test Connection first
    print("\n⏳ Testez conexiunea...")
    try:
        engine = create_engine(conn_str)
        with engine.connect() as conn:
            res = conn.execute(text("SELECT version()"))
            ver = res.fetchone()[0]
            print(f"✅ CONECTAT CU SUCCES!\n   Versiune: {ver[:50]}...")
    except Exception as e:
        print(f"\n❌ EROARE CONEXIUNE: {e}")
        print("Verifică parola și dacă ai selectat 'Direct Connection' sau 'Transaction Pooler' (ambele merg, dar parola trebuie să fie corectă).")
        return

    # 2. Run Import
    print("\n" + "="*30)
    print("[PASUL 2] Încep Importul de Date...")
    print("="*30)
    time.sleep(1)
    
    try:
        import scripts.import_full_data as importer
        importer.main()
    except Exception as e:
        print(f"❌ EROARE LA IMPORT: {e}")
        return

    # 3. Run Precompute
    print("\n" + "="*30)
    print("[PASUL 3] Calcul Segmente & Sugestii...")
    print("="*30)
    time.sleep(1)

    try:
        import scripts.precompute_segments as seg
        seg.add_segment_column()
    except Exception as e:
        print(f"❌ EROARE LA CALCUL SEGMENTE: {e}")
        return

    print("\n" + "="*60)
    print("✅✅ MIGRARE COMPLETĂ! ✅✅")
    print("Datele sunt acum pe Cloud.")
    print("="*60)
    print("\nUrmătorul pas: Deploy la aplicația Streamlit și setează variabila DB_CONNECTION_STRING acolo.")

if __name__ == "__main__":
    main()
