import streamlit as st
import pandas as pd
import os
import sys
import json

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.loader import DataLoader
from src.models.product import Product, get_sales_ref_month_yoy
from src.core.database import (
    load_products_from_db, get_unique_suppliers, get_unique_statuses, 
    load_products_from_db, get_unique_suppliers, get_unique_statuses, 
    test_connection, get_segment_counts, load_segment_from_db,
    get_unique_families, load_family_products_from_db,
    get_subclass_summary, load_subclass_products
)
from src.core.processor import process_products_vectorized
from types import SimpleNamespace
from src.core.cubaj_loader import get_cubaj_map, get_cubaj_stats
from src.ui.order_builder import render_order_builder_v2

# ============================================================
# CONFIG
# ============================================================
CONFIG_PATH = "data/supplier_config.json"
GEMINI_CONFIG_PATH = "data/gemini_config.json"
SEASONALITY_PATH = "data/seasonality_index.json"
ADVANCED_TRENDS_PATH = "data/advanced_trends.json"

def load_supplier_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"default": {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1}}

def load_seasonality_index():
    """Load pre-computed seasonality index from JSON"""
    if os.path.exists(SEASONALITY_PATH):
        with open(SEASONALITY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_advanced_trends():
    """Load pre-computed advanced trends from JSON"""
    if os.path.exists(ADVANCED_TRENDS_PATH):
        with open(ADVANCED_TRENDS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

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


def sync_supplier_to_db(supplier_name, lead_time, safety_stock, moq):
    """
    Sync supplier config to DB and recalculate segments for that supplier.
    This updates lead_time_days, safety_stock_days, moq AND recalculates segments.
    """
    try:
        from src.core.database import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            # 1. Update config columns for this supplier
            conn.execute(text("""
                UPDATE products SET 
                    lead_time_days = :lt, 
                    safety_stock_days = :ss, 
                    moq = :moq
                WHERE furnizor = :furn
            """), {"lt": lead_time, "ss": safety_stock, "moq": moq, "furn": supplier_name})
            
            # 2. Recalculate avg_daily_sales and days_of_coverage for this supplier
            conn.execute(text("""
                UPDATE products SET 
                    avg_daily_sales = COALESCE(vanzari_4luni, 0) / 120.0,
                    days_of_coverage = CASE 
                        WHEN COALESCE(vanzari_4luni, 0) = 0 THEN 999
                        ELSE (COALESCE(stoc_total, 0) + COALESCE(stoc_tranzit, 0)) / (COALESCE(vanzari_4luni, 0) / 120.0)
                    END
                WHERE furnizor = :furn
            """), {"furn": supplier_name})
            
            # 3. Recalculate segments for this supplier
            # CRITICAL
            conn.execute(text("""
                UPDATE products SET segment = 'CRITICAL'
                WHERE furnizor = :furn AND days_of_coverage < lead_time_days
            """), {"furn": supplier_name})
            
            # URGENT
            conn.execute(text("""
                UPDATE products SET segment = 'URGENT'
                WHERE furnizor = :furn 
                AND segment != 'CRITICAL'
                AND days_of_coverage >= lead_time_days
                AND days_of_coverage < (lead_time_days + safety_stock_days)
            """), {"furn": supplier_name})
            
            # ATTENTION
            conn.execute(text("""
                UPDATE products SET segment = 'ATTENTION'
                WHERE furnizor = :furn 
                AND segment NOT IN ('CRITICAL', 'URGENT')
                AND days_of_coverage >= (lead_time_days + safety_stock_days)
                AND days_of_coverage < (lead_time_days + safety_stock_days + 30)
            """), {"furn": supplier_name})
            
            # OVERSTOCK
            conn.execute(text("""
                UPDATE products SET segment = 'OVERSTOCK'
                WHERE furnizor = :furn 
                AND segment NOT IN ('CRITICAL', 'URGENT', 'ATTENTION')
                AND days_of_coverage > 180
            """), {"furn": supplier_name})
            
            # OK (everything else)
            conn.execute(text("""
                UPDATE products SET segment = 'OK'
                WHERE furnizor = :furn 
                AND segment NOT IN ('CRITICAL', 'URGENT', 'ATTENTION', 'OVERSTOCK')
            """), {"furn": supplier_name})
            
            conn.commit()
            return True, "OK"
    except Exception as e:
        return False, str(e)

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="INDOMEX Aprovizionare v27.01 11:05",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# COMPACT ENTERPRISE THEME
# ============================================================
st.markdown("""
<style>
    /* Base */
    .stApp { background-color: #f8f9fa; }
    section[data-testid="stSidebar"] { 
        background-color: #ffffff; 
        border-right: 1px solid #e0e0e0;
        width: 260px !important;
    }
    section[data-testid="stSidebar"] > div { padding-top: 1rem !important; }
    
    /* Reduce vertical margins */
    .block-container { padding-top: 1rem !important; padding-bottom: 0 !important; }
    .element-container { margin-bottom: 0.25rem !important; }
    
    /* Headers - smaller */
    h1, h2, h3 { color: #1a1a2e !important; font-weight: 600 !important; margin-bottom: 0.5rem !important; }
    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.2rem !important; }
    h3 { font-size: 1rem !important; }
    
    /* Metrics - compact */
    [data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px; }
    [data-testid="stMetricLabel"] { color: #6c757d !important; font-size: 0.7rem !important; }
    [data-testid="stMetricValue"] { color: #212529 !important; font-family: 'Consolas', monospace !important; font-size: 1rem !important; }
    
    /* Data table */
    .stDataFrame { border: 1px solid #dee2e6 !important; border-radius: 6px; }
    .stDataFrame thead th { background-color: #f1f3f4 !important; color: #495057 !important; font-size: 0.7rem !important; text-transform: uppercase; font-weight: 600 !important; padding: 6px !important; }
    .stDataFrame tbody td { background-color: #ffffff !important; color: #212529 !important; font-family: 'Consolas', monospace !important; font-size: 0.8rem !important; padding: 4px 6px !important; }
    
    /* Tabs - compact, sticky */
    .stTabs [data-baseweb="tab-list"] { 
        background-color: #ffffff; 
        border-bottom: 2px solid #e0e0e0; 
        position: sticky; 
        top: 0; 
        z-index: 100;
        padding: 0 !important;
    }
    .stTabs [data-baseweb="tab"] { background-color: transparent; color: #6c757d; border: none; padding: 8px 12px; font-size: 0.8rem; font-weight: 500; }
    .stTabs [aria-selected="true"] { color: #1a1a2e !important; border-bottom: 3px solid #3b82f6 !important; background: #f8f9fa; }
    
    /* Buttons - compact */
    .stButton > button { background-color: #3b82f6; color: white; border: none; border-radius: 4px; font-size: 0.8rem; font-weight: 500; padding: 6px 12px; }
    .stButton > button:hover { background-color: #2563eb; }
    
    /* Inputs - compact */
    .stTextInput input, .stSelectbox select { font-size: 0.85rem !important; padding: 4px 8px !important; }
    .stTextInput > div > div, .stSelectbox > div > div { min-height: 32px !important; }
    
    /* Hide streamlit extras */
    #MainMenu, footer, header { visibility: hidden; }
    
    /* Expander compact */
    .streamlit-expanderHeader { font-size: 0.85rem !important; padding: 8px !important; }
    
    /* Sidebar inputs - compact */
    section[data-testid="stSidebar"] .stTextInput input,
    section[data-testid="stSidebar"] .stSelectbox select,
    section[data-testid="stSidebar"] .stNumberInput input { font-size: 0.85rem !important; }
    
    /* Red Alert - Critical coverage styling */
    .critical-alert {
        color: #dc2626 !important;
        font-weight: 700 !important;
    }
    .critical-row {
        background-color: #fef2f2 !important;
    }
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
    seasonality_data = load_seasonality_index()  # Load at startup
    advanced_trends_data = load_advanced_trends()  # Load advanced trends
    cubaj_data = get_cubaj_map()  # Load cubaj/logistics data
    default_cfg = config.get("default", {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1})
    
    # Initialize ORDER BUILDER session state at top level for persistence
    if "order_items" not in st.session_state:
        st.session_state.order_items = {}
    if "current_subclass" not in st.session_state:
        st.session_state.current_subclass = None
    if "current_subclass_supplier" not in st.session_state:
        st.session_state.current_subclass_supplier = None
    
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
        st.header("Indomex Aprovizionare")
        st.caption("v27.01 11:10 - Lead Time Alert")
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
                                # Sync to DB and recalculate segments
                                success, msg = sync_supplier_to_db(new_supplier_name, sup_lt, sup_ss, sup_moq)
                                if success:
                                    st.success(f"Salvat si sincronizat: {new_supplier_name}")
                                else:
                                    st.warning(f"Salvat in JSON, dar eroare DB: {msg}")
                                st.cache_data.clear()
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
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Build: 26.01.2026 (Clean UI)")
    
    # ============================================================
    # SIDEBAR - COMPACT FILTERS
    # ============================================================
    
    # Data Source Toggle (compact)
    use_postgres = st.sidebar.toggle("PostgreSQL", value=True, help="Folosește PostgreSQL pentru viteză")
    
    if use_postgres:
        success, msg = test_connection()
        if success:
            suppliers = get_unique_suppliers()
            pm_statuses = get_unique_statuses()
            
            selected_supplier = st.sidebar.selectbox("Furnizor", ["ALL"] + suppliers, key="pg_supplier")
            selected_status = st.sidebar.selectbox("Stare PM", ["ALL"] + pm_statuses, key="pg_status")
            
            with st.spinner("Incarcare..."):
                raw_df = load_products_from_db(
                    furnizor=selected_supplier if selected_supplier != "ALL" else None,
                    stare_pm=selected_status if selected_status != "ALL" else None
                )
        else:
            st.sidebar.error(f"Nu pot conecta la PostgreSQL: {msg}")
            use_postgres = False
    
    if not use_postgres:
        data_files = [f for f in os.listdir("data") if f.endswith('.csv')] if os.path.exists("data") else []
        if not data_files:
            st.sidebar.warning("No CSV in /data")
            return
        
        selected_file = st.sidebar.selectbox("Fișier", data_files, 
            index=data_files.index("Tcioara Forecast_.csv") if "Tcioara Forecast_.csv" in data_files else 0,
            key="csv_file")
        data_path = f"data/{selected_file}"
        
        @st.cache_data(show_spinner=False)
        def load_raw(path):
            loader = DataLoader(path)
            loader.load_data()
            return loader.df
        
        with st.spinner("Incarcare CSV..."):
            try:
                raw_df = load_raw(data_path)
            except Exception as e:
                st.error(f"Eroare: {e}")
                return
        
        suppliers = sorted(raw_df["FURNIZOR EXT"].dropna().unique().tolist()) if "FURNIZOR EXT" in raw_df.columns else []
        pm_statuses = sorted(raw_df["STARE PM"].dropna().unique().tolist()) if "STARE PM" in raw_df.columns else []
        
        selected_supplier = st.sidebar.selectbox("Furnizor", ["ALL"] + suppliers, key="csv_supplier")
        selected_status = st.sidebar.selectbox("Stare PM", ["ALL"] + pm_statuses, key="csv_status")
    
    # Supplier Config (collapsed by default)
    if selected_supplier != "ALL":
        with st.sidebar.expander(f"Config: {selected_supplier[:20]}...", expanded=False):
            current_cfg = config.get(selected_supplier, default_cfg.copy())
            sup_lt = st.number_input("Lead Time", value=int(current_cfg.get("lead_time_days", 30)), min_value=1, max_value=180, key="sb_lt")
            sup_ss = st.number_input("Safety Stock", value=float(current_cfg.get("safety_stock_days", 7)), min_value=0.0, key="sb_ss")
            sup_moq = st.number_input("MOQ", value=float(current_cfg.get("moq", 1)), min_value=1.0, key="sb_moq")
            
            if st.button("Salveaza", key="sb_save"):
                config[selected_supplier] = {"lead_time_days": sup_lt, "safety_stock_days": sup_ss, "moq": sup_moq}
                save_supplier_config(config)
                # Sync to DB and recalculate segments
                success, msg = sync_supplier_to_db(selected_supplier, sup_lt, sup_ss, sup_moq)
                if success:
                    st.success("Salvat si sincronizat!")
                else:
                    st.warning(f"Salvat in JSON, dar eroare DB: {msg}")
                st.cache_data.clear()
                st.rerun()
    
    # ============================================================
    # PARSE PRODUCTS
    # ============================================================
    
    def parse_from_postgres(df, cfg, seasonality_data=None, advanced_trends_data=None, cubaj_data=None):
        """Parse products from PostgreSQL DataFrame (different column names)"""
        products = []
        default = cfg.get("default", {"lead_time_days": 30, "safety_stock_days": 7, "moq": 1})
        seasonality_data = seasonality_data or {}
        advanced_trends_data = advanced_trends_data or {}
        cubaj_data = cubaj_data or {}
        
        for _, row in df.iterrows():
            try:
                furnizor = str(row.get("furnizor", "")) if pd.notnull(row.get("furnizor")) else ""
                supplier_cfg = cfg.get(furnizor, default)
                cod = str(row.get("cod_articol", ""))
                
                # Get seasonality info for this product
                season_info = seasonality_data.get(cod, {})
                # Get advanced trends for this product
                trends_info = advanced_trends_data.get(cod, {})
                # Get cubaj/logistics info for this product
                cubaj_info = cubaj_data.get(cod, {})
                
                p = Product(
                    nr_art=cod,
                    cod_articol=cod,
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
                    moq=float(row.get("moq", 1) or 1),
                    # Seasonality fields
                    seasonality_index=float(season_info.get("seasonality_index", 1.0)),
                    is_rising_star=bool(season_info.get("is_rising_star", False)),
                    trend=str(season_info.get("trend", "STABLE")),
                    # Advanced Trends fields
                    yoy_growth=float(trends_info.get("yoy_growth", 0.0)),
                    acceleration=float(trends_info.get("acceleration", 0.0)),
                    volatility=float(trends_info.get("volatility", 1.0)),
                    repeat_rate=float(trends_info.get("repeat_rate", 0.0)),
                    peak_month=int(trends_info.get("peak_month", 0)),
                    # Historical sales data from DB
                    sales_history=json.loads(row.get("sales_history", "{}") or "{}") if isinstance(row.get("sales_history"), str) else (row.get("sales_history") or {}),
                    sales_last_3m=float(row.get("sales_last_3m", 0) or 0),
                    # Cubaj & Logistics
                    cubaj_m3=cubaj_info.get("cubaj_m3"),
                    masa_kg=cubaj_info.get("masa_kg")
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
    # UNIFIED NAVIGATION & KPI CARDS (Minimalist "Buttons in Cards")
    # ============================================================
    
    st.markdown("""
    <style>
        /* Modern Gradient Background (Subtle) */
        .stApp {
            background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
        }
        
        /* Glassmorphism Cards for Metrics */
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.7);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.5);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
        }
        
        /* Metric Label & Value Styling */
        [data-testid="stMetricLabel"] {
            font-size: 0.9rem !important;
            color: #64748b !important;
            font-weight: 600 !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.8rem !important;
            color: #0f172a !important;
            font-weight: 700 !important;
        }
        [data-testid="stMetricDelta"] {
            font-size: 0.8rem !important;
        }

        /* Sleek Button Styling */
        div.stButton > button {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 0.5rem 1rem;
            font-weight: 500;
            margin-top: 10px;
            width: 100%;
            transition: all 0.2s ease;
            box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3);
        }
        div.stButton > button:hover {
            background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
            box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.4);
            border-color: transparent;
        }
        div.stButton > button:active {
            transform: scale(0.98);
        }
        
        /* Active State Button Override */
        div.stButton > button[kind="secondary"] {
            background: transparent;
            color: #3b82f6;
            border: 1px solid #3b82f6;
            box-shadow: none;
        }
        div.stButton > button[kind="secondary"]:hover {
             background: rgba(59, 130, 246, 0.05);
        }
        
        /* Hide default header decoration */
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

    # Initialize State
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = "Critical"
    
    # Render 6 Columns (5 Segments + Order Builder)
    nav_cols = st.columns(6)
    
    seg_definitions = [
        ("CRITICAL", "Critical"), 
        ("URGENT", "Urgent"), 
        ("ATTENTION", "Attention"), 
        ("OK", "OK"), 
        ("OVERSTOCK", "Overstock")
    ]
    
    # Render Segment Cards
    for i, (seg_key, label) in enumerate(seg_definitions):
        count = segment_stats.get(seg_key, {}).get("count", 0)
        value = segment_stats.get(seg_key, {}).get("value", 0)
        
        with nav_cols[i]:
            # Metric Display
            st.metric(label, f"{count:,}", f"{value/1000:,.0f}k RON")
            
            # Selection Button
            is_active = (st.session_state.active_tab == label)
            btn_label = "Active" if is_active else "Select"
            if st.button(btn_label, key=f"nav_{seg_key}", 
                         type="primary" if is_active else "secondary", 
                         use_container_width=True):
                st.session_state.active_tab = label
                st.rerun()
                
    # Render Order Builder Card
    with nav_cols[5]:
        st.metric("Order Builder", "v2", "")
        if st.button("Open", key="nav_ob", type="secondary", use_container_width=True):
             st.switch_page("pages/1_Order_Builder.py")
             
    # Compatibility mapping for downstream logic
    selected_nav = st.session_state.active_tab
    
    st.markdown("---")
    
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
        
        # ============================================================
        # BUILD DATA - "BUYER 12" SIMPLIFIED COLUMNS
        # ============================================================
        from datetime import datetime
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # FIXED: Target months for comparison = Oct, Nov, Dec (2025 vs 2024)
        target_months = [10, 11, 12]  # Oct, Nov, Dec
        compare_year = 2025  # Current year to show
        prior_year = 2024    # Prior year for comparison
        
        month_names = {1: "Ian", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mai", 6: "Iun",
                       7: "Iul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
        
        data = []
        for p in sorted_products:
            # Get YoY data for Oct, Nov, Dec (2025 vs 2024)
            oct_data = get_sales_ref_month_yoy(p.sales_history, 10, compare_year)
            nov_data = get_sales_ref_month_yoy(p.sales_history, 11, compare_year)
            dec_data = get_sales_ref_month_yoy(p.sales_history, 12, compare_year)
            
            # Check if unbalanced within family
            is_unbal = is_unbalanced(p)
            
            # Calculate suggested quantity with formula explanation
            suggested_qty = int(p.suggested_order_qty)
            adjusted_safety = round(p.safety_stock_days * p.dimension_coefficient, 1)
            formula_text = f"Media: {p.avg_daily_sales:.2f}/zi × (Lead:{p.lead_time_days} + Safety:{adjusted_safety} + 60) - Stoc:{int(p.total_stock)} = {suggested_qty} buc"
            
            # ============================================================
            # PRIMARY COLUMNS (Always Visible - "Buyer 12")
            # Oct, Nov, Dec with 2025 vs 2024 comparison + Trend for Oct and Nov
            # ============================================================
            row = {
                "Selecteaza": False,  # Checkbox column
                # 0. Image
                "Img": p.image_url if hasattr(p, 'image_url') else None,
                # 1. Produs (Code + Name)
                "Produs": f"{p.nr_art} | {(p.nume_produs[:18] + '..' if len(p.nume_produs) > 18 else p.nume_produs)}",
                # 2. Pret (Cost / Sell)
                "Cost": round(p.cost_achizitie, 0),
                "PVanz": round(p.pret_vanzare, 0),
                # 3. Stoc Indomex (Primary - Furnizor)
                "Stoc Idx": int(p.stoc_indomex),
                # 4. Stoc Magazine (Network)
                "Stoc Mag": int(p.stoc_magazin_total),
                # 5. Sales Last 3 Months
                "V.3L": int(p.sales_last_3m) if p.sales_last_3m > 0 else int(p.vanzari_ultimele_4_luni),
                # 6-8. OCTOBER: 2025 vs 2024 + Trend
                "V.Oct'25": int(oct_data["current_year_sales"]),
                "V.Oct'24": int(oct_data["prior_year_sales"]),
                "Tr.Oct": f"{int(oct_data['yoy_pct']):+d}%" if oct_data["prior_year_sales"] > 0 else "-",
                # 9-11. NOVEMBER: 2025 vs 2024 + Trend
                "V.Nov'25": int(nov_data["current_year_sales"]),
                "V.Nov'24": int(nov_data["prior_year_sales"]),
                "Tr.Nov": f"{int(nov_data['yoy_pct']):+d}%" if nov_data["prior_year_sales"] > 0 else "-",
                # 12-13. DECEMBER: 2025 vs 2024 (no trend - future month)
                "V.Dec'25": int(dec_data["current_year_sales"]),
                "V.Dec'24": int(dec_data["prior_year_sales"]),
                # 14. Status + Suggested Qty
                "Status": p.segment,
                "NECESAR": suggested_qty,
                
                # ============================================================
                # LEAD TIME ALERT COLUMNS (Primary - always visible)
                # Marja = Zile Acoperire - Lead Time
                # Red alert (🔴) when Marja < 5
                # ============================================================
                "_marja_raw": (round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999) - p.lead_time_days,
                "Zile Ac.": f"🔴 {round(p.days_of_coverage, 1):.1f}" if ((round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999) - p.lead_time_days < 5 and p.days_of_coverage < 999) else (f"{round(p.days_of_coverage, 1):.1f}" if p.days_of_coverage < 999 else "999"),
                "Lead": f"🔴 {p.lead_time_days}" if ((round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999) - p.lead_time_days < 5 and p.days_of_coverage < 999) else str(p.lead_time_days),
                "Marja": f"🔴 {((round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999) - p.lead_time_days):.1f}" if ((round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999) - p.lead_time_days < 5 and p.days_of_coverage < 999) else f"{((round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999) - p.lead_time_days):.1f}",
                
                # ============================================================
                # SECONDARY COLUMNS (Hidden by default - show via toggle)
                # ============================================================
                "Cod": p.nr_art,
                "Denumire": p.nume_produs,
                "Familie": f"{p.familie}" if (p.familie and is_unbal) else (p.familie if p.familie else "-"),
                "Dim": p.dimensiune if p.dimensiune else "-",
                "Tranzit": int(p.stoc_in_tranzit),
                "V.4L": int(p.vanzari_ultimele_4_luni),
                "V.360": int(p.vanzari_ultimele_360_zile),
                "V.2024": int(p.vanzari_2024),
                "V.2025": int(p.vanzari_2025),
                "Med/Zi": round(p.avg_daily_sales, 2),
                "Sezon": round(p.seasonality_index, 2),
                "YoY%": f"{int(p.yoy_growth):+d}%" if p.yoy_growth != 0 else "-",
                "Clasa": p.clasa[:15] if p.clasa else "-",
                "Subclasa": p.subclasa[:15] if p.subclasa else "-",
                # Store stocks
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
                # Cubaj & Logistics
                "Cubaj": f"{p.cubaj_m3:.3f}" if p.cubaj_m3 else "N/A",
                "Masa": f"{p.masa_kg:.1f}" if p.masa_kg else "-",
                # Metadata
                "_formula": formula_text,
                "_unbalanced": is_unbal,
                "_cubaj_m3": p.cubaj_m3,  # Raw value for calculation
                "_masa_kg": p.masa_kg,    # Raw value for calculation
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # ============================================================
        # "BUYER 12" COLUMN CONFIGURATION
        # Primary columns are always visible, secondary are hidden by default
        # ============================================================
        
        # Define PRIMARY columns (Buyer 12 - always visible)
        # Oct, Nov, Dec 2025 vs 2024 + Trends for Oct and Nov
        primary_cols = [
            "Selecteaza", "Img", "Produs", "Cost", "PVanz", "Stoc Idx", "Stoc Mag", "V.3L",
            "V.Oct'25", "V.Oct'24", "Tr.Oct",
            "V.Nov'25", "V.Nov'24", "Tr.Nov",
            "V.Dec'25", "V.Dec'24",
            "Zile Ac.", "Lead", "Marja", "Status", "NECESAR"
        ]
        
        # Define SECONDARY columns (hidden by default, toggle to show)
        # Includes Jan/Feb data moved here
        secondary_cols = [
            "Cod", "Denumire", "Familie", "Dim", "Tranzit", 
            "V.4L", "V.360", "V.2024", "V.2025", "Med/Zi",
            "Sezon", "YoY%", "Clasa", "Subclasa",
            "S.Ban", "S.Pip", "S.Mil", "S.Pan", "S.Iasi", "S.Bras", "S.Pit", "S.Sib", "S.Ora", "S.Cta"
        ]
        
        column_config = {
            # PRIMARY COLUMNS
            "Selecteaza": st.column_config.CheckboxColumn(
                "✓",
                help="Bifează produsele pentru comandă",
                default=False
            ),
            "Img": st.column_config.ImageColumn(
                "Img",
                help="Poză produs"
            ),
            "Produs": st.column_config.TextColumn(
                "Produs",
                help="Cod | Denumire produs"
            ),
            "Cost": st.column_config.NumberColumn(
                "Cost",
                help="Cost achiziție furnizor (fără TVA)",
                format="%.0f"
            ),
            "PVanz": st.column_config.NumberColumn(
                "P.Vanz",
                help="Preț vânzare cu TVA",
                format="%.0f"
            ),
            "Stoc Idx": st.column_config.NumberColumn(
                "Stoc Idx",
                help="STOC INDOMEX = Dep + Acc + Outlet. Disponibil pentru livrare către magazine.",
                format="%d"
            ),
            "Stoc Mag": st.column_config.NumberColumn(
                "Stoc Mag",
                help="Stoc în magazine (raft). Pentru informare, nu pentru aprovizionare centrală.",
                format="%d"
            ),
            "V.3L": st.column_config.NumberColumn(
                "V.3L",
                help="Vânzări ultimele 3 luni (sau 4 luni dacă 3L nu e disponibil)",
                format="%d"
            ),
            # OCTOBER columns
            "V.Oct'25": st.column_config.NumberColumn(
                "V.Oct'25",
                help="Vânzări Octombrie 2025",
                format="%d"
            ),
            "V.Oct'24": st.column_config.NumberColumn(
                "V.Oct'24",
                help="Vânzări Octombrie 2024 (baseline)",
                format="%d"
            ),
            "Tr.Oct": st.column_config.TextColumn(
                "Tr.Oct",
                help="Trend YoY pentru Octombrie: (2025/2024 - 1) × 100%"
            ),
            # NOVEMBER columns
            "V.Nov'25": st.column_config.NumberColumn(
                "V.Nov'25",
                help="Vânzări Noiembrie 2025",
                format="%d"
            ),
            "V.Nov'24": st.column_config.NumberColumn(
                "V.Nov'24",
                help="Vânzări Noiembrie 2024 (baseline)",
                format="%d"
            ),
            "Tr.Nov": st.column_config.TextColumn(
                "Tr.Nov",
                help="Trend YoY pentru Noiembrie: (2025/2024 - 1) × 100%"
            ),
            # DECEMBER columns
            "V.Dec'25": st.column_config.NumberColumn(
                "V.Dec'25",
                help="Vânzări Decembrie 2025",
                format="%d"
            ),
            "V.Dec'24": st.column_config.NumberColumn(
                "V.Dec'24",
                help="Vânzări Decembrie 2024 (baseline)",
                format="%d"
            ),
            "Status": st.column_config.TextColumn(
                "Status",
                help="CRITICAL = stockout iminent, URGENT = comandă azi, OK = stoc suficient, OVERSTOCK = prea mult"
            ),
            "NECESAR": st.column_config.NumberColumn(
                "NECESAR (buc)",
                help="Cantitatea necesară de comandat",
                format="%d"
            ),
            
            # SECONDARY COLUMNS (hidden by default)
            "Cod": st.column_config.TextColumn("Cod", help="Codul unic al articolului"),
            "Denumire": st.column_config.TextColumn("Denumire", help="Numele complet al produsului"),
            "Familie": st.column_config.TextColumn("Familie", help="Familia de produse. ⚠️ = stoc dezechilibrat"),
            "Dim": st.column_config.TextColumn("Dim", help="Dimensiune produs"),
            "Tranzit": st.column_config.NumberColumn("Tranzit", help="Marfă în tranzit", format="%d"),
            "V.4L": st.column_config.NumberColumn("V.4L", help="Vânzări 4 luni", format="%d"),
            "V.360": st.column_config.NumberColumn("V.360", help="Vânzări 360 zile", format="%d"),
            "V.2024": st.column_config.NumberColumn("V.2024", help="Vânzări 2024", format="%d"),
            "V.2025": st.column_config.NumberColumn("V.2025", help="Vânzări 2025", format="%d"),
            "Med/Zi": st.column_config.NumberColumn("Med/Zi", help="Media zilnică", format="%.2f"),
            "Zile Ac.": st.column_config.TextColumn("Zile Ac.", help="Zile acoperire. 🔴 = Marja < 5 zile"),
            "Lead": st.column_config.TextColumn("Lead", help="Lead time zile. 🔴 = Marja < 5 zile"),
            "Marja": st.column_config.TextColumn("Marja", help="Zile Acoperire - Lead Time. 🔴 = sub 5 zile marjă de siguranță"),
            "_marja_raw": None,
            "Sezon": st.column_config.NumberColumn("Sezon", help="Index sezonalitate", format="%.2f"),
            "YoY%": st.column_config.TextColumn("YoY%", help="Trend anual"),
            "Clasa": st.column_config.TextColumn("Clasa"),
            "Subclasa": st.column_config.TextColumn("Subclasa"),
            
            # Store columns
            "S.Ban": st.column_config.NumberColumn("Baneasa", format="%d"),
            "S.Pip": st.column_config.NumberColumn("Pipera", format="%d"),
            "S.Mil": st.column_config.NumberColumn("Militari", format="%d"),
            "S.Pan": st.column_config.NumberColumn("Pantelimon", format="%d"),
            "S.Iasi": st.column_config.NumberColumn("Iasi", format="%d"),
            "S.Bras": st.column_config.NumberColumn("Brasov", format="%d"),
            "S.Pit": st.column_config.NumberColumn("Pitesti", format="%d"),
            "S.Sib": st.column_config.NumberColumn("Sibiu", format="%d"),
            "S.Ora": st.column_config.NumberColumn("Oradea", format="%d"),
            "S.Cta": st.column_config.NumberColumn("Constanta", format="%d"),
            
            # Cubaj & Logistics columns
            "Cubaj": st.column_config.TextColumn("Cubaj (m³)", help="Volum ambalat cilindric"),
            "Masa": st.column_config.TextColumn("Masa (kg)", help="Masa ambalat"),
            
            # Hide internal columns
            "_formula": None,
            "_unbalanced": None,
            "_cubaj_m3": None,
            "_masa_kg": None,
        }

        

        
        # ============================================================
        # INLINE TOOLBAR (Consolidated: Search | Details | All | AI | CSV)
        # ============================================================
        
        # Layout: Search (3) | Details (1) | All (1) | CSV (1)
        toolbar_cols = st.columns([3, 1.5, 1, 1])
        
        with toolbar_cols[0]:
             search_text = st.text_input("🔎", key=f"search_{segment_name}", placeholder="Caută cod/denumire...", label_visibility="collapsed")
        
        with toolbar_cols[1]:
             show_details = st.checkbox("Detalii extinse", key=f"details_{segment_name}", help="Afișează tranzit, vânzări 360, etc.")

        with toolbar_cols[2]:
             if allow_order:
                 select_all = st.checkbox("All", key=f"sel_all_{segment_name}")
             else:
                 select_all = False
             
        # Eliminated AI Button
        explain_btn = False  # AI button was removed, keeping variable for backward compatibility
                  
        with toolbar_cols[3]:
             csv_data = df.to_csv(index=False).encode('utf-8')
             st.download_button("📥 CSV", csv_data, f"{segment_name.lower()}.csv", "text/csv", key=f"exp_{segment_name}", use_container_width=True)
             
        # Logic for columns display moved AFTER toolbar interaction
        if show_details:
            display_cols = [col for col in df.columns if not col.startswith("_")]
        else:
            display_cols = [col for col in primary_cols if col in df.columns]
            
        display_df = df[display_cols].copy()
            
        if "NECESAR" in display_df.columns:
             display_df.set_index("NECESAR", inplace=True)
        
        # Apply search filter
        family_filter = "Toate"  # Disabled for now
        class_filter = "Toate"
        subclass_filter = "Toate"
        
        if search_text:
            search_lower = search_text.lower()
            # Search in Produs column (which contains Cod | Denumire)
            if "Produs" in display_df.columns:
                display_df = display_df[
                    display_df["Produs"].astype(str).str.lower().str.contains(search_lower, na=False)
                ]
            elif "Cod" in display_df.columns:
                display_df = display_df[
                    display_df["Cod"].astype(str).str.lower().str.contains(search_lower, na=False) |
                    display_df["Denumire"].astype(str).str.lower().str.contains(search_lower, na=False)
                ]
        
        # If select all is checked, update all checkboxes
        if select_all:
            display_df["Selecteaza"] = True
        
        # Render editable table
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            width="stretch",
            height=550,
            hide_index=False,
            key=f"editor_{segment_name}",
            disabled=[col for col in display_df.columns if col != "Selecteaza"]  # All columns except checkbox are read-only
        )
        
        # ============================================================
        # AI ANALYSIS
        # ============================================================
        if allow_order and explain_btn:
            # Extract codes from Produs column (format: "CODE | Name")
            if "Produs" in edited_df.columns:
                selected_rows = edited_df[edited_df["Selecteaza"] == True]["Produs"].tolist()
                selected_codes = [row.split(" | ")[0] for row in selected_rows if " | " in row]
            else:
                selected_codes = edited_df[edited_df["Selecteaza"] == True]["Cod"].tolist()
            
            if not selected_codes:
                st.warning("Selectează cel puțin un produs pentru explicație!")
            elif not gemini_cfg.get("api_key"):
                st.warning("Configurează API key în Settings > Gemini API")
            else:
                # TOAST notification - alert user to scroll
                st.toast("AI analizează... Scrollează în jos pentru rezultate!")
                
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
                        
                        # Calculate dynamic buffer for formula display
                        buffer_days = 30 if p.avg_daily_sales > 0.2 else 21
                        rising_star_mult = 1.5 if p.is_rising_star else 1.0
                        adjusted_safety_with_star = round(adjusted_safety * rising_star_mult, 1)
                        
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
                            "Safety_Ajustat": adjusted_safety_with_star,
                            "Buffer_Dinamic": buffer_days,
                            # NEW: Seasonality data
                            "Sezonalitate_Index": p.seasonality_index,
                            "Trend_HOT_COLD": p.trend,
                            "Is_Rising_Star": "DA" if p.is_rising_star else "NU",
                            "Is_Dead_Stock": "DA" if p.is_dead_stock else "NU",
                            # Advanced Trends
                            "YoY_Growth": f"{int(p.yoy_growth):+d}%",
                            "Acceleration": f"{int(p.acceleration):+d}%",
                            "Volatility": round(p.volatility, 2),
                            "Repeat_Rate": f"{int(p.repeat_rate)}%",
                            "Trend_Viteza": f"{trend_pct:+d}%",
                            "CANTITATE_SUGERATA": qty,
                            "FORMULA": f"{p.avg_daily_sales:.2f}/zi × {p.seasonality_index:.2f} × ({p.lead_time_days} + {adjusted_safety_with_star} + {buffer_days}) - {int(p.total_stock)} = {qty}",
                            "Stoc_Dezechilibrat_Familie": "DA" if is_unbal else "NU",
                        })
                    
                    # Build AI prompt with EXPLICIT THINKING TAGS
                    prompt = f"""Ești un expert în supply chain. Explică de ce s-a ajuns la cantitățile sugerate.

DATE PRODUSE:
{json.dumps(products_for_ai, indent=2, ensure_ascii=False)}

FORMULA 3.0 (CU LOGICA INTEGRATA):
Cantitate = (Media × Sezonalitate × Coverage_Days × Trend_Multiplier) - Stoc_Actual

REGULI IMPLEMENTATE:
- **Buffer Dinamic**: 30 zile (Fast Mover >0.2/zi) sau 21 zile (Slow Mover)
- **Sezonalitate_Index**: >1.0 = vine vârful de sezon, <1.0 = off-season
- **Is_Rising_Star=DA**: +50% Safety Stock (creștere așteptată)
- **Volatility>1.0**: +30% Safety Stock (cerere impredictibilă)
- **YoY_Growth>+20%**: Trend multiplier +10-30% (creștere confirmată)
- **YoY_Growth<-30%**: Trend multiplier -15-30% (declin confirmat)  
- **Trend_HOT_COLD=COLD**: -20% suplimentar (reduce comenzile pentru produse în declin)
- **Is_Dead_Stock=DA**: Sugestie = 0 SAU 1 unit (Family Rescue pentru sortimentație)
- **MIN_VOLUME pentru trend**: Trend% ignorat dacă <5 buc vândute (evita +200% pe 1 vânzare)

INSTRUCȚIUNI CRITICE DE FORMAT:
1. MAI ÎNTÂI, scrie procesul tău de gândire în tag-uri <thinking>...</thinking>
   - Verifică dacă YoY_Growth și Trend_HOT_COLD sunt COERENTE
   - Verifică dacă Volatility necesită extra safety
   - Pentru Dead Stock: verifică dacă are Family Rescue (1 buc vs 0)

2. DUPĂ </thinking>, scrie răspunsul final clar și structurat.

3. LA FINAL, joacă rolul AVOCATULUI DIAVOLULUI:
   - YoY_Growth și Trend_Viteza spun același lucru?
   - Dead Stock cu familie: merită 1 bucată pentru sortimentație?
   - Marja de profit justifică riscul de a ține stoc?

EXEMPLU FORMAT:
<thinking>
Produsul X... Media 0.3/zi, YoY=-40% (în declin sever).
Trend_HOT_COLD = COLD → trend_multiplier = 0.8
Volatility = 1.2 → safety majorat cu 30%
Formula: 0.3 × 1.2 × 70.5 × 0.8 - 15 = 16.2 - 15 = 1.2 ≈ 1 buc
Dar YoY e -40%... chiar vrem să comandăm?
</thinking>

**ANALIZA PRODUSELOR:**
[răspunsul structurat aici]

**🔥 AVOCATUL DIAVOLULUI:**
[critici și provocări aici]

Răspunde în română. FII AUTENTIC în thinking."""
                    
                    # Get model name
                    model_name = gemini_cfg.get("model", "gemini-pro-latest")
                    
                    # ============================================================
                    # DRAMATIC AI MODAL EXPERIENCE - NO SCROLL NEEDED
                    # Display at CURRENT position (after button click, before table rerenders)
                    # ============================================================
                    
                    # Create a modal-like container at the top
                    ai_container = st.container()
                    
                    with ai_container:
                        st.markdown("""
                        <div id="ai-analysis-container" style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); 
                                    padding: 24px; border-radius: 12px; margin: 16px 0;
                                    box-shadow: 0 10px 40px rgba(0,0,0,0.3);">
                            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                                <span style="color: #60a5fa; font-weight: 600; font-size: 1.1rem;">AI Analysis</span>
                                <span style="color: #64748b; font-size: 0.85rem; margin-left: auto;">Model: """ + model_name + """</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # PROMPT - EXPANDED BY DEFAULT
                        with st.expander("📝 Prompt trimis la AI", expanded=True):
                            st.code(prompt, language="markdown")
                        
                        st.markdown("---")
                        
                        # Placeholders for real-time display
                        status_placeholder = st.empty()
                        thinking_container = st.container()
                        response_container = st.container()
                        
                        full_response = ""
                        thinking_content = ""
                        in_thinking = False
                        thinking_done = False
                        
                        try:
                            import google.generativeai as genai
                            import re
                            import time
                            
                            genai.configure(api_key=gemini_cfg["api_key"])
                            
                            generation_config = {
                                "temperature": 0.8,
                                "top_p": 0.95,
                                "max_output_tokens": 8192,
                            }
                            
                            model = genai.GenerativeModel(
                                model_name,
                                generation_config=generation_config
                            )
                            
                            # Initial status
                            status_placeholder.markdown("""
                            <div style="display: flex; align-items: center; gap: 8px; color: #facc15;">
                                <div class="typing-indicator" style="display: flex; gap: 4px;">
                                    <span style="animation: pulse 1s infinite;">●</span>
                                    <span style="animation: pulse 1s infinite 0.2s;">●</span>
                                    <span style="animation: pulse 1s infinite 0.4s;">●</span>
                                </div>
                                <span>AI se conectează...</span>
                            </div>
                            <style>
                                @keyframes pulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
                            </style>
                            """, unsafe_allow_html=True)
                            
                            time.sleep(0.5)  # Dramatic pause
                            
                            # Start thinking header
                            with thinking_container:
                                thinking_header = st.empty()
                                thinking_text = st.empty()
                            
                            thinking_header.markdown("""
                            <div style="color: #94a3b8; font-size: 0.85rem; margin-bottom: 8px;">
                                <strong>THINKING</strong> — procesul intern de gândire
                            </div>
                            """, unsafe_allow_html=True)
                            
                            status_placeholder.markdown("""
                            <div style="color: #22c55e; font-size: 0.85rem;">
                                ✓ Conectat. AI gândește...
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Streaming with DRAMATIC TYPING EFFECT
                            response = model.generate_content(prompt, stream=True)
                            
                            displayed_thinking = ""
                            displayed_response = ""
                            
                            with response_container:
                                response_header = st.empty()
                                response_text = st.empty()
                            
                            for chunk in response:
                                if chunk.text:
                                    full_response += chunk.text
                                    
                                    # Detect thinking tags
                                    if "<thinking>" in full_response and not in_thinking:
                                        in_thinking = True
                                    
                                    if "</thinking>" in full_response and not thinking_done:
                                        thinking_done = True
                                        match = re.search(r'<thinking>(.*?)</thinking>', full_response, re.DOTALL)
                                        if match:
                                            thinking_content = match.group(1).strip()
                                    
                                    # DRAMATIC DISPLAY with slight delay
                                    if in_thinking and not thinking_done:
                                        current = full_response.split("<thinking>")[-1] if "<thinking>" in full_response else ""
                                        # Show with typing cursor
                                        thinking_text.markdown(f"""
<div style="background: #1e293b; border-left: 3px solid #94a3b8; padding: 16px; 
            border-radius: 8px; color: #cbd5e1; font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 0.9rem; line-height: 1.7; white-space: pre-wrap;">
{current}<span style="animation: blink 0.7s infinite; color: #60a5fa;">▌</span>
</div>
<style>@keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}</style>
""", unsafe_allow_html=True)
                                        time.sleep(0.03)  # Typing delay effect
                                    
                                    elif thinking_done:
                                        # Final thinking (collapsed look)
                                        thinking_text.markdown(f"""
<div style="background: #1e293b; border-left: 3px solid #22c55e; padding: 16px; 
            border-radius: 8px; color: #94a3b8; font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; max-height: 200px; overflow-y: auto;">
{thinking_content}
</div>
""", unsafe_allow_html=True)
                                        
                                        # Show response header
                                        response_header.markdown("""
<div style="color: #60a5fa; font-size: 0.9rem; margin: 16px 0 8px 0; font-weight: 600;">
    <strong>RASPUNS FINAL</strong>
</div>
""", unsafe_allow_html=True)
                                        
                                        # Response with typing effect
                                        after = full_response.split("</thinking>")[-1].strip() if "</thinking>" in full_response else ""
                                        response_text.markdown(after + " ▌")
                                        time.sleep(0.02)
                            
                            # FINAL DISPLAY
                            if thinking_content:
                                thinking_text.markdown(f"""
<div style="background: #1e293b; border-left: 3px solid #22c55e; padding: 16px; 
            border-radius: 8px; color: #94a3b8; font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; max-height: 250px; overflow-y: auto;">
{thinking_content}
</div>
""", unsafe_allow_html=True)
                            
                            final_response = full_response.split("</thinking>")[-1].strip() if "</thinking>" in full_response else full_response
                            response_text.markdown(final_response)
                            
                            status_placeholder.markdown("""
                            <div style="color: #22c55e; font-size: 0.9rem; font-weight: 600;">
                                Analiză completă!
                            </div>
                            """, unsafe_allow_html=True)
                            
                        except Exception as e:
                            st.error(f"Eroare AI: {e}")
        
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
            
            # Calculate Marja for Lead Time Alert
            days_cov = round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999.0
            lead_time = p.lead_time_days
            marja = days_cov - lead_time
            is_alert = marja < 5 and days_cov < 999
            
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
                "Zile Acoperire": f"🔴 {days_cov}" if is_alert else str(days_cov),
                "Timp Livrare": f"🔴 {lead_time}" if is_alert else str(lead_time),
                "Marja": f"🔴 {marja:.1f}" if is_alert else f"{marja:.1f}",
                "Cost Unitar": round(p.cost_achizitie, 2),
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        st.dataframe(df, width="stretch", height=400)
        return df
    
    if "Critical" in selected_nav:
        with st.expander("Cum se calculeaza Critical?", expanded=False):
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
        
        # Lazy Load Logic for CRITICAL (same as other tabs)
        if use_postgres:
            with st.spinner("Se încarcă produsele CRITICAL (Rapid)..."):
                # FAST VECTORIZED LOAD
                raw_df = load_segment_from_db("CRITICAL", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=5000
                )
                proc_df = process_products_vectorized(raw_df, config, seasonality_data, advanced_trends_data, cubaj_data)
                seg_products = [SimpleNamespace(**x) for x in proc_df.to_dict('records')]
            render_interactive_table(seg_products, "CRITICAL", allow_order=True)
        else:
            render_interactive_table(segments["CRITICAL"], "CRITICAL", allow_order=True)
    
    if "Urgent" in selected_nav:
        with st.expander("Cum se calculeaza Urgent?", expanded=False):
            st.markdown("""
**Conditie:** `Lead Time <= Zile Acoperire < Lead Time + Safety Stock`

**Ce inseamna:** Marfa poate ajunge la timp, dar fara margine de siguranta. Orice intarziere sau varf de vanzari = STOCKOUT.

**Exemplu:** Lead Time = 30 zile, Safety Stock = 7 zile
- Daca Zile Acoperire = 32, esti in zona URGENT (intre 30 si 37)

**Ce inseamna:** Stocul acopera timpul de livrare, dar intri in Safety Stock. Risc de ruptura daca vanzarile cresc.
**Actiune recomandata:** Comanda Acum.
            """)

        
        # Lazy Load Logic
        if use_postgres:
            with st.spinner("Se încarcă produsele URGENT (Rapid)..."):
                raw_df = load_segment_from_db("URGENT", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=5000
                )
                proc_df = process_products_vectorized(raw_df, config, seasonality_data, advanced_trends_data, cubaj_data)
                seg_products = [SimpleNamespace(**x) for x in proc_df.to_dict('records')]
            render_interactive_table(seg_products, "URGENT")
        else:
            render_interactive_table(segments["URGENT"], "URGENT", allow_order=True)
    
    if "Attention" in selected_nav:
        with st.expander("Cum se calculeaza Attention?", expanded=False):
            st.markdown("""
**Conditie:** `Lead Time + Safety Stock <= Zile Acoperire < Lead Time + Safety Stock + 14 zile`

**Ce inseamna:** Ai ~2 saptamani sa planifici comanda. Stocul este "la limita" dar nu urgent.

**Actiune recomandata:** Planifica comanda, verifica MOQ (Minimum Order Quantity), negociaza cu furnizorul.
            """)

        
        # Lazy Load Logic
        if use_postgres:
            with st.spinner("Se încarcă produsele ATTENTION (Rapid)..."):
                raw_df = load_segment_from_db("ATTENTION", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=5000
                )
                proc_df = process_products_vectorized(raw_df, config, seasonality_data, advanced_trends_data, cubaj_data)
                seg_products = [SimpleNamespace(**x) for x in proc_df.to_dict('records')]
            render_interactive_table(seg_products, "ATTENTION", allow_order=True)
        else:
            render_interactive_table(segments["ATTENTION"], "ATTENTION", allow_order=True)
    
    if "OK" in selected_nav:
        with st.expander("ℹ️ Cum se calculeaza OK? (click pentru detalii)", expanded=False):
            st.markdown("""
**Conditie:** `Lead Time + Safety Stock + 14 zile <= Zile Acoperire <= 90 zile`

**Ce inseamna:** Stocul este sanatos. Ai suficienta marfa pentru a acoperi cererea curenta.

**Actiune recomandata:** Monitorizare saptamanala. Nu e nevoie de actiune imediata.
            """)

        
        # Lazy Load Logic
        if use_postgres:
            with st.spinner("Se încarcă produsele OK (Rapid)..."):
                raw_df = load_segment_from_db("OK", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=5000
                )
                proc_df = process_products_vectorized(raw_df, config, seasonality_data, advanced_trends_data, cubaj_data)
                seg_products = [SimpleNamespace(**x) for x in proc_df.to_dict('records')]
            render_interactive_table(seg_products, "OK", allow_order=True)
        else:
            render_interactive_table(segments["OK"], "OK", allow_order=True)
    
    if "Overstock" in selected_nav:
        with st.expander("Cum se calculeaza Overstock?", expanded=False):
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
            with st.spinner("Se încarcă produsele OVERSTOCK (Rapid)..."):
                raw_df = load_segment_from_db("OVERSTOCK", 
                    furnizor=selected_supplier if selected_supplier != "ALL" else None, 
                    stare_pm=selected_status if selected_status != "ALL" else None,
                    limit=5000
                )
                proc_df = process_products_vectorized(raw_df, config, seasonality_data, advanced_trends_data, cubaj_data)
                seg_products = [SimpleNamespace(**x) for x in proc_df.to_dict('records')]
                
            render_interactive_table(seg_products, "OVERSTOCK", allow_order=False)
            
            # Use pre-calculated stats for total value
            total = segment_stats.get("OVERSTOCK", {}).get("value", 0)
        else:
            render_interactive_table(segments["OVERSTOCK"], "OVERSTOCK", allow_order=False)
            total = sum(p.stock_value for p in segments["OVERSTOCK"])
            
        st.markdown(f"**Total overstock: {total:,.0f} RON**")
    
    # ============================================================
    # ALL DATA TAB - 🚫 INACTIVAT
    # ============================================================
    if False:  # tab_all - DEZACTIVAT
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
                all_products = parse_from_postgres(raw_all, config, seasonality_data, advanced_trends_data)
            render_interactive_table(all_products, "ALL", allow_order=True)
        else:
            st.markdown(f"**Total produse: {len(products)}**")
            # Use legacy table for CSV mode to show everything (might be slow)
            render_table(products)
    
    # ============================================================
    # FAMILY VIEW TAB - 🚫 INACTIVAT
    # ============================================================
    if False:  # tab_family - DEZACTIVAT
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
                        family_products = parse_from_postgres(raw_fam_df, config, seasonality_data, advanced_trends_data)
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
    
    
    if False:  # tab_all - DEZACTIVAT (duplicate block)
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
    # SUPPLIER AUDIT TAB - 🚫 INACTIVAT
    # ============================================================
    if False:  # tab_audit - DEZACTIVAT
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
    
    # ============================================================
    # ORDER BUILDER TAB (OLD) - 🚫 INACTIVAT
    # ============================================================
    if False:  # tab_order - DEZACTIVAT
        st.markdown("### 📦 Order Builder - Construire Comandă pe Subclasă")
        st.markdown("*Selectează furnizor → Click + pe subclasă → Bifează articole → Export Excel*")
        
        # Step 1: Supplier Selection
        suppliers = get_unique_suppliers()
        order_supplier = st.selectbox("🏭 Selectează Furnizor", ["(alege)"] + suppliers, key="order_supplier")
        
        if order_supplier and order_supplier != "(alege)":
            # Get subclass summaries for this supplier
            subclass_summaries = get_subclass_summary(order_supplier)
            
            if not subclass_summaries:
                st.warning("Nu există subclase pentru acest furnizor.")
            else:
                # Two-column layout: Subclasses | Order Summary
                col_subclasses, col_summary = st.columns([2, 1])
                
                with col_subclasses:
                    st.markdown("#### Subclase Disponibile")
                    st.markdown(f"*{len(subclass_summaries)} subclase, sortate după urgență*")
                    
                    for sub in subclass_summaries:
                        # Urgency badge
                        if sub["critical_count"] > 0:
                            badge = "🔴"
                        elif sub["urgent_count"] > 0:
                            badge = "🟠"
                        elif sub["attention_count"] > 0:
                            badge = "🟡"
                        else:
                            badge = "🟢"
                        
                        # Card container
                        with st.container():
                            card_cols = st.columns([4, 1])
                            with card_cols[0]:
                                st.markdown(f"""
                                **{badge} {sub['subclasa']}** ({sub['article_count']} art)  
                                <span style="font-size:0.85rem; color:#6b7280;">CRIT: {sub['critical_count']} | URG: {sub['urgent_count']} | ATT: {sub['attention_count']} | {sub['total_value']:,.0f} RON</span>
                                """, unsafe_allow_html=True)
                            with card_cols[1]:
                                if st.button("➕", key=f"add_sub_{sub['subclasa'][:20]}", help=f"Deschide {sub['subclasa']}"):
                                    st.session_state.current_subclass = sub['subclasa']
                                    st.session_state.current_subclass_supplier = order_supplier
                            st.markdown("---")
                
                with col_summary:
                    st.markdown("#### 📋 Comandă Curentă")
                    if st.session_state.order_items:
                        total_articles = 0
                        total_qty = 0
                        total_value = 0
                        total_cubaj = 0
                        total_masa = 0
                        
                        for subclass_name, items in st.session_state.order_items.items():
                            sub_qty = sum(item.get("qty", 0) for item in items)
                            sub_value = sum(item.get("value", 0) for item in items)
                            st.markdown(f"✓ **{subclass_name[:25]}**: {len(items)} art, {sub_qty} buc, {sub_value:,.0f} RON")
                            total_articles += len(items)
                            total_qty += sub_qty
                            total_value += sub_value
                            total_cubaj += sum(item.get("cubaj", 0) or 0 for item in items)
                            total_masa += sum(item.get("masa", 0) or 0 for item in items)
                        
                        st.markdown("---")
                        st.markdown(f"""
                        **TOTAL:**  
                        📦 {total_articles} articole | {total_qty} buc  
                        💰 {total_value:,.0f} RON  
                        📐 {total_cubaj:.2f} m³ | ⚖️ {total_masa:.1f} kg
                        """)
                        
                        # Export button
                        if st.button("📤 Export Excel", key="export_order"):
                            import io
                            output = io.BytesIO()
                            rows = []
                            for subclass_name, items in st.session_state.order_items.items():
                                for item in items:
                                    rows.append(item)
                            if rows:
                                export_df = pd.DataFrame(rows)
                                export_df.to_excel(output, index=False)
                                st.download_button(
                                    "⬇️ Descarcă Excel",
                                    output.getvalue(),
                                    f"comanda_{order_supplier[:20]}.xlsx",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                        
                        if st.button("🗑️ Golește Comanda", key="clear_order"):
                            st.session_state.order_items = {}
                            st.rerun()
                    else:
                        st.info("Comanda goală. Click ➕ pe o subclasă pentru a adăuga articole.")
        
        # Step 3: If subclass selected, show full article table
        if st.session_state.current_subclass and st.session_state.current_subclass_supplier:
            st.markdown("---")
            st.markdown(f"### 📋 Articole din: **{st.session_state.current_subclass}**")
            
            # Back button
            if st.button("← Înapoi la Subclase", key="back_to_subclasses"):
                st.session_state.current_subclass = None
                st.session_state.current_subclass_supplier = None
                st.rerun()
            
            # Load products for this subclass
            with st.spinner("Se încarcă articolele..."):
                subclass_df = load_subclass_products(
                    st.session_state.current_subclass_supplier,
                    st.session_state.current_subclass
                )
            
            if subclass_df.empty:
                st.warning("Nu există articole în această subclasă.")
            else:
                # Parse into Product objects (reuse existing logic)
                subclass_products = parse_from_postgres(subclass_df, config, seasonality_data, advanced_trends_data, cubaj_data)
                
                # Build data with columns (SAME structure as render_interactive_table)
                from datetime import datetime
                compare_year = 2025
                
                data = []
                for p in subclass_products:
                    oct_data = get_sales_ref_month_yoy(p.sales_history, 10, compare_year)
                    nov_data = get_sales_ref_month_yoy(p.sales_history, 11, compare_year)
                    dec_data = get_sales_ref_month_yoy(p.sales_history, 12, compare_year)
                    
                    suggested_qty = int(p.suggested_order_qty)
                    
                    row = {
                        "Selecteaza": False,
                        # PRIMARY COLUMNS (same as other tabs)
                        "Produs": f"{p.nr_art} | {(p.nume_produs[:18] + '..' if len(p.nume_produs) > 18 else p.nume_produs)}",
                        "Cost": round(p.cost_achizitie, 0),
                        "PVanz": round(p.pret_vanzare, 0),
                        "Stoc Idx": int(p.stoc_indomex),
                        "Stoc Mag": int(p.stoc_magazin_total),
                        "V.3L": int(p.sales_last_3m) if p.sales_last_3m > 0 else int(p.vanzari_ultimele_4_luni),
                        "V.Oct'25": int(oct_data["current_year_sales"]),
                        "V.Oct'24": int(oct_data["prior_year_sales"]),
                        "Tr.Oct": f"{int(oct_data['yoy_pct']):+d}%" if oct_data["prior_year_sales"] > 0 else "-",
                        "V.Nov'25": int(nov_data["current_year_sales"]),
                        "V.Nov'24": int(nov_data["prior_year_sales"]),
                        "Tr.Nov": f"{int(nov_data['yoy_pct']):+d}%" if nov_data["prior_year_sales"] > 0 else "-",
                        "V.Dec'25": int(dec_data["current_year_sales"]),
                        "V.Dec'24": int(dec_data["prior_year_sales"]),
                        "Status": p.segment,
                        "Cant.Sug.": suggested_qty,
                        # SECONDARY COLUMNS (hidden by default)
                        "Cod": p.nr_art,
                        "Denumire": p.nume_produs,
                        "Familie": p.familie if p.familie else "-",
                        "Dim": p.dimensiune if p.dimensiune else "-",
                        "Tranzit": int(p.stoc_in_tranzit),
                        "V.4L": int(p.vanzari_ultimele_4_luni),
                        "V.360": int(p.vanzari_ultimele_360_zile),
                        "V.2024": int(p.vanzari_2024),
                        "V.2025": int(p.vanzari_2025),
                        "Med/Zi": round(p.avg_daily_sales, 2),
                        "Zile Ac.": round(p.days_of_coverage, 1) if p.days_of_coverage < 999 else 999.0,
                        "Lead": p.lead_time_days,
                        "Sezon": round(p.seasonality_index, 2),
                        "YoY%": f"{int(p.yoy_growth):+d}%" if p.yoy_growth != 0 else "-",
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
                        "Cubaj": f"{p.cubaj_m3:.3f}" if p.cubaj_m3 else "N/A",
                        "Masa": f"{p.masa_kg:.1f}" if p.masa_kg else "-",
                        # Hidden for calculations
                        "_cost": p.cost_achizitie,
                        "_cubaj": p.cubaj_m3,
                        "_masa": p.masa_kg,
                        "_qty": suggested_qty,
                    }
                    data.append(row)
                
                df = pd.DataFrame(data)
                
                # PRIMARY COLUMNS (same as render_interactive_table)
                primary_cols = [
                    "Selecteaza", "Produs", "Cost", "PVanz", "Stoc Idx", "Stoc Mag", "V.3L",
                    "V.Oct'25", "V.Oct'24", "Tr.Oct",
                    "V.Nov'25", "V.Nov'24", "Tr.Nov",
                    "V.Dec'25", "V.Dec'24",
                    "Status", "Cant.Sug."
                ]
                
                # Toggle for extended details (same as other tabs)
                show_details = st.checkbox("📋 Detalii extinse", key="order_show_details", 
                                           help="Afișează coloane suplimentare (familie, stoc pe magazine, etc.)")
                
                # Select columns based on toggle
                if show_details:
                    display_cols = [col for col in df.columns if not col.startswith("_")]
                else:
                    display_cols = [col for col in primary_cols if col in df.columns]
                
                display_df = df[display_cols].copy()
                
                # Create stable key for this subclass
                table_key = f"order_table_{st.session_state.current_subclass[:20].replace(' ', '_')}"
                
                # Editable table with stable key
                edited_df = st.data_editor(
                    display_df,
                    column_config={
                        "Selecteaza": st.column_config.CheckboxColumn("☑️", default=False),
                        "Status": st.column_config.TextColumn("Segment"),
                        "Cant.Sug.": st.column_config.NumberColumn("Cant Sug", format="%d"),
                    },
                    hide_index=True,
                    height=450,
                    key=table_key
                )
                
                # Live Totals - calculate from selected rows
                selected_mask = edited_df["Selecteaza"] == True
                selected_df = df[selected_mask]
                
                sel_count = len(selected_df)
                sel_qty = int(selected_df["_qty"].sum()) if sel_count > 0 else 0
                sel_value = int((selected_df["_qty"] * selected_df["_cost"]).sum()) if sel_count > 0 else 0
                sel_cubaj = selected_df["_cubaj"].fillna(0).sum() if sel_count > 0 else 0
                sel_masa = selected_df["_masa"].fillna(0).sum() if sel_count > 0 else 0
                
                # Live Totals Panel
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); 
                            padding: 16px; border-radius: 12px; margin: 16px 0;">
                    <div style="color: #60a5fa; font-weight: 600; margin-bottom: 8px;">📊 LIVE TOTALS</div>
                    <div style="display: flex; gap: 24px; flex-wrap: wrap; color: white;">
                        <div>☑️ <strong>{sel_count}</strong> articole</div>
                        <div>📦 <strong>{sel_qty}</strong> buc</div>
                        <div>💰 <strong>{sel_value:,}</strong> RON</div>
                        <div>📐 <strong>{sel_cubaj:.2f}</strong> m³</div>
                        <div>⚖️ <strong>{sel_masa:.1f}</strong> kg</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Add to Order button - NO st.rerun() for speed
                if st.button("✅ Adaugă Selectate în Comandă", key="add_to_order", type="primary"):
                    if sel_count > 0:
                        # Build order items
                        items = []
                        for idx in selected_df.index:
                            orig_row = df.iloc[idx]
                            items.append({
                                "cod": orig_row["Cod"],
                                "denumire": orig_row["Denumire"],
                                "qty": int(orig_row["_qty"]),
                                "cost": orig_row["_cost"],
                                "value": int(orig_row["_qty"] * orig_row["_cost"]),
                                "cubaj": orig_row["_cubaj"],
                                "masa": orig_row["_masa"],
                                "subclasa": st.session_state.current_subclass,
                                "furnizor": st.session_state.current_subclass_supplier,
                            })
                        
                        # Add to session state
                        subclass_key = st.session_state.current_subclass
                        if subclass_key in st.session_state.order_items:
                            existing_codes = {i["cod"] for i in st.session_state.order_items[subclass_key]}
                            for item in items:
                                if item["cod"] not in existing_codes:
                                    st.session_state.order_items[subclass_key].append(item)
                        else:
                            st.session_state.order_items[subclass_key] = items
                        
                        st.success(f"✅ Adăugat {sel_count} articole în comandă!")
                        st.rerun()  # Force refresh to update "Comandă Curentă" panel
                    else:
                        st.warning("⚠️ Selectează cel puțin un articol!")
    
    # ============================================================
    # ORDER BUILDER v2 TAB
    # ============================================================
    if "ORDER v2" in selected_nav:
        render_order_builder_v2(config, cubaj_data)


if __name__ == "__main__":
    main()
