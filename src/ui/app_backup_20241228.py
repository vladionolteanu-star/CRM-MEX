import streamlit as st
import pandas as pd
import os
import sys
import json

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.loader import DataLoader
from src.models.product import Product
from src.core.database import (
    load_products_from_db, get_unique_suppliers, get_unique_statuses, 
    test_connection, get_segment_counts, load_segment_from_db,
    get_unique_families, load_family_products_from_db
)

# ============================================================
# CONFIG
# ============================================================
CONFIG_PATH = "data/supplier_config.json"
GEMINI_CONFIG_PATH = "data/gemini_config.json"

def load_supplier_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"default": {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1}}

def save_supplier_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def load_gemini_config():
    if os.path.exists(GEMINI_CONFIG_PATH):
        with open(GEMINI_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"api_key": "", "model": "gemini-2.0-flash-exp"}

def save_gemini_config(config):
    with open(GEMINI_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="INDOMEX Calcul Aprovizionare",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# LIGHT ENTERPRISE THEME (more readable)
# ============================================================
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
    h1, h2, h3 { color: #1a1a2e !important; font-weight: 600 !important; }
    h1 { font-size: 1.6rem !important; }
    
    [data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 14px; }
    [data-testid="stMetricLabel"] { color: #6c757d !important; font-size: 0.8rem !important; }
    [data-testid="stMetricValue"] { color: #212529 !important; font-family: 'Consolas', monospace !important; }
    
    .stDataFrame { border: 1px solid #dee2e6 !important; border-radius: 6px; }
    .stDataFrame thead th { background-color: #f1f3f4 !important; color: #495057 !important; font-size: 0.75rem !important; text-transform: uppercase; font-weight: 600 !important; }
    .stDataFrame tbody td { background-color: #ffffff !important; color: #212529 !important; font-family: 'Consolas', monospace !important; font-size: 0.85rem !important; }
    
    .stTabs [data-baseweb="tab-list"] { background-color: transparent; border-bottom: 2px solid #e0e0e0; }
    .stTabs [data-baseweb="tab"] { background-color: transparent; color: #6c757d; border: none; padding: 10px 18px; font-size: 0.85rem; font-weight: 500; }
    .stTabs [aria-selected="true"] { color: #1a1a2e !important; border-bottom: 3px solid #3b82f6 !important; background: #f8f9fa; }
    
    .stButton > button { background-color: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 0.85rem; font-weight: 500; padding: 8px 16px; }
    .stButton > button:hover { background-color: #2563eb; }
    
    #MainMenu, footer, header { visibility: hidden; }
    
    .alarm-critical { background: linear-gradient(90deg, #dc2626 0%, #fee2e2 100%); padding: 14px 18px; border-radius: 6px; margin: 10px 0; border-left: 4px solid #b91c1c; }
    .alarm-urgent { background: linear-gradient(90deg, #f97316 0%, #ffedd5 100%); padding: 14px 18px; border-radius: 6px; margin: 10px 0; border-left: 4px solid #c2410c; }
    
    .settings-btn { background: #e2e8f0 !important; color: #475569 !important; border: 1px solid #cbd5e1 !important; }
    .settings-btn:hover { background: #cbd5e1 !important; }
    
    .kpi-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 4px 0; }
</style>
""", unsafe_allow_html=True)


def analyze_with_gemini(api_key, model_name, supplier_data, products_summary):
    """Call Gemini API for supplier analysis"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""Analizeaza urmatoarele date pentru furnizorul si ofera sugestii de aprovizionare:

SUMAR FURNIZOR:
{json.dumps(supplier_data, indent=2, ensure_ascii=False)}

PRODUSE (sample):
{products_summary}

Oferă:
1. Analiza situatiei stocurilor (CRITICAL, URGENT, etc)
2. Recomandari concrete de actiune
3. Riscuri identificate
4. Sugestii de optimizare a parametrilor (Lead Time, Safety Stock, MOQ)

Raspunde in romana, concis si actionabil."""

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Eroare Gemini API: {str(e)}"


def main():
    config = load_supplier_config()
    gemini_cfg = load_gemini_config()
    default_cfg = config.get("default", {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1})
    
    # Pre-load suppliers list for Settings dropdown
    @st.cache_data(show_spinner=False)
    def get_suppliers_list():
        data_path = "data/Tcioara Forecast_.csv"
        if os.path.exists(data_path):
            try:
                import pandas as pd
                df = pd.read_csv(data_path, usecols=["FURNIZOR EXT"], low_memory=False)
                return sorted(df["FURNIZOR EXT"].dropna().unique().tolist())
            except:
                return []
        return []
    
    all_suppliers = get_suppliers_list()
    
    # ============================================================
    # HEADER with Settings Button
    # ============================================================
    col_title, col_settings = st.columns([6, 1])
    with col_title:
        st.markdown("## INDOMEX Calcul Aprovizionare")
    with col_settings:
        if st.button("Settings", key="open_settings"):
            st.session_state.show_settings = True
    
    # ============================================================
    # SETTINGS MODAL
    # ============================================================
    if st.session_state.get("show_settings", False):
        with st.expander("SETTINGS", expanded=True):
            tab_defaults, tab_suppliers, tab_gemini, tab_help = st.tabs(["Default Parameters", "Suppliers", "Gemini API", "Ajutor"])
            
            with tab_defaults:
                st.markdown("### Default Supplier Parameters")
                st.markdown("*Acesti parametri se aplica furnizorilor fara setari specifice*")
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_lt = st.number_input("Lead Time (days)", value=default_cfg.get("lead_time_days", 30), min_value=1, max_value=180, key="set_lt")
                with col2:
                    new_ss = st.number_input("Safety Stock (days)", value=float(default_cfg.get("safety_stock_days", 7)), min_value=0.0, max_value=60.0, key="set_ss")
                with col3:
                    new_moq = st.number_input("MOQ", value=float(default_cfg.get("moq", 1)), min_value=1.0, key="set_moq")
                
                if st.button("Save Defaults"):
                    config["default"] = {"lead_time_days": new_lt, "safety_stock_days": new_ss, "moq": new_moq}
                    save_supplier_config(config)
                    st.success("Saved")
                    st.rerun()
                
                st.markdown("---")
                st.markdown("### 🔄 Recalculare Segmente")
                st.markdown("*După modificarea Lead Time sau Safety Stock, recalculează segmentele în baza de date*")
                if st.button("🔄 Recalculează Segmente", type="primary", key="recalc_segments"):
                    with st.spinner("Se recalculează segmentele... Poate dura 1-2 minute"):
                        import subprocess
                        result = subprocess.run(
                            ["python", "scripts/precompute_segments.py"],
                            capture_output=True,
                            text=True,
                            cwd="."
                        )
                        if result.returncode == 0:
                            st.success("✅ Segmentele au fost recalculate! Refresh pagina pentru a vedea noile valori.")
                            st.cache_data.clear()  # Clear cached data
                        else:
                            st.error(f"❌ Eroare: {result.stderr}")
            
            with tab_suppliers:
                st.markdown("### Configurare per Furnizor")
                st.markdown("*Selecteaza furnizorul si seteaza parametrii specifici*")
                
                # Need to load suppliers list - this will be populated after data load
                # For now show configured suppliers
                configured = [k for k in config.keys() if k != "default"]
                
                st.markdown("#### Furnizori Configurati")
                if configured:
                    cfg_data = []
                    for sup in configured:
                        cfg_data.append({
                            "Furnizor": sup[:40],
                            "Lead Time": config[sup].get("lead_time_days", "-"),
                            "Safety Stock": config[sup].get("safety_stock_days", "-"),
                            "MOQ": config[sup].get("moq", "-"),
                        })
                    st.dataframe(cfg_data, width='stretch')
                else:
                    st.info("Niciun furnizor configurat. Selecteaza un furnizor din sidebar pentru a-i seta parametrii.")
                
                st.markdown("---")
                st.markdown("#### Selecteaza Furnizor")
                
                if all_suppliers:
                    new_supplier_name = st.selectbox("Alege Furnizor", ["(alege)"] + all_suppliers, key="new_sup_select")
                    if new_supplier_name and new_supplier_name != "(alege)":
                        existing = config.get(new_supplier_name, default_cfg.copy())
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            sup_lt = st.number_input("Lead Time", value=int(existing.get("lead_time_days", 30)), min_value=1, max_value=180, key="new_sup_lt")
                        with col2:
                            sup_ss = st.number_input("Safety Stock", value=float(existing.get("safety_stock_days", 7)), min_value=0.0, key="new_sup_ss")
                        with col3:
                            sup_moq = st.number_input("MOQ", value=float(existing.get("moq", 1)), min_value=1.0, key="new_sup_moq")
                        
                        col_save, col_del = st.columns(2)
                        with col_save:
                            if st.button("Salveaza Furnizor", key="save_new_sup"):
                                config[new_supplier_name] = {"lead_time_days": sup_lt, "safety_stock_days": sup_ss, "moq": sup_moq}
                                save_supplier_config(config)
                                st.success(f"Salvat: {new_supplier_name}")
                                st.rerun()
                        with col_del:
                            if new_supplier_name in config and new_supplier_name != "default":
                                if st.button("Sterge Config", key="del_new_sup"):
                                    del config[new_supplier_name]
                                    save_supplier_config(config)
                                    st.info(f"Sters: {new_supplier_name}")
                                    st.rerun()
                else:
                    st.warning("Lista furnizorilor nu este disponibila. Incarca fisierul CSV.")
            
            with tab_gemini:
                st.markdown("### Gemini API Configuration")
                api_key = st.text_input("API Key", value=gemini_cfg.get("api_key", ""), type="password", key="gem_key")
                models_list = ["gemini-pro-latest", "gemini-flash-latest", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash-exp"]
                current_model = gemini_cfg.get("model", "gemini-pro-latest")
                model_idx = models_list.index(current_model) if current_model in models_list else 0
                model_name = st.selectbox("Model", models_list, index=model_idx)
                
                if st.button("Save API Config"):
                    save_gemini_config({"api_key": api_key, "model": model_name})
                    st.success("API config saved")
            
            with tab_help:
                st.markdown("""
### Parametri de Aprovizionare

**Lead Time (Timp de Livrare)**
- Numarul de zile de la plasarea comenzii pana la receptia marfii
- Exemplu: Daca furnizorul livreaza in 30 zile, Lead Time = 30

**Safety Stock (Stoc de Siguranta)**
- Buffer suplimentar de zile pentru a acoperi variatii in cerere sau intarzieri
- Protejeaza impotriva lipsei de stoc in cazul vanzarilor mai mari decat normal
- Exemplu: 7 zile = stoc suplimentar pentru o saptamana de vanzari

**MOQ (Minimum Order Quantity)**
- Cantitatea minima pe care o poti comanda de la furnizor
- Comenzile sugerate vor fi rotunjite la multipli de MOQ

---

### Formule de Calcul

**Vanzari Medii Zilnice:**
```
= Vanzari ultim 4 luni / 120 zile
```
(sau Vanzari 360 zile / 360 daca nu exista date pe 4 luni)

**Zile de Acoperire (Days Coverage):**
```
= (Stoc disponibil + Stoc in tranzit) / Vanzari medii zilnice
```
Raspunde la intrebarea: "Cate zile mai pot vinde cu stocul actual?"

**Prag de Reaprovizionare (Reorder Point):**
```
= Lead Time + Safety Stock (in zile)
```
Cand zilele de acoperire scad sub acest prag, trebuie comandat.

---

### Categorii Stoc (Segmente)

**CRITICAL (Rosu)**
- Acoperire < Lead Time
- Marfa NU va ajunge la timp - STOCKOUT iminent
- Actiune: Comanda EXPRESS sau furnizor alternativ

**URGENT (Portocaliu)**
- Acoperire < Lead Time + Safety Stock
- Risc mare de lipsa stoc
- Actiune: Plaseaza comanda ACUM

**ATTENTION (Galben)**
- Acoperire < Lead Time + Safety Stock + 14 zile
- Ai ~2 saptamani sa comanzi
- Actiune: Planifica comanda, verifica MOQ

**OK (Verde)**
- Acoperire suficienta
- Stocul este sanatos
- Actiune: Monitorizare saptamanala

**OVERSTOCK (Albastru)**
- Acoperire > 90 zile
- Capital blocat in marfa
- Actiune: Promotie? Reduce comenzile viitoare
                """)
            
            if st.button("Close Settings"):
                st.session_state.show_settings = False
                st.rerun()
    
    st.markdown("---")
    
    # ============================================================
    # SIDEBAR - FILTERS
    # ============================================================
    st.sidebar.markdown("### FILTERS")
    
    
    # Data Source Toggle
    st.sidebar.markdown("### 📊 DATA SOURCE")
    use_postgres = st.sidebar.toggle("🐘 PostgreSQL (rapid)", value=True, help="Folosește PostgreSQL pentru viteză. Dezactivează pentru CSV.")
    
    if use_postgres:
        # PostgreSQL mode - FAST!
        success, msg = test_connection()
        if success:
            st.sidebar.success(msg)
            
            # Get filters from database (fast!)
            suppliers = get_unique_suppliers()
            pm_statuses = get_unique_statuses()
            
            # Filters
            selected_supplier = st.sidebar.selectbox("Supplier", ["ALL"] + suppliers, key="pg_supplier")
            selected_status = st.sidebar.selectbox("PM Status", ["ALL"] + pm_statuses, key="pg_status")
            
            # Load data from PostgreSQL - FAST!
            with st.spinner("🐘 Se încarcă din PostgreSQL..."):
                raw_df = load_products_from_db(
                    furnizor=selected_supplier if selected_supplier != "ALL" else None,
                    stare_pm=selected_status if selected_status != "ALL" else None
                )
        else:
            st.sidebar.error("❌ Nu pot conecta la PostgreSQL. Folosește CSV.")
            use_postgres = False
    
    if not use_postgres:
        # CSV mode - fallback
        data_files = [f for f in os.listdir("data") if f.endswith('.csv')] if os.path.exists("data") else []
        if not data_files:
            st.sidebar.warning("No CSV in /data")
            return
        
        selected_file = st.sidebar.selectbox("Data Source", data_files, 
            index=data_files.index("Tcioara Forecast_.csv") if "Tcioara Forecast_.csv" in data_files else 0,
            key="csv_file")
        data_path = f"data/{selected_file}"
        
        @st.cache_data(show_spinner=False)
        def load_raw(path):
            loader = DataLoader(path)
            loader.load_data()
            return loader.df
        
        with st.spinner("📂 Se încarcă din CSV... Poate dura mai mult."):
            try:
                raw_df = load_raw(data_path)
            except Exception as e:
                st.error(f"Eroare incarcare: {e}")
                return
        
        # Get unique values for filters
        suppliers = sorted(raw_df["FURNIZOR EXT"].dropna().unique().tolist()) if "FURNIZOR EXT" in raw_df.columns else []
        pm_statuses = sorted(raw_df["STARE PM"].dropna().unique().tolist()) if "STARE PM" in raw_df.columns else []
        
        # Filters
        selected_supplier = st.sidebar.selectbox("Supplier", ["ALL"] + suppliers, key="csv_supplier")
        selected_status = st.sidebar.selectbox("PM Status", ["ALL"] + pm_statuses, key="csv_status")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### SUPPLIER CONFIG")
    
    # Quick supplier config in sidebar
    if selected_supplier != "ALL":
        current_cfg = config.get(selected_supplier, default_cfg.copy())
        st.sidebar.markdown(f"**{selected_supplier[:30]}**")
        sup_lt = st.sidebar.number_input("Lead Time", value=int(current_cfg.get("lead_time_days", 30)), min_value=1, max_value=180, key="sb_lt")
        sup_ss = st.sidebar.number_input("Safety Stock", value=float(current_cfg.get("safety_stock_days", 7)), min_value=0.0, key="sb_ss")
        sup_moq = st.sidebar.number_input("MOQ", value=float(current_cfg.get("moq", 1)), min_value=1.0, key="sb_moq")
        
        if st.sidebar.button("Save for this Supplier"):
            config[selected_supplier] = {"lead_time_days": sup_lt, "safety_stock_days": sup_ss, "moq": sup_moq}
            save_supplier_config(config)
            st.sidebar.success("Saved")
            st.rerun()
    
    # ============================================================
    # PARSE PRODUCTS
    # ============================================================
    
    def parse_from_postgres(df, cfg):
        """Parse products from PostgreSQL DataFrame (different column names)"""
        products = []
        default = cfg.get("default", {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1})
        
        for _, row in df.iterrows():
            try:
                furnizor = str(row.get("furnizor", "")) if pd.notnull(row.get("furnizor")) else ""
                supplier_cfg = cfg.get(furnizor, default)
                
                p = Product(
                    nr_art=str(row.get("cod_articol", "")),
                    cod_articol=str(row.get("cod_articol", "")),
                    nume_produs=str(row.get("denumire", "")),
                    furnizor=furnizor,
                    categorie=str(row.get("clasa", "")),
                    stare_pm=str(row.get("stare_pm", "")),
                    clasa=str(row.get("clasa", "")),
                    subclasa=str(row.get("subclasa", "")),
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
                    vanzari_fara_m16=float(row.get("vanzari_fara_m16", 0) or 0),
                    stoc_baneasa=int(row.get("stoc_baneasa", 0) or 0),
                    stoc_pipera=int(row.get("stoc_pipera", 0) or 0),
                    stoc_militari=int(row.get("stoc_militari", 0) or 0),
                    stoc_pantelimon=int(row.get("stoc_pantelimon", 0) or 0),
                    stoc_iasi=int(row.get("stoc_iasi", 0) or 0),
                    stoc_brasov=int(row.get("stoc_brasov", 0) or 0),
                    stoc_pitesti=int(row.get("stoc_pitesti", 0) or 0),
                    stoc_sibiu=int(row.get("stoc_sibiu", 0) or 0),
                    stoc_oradea=int(row.get("stoc_oradea", 0) or 0),
                    stoc_constanta=int(row.get("stoc_constanta", 0) or 0),
                    stoc_outlet_constanta=int(row.get("stoc_outlet_constanta", 0) or 0),
                    stoc_outlet_pipera=int(row.get("stoc_outlet_pipera", 0) or 0),
                    lead_time_days=int(row.get("lead_time_days", 30) or 30),
                    safety_stock_days=float(row.get("safety_stock_days", 7) or 7),
                    moq=float(row.get("moq", 1) or 1)
                )
                products.append(p)
            except Exception:
                continue
        return products
    
    def parse_with_config(df, cfg):
        products = []
        default = cfg.get("default", {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1})
        
        for _, row in df.iterrows():
            try:
                def get_float(col, d=0.0):
                    val = row.get(col, d)
                    try: return float(val) if pd.notnull(val) else d
                    except: return d
                def get_str(col, d=""):
                    val = row.get(col, d)
                    if pd.notnull(val):
                        # Handle numeric values - convert to int first to remove .0
                        try:
                            if isinstance(val, float):
                                return str(int(val))
                            return str(val).strip()
                        except:
                            return str(val).strip()
                    return d
                
                # Use COD ARTICOL as primary identifier (NR ART is just row number)
                nr_art = get_str("COD ARTICOL")
                if not nr_art: continue
                
                furnizor = get_str("FURNIZOR EXT")
                supplier_cfg = cfg.get(furnizor, default)
                
                p = Product(
                    nr_art=nr_art,
                    cod_articol=get_str("COD ARTICOL"),
                    nume_produs=get_str("DENUMIRE ARTICOL"),
                    furnizor=furnizor,
                    categorie=get_str("CLASA DENUMIRE"),
                    stare_pm=get_str("STARE PM", ""),
                    # Classification
                    clasa=get_str("CLASA DENUMIRE"),
                    subclasa=get_str("SUBCLASA DENUMIRE"),
                    pm=get_str("PM"),
                    # Prices
                    cost_achizitie=get_float("Cost Achizitie Furnizor (ultimul NIR_cronologic)"),
                    pret_catalog=get_float("Pret de Catalog cu TVA"),
                    pret_vanzare=get_float("Pret Vanzare cu TVA (magazin _client final)"),
                    pret_retea=get_float("Pret mediu Vanzare Furnizor catre Retea la zi"),
                    # Stock totals
                    stoc_disponibil_total=get_float("Stoc Disponibil Cantitativ Magazine Dep+Acc+Outlet"),
                    stoc_in_tranzit=get_float("CAFE cantitativ nereceptionat Furnizor"),
                    stoc_magazin_total=get_float("Stoc Disponibil Cantitativ Magazine"),
                    # Stock per store
                    stoc_baneasa=get_float("Stoc Disponibil Cantitativ Baneasa"),
                    stoc_pipera=get_float("Stoc Disponibil Cantitativ Pipera"),
                    stoc_militari=get_float("Stoc Disponibil Cantitativ Militari"),
                    stoc_pantelimon=get_float("Stoc Disponibil Cantitativ Pantelimon"),
                    stoc_iasi=get_float("Stoc Disponibil Cantitativ Iasi"),
                    stoc_brasov=get_float("Stoc Disponibil Cantitativ Brasov"),
                    stoc_pitesti=get_float("Stoc Disponibil Cantitativ Pitesti"),
                    stoc_sibiu=get_float("Stoc Disponibil Cantitativ Sibiu"),
                    stoc_oradea=get_float("Stoc Disponibil Cantitativ Oradea"),
                    stoc_constanta=get_float("Stoc Disponibil Cantitativ Constanta"),
                    stoc_outlet_constanta=get_float("Stoc Disponibil Cantitativ Constanta Outlet"),
                    stoc_outlet_pipera=get_float("Stoc Disponibil Cantitativ Pipera Outlet"),
                    # Sales
                    vanzari_ultimele_4_luni=get_float("Vanzari Cantitative Magazine_client final ult. 4 Luni"),
                    vanzari_ultimele_360_zile=get_float("Vanzari Cantitative Magazine 360z (client final)"),
                    vanzari_2024=get_float("Vanzari Cantitative Magazine 2024 (client final)"),
                    vanzari_2025=get_float("Vanzari Cantitative Magazine 2025 (client final)"),
                    vanzari_m16=get_float("Vanzari Cantitative Furnizor 360z catre M16"),
                    vanzari_fara_m16=get_float("Vanzari Cantitative Furnizor 360z exclus M16"),
                    # Supplier config
                    lead_time_days=int(supplier_cfg.get("lead_time_days", 30)),
                    safety_stock_days=float(supplier_cfg.get("safety_stock_days", 7)),
                    moq=float(supplier_cfg.get("moq", 1))
                )
                products.append(p)
            except: continue
        return products
    
    # ============================================================
    # PROCESS DATA - OPTIMIZED PATH FOR POSTGRESQL
    # ============================================================
    
    segments = {"CRITICAL": [], "URGENT": [], "ATTENTION": [], "OK": [], "OVERSTOCK": []}
    segment_stats = {}
    
    if use_postgres:
        # PostgreSQL OPTIMIZED PATH - instant segment counts from DB
        segment_stats = get_segment_counts(
            furnizor=selected_supplier if selected_supplier != "ALL" else None,
            stare_pm=selected_status if selected_status != "ALL" else None
        )
        # Don't load all products upfront - load per-tab later
        products = []  # Empty - will load per segment in tabs
    else:
        # CSV mode - need to parse all
        with st.spinner("⏳ Se procesează produsele din CSV... Poate dura mai mult."):
            products = parse_with_config(raw_df, config)
        
        # Apply filters for CSV mode
        if selected_supplier != "ALL":
            products = [p for p in products if p.furnizor == selected_supplier]
        if selected_status != "ALL":
            products = [p for p in products if p.stare_pm == selected_status]
        
        # Build segments for CSV mode
        for p in products:
            segments[p.segment].append(p)
        
        # Build stats from parsed products
        for seg_name in segments:
            segment_stats[seg_name] = {
                "count": len(segments[seg_name]),
                "value": sum(p.stock_value for p in segments[seg_name])
            }
    
    # ============================================================
    # ALARM PANEL
    # ============================================================
    critical_count = segment_stats.get("CRITICAL", {}).get("count", 0)
    urgent_count = segment_stats.get("URGENT", {}).get("count", 0)
    
    if critical_count > 0:
        critical_value = segment_stats.get("CRITICAL", {}).get("value", 0)
        st.markdown(f"""
        <div class="alarm-critical">
            <strong style="color:#991b1b;">CRITICAL</strong>
            <span style="color:#1f2937;margin-left:16px;">{critical_count} items below lead time</span>
            <span style="color:#6b7280;margin-left:16px;">Value: {critical_value:,.0f} RON</span>
        </div>
        """, unsafe_allow_html=True)
    
    if urgent_count > 0:
        st.markdown(f"""
        <div class="alarm-urgent">
            <strong style="color:#9a3412;">URGENT</strong>
            <span style="color:#1f2937;margin-left:16px;">{urgent_count} items need ordering</span>
        </div>
        """, unsafe_allow_html=True)
    
    # ============================================================
    # KPI CARDS
    # ============================================================
    cols = st.columns(5)
    segment_info = [
        ("CRITICAL", "#dc2626", "#fef2f2"), 
        ("URGENT", "#f97316", "#fff7ed"), 
        ("ATTENTION", "#eab308", "#fefce8"), 
        ("OK", "#22c55e", "#f0fdf4"), 
        ("OVERSTOCK", "#3b82f6", "#eff6ff"),
    ]
    
    for i, (seg, color, bg) in enumerate(segment_info):
        count = segment_stats.get(seg, {}).get("count", 0)
        value = segment_stats.get(seg, {}).get("value", 0)
        with cols[i]:
            st.markdown(f"""
            <div style="background:{bg};border:1px solid {color}33;border-left:4px solid {color};padding:14px;border-radius:6px;">
                <div style="color:#6b7280;font-size:0.75rem;text-transform:uppercase;font-weight:600;">{seg}</div>
                <div style="color:#1f2937;font-size:1.6rem;font-family:monospace;font-weight:700;">{count}</div>
                <div style="color:#9ca3af;font-size:0.75rem;">{value:,.0f} RON</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("")
    
    # ============================================================
    # TABS
    # ============================================================
    tab_critical, tab_urgent, tab_attention, tab_ok, tab_overstock, tab_all, tab_family, tab_audit = st.tabs([
        f"CRITICAL ({segment_stats.get('CRITICAL', {}).get('count', 0)})",
        f"URGENT ({segment_stats.get('URGENT', {}).get('count', 0)})",
        f"ATTENTION ({segment_stats.get('ATTENTION', {}).get('count', 0)})",
        f"OK ({segment_stats.get('OK', {}).get('count', 0)})",
        f"OVERSTOCK ({segment_stats.get('OVERSTOCK', {}).get('count', 0)})",
        "ALL DATA",
        "FAMILY VIEW",
        "SUPPLIER AUDIT"
    ])
    
    def render_interactive_table(product_list, segment_name, allow_order=True):
        """
        Renders an interactive table with checkbox selection and on-demand order calculation.
        
        Args:
            product_list: List of Product objects
            segment_name: Name of segment (for unique keys)
            allow_order: If False, no order calculation is available (for OVERSTOCK)
        """
        if not product_list:
            st.info("Nu exista produse in aceasta categorie")
            return None
            
        # Build product lookup by nr_art
        product_lookup = {p.nr_art: p for p in product_list}
        
        # ============================================================
        # FAMILY GROUPING: Sort products so families stay together
        # ============================================================
        # First, identify all families and their total sales
        family_sales = {}
        family_stocks = {}
        for p in product_list:
            if p.familie:
                family_sales[p.familie] = family_sales.get(p.familie, 0) + p.vanzari_ultimele_4_luni
                family_stocks[p.familie] = family_stocks.get(p.familie, 0) + p.total_stock
        
        # Calculate family-level unbalanced status for each product
        def is_unbalanced(p):
            """Check if product has unbalanced stock within its family"""
            if not p.familie or p.familie not in family_sales:
                return False
            fam_sales = family_sales[p.familie]
            fam_stock = family_stocks[p.familie]
            if fam_sales <= 0 or fam_stock <= 0:
                return False
            # Calculate shares
            sales_share = p.vanzari_ultimele_4_luni / fam_sales if fam_sales > 0 else 0
            stock_share = p.total_stock / fam_stock if fam_stock > 0 else 0
            # Unbalanced if difference > 15%
            return abs(sales_share - stock_share) > 0.15
        
        # Sort: family groups together, then by dimension within family
        # Non-family products go last
        def sort_key(p):
            if p.familie:
                # Primary: family sales (descending), Secondary: family name, Tertiary: dimension
                fam_sales_val = family_sales.get(p.familie, 0)
                return (0, -fam_sales_val, p.familie, p.dimensiune or "zzz")
            else:
                return (1, 0, "", p.nume_produs)
        
        sorted_products = sorted(product_list, key=sort_key)
        
        # Build data for display
        data = []
        for p in sorted_products:
            # Calculate Trend based on Sales Velocity (Recent vs Annual)
            # p.sales_trend returns a ratio (e.g. 1.15 for 15% growth)
            sales_trend_val = p.sales_trend
            trend_pct = int((sales_trend_val - 1.0) * 100)
            # Calculate margin %
            marja_pct = None
            if p.pret_vanzare > 0 and p.cost_achizitie > 0:
                marja_pct = round(((p.pret_vanzare - p.cost_achizitie) / p.pret_vanzare) * 100, 1)
            
            # Calculate suggested quantity with formula explanation
            suggested_qty = int(p.suggested_order_qty)
            adjusted_safety = round(p.safety_stock_days * p.dimension_coefficient, 1)
            formula_text = f"Media: {p.avg_daily_sales:.2f}/zi × (Lead:{p.lead_time_days} + Safety:{adjusted_safety} + 60) - Stoc:{int(p.total_stock)} = {suggested_qty} buc"
            
            # Check if unbalanced within family
            is_unbal = is_unbalanced(p)
            
            row = {
                "Selecteaza": False,  # Checkbox column
                "Cod": p.nr_art,
                "Denumire": (p.nume_produs[:22] + "..") if len(p.nume_produs) > 22 else p.nume_produs,
                # Familie with unbalanced indicator
                "Familie": f"⚠️ {p.familie}" if (p.familie and is_unbal) else (p.familie if p.familie else "-"),
                "Dim": p.dimensiune if p.dimensiune else "-",
                # Stock totals
                "Stoc": int(p.total_stock),
                "Tranzit": int(p.stoc_in_tranzit),
                "StocMag": int(p.stoc_magazin_total),
                # Sales columns
                "V.4L": int(p.vanzari_ultimele_4_luni),
                "V.360": int(p.vanzari_ultimele_360_zile),
                "V.2024": int(p.vanzari_2024),
                "V.2025": int(p.vanzari_2025),
                "Trend%": f"{int(trend_pct):+d}%",
                "V.M16": int(p.vanzari_m16),
                "V.NonM16": int(p.vanzari_fara_m16),
                # Calculated
                "Med/Zi": round(p.avg_daily_sales, 2),
                "Zile Ac.": round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999.0,
                "Lead": p.lead_time_days,
                # SUGGESTED QUANTITY (NEW)
                "Cant.Sug.": suggested_qty,
                "_formula": formula_text,  # Hidden column for tooltip
                "_unbalanced": is_unbal,   # Hidden column for styling
                # Prices
                "Cost": round(p.cost_achizitie, 2),
                "PVanz": round(p.pret_vanzare, 2),
                "PCat": round(p.pret_catalog, 2),
                "Marja%": f"{marja_pct}%" if marja_pct else "-",
                # Classification
                "Clasa": p.clasa[:15] if p.clasa else "-",
                "Subclasa": p.subclasa[:15] if p.subclasa else "-",
                # Store stocks (optional columns)
                "S.Ban": int(p.stoc_baneasa),
                "S.Pip": int(p.stoc_pipera),
                "S.Mil": int(p.stoc_militari),
                "S.Pan": int(p.stoc_pantelimon),
                "S.Iasi": int(p.stoc_iasi),
                "S.Bras": int(p.stoc_brasov),
                "S.Pit": int(p.stoc_pitesti),
                "S.Sib": int(p.stoc_sibiu),
                "S.Ora": int(p.stoc_oradea),
                "S.Cta": int(p.stoc_constanta),
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Column config with DETAILED hover help texts (restaurat)
        column_config = {
            "Selecteaza": st.column_config.CheckboxColumn(
                "✓",
                help="Bifează produsele pe care vrei să le incluzi în calculul comenzii. Apoi apasă 'Calculează Selectate'.",
                default=False
            ),
            "Cod": st.column_config.TextColumn(
                "Cod Produs",
                help="Codul unic al articolului (NR ART). Foloseste acest cod pentru identificarea produsului in sistem."
            ),
            "Denumire": st.column_config.TextColumn(
                "Denumire",
                help="Numele complet al produsului. Daca este trunchiat, poti vedea numele complet in export."
            ),
            "Familie": st.column_config.TextColumn(
                "Familie",
                help="Familia de produse (ex: FLORENCE, SEBRA). ⚠️ = Stoc DEZECHILIBRAT în cadrul familiei (diferență >15% între proporția vânzări și proporția stoc)."
            ),
            "Dim": st.column_config.TextColumn(
                "Dimensiune",
                help="Dimensiunea produsului (ex: 080x150cm). Dimensiunile mici (060, 080) au coeficient +15% safety stock, cele mari (200, 300) au -20%."
            ),
            "Stoc": st.column_config.NumberColumn(
                "Stoc",
                help="Cantitatea totala disponibila pentru vanzare. Include stocul din Magazine, Depozit, Accesorii si Outlet. NU include marfa in tranzit.",
                format="%d"
            ),
            "Tranzit": st.column_config.NumberColumn(
                "Tranzit",
                help="Cantitatea comandata de la furnizor care este in drum dar INCA nu a fost receptionata. Aceasta marfa va fi disponibila dupa receptie.",
                format="%d"
            ),
            "V.4L": st.column_config.NumberColumn(
                "V. 4 Luni",
                help="Numarul total de bucati vandute catre clienti finali in ultimele 4 luni (aproximativ 120 zile). Aceasta este baza principala pentru calculul mediei zilnice.",
                format="%d"
            ),
            "V.360": st.column_config.NumberColumn(
                "V. 360 Zile",
                help="Numarul total de bucati vandute in ultimele 360 de zile. Ofera o perspectiva anuala completa asupra performantei produsului.",
                format="%d"
            ),
            "V.2024": st.column_config.NumberColumn(
                "V. 2024",
                help="Totalul vanzarilor inregistrate in anul calendaristic 2024. Foloseste pentru comparatie cu 2025.",
                format="%d"
            ),
            "V.2025": st.column_config.NumberColumn(
                "V. 2025",
                help="Totalul vanzarilor inregistrate in anul 2025 pana la data actuala.",
                format="%d"
            ),
            "Trend%": st.column_config.TextColumn(
                "Trend",
                help="Trend Viteză (4L vs 360z). Compara viteza recenta de vanzari (4 luni) cu media anuala (360 zile). +10% inseamna ca in ultimele 4 luni s-a vandut cu 10% mai repede decat media anuala."
            ),
            "Med/Zi": st.column_config.NumberColumn(
                "Media/Zi",
                help="Cate bucati se vand IN MEDIE pe zi. Formula: Vanzari 4 Luni / 120 zile. Aceasta valoare este folosita pentru toate calculele de acoperire si reaprovizionare.",
                format="%.2f"
            ),
            "Zile Ac.": st.column_config.NumberColumn(
                "Zile Acop.",
                help="Cate ZILE mai poti vinde cu stocul actual la ritmul mediu de vanzari. Formula: (Stoc + Tranzit) / Media Zilnica. Daca acest numar scade sub Lead Time, marfa nu va ajunge la timp!",
                format="%.1f"
            ),
            "Lead": st.column_config.NumberColumn(
                "Lead Time",
                help="Numarul de ZILE de la plasarea comenzii pana cand marfa ajunge si este disponibila pentru vanzare. Include timpul de productie, transport si receptie. Poti configura aceasta valoare per furnizor din Settings.",
                format="%d"
            ),
            "Cant.Sug.": st.column_config.NumberColumn(
                "📊 Cant.Sug.",
                help="Cantitatea sugerata de comandat. Formula: Media/zi × (Lead + Safety×CoefDim + 60) - Stoc. Hover peste valoare pentru formula exacta pentru acest produs.",
                format="%d"
            ),
            # Hide internal columns
            "_formula": None,
            "_unbalanced": None,
        }
        
        # Remove hidden columns from display dataframe
        display_cols = [col for col in df.columns if not col.startswith("_")]
        display_df = df[display_cols].copy()
        
        # ============================================================
        # SIMPLE FILTERS (Feature 2)
        # ============================================================
        with st.expander("🔍 Filtre", expanded=False):
            filter_cols = st.columns([2, 2, 2, 2])
            with filter_cols[0]:
                search_text = st.text_input("🔎 Caută (cod/denumire)", key=f"search_{segment_name}", placeholder="ex: FLORENCE sau 123456")
            with filter_cols[1]:
                # Get unique families from current data
                unique_families = sorted([f for f in display_df["Familie"].unique() if f != "-"])
                family_filter = st.selectbox("👨‍👩‍👧 Familie", ["Toate"] + unique_families, key=f"fam_{segment_name}")
            with filter_cols[2]:
                # Get unique classes
                unique_classes = sorted([c for c in display_df["Clasa"].unique() if c != "-"])
                class_filter = st.selectbox("📁 Clasă", ["Toate"] + unique_classes, key=f"cls_{segment_name}")
            with filter_cols[3]:
                # Get unique subclasses
                unique_subclasses = sorted([s for s in display_df["Subclasa"].unique() if s != "-"])
                subclass_filter = st.selectbox("📂 Subclasă", ["Toate"] + unique_subclasses, key=f"subcls_{segment_name}")
        
        # Apply filters
        if search_text:
            search_lower = search_text.lower()
            display_df = display_df[
                display_df["Cod"].astype(str).str.lower().str.contains(search_lower, na=False) |
                display_df["Denumire"].astype(str).str.lower().str.contains(search_lower, na=False)
            ]
        if family_filter != "Toate":
            display_df = display_df[display_df["Familie"] == family_filter]
        if class_filter != "Toate":
            display_df = display_df[display_df["Clasa"] == class_filter]
        if subclass_filter != "Toate":
            display_df = display_df[display_df["Subclasa"] == subclass_filter]
        
        # Action buttons row (only if order is allowed)
        if allow_order:
            col_sel, col_calc, col_exp = st.columns([2, 2, 2])
            with col_sel:
                select_all = st.checkbox(f"Selectează Toate ({len(product_list)})", key=f"sel_all_{segment_name}")
            with col_calc:
                explain_btn = st.button("🤖 Explică Cant. Sugerată", key=f"explain_{segment_name}", type="primary")
            with col_exp:
                csv_data = display_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Export", csv_data, f"{segment_name.lower()}_products.csv", "text/csv", key=f"exp_{segment_name}")
        else:
            col_exp = st.columns([1])[0]
            with col_exp:
                csv_data = display_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Export", csv_data, f"{segment_name.lower()}_products.csv", "text/csv", key=f"exp_{segment_name}")
            select_all = False
            explain_btn = False
        
        # If select all is checked, update all checkboxes
        if select_all:
            display_df["Selecteaza"] = True
        
        # Render editable table
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            width="stretch",
            height=350,
            hide_index=True,
            key=f"editor_{segment_name}",
            disabled=[col for col in display_df.columns if col != "Selecteaza"]  # All columns except checkbox are read-only
        )
        
        if allow_order and explain_btn:
            selected_codes = edited_df[edited_df["Selecteaza"] == True]["Cod"].tolist()
            
            if not selected_codes:
                st.warning("⚠️ Selectează cel puțin un produs pentru explicație!")
            else:
                # Check Gemini config
                if not gemini_cfg.get("api_key"):
                    st.warning("⚠️ Configurează API key în Settings > Gemini API")
                else:
                    # Build explanation data for selected products
                    products_for_ai = []
                    for code in selected_codes:
                        if code in product_lookup:
                            p = product_lookup[code]
                            qty = int(p.suggested_order_qty)
                            adjusted_safety = round(p.safety_stock_days * p.dimension_coefficient, 1)
                            trend_pct = int((p.sales_trend - 1.0) * 100)
                            
                            # Check family balance
                            fam_sales = family_sales.get(p.familie, 0) if p.familie else 0
                            fam_stock = family_stocks.get(p.familie, 0) if p.familie else 0
                            sales_share = p.vanzari_ultimele_4_luni / fam_sales if fam_sales > 0 else 0
                            stock_share = p.total_stock / fam_stock if fam_stock > 0 else 0
                            is_unbal = abs(sales_share - stock_share) > 0.15 if p.familie else False
                            
                            products_for_ai.append({
                                "Cod": code,
                                "Denumire": p.nume_produs,
                                "Familie": p.familie or "-",
                                "Dimensiune": p.dimensiune or "-",
                                "Stoc_Actual": int(p.total_stock),
                                "Tranzit": int(p.stoc_in_tranzit),
                                "Vanzari_4Luni": int(p.vanzari_ultimele_4_luni),
                                "Vanzari_360z": int(p.vanzari_ultimele_360_zile),
                                "Media_Zilnica": round(p.avg_daily_sales, 2),
                                "Zile_Acoperire": round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999,
                                "Lead_Time_Zile": p.lead_time_days,
                                "Safety_Stock_Zile": p.safety_stock_days,
                                "Coef_Dimensiune": p.dimension_coefficient,
                                "Safety_Ajustat": adjusted_safety,
                                "Trend_Viteza": f"{trend_pct:+d}%",
                                "CANTITATE_SUGERATA": qty,
                                "FORMULA": f"{p.avg_daily_sales:.2f}/zi × ({p.lead_time_days} + {adjusted_safety} + 60) - {int(p.total_stock)} = {qty}",
                                "Stoc_Dezechilibrat_Familie": "DA" if is_unbal else "NU",
                            })
                    
                    # Build AI prompt with chain of thought instruction
                    prompt = f"""Ești un expert în supply chain. Explică în LIMBAJ NATURAL de ce s-a ajuns la cantitățile sugerate.

DATE PRODUSE:
{json.dumps(products_for_ai, indent=2, ensure_ascii=False)}

FORMULA GENERALĂ:
Cantitate = Media_Zilnica × (Lead_Time + Safety_Stock×CoefDim + 60_zile) - Stoc_Actual

REGULI:
- Coef.Dim: mici (060,080)=1.15, medii=1.0, mari (200+)=0.8
- Stoc_Dezechilibrat_Familie=DA înseamnă că proporția stocului nu corespunde cu proporția vânzărilor în familie

INSTRUCȚIUNI:
1. GÂNDEȘTE PAS CU PAS (arată-ți raționamentul):
   - Pentru FIECARE produs, arată cum aplici formula cu numerele concrete
   - Verifică dacă trendul (+/-) justifică sau contrazice sugestia
   - Dacă familia e dezechilibrată, explică impactul

2. AVOCATUL DIAVOLULUI (la final):
   - Ce fracturi logice vezi în aceste calcule?
   - Se ține cont corect de sezonalitate? (nu avem date)
   - Pentru familii dezechilibrate: are sens să comanzi mai mult din dimensiunile slabe?
   - Ce informații lipsesc pentru o decizie mai bună?

FII CONCIS dar arată-ți raționamentul. Răspunde în română."""
                    
                    # Get model name
                    model_name = gemini_cfg.get("model", "gemini-2.0-flash-exp")
                    
                    st.markdown("---")
                    
                    # Show model being used
                    st.markdown(f"**🤖 Model AI:** `{model_name}`")
                    
                    # Show prompt in expander
                    with st.expander("📝 Prompt trimis la AI (click pentru a vedea)", expanded=False):
                        st.code(prompt, language="markdown")
                    
                    # Show AI thinking in real-time using streaming
                    st.markdown("### 🧠 AI Gândește... (live)")
                    
                    # Create placeholder for streaming output - simple like chat
                    thinking_placeholder = st.empty()
                    full_response = ""
                    
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=gemini_cfg["api_key"])
                        
                        # Configure model for chain of thought
                        generation_config = {
                            "temperature": 0.7,
                            "top_p": 0.95,
                            "max_output_tokens": 4096,
                        }
                        
                        model = genai.GenerativeModel(
                            model_name,
                            generation_config=generation_config
                        )
                        
                        # Use streaming to show AI thinking in real-time
                        response = model.generate_content(prompt, stream=True)
                        
                        for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                                # Simple markdown display - like chat, no fancy styling
                                thinking_placeholder.markdown(full_response + "▌")
                        
                        # Final display without cursor
                        thinking_placeholder.markdown(full_response)
                        st.success("✅ Analiză completă!")
                        
                    except Exception as e:
                        st.error(f"❌ Eroare AI: {e}")
        
        return edited_df
    
    # Legacy function for compatibility (OVERSTOCK and ALL DATA)
    def render_table(product_list, show_order=False):
        if not product_list:
            st.info("Nu exista produse in aceasta categorie")
            return None
        data = []
        for p in product_list:
            trend_pct = None
            if p.vanzari_2024 > 0 and p.vanzari_2025 > 0:
                trend_pct = round(((p.vanzari_2025 - p.vanzari_2024) / p.vanzari_2024) * 100, 0)
            elif p.vanzari_2025 > 0 and p.vanzari_2024 == 0:
                trend_pct = 100
            elif p.vanzari_2024 > 0 and p.vanzari_2025 == 0:
                trend_pct = -100
            
            row = {
                "Cod Produs": p.nr_art,
                "Denumire Produs": (p.nume_produs[:28] + "...") if len(p.nume_produs) > 28 else p.nume_produs,
                "Familie": p.familie if p.familie else "-",
                "Furnizor": (p.furnizor[:16] + "...") if len(p.furnizor) > 16 else p.furnizor,
                "Stare": p.stare_pm,
                "Stoc Disponibil": int(p.total_stock),
                "In Tranzit": int(p.stoc_in_tranzit),
                "Vanzari 4 Luni": int(p.vanzari_ultimele_4_luni),
                "Media Zilnica": round(p.avg_daily_sales, 2),
                "Zile Acoperire": round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999.0,
                "Timp Livrare": p.lead_time_days,
                "Cost Unitar": round(p.cost_achizitie, 2),
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        st.dataframe(df, width="stretch", height=400)
        return df
    
    with tab_critical:
        with st.expander("ℹ️ Cum se calculeaza CRITICAL? (click pentru detalii)", expanded=False):
            st.markdown("""
**Conditie:** `Zile Acoperire < Lead Time`

**Ce inseamna:** Marfa comandata AZI nu va ajunge la timp. Stocul se va epuiza INAINTE de receptia noii comenzi.

**Formula Zile Acoperire:**
```
Zile Acoperire = (Stoc Disponibil + Stoc Tranzit) / Vanzari Medii Zilnice
```

**Vanzari Medii Zilnice** = Vanzari ultimele 4 luni / 120 zile

**Actiune recomandata:** Comanda EXPRESS sau cauta furnizor alternativ URGENT!
            """)
        st.markdown("**🔢 Bifează produsele și apasă 'Calculează Selectate' pentru a vedea cantitățile sugerate**")
        
        # Lazy Load Logic for CRITICAL (same as other tabs)
        if use_postgres:
            with st.spinner("Se încarcă produsele CRITICAL..."):
                seg_products = parse_from_postgres(load_segment_from_db("CRITICAL", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=1000
                ), config)
            render_interactive_table(seg_products, "CRITICAL", allow_order=True)
        else:
            render_interactive_table(segments["CRITICAL"], "CRITICAL", allow_order=True)
    
    with tab_urgent:
        with st.expander("ℹ️ Cum se calculeaza URGENT? (click pentru detalii)", expanded=False):
            st.markdown("""
**Conditie:** `Lead Time <= Zile Acoperire < Lead Time + Safety Stock`

**Ce inseamna:** Marfa poate ajunge la timp, dar fara margine de siguranta. Orice intarziere sau varf de vanzari = STOCKOUT.

**Exemplu:** Lead Time = 30 zile, Safety Stock = 7 zile
- Daca Zile Acoperire = 32, esti in zona URGENT (intre 30 si 37)

**Ce inseamna:** Stocul acopera timpul de livrare, dar intri in Safety Stock. Risc de ruptura daca vanzarile cresc.
**Actiune recomandata:** Comanda Acum.
            """)
        st.markdown("**🔢 Bifează produsele și apasă 'Calculează Selectate' pentru a vedea cantitățile sugerate**")
        
        # Lazy Load Logic
        if use_postgres:
            with st.spinner("Se încarcă produsele URGENT..."):
                seg_products = parse_from_postgres(load_segment_from_db("URGENT", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=1000
                ), config)
            render_interactive_table(seg_products, "URGENT")
        else:
            render_interactive_table(segments["URGENT"], "URGENT", allow_order=True)
    
    with tab_attention:
        with st.expander("ℹ️ Cum se calculeaza ATTENTION? (click pentru detalii)", expanded=False):
            st.markdown("""
**Conditie:** `Lead Time + Safety Stock <= Zile Acoperire < Lead Time + Safety Stock + 14 zile`

**Ce inseamna:** Ai ~2 saptamani sa planifici comanda. Stocul este "la limita" dar nu urgent.

**Actiune recomandata:** Planifica comanda, verifica MOQ (Minimum Order Quantity), negociaza cu furnizorul.
            """)
        st.markdown("**🔢 Bifează produsele și apasă 'Calculează Selectate' pentru a vedea cantitățile sugerate**")
        
        # Lazy Load Logic
        if use_postgres:
            with st.spinner("Se încarcă produsele ATTENTION..."):
                seg_products = parse_from_postgres(load_segment_from_db("ATTENTION", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=1000
                ), config)
            render_interactive_table(seg_products, "ATTENTION", allow_order=True)
        else:
            render_interactive_table(segments["ATTENTION"], "ATTENTION", allow_order=True)
    
    with tab_ok:
        with st.expander("ℹ️ Cum se calculeaza OK? (click pentru detalii)", expanded=False):
            st.markdown("""
**Conditie:** `Lead Time + Safety Stock + 14 zile <= Zile Acoperire <= 90 zile`

**Ce inseamna:** Stocul este sanatos. Ai suficienta marfa pentru a acoperi cererea curenta.

**Actiune recomandata:** Monitorizare saptamanala. Nu e nevoie de actiune imediata.
            """)
        st.markdown("**🔢 Bifează produsele și apasă 'Calculează Selectate' pentru a vedea cantitățile sugerate**")
        
        # Lazy Load Logic
        if use_postgres:
            with st.spinner("Se încarcă produsele OK..."):
                seg_products = parse_from_postgres(load_segment_from_db("OK", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=1000
                ), config)
            render_interactive_table(seg_products, "OK", allow_order=True)
        else:
            render_interactive_table(segments["OK"], "OK", allow_order=True)
    
    with tab_overstock:
        with st.expander("ℹ️ Cum se calculeaza OVERSTOCK? (click pentru detalii)", expanded=False):
            st.markdown("""
**Conditie:** `Zile Acoperire > 90 zile`

**Ce inseamna:** Ai prea multa marfa pe stoc. Capital blocat, risc de depreciere sau uzura morala.

**Calcul valoare blocata:**
```
Valoare Stoc = Cantitate x Cost Achizitie
```

**Actiune recomandata:** 
- Promotii sau reduceri pentru a accelera vanzarile
- Reducerea sau oprirea comenzilor viitoare
- Analiza cauza: Sezonalitate? Produs in declin? Eroare de forecast?
            """)
        st.markdown("")
        # OVERSTOCK doesn't need order calculation
        
        if use_postgres:
            # Load lazy
            with st.spinner("Se încarcă produsele OVERSTOCK..."):
                seg_products = parse_from_postgres(load_segment_from_db("OVERSTOCK", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=1000
                ), config)
            render_interactive_table(seg_products, "OVERSTOCK", allow_order=False)
            
            # Use pre-calculated stats for total value
            total = segment_stats.get("OVERSTOCK", {}).get("value", 0)
        else:
            render_interactive_table(segments["OVERSTOCK"], "OVERSTOCK", allow_order=False)
            total = sum(p.stock_value for p in segments["OVERSTOCK"])
            
        st.markdown(f"**💰 Total overstock: {total:,.0f} RON**")
    
    # ============================================================
    # ALL DATA TAB
    # ============================================================
    with tab_all:
        st.markdown("### 📋 Toate Datele")
        
        if use_postgres:
            # Get total count for pagination
            from src.core.database import get_product_count
            try:
                total_products = get_product_count()
            except:
                total_products = 10000  # Fallback
            
            page_size = 500
            total_pages = (total_products // page_size) + 1
            
            # Sort and Pagination controls
            st.markdown(f"**Total produse în baza de date: {total_products:,}**")
            
            col_sort, col_dir, col_page = st.columns([2, 1, 2])
            with col_sort:
                sort_options = {
                    "Cod Articol": "cod_articol",
                    "Stoc Total (cel mai mare)": "stoc_total",
                    "Vânzări 4 Luni (cele mai mari)": "vanzari_4luni",
                    "Vânzări 360 Zile": "vanzari_360z",
                    "Zile Acoperire": "days_of_coverage",
                    "Cost Achiziție": "cost_achizitie",
                    "Preț Vânzare": "pret_vanzare",
                }
                sort_label = st.selectbox("📊 Sortează după", list(sort_options.keys()), key="all_data_sort")
                sort_column = sort_options[sort_label]
            with col_dir:
                sort_dir = st.selectbox("Direcție", ["DESC", "ASC"], key="all_data_dir")
            with col_page:
                current_page = st.number_input("Pagina", min_value=1, max_value=total_pages, value=1, key="all_data_page")
            
            offset = (current_page - 1) * page_size
            st.markdown(f"*Afișează produsele {offset + 1} - {min(offset + page_size, total_products)} din {total_products}, sortate {sort_label} ({sort_dir})*")
            
            # Load current page with sorting
            with st.spinner(f"Se încarcă pagina {current_page} sortată după {sort_label}..."):
                raw_all = load_products_from_db(
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=page_size,
                    offset=offset,
                    order_by=sort_column,
                    order_dir=sort_dir
                )
                all_products = parse_from_postgres(raw_all, config)
            render_interactive_table(all_products, "ALL", allow_order=True)
        else:
            st.markdown(f"**Total produse: {len(products)}**")
            # Use legacy table for CSV mode to show everything (might be slow)
            render_table(products)
    
    # ============================================================
    # FAMILY VIEW TAB
    # ============================================================
    with tab_family:
        st.markdown("### 👨‍👩‍👧‍👦 Family View - Analiza pe Game de Produse")
        st.markdown("*Vizualizează și compară toate dimensiunile dintr-o familie de covoare*")
        
        # Get unique families
        if use_postgres:
            all_families = get_unique_families()
        else:
            all_families = sorted(set(p.familie for p in products if p.familie))
        
        if not all_families:
            st.info("Nu există familii de produse identificate. Această funcție funcționează pentru produse de tip COVOR [FAMILIE] [DIMENSIUNE].")
        else:
            selected_family = st.selectbox("🔍 Selectează Familia", ["(alege o familie)"] + all_families, key="family_select")
            
            if selected_family and selected_family != "(alege o familie)":
                # Filter products for this family
                if use_postgres:
                    with st.spinner(f"Se încarcă familia {selected_family}..."):
                        raw_fam_df = load_family_products_from_db(selected_family)
                        family_products = parse_from_postgres(raw_fam_df, config)
                else:
                    family_products = [p for p in products if p.familie == selected_family]
                
                if family_products:
                    # Analyze family balance
                    st.markdown(f"#### 📊 Analiza Familie: **{selected_family}** ({len(family_products)} dimensiuni)")
                    
                    # Build summary table
                    family_data = []
                    total_sales = sum(p.vanzari_ultimele_4_luni for p in family_products)
                    total_stock = sum(p.total_stock for p in family_products)
                    
                    imbalances = []
                    
                    for p in sorted(family_products, key=lambda x: x.dimensiune):
                        sales_pct = (p.vanzari_ultimele_4_luni / total_sales * 100) if total_sales > 0 else 0
                        stock_pct = (p.total_stock / total_stock * 100) if total_stock > 0 else 0
                        
                        # Detect imbalance
                        balance_status = "✅"
                        if p.segment == "CRITICAL":
                            balance_status = "🔴 CRITICAL"
                            imbalances.append(f"{p.dimensiune} este CRITICAL!")
                        elif p.segment == "URGENT":
                            balance_status = "🟠 URGENT"
                            imbalances.append(f"{p.dimensiune} este URGENT")
                        elif p.segment == "OVERSTOCK":
                            balance_status = "🔵 OVERSTOCK"
                            imbalances.append(f"{p.dimensiune} este OVERSTOCK")
                        
                        family_data.append({
                            "Dimensiune": p.dimensiune,
                            "Status": balance_status,
                            "Stoc": int(p.total_stock),
                            "Tranzit": int(p.stoc_in_tranzit),
                            "Vânzări 4L": int(p.vanzari_ultimele_4_luni),
                            "% Vânzări": f"{sales_pct:.1f}%",
                            "% Stoc": f"{stock_pct:.1f}%",
                            "Zile Ac.": round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999,
                            "Coef.": p.dimension_coefficient,
                        })
                    
                    # Show imbalances
                    if imbalances:
                        st.warning(f"⚠️ **Dezechilibru detectat:** {', '.join(imbalances)}")
                    else:
                        st.success("✅ Familia este echilibrată")
                    
                    # Display family table
                    family_df = pd.DataFrame(family_data)
                    st.dataframe(family_df, width="stretch", hide_index=True)
                    
                    # Calculate balanced order button
                    if st.button("📊 Calculează Comandă Echilibrată pentru Familie", key="calc_family", type="primary"):
                        results = []
                        total_value = 0
                        for p in family_products:
                            qty = int(p.suggested_order_qty)
                            if qty > 0:
                                value = qty * p.cost_achizitie
                                total_value += value
                                results.append({
                                    "Dimensiune": p.dimensiune,
                                    "Stoc Actual": int(p.total_stock),
                                    "Cantitate Sugerată": qty,
                                    "Coef. Dimensiune": p.dimension_coefficient,
                                    "Valoare": round(value, 2),
                                })
                        
                        if results:
                            st.markdown("---")
                            st.markdown(f"### 📦 Comandă Sugerată pentru {selected_family}")
                            result_df = pd.DataFrame(results)
                            st.dataframe(result_df, width="stretch", hide_index=True)
                            st.markdown(f"**💰 Valoare totală: {total_value:,.2f} RON**")
                            
                            # AI Verification
                            if st.button("🤖 Verifică cu AI", key="ai_family", type="secondary"):
                                if gemini_cfg.get("api_key"):
                                    with st.spinner("Analizăm familia cu AI..."):
                                        prompt = f"""Analizează comanda pentru familia de covoare {selected_family}:

PRODUSE DIN FAMILIE:
{json.dumps(results, indent=2, ensure_ascii=False)}

VALOARE TOTALĂ: {total_value:,.2f} RON

Verifică:
1. Este distribuția pe dimensiuni echilibrată?
2. Există riscuri de stoc mort?
3. Sugestii de ajustare?

Răspunde concis în română."""
                                        try:
                                            import google.generativeai as genai
                                            genai.configure(api_key=gemini_cfg["api_key"])
                                            model = genai.GenerativeModel(gemini_cfg.get("model", "gemini-pro-latest"))
                                            response = model.generate_content(prompt)
                                            st.markdown("#### 🤖 Analiza AI:")
                                            st.markdown(response.text)
                                        except Exception as e:
                                            st.error(f"Eroare AI: {e}")
                                else:
                                    st.warning("⚠️ Configurează API key în Settings > Gemini API")
                            
                            result_csv = result_df.to_csv(index=False).encode('utf-8')
                            st.download_button("📥 Export Comandă Familie", result_csv, f"comanda_{selected_family.lower()}.csv", "text/csv", key="exp_family")
                        else:
                            st.info("Nu sunt necesare comenzi pentru această familie.")
    
    
    with tab_all:
        with st.expander("ℹ️ Explicatii coloane si formule (click pentru detalii)", expanded=False):
            st.markdown("""
**Coloane din tabel:**

| Coloana | Semnificatie |
|---------|-------------|
| **Segment** | Clasificarea automata (CRITICAL/URGENT/ATTENTION/OK/OVERSTOCK) |
| **SKU** | Codul produsului (NR ART) |
| **Stock** | Stoc Disponibil Total (Magazine + Depozit + Accesorii + Outlet) |
| **Transit** | Cantitate comandata, in drum de la furnizor (nereceptionata) |
| **S.4mo** | Vanzari cantitative din ultimele 4 luni |
| **S.360d** | Vanzari cantitative pe ultimele 360 zile (perspectiva anuala) |
| **2024** | Vanzari totale in anul 2024 |
| **2025** | Vanzari totale in anul 2025 (pana la data curenta) |
| **Trend%** | Trend YoY = ((2025 - 2024) / 2024) × 100. Valori pozitive = crestere, negative = scadere |
| **Day Avg** | Vanzari medii zilnice (baza calculului pentru Zile Acoperire) |
| **Days Cov.** | Zile de acoperire = cate zile mai poti vinde cu stocul actual |
| **Lead** | Timp de livrare configurat pentru furnizor (zile) |
| **Cost** | Cost de achizitie unitar (ultimul NIR) |
| **Order Qty** | Cantitate sugerata pentru comanda (rotunjita la MOQ) |

---

**Indicatori pentru Sezonalitate / Trend:**

🔺 **Trend% pozitiv** = Produsul se vinde mai bine in 2025 comparativ cu 2024. Posibil trend ascendent sau sezonalitate favorabila.

🔻 **Trend% negativ** = Scadere vanzari. Verifica daca este sezonalitate (ex: produse de vara) sau declin permanent.

⚠️ **Atentie la OVERSTOCK cu Trend negativ** = Capital blocat in produse care se vand din ce in ce mai putin.

---

**Formule cheie:**

```
Vanzari Medii Zilnice = Vanzari 4 luni / 120
Zile Acoperire = (Stoc + Tranzit) / Vanzari Medii Zilnice
Prag Reaprovizionare = Lead Time + Safety Stock
Cantitate Sugerata = Vanzari Medii Zilnice × (Lead Time + Safety Stock + 60) - Stoc - Tranzit
```

---

💡 **Sfat:** Compara coloanele 2024 vs 2025 pentru a identifica produse cu sezonalitate sau trend descendent inainte de a plasa comenzi mari.
            """)
        st.markdown(f"**Total: {len(products)} produse**")
        all_data = [{
            "Segment": p.segment, "SKU": p.nr_art, 
            "Product": p.nume_produs[:30] if p.nume_produs else "-",
            "Supplier": p.furnizor[:20] if p.furnizor else "-",
            "Status": p.stare_pm,
            "Stock": int(p.total_stock), 
            "Days Cov.": round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999.0,
            "Value": round(p.stock_value, 2)
        } for p in products]
        df_all = pd.DataFrame(all_data)
        st.dataframe(df_all, width='stretch', height=500)
        csv = df_all.to_csv(index=False).encode('utf-8')
        st.download_button("Export All", csv, "full_inventory.csv", "text/csv")
    
    # ============================================================
    # SUPPLIER AUDIT TAB
    # ============================================================
    with tab_audit:
        st.markdown("### Supplier Audit & AI Analysis")
        
        audit_supplier = st.selectbox("Select Supplier for Audit", suppliers, key="audit_sup")
        
        if audit_supplier:
            sup_products = [p for p in products if p.furnizor == audit_supplier]
            
            if sup_products:
                # Supplier summary
                sup_segments = {"CRITICAL": 0, "URGENT": 0, "ATTENTION": 0, "OK": 0, "OVERSTOCK": 0}
                for p in sup_products:
                    sup_segments[p.segment] += 1
                
                total_stock_value = sum(p.stock_value for p in sup_products)
                total_items = len(sup_products)
                avg_coverage = sum(p.days_of_coverage for p in sup_products if p.days_of_coverage < 999) / max(1, len([p for p in sup_products if p.days_of_coverage < 999]))
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Items", total_items)
                col2.metric("Stock Value", f"{total_stock_value:,.0f} RON")
                col3.metric("Avg Coverage", f"{avg_coverage:.0f} days")
                col4.metric("Critical", sup_segments["CRITICAL"])
                
                st.markdown("#### Segment Distribution")
                seg_df = pd.DataFrame([{"Segment": k, "Count": v, "Pct": f"{v/total_items*100:.1f}%"} for k, v in sup_segments.items()])
                st.dataframe(seg_df, width='stretch')
                
                # Export for this supplier
                st.markdown("#### Export")
                sup_data = [{
                    "SKU": p.nr_art, "Product": p.nume_produs, "Segment": p.segment,
                    "Stock": int(p.total_stock), "Transit": int(p.stoc_in_tranzit),
                    "Sales 4mo": int(p.vanzari_ultimele_4_luni), "Days Coverage": round(p.days_of_coverage, 1),
                    "Cost": p.cost_achizitie, "Stock Value": round(p.stock_value, 2),
                    "Suggested Order": int(p.suggested_order_qty)
                } for p in sup_products]
                sup_df = pd.DataFrame(sup_data)
                csv = sup_df.to_csv(index=False).encode('utf-8')
                st.download_button(f"Export {audit_supplier[:20]} Audit", csv, f"audit_{audit_supplier[:15]}.csv", "text/csv")
                
                # AI Analysis
                st.markdown("---")
                st.markdown("#### AI Analysis (Gemini)")
                
                if gemini_cfg.get("api_key"):
                    if st.button("Analyze with Gemini", key="run_gemini"):
                        with st.spinner("Analyzing with Gemini..."):
                            supplier_summary = {
                                "furnizor": audit_supplier,
                                "total_items": total_items,
                                "stock_value_ron": total_stock_value,
                                "avg_coverage_days": round(avg_coverage, 1),
                                "segments": sup_segments,
                                "current_config": config.get(audit_supplier, default_cfg)
                            }
                            sample_products = sup_data[:20]  # First 20 for context
                            
                            result = analyze_with_gemini(
                                gemini_cfg["api_key"],
                                gemini_cfg.get("model", "gemini-pro-latest"),
                                supplier_summary, 
                                json.dumps(sample_products, indent=2, ensure_ascii=False)
                            )
                            st.markdown("##### AI Recommendations")
                            st.markdown(result)
                else:
                    st.warning("Configure Gemini API key in Settings first")
            else:
                st.info("No products for this supplier with current filters")


if __name__ == "__main__":
    main()
