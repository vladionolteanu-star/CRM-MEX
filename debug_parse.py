from src.core.database import load_segment_from_db
from src.models.product import Product
import pandas as pd

# Mock config
config = {"default": {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1}}
cfg = config

print("Loading data...")
try:
    df = load_segment_from_db("CRITICAL", limit=1)
    if df.empty:
        print("DF Empty")
        exit()
        
    row = df.iloc[0]
    # print("Row keys:", row.keys())
    
    # Copy paste logic from app.py
    furnizor = str(row.get("furnizor", "")) if pd.notnull(row.get("furnizor")) else ""
    supplier_cfg = cfg.get(furnizor, cfg["default"])
    
    print("Instantiating Product...")
    p = Product(
        nr_art=str(row.get("cod_articol", "")),
        cod_articol=str(row.get("cod_articol", "")),
        nume_produs=str(row.get("denumire", "")),
        furnizor=furnizor,
        categorie=str(row.get("clasa", "")),
        stare_pm=str(row.get("stare_pm", "")),
        clasa=str(row.get("clasa", "")),
        subclasa=str(row.get("subclasa", "")),
        # pm=str(row.get("pm", "")), # Missing in app.py?
        cost_achizitie=float(row.get("cost_achizitie", 0) or 0),
        pret_catalog=float(row.get("pret_catalog", 0) or 0),
        pret_vanzare=float(row.get("pret_vanzare", 0) or 0),
        stoc_disponibil_total=float(row.get("stoc_total", 0) or 0),
        stoc_in_tranzit=float(row.get("stoc_tranzit", 0) or 0),
        stoc_magazin_total=float(row.get("stoc_magazine", 0) or 0),
        vanzari_ultimele_4_luni=float(row.get("vanzari_4luni", 0) or 0),
        vanzari_ultimele_360_zile=float(row.get("vanzari_360z", 0) or 0),
        vanzari_2024=float(row.get("vanzari_2024", 0) or 0),
        vanzari_2025=float(row.get("vanzari_2025", 0) or 0),
        vanzari_m16=float(row.get("vanzari_m16", 0) or 0),
        lead_time_days=int(supplier_cfg.get("lead_time_days", 30)),
        safety_stock_days=float(supplier_cfg.get("safety_stock_days", 7)),
        moq=float(supplier_cfg.get("moq", 1))
    )
    print("Success!")
except Exception as e:
    print(f"FAILED: {e}")
    # import traceback
    # traceback.print_exc()
