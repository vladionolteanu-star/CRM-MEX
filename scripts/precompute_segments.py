"""
Script pentru pre-calcularea segmentelor in PostgreSQL
Adauga coloana 'segment' si o populeaza bazat pe days_of_coverage
"""
from sqlalchemy import create_engine, text
import sys
sys.path.insert(0, '.')
from src.core.database import get_engine, get_connection_string

def add_segment_column():
    """Add segment column and calculate segments in SQL"""
    
    engine = get_engine()
    
    with engine.connect() as conn:
        print("[*] Adaugare coloana segment...")
        
        # Add segment column if not exists
        try:
            conn.execute(text("""
                ALTER TABLE products ADD COLUMN IF NOT EXISTS segment VARCHAR(20);
            """))
            conn.commit()
            print("   [OK] Coloana adaugata")
        except Exception as e:
            print(f"   Coloana exista deja sau eroare: {e}")
        
        # Add computed/config columns
        print("[*] Adaugare coloane configurare (Lead Time, Safety Stock)...")
        try:
            conn.execute(text("""
                ALTER TABLE products ADD COLUMN IF NOT EXISTS avg_daily_sales DECIMAL(10,4) DEFAULT 0;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS days_of_coverage DECIMAL(10,2) DEFAULT 999;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS lead_time_days INT DEFAULT 30;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS safety_stock_days INT DEFAULT 7;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS moq DECIMAL(10,2) DEFAULT 1;
            """))
            conn.commit()
        except Exception as e:
            print(f"   Eroare: {e}")

        # ---------------------------------------------------------
        # UPDATE FROM CONFIG
        # ---------------------------------------------------------
        print("[*] Actualizare parametri din supplier_config.json...")
        import json
        import os
        
        try:
            if os.path.exists('data/supplier_config.json'):
                with open('data/supplier_config.json', 'r') as f:
                    config = json.load(f)
                
                # 1. Globals (Default)
                defaults = config.get("default", {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1})
                conn.execute(text("""
                    UPDATE products SET 
                        lead_time_days = :lt,
                        safety_stock_days = :ss,
                        moq = :moq
                """), {
                    "lt": defaults.get("lead_time_days", 30),
                    "ss": defaults.get("safety_stock_days", 7),
                    "moq": defaults.get("moq", 1)
                })
                
                # 2. Specific Suppliers
                for supplier, params in config.items():
                    if supplier == "default": continue
                    
                    # Construct update for this supplier
                    update_parts = []
                    query_params = {"s": supplier}
                    
                    if "lead_time_days" in params:
                        update_parts.append("lead_time_days = :lt")
                        query_params["lt"] = params["lead_time_days"]
                    
                    if "safety_stock_days" in params:
                        update_parts.append("safety_stock_days = :ss")
                        query_params["ss"] = params["safety_stock_days"]
                        
                    if "moq" in params:
                        update_parts.append("moq = :moq")
                        query_params["moq"] = params["moq"]
                        
                    if update_parts:
                        sql = f"UPDATE products SET {', '.join(update_parts)} WHERE furnizor = :s"
                        conn.execute(text(sql), query_params)
                
                conn.commit()
                print("   [OK] Configuratie aplicata din JSON in DB")
            else:
                print("   [!] Nu am gasit supplier_config.json, folosesc valori default.")
        except Exception as e:
            print(f"   [X] Eroare la citirea config: {e}")
        
        # Calculate avg_daily_sales and days_of_coverage
        print("[*] Calculare medie zilnica si zile acoperire...")
        conn.execute(text("""
            UPDATE products SET 
                avg_daily_sales = COALESCE(vanzari_4luni, 0) / 120.0,
                days_of_coverage = CASE 
                    WHEN COALESCE(vanzari_4luni, 0) = 0 THEN 999
                    ELSE (COALESCE(stoc_total, 0) + COALESCE(stoc_tranzit, 0)) / (COALESCE(vanzari_4luni, 0) / 120.0)
                END
        """))
        conn.commit()
        print("   [OK] Calculat")
        
        # Update segments based on days_of_coverage and lead_time
        print("[*] Calculare segmente...")
        
        # RESET ALL SEGMENTS TO NULL - force full recalculation
        print("   [*] Resetare segmente existente...")
        conn.execute(text("UPDATE products SET segment = NULL"))
        conn.commit()
        
        # CRITICAL: days_of_coverage < lead_time_days
        conn.execute(text("""
            UPDATE products SET segment = 'CRITICAL'
            WHERE days_of_coverage < COALESCE(lead_time_days, 30)
        """))
        
        # URGENT: lead_time <= days_of_coverage < lead_time + safety_stock
        conn.execute(text("""
            UPDATE products SET segment = 'URGENT'
            WHERE segment IS NULL 
            AND days_of_coverage >= COALESCE(lead_time_days, 30)
            AND days_of_coverage < (COALESCE(lead_time_days, 30) + COALESCE(safety_stock_days, 7))
        """))
        
        # ATTENTION: slight buffer zone
        conn.execute(text("""
            UPDATE products SET segment = 'ATTENTION'
            WHERE segment IS NULL 
            AND days_of_coverage >= (COALESCE(lead_time_days, 30) + COALESCE(safety_stock_days, 7))
            AND days_of_coverage < (COALESCE(lead_time_days, 30) + COALESCE(safety_stock_days, 7) + 30)
        """))
        
        # OVERSTOCK: very high coverage (>180 days)
        conn.execute(text("""
            UPDATE products SET segment = 'OVERSTOCK'
            WHERE segment IS NULL 
            AND days_of_coverage > 180
        """))
        
        # OK: everything else
        conn.execute(text("""
            UPDATE products SET segment = 'OK'
            WHERE segment IS NULL
        """))
        
        conn.commit()
        print("   [OK] Segmente calculate")
        
        # ---------------------------------------------------------
        # PRE-COMPUTE SUGGESTED QTY (Performance Optimization)
        # ---------------------------------------------------------
        print("[*] Pre-calculare cantitati sugerate...")
        
        # Add column if not exists
        try:
            conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS suggested_qty INT DEFAULT 0;"))
            conn.commit()
        except:
            pass
        
        # Calculate suggested_qty in SQL (same logic as Product.suggested_order_qty)
        # Formula: (avg_daily * coverage_days) - current_stock, rounded to MOQ
        # Dead Stock rule: if vanzari_360z < 3, suggested = 0
        conn.execute(text("""
            UPDATE products SET 
                suggested_qty = CASE
                    -- Dead Stock: < 3 vânzări în 360 zile
                    WHEN COALESCE(vanzari_360z, 0) < 3 THEN 0
                    
                    -- Formula normală
                    ELSE GREATEST(0, 
                        CAST(
                            CEIL(
                                (
                                    -- Cantitate necesară pentru acoperire
                                    (COALESCE(avg_daily_sales, 0) * 
                                        (COALESCE(lead_time_days, 30) + 30 + COALESCE(safety_stock_days, 7))
                                    )
                                    -- Minus stoc actual
                                    - (COALESCE(stoc_total, 0) + COALESCE(stoc_tranzit, 0))
                                )
                                -- Rotunjire la MOQ
                                / GREATEST(COALESCE(moq, 1), 1)
                            ) * GREATEST(COALESCE(moq, 1), 1)
                        AS INTEGER)
                    )
                END
        """))
        conn.commit()
        print("   [OK] Cantități sugerate pre-calculate")
        
        # Create index for fast segment queries
        print("[*] Creare index pentru segmente...")
        try:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_segment ON products(segment);"))
            conn.commit()
        except:
            pass
        
        # Show stats
        result = conn.execute(text("""
            SELECT segment, COUNT(*) as cnt 
            FROM products 
            GROUP BY segment 
            ORDER BY segment
        """))
        
        print("\n[+] STATISTICI SEGMENTE:")
        print("-" * 30)
        for row in result:
            print(f"   {row[0]}: {row[1]:,} produse")
        
        print("\n[OK] SUCCES! Segmentele sunt acum pre-calculate in PostgreSQL.")
        print("   Queries pe segment vor fi INSTANTANEE.")

if __name__ == "__main__":
    add_segment_column()
