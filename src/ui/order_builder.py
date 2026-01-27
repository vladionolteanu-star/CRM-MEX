"""
Order Builder v2 - Planșă rapidă pentru comenzi
===============================================
Modul separat pentru construirea comenzilor pe subclasă.

Layout: 2 coloane (Articole | Comandă Curentă)
Features:
- Căutare globală în articole furnizor
- Cantitate editabilă + sugestie sistem
- Live totals vizibile permanent
"""

import streamlit as st
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional
import io
import math
import numpy as np

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class OrderItem:
    """Un articol din comandă"""
    cod: str
    denumire: str
    qty_sugerata: int
    qty: int  # Cantitate editabilă
    cost: float
    cubaj: Optional[float]
    masa: Optional[float]
    subclasa: str
    furnizor: str
    segment: str
    
    @property
    def value(self) -> float:
        return self.qty * self.cost
    
    @property
    def total_cubaj(self) -> float:
        return (self.cubaj or 0) * self.qty
    
    @property
    def total_masa(self) -> float:
        return (self.masa or 0) * self.qty


# ============================================================
# SESSION STATE HELPERS
# ============================================================

def init_order_state():
    """Inițializează session state pentru Order Builder v2"""
    if "ob2_order_items" not in st.session_state:
        st.session_state.ob2_order_items = {}  # {cod: OrderItem}
    
    if "ob2_current_subclass" not in st.session_state:
        st.session_state.ob2_current_subclass = None
    
    if "ob2_supplier" not in st.session_state:
        st.session_state.ob2_supplier = None
    
    if "ob2_search" not in st.session_state:
        st.session_state.ob2_search = ""

    # Simulation params
    if "sim_order_freq" not in st.session_state:
        st.session_state.sim_order_freq = 30
    if "sim_safety_buffer" not in st.session_state:
        st.session_state.sim_safety_buffer = 0
    if "sim_seasonal_factor" not in st.session_state:
        st.session_state.sim_seasonal_factor = 1.0
    if "sim_lead_time_override" not in st.session_state:
        st.session_state.sim_lead_time_override = 0 # 0 means disabled
    if "sim_ignore_moq" not in st.session_state:
        st.session_state.sim_ignore_moq = False


def add_to_order(items: List[OrderItem]):
    """Adaugă articole în comandă (sau actualizează dacă există)"""
    for item in items:
        st.session_state.ob2_order_items[item.cod] = item


def remove_from_order(cod: str):
    """Șterge articol din comandă"""
    if cod in st.session_state.ob2_order_items:
        del st.session_state.ob2_order_items[cod]


def update_qty(cod: str, new_qty: int):
    """Actualizează cantitatea pentru un articol"""
    if cod in st.session_state.ob2_order_items:
        st.session_state.ob2_order_items[cod].qty = max(0, new_qty)


def clear_order():
    """Golește comanda"""
    st.session_state.ob2_order_items = {}


def get_order_totals() -> dict:
    """Calculează totaluri comandă"""
    items = st.session_state.ob2_order_items.values()
    return {
        "count": len(items),
        "qty": sum(i.qty for i in items),
        "value": sum(i.value for i in items),
        "cubaj": sum(i.total_cubaj for i in items),
        "masa": sum(i.total_masa for i in items),
    }


# ============================================================
# RENDER FUNCTIONS
# ============================================================

def render_order_panel():
    """
    Panoul din dreapta: Comandă Curentă
    OPTIMIZED: Cantitățile sunt editate într-un form pentru a preveni reruns.
    """
    st.markdown("### Comandă Curentă")
    
    order_items = st.session_state.ob2_order_items
    
    if not order_items:
        st.info("Comandă goală. Selectează articole din lista din stânga.")
        return
    
    # Grupează pe subclasă pentru afișare
    by_subclass = {}
    for item in order_items.values():
        if item.subclasa not in by_subclass:
            by_subclass[item.subclasa] = []
        by_subclass[item.subclasa].append(item)
    
    # WRAP IN FORM to prevent reruns on quantity edit
    with st.form(key="ob2_order_edit_form"):
        qty_updates = {}  # Collect all quantity changes
        items_to_delete = []  # Collect items to delete
        
        for subclass, items in by_subclass.items():
            st.markdown(f"**{subclass}** ({len(items)} art)")
            
            for item in items:
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.markdown(f"**{item.cod}**")
                    st.caption(item.denumire[:30] + "..." if len(item.denumire) > 30 else item.denumire)
                
                with col2:
                    new_qty = st.number_input(
                        f"Cant. (sug: {item.qty_sugerata})",
                        min_value=0,
                        value=item.qty,
                        step=1,
                        key=f"qty_{item.cod}",
                        label_visibility="collapsed"
                    )
                    qty_updates[item.cod] = new_qty
                    st.caption(f"{item.cost:.0f} × {new_qty} = **{item.cost * new_qty:,.0f}** RON")
                
                with col3:
                    if st.checkbox("Sterge", key=f"del_{item.cod}", help="Marchează pentru ștergere"):
                        items_to_delete.append(item.cod)
            
            st.markdown("---")
        
        # Submit button for quantity updates
        submitted = st.form_submit_button("Actualizează Cantități", type="secondary")
    
    # Process form submission
    if submitted:
        # Apply quantity updates
        for cod, new_qty in qty_updates.items():
            if cod in st.session_state.ob2_order_items:
                st.session_state.ob2_order_items[cod].qty = max(0, new_qty)
        
        # Delete marked items
        for cod in items_to_delete:
            if cod in st.session_state.ob2_order_items:
                del st.session_state.ob2_order_items[cod]
        
        if items_to_delete:
            st.success(f"Șters {len(items_to_delete)} articole")
        st.rerun()
    
    # Totaluri (calculated fresh)
    totals = get_order_totals()
    st.markdown(f"""
    ### 📊 TOTAL
    | Metric | Valoare |
    |--------|---------|
    | **Articole** | {totals['count']} |
    | **Bucăți** | {totals['qty']} |
    | **Valoare** | {totals['value']:,.0f} RON |
    | **Cubaj** | {totals['cubaj']:.2f} m³ |
    | **Masă** | {totals['masa']:.1f} kg |
    """)
    
    # Butoane acțiuni (outside form)
    col_exp, col_clear = st.columns(2)
    with col_exp:
        if st.button("Export Excel", key="ob2_export", type="primary"):
            excel_data = export_order_excel()
            st.download_button(
                "⬇️ Descarcă",
                excel_data,
                f"comanda_{st.session_state.ob2_supplier or 'export'}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="ob2_download"
            )
    
    with col_clear:
        if st.button("Golește Tot", key="ob2_clear"):
            clear_order()
            st.rerun()


def render_subclass_list(subclass_summaries: List[dict]):
    """
    Lista subclase cu urgency badges și buton +
    """
    st.markdown("#### Subclase")
    st.caption(f"{len(subclass_summaries)} subclase, sortate după urgență")
    
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
        
        col1, col2 = st.columns([4, 1])
        
        with col1:
            label = f"**{sub['subclasa']}** ({sub['article_count']})"
            stats = f"C:{sub['critical_count']} U:{sub['urgent_count']} | {sub['total_value']:,.0f} RON"
            st.markdown(label)
            st.caption(stats)
        
        with col2:
            if st.button("Deschide", key=f"ob2_sub_{sub['subclasa'][:20]}", help="Deschide"):
                st.session_state.ob2_current_subclass = sub['subclasa']
                st.rerun()
        
        st.markdown("---")


def render_simulation_controls():
    """Panou control pentru simulare parametrii calcul"""
    with st.expander("Configurare Calcul Necesar (Simulare)", expanded=False):
        st.markdown("### Parametrii Simulare")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.session_state.sim_order_freq = st.number_input(
                "📅 Interval Comenzi (Zile)", 
                min_value=1, max_value=365, 
                value=st.session_state.sim_order_freq,
                help="La câte zile dai comandă? (Fostul 'Frecvență')"
            )
            st.session_state.sim_lead_time_override = st.number_input(
                "🚢 Override Lead Time (Zile)", 
                min_value=0, max_value=365,
                value=st.session_state.sim_lead_time_override,
                help="Pune 0 pentru a folosi Lead Time-ul din sistem. Orice altă valoare va suprascrie LT pentru TOATE produsele."
            )

        with c2:
            st.session_state.sim_safety_buffer = st.number_input(
                "🛡️ Buffer Siguranță Extra (Zile)", 
                value=st.session_state.sim_safety_buffer,
                help="Zile extra adăugate la stocul de siguranță."
            )
            st.session_state.sim_seasonal_factor = st.number_input(
                "📈 Multiplicator Sezon (Vânzări)",
                min_value=0.1, max_value=5.0, step=0.1,
                value=st.session_state.sim_seasonal_factor,
                help="Ex: 1.5 înseamnă că te aștepți la vânzări cu 50% mai mari (Sezon). 1.0 e normal."
            )

        with c3:
            st.markdown("**Opțiuni Speciale**")
            st.session_state.sim_ignore_moq = st.checkbox(
                "📦 Ignoră Baxarea (MOQ=1)",
                value=st.session_state.sim_ignore_moq,
                help="Calculează necesarul exact, fără rotunjire la bax."
            )
            st.info(
                "**Formula Nouă:**\\n"
                "`Necesar = ((MedieZi * Factor) * (LeadTime + Interval + Safety + Buffer)) - Stoc`"
            )


def render_articles_table(products_df: pd.DataFrame, config: dict, cubaj_data: dict = None):
    """
    Tabelul de articole cu checkbox pentru selecție.
    OPTIMIZED: Folosește date pre-calculate din DB, fără loop Product().
    Wrapped în st.form pentru a preveni reruns la fiecare bifare.
    """
    if products_df.empty:
        st.warning("Nu există articole în această subclasă.")
        return
    
    cubaj_data = cubaj_data or {}
    
    # Simulation Parameters
    sim_freq = st.session_state.get("sim_order_freq", 30)
    sim_buffer = st.session_state.get("sim_safety_buffer", 0)
    sim_factor = st.session_state.get("sim_seasonal_factor", 1.0)
    sim_lt_override = st.session_state.get("sim_lead_time_override", 0)
    sim_ignore_moq = st.session_state.get("sim_ignore_moq", False)

    # ----------------------------------------------------------------
    # VECTORIZED CALCULATION (FAST)
    # ----------------------------------------------------------------
    
    # 1. Fill NA to ensures numeric ops work
    df_calc = products_df.copy()
    cols_to_fix = ["avg_daily_sales", "lead_time_days", "safety_stock_days", "stoc_total", "stoc_tranzit", "moq", "vanzari_360z", "vanzari_4luni", "cost_achizitie", "pret_vanzare", "days_of_coverage"]
    for c in cols_to_fix:
        if c not in df_calc.columns:
            df_calc[c] = 0.0
        df_calc[c] = pd.to_numeric(df_calc[c], errors='coerce').fillna(0)

    # 2. Apply Simulation Parameters
    # Seasonality
    df_calc["sim_avg_daily"] = df_calc["avg_daily_sales"] * sim_factor
    
    # Lead Time Override
    if sim_lt_override > 0:
        df_calc["sim_lead_time"] = sim_lt_override
    else:
        df_calc["sim_lead_time"] = df_calc["lead_time_days"]
        
    # MOQ Override
    if sim_ignore_moq:
        df_calc["sim_moq"] = 1.0
    else:
        df_calc["sim_moq"] = df_calc["moq"].clip(lower=1.0)

    # 3. Calculate Formulas
    # Target Days = Lead + Interval + Safety + Buffer
    df_calc["target_days"] = df_calc["sim_lead_time"] + sim_freq + df_calc["safety_stock_days"] + sim_buffer
    
    # Target Qty
    df_calc["target_qty"] = df_calc["sim_avg_daily"] * df_calc["target_days"]
    
    # Stock
    df_calc["total_stock_avail"] = df_calc["stoc_total"] + df_calc["stoc_tranzit"]
    
    # Net Need
    df_calc["needed"] = (df_calc["target_qty"] - df_calc["total_stock_avail"]).clip(lower=0)
    
    # Rounding to MOQ
    # ceil(needed / moq) * moq
    df_calc["qty_suggested"] = np.ceil(df_calc["needed"] / df_calc["sim_moq"]) * df_calc["sim_moq"]
    
    # Dead Stock Rule (<3 sales in 360 days)
    # If sim_factor is extreme (>1.5), maybe ignore? No, stick to logic
    dead_mask = df_calc["vanzari_360z"] < 3
    df_calc.loc[dead_mask, "qty_suggested"] = 0
    
    # Prepare Display Columns
    df_calc["qty_suggested"] = df_calc["qty_suggested"].astype(int)
    
    # Details String (Vectorized string formatting? Can be slow. Use list comp mostly or just format when needed?)
    # Generating 1000 strings is okay-ish.
    # Let's simple format.
    # We can pre-calculate components
    
    def fmt_details(row):
        return (
            f"1. CONSUM: {row['avg_daily_sales']:.2f}/zi (x {sim_factor}) = {row['sim_avg_daily']:.2f}/zi || "
            f"2. DURATA: {row['sim_lead_time']:.0f} (Lead) + {sim_freq:.0f} (Int) + {row['safety_stock_days']+sim_buffer:.0f} (Safe) = {row['target_days']:.0f} Zile || "
            f"3. NECESAR: {row['sim_avg_daily']:.2f} x {row['target_days']:.0f} = {row['target_qty']:.0f} buc || "
            f"4. STOC: {row['stoc_total']:.0f} + {row['stoc_tranzit']:.0f} = {row['total_stock_avail']:.0f} || "
            f"5. FINAL: {row['target_qty']:.0f} - {row['total_stock_avail']:.0f} = {row['needed']:.0f} -> {row['qty_suggested']} (bax {row['sim_moq']:.0f})"
        )
            
    df_calc["details_calc"] = df_calc.apply(fmt_details, axis=1)
    
    # Map cubaj if needed
    # (Leaving iterating for cubaj map if dict provided, or map using map())
    # cubaj_data is dict: cod -> {cubaj_m3, ...}
    # Optimized map:
    if cubaj_data:
        df_calc["_cubaj"] = df_calc["cod_articol"].map(lambda x: cubaj_data.get(str(x), {}).get("cubaj_m3"))
        df_calc["_masa"] = df_calc["cod_articol"].map(lambda x: cubaj_data.get(str(x), {}).get("masa_kg"))
    else:
        df_calc["_cubaj"] = None
        df_calc["_masa"] = None
        
    # Construct Final DataFrame
    data_list = []
    # We can use to_dict('records') directly to be faster, but we need mapping to UI names
    # Mapping columns directly:
    
    df_ui = pd.DataFrame()
    df_ui["Sel"] = [False] * len(df_calc)
    df_ui["Cod"] = df_calc["cod_articol"].astype(str)
    # Name truncation
    df_ui["Produs"] = df_calc["denumire"].astype(str).str.slice(0, 25) + ".."
    df_ui["Seg"] = df_calc["segment"].fillna("OK")
    df_ui["Stoc"] = df_calc["stoc_total"].astype(int)
    df_ui["V.4L"] = df_calc["vanzari_4luni"].fillna(0).astype(int)
    df_ui["Cost"] = df_calc["cost_achizitie"].fillna(0).astype(int)
    df_ui["Cant"] = df_calc["qty_suggested"]
    
    # Extended
    df_ui["Denumire"] = df_calc["denumire"].astype(str)
    df_ui["Tranzit"] = df_calc["stoc_tranzit"].fillna(0).astype(int)
    df_ui["V.360"] = df_calc["vanzari_360z"].fillna(0).astype(int)
    df_ui["Med/Zi"] = df_calc["sim_avg_daily"].round(2)
    days_cov = df_calc["days_of_coverage"].fillna(999)
    df_ui["_days_cov_raw"] = np.where(days_cov < 999, days_cov.round(1), 999.0)
    df_ui["_lead_raw"] = df_calc["sim_lead_time"].astype(int)
    df_ui["_marja_raw"] = df_ui["_days_cov_raw"] - df_ui["_lead_raw"]
    
    # Apply Lead Time Alert styling (🔴 when Marja < 5)
    def fmt_with_alert(val, marja, is_marja=False):
        if marja < 5 and val < 999:
            return f"🔴 {val:.1f}" if isinstance(val, float) else f"🔴 {val}"
        return f"{val:.1f}" if isinstance(val, float) else str(val)
    
    df_ui["Zile Ac."] = df_ui.apply(lambda r: fmt_with_alert(r["_days_cov_raw"], r["_marja_raw"]), axis=1)
    df_ui["Lead"] = df_ui.apply(lambda r: fmt_with_alert(r["_lead_raw"], r["_marja_raw"]), axis=1)
    df_ui["Marja"] = df_ui.apply(lambda r: fmt_with_alert(r["_marja_raw"], r["_marja_raw"], True), axis=1)
    
    df_ui["PVanz"] = df_calc["pret_vanzare"].fillna(0).astype(int)
    df_ui["Cubaj"] = df_calc["_cubaj"]
    df_ui["Masa"] = df_calc["_masa"]
    df_ui["Detalii Calcul"] = df_calc["details_calc"]
    
    # Hidden
    df_ui["_cod"] = df_calc["cod_articol"].astype(str)
    df_ui["_denumire"] = df_calc["denumire"].astype(str)
    df_ui["_cost"] = df_calc["cost_achizitie"]
    df_ui["_cubaj"] = df_calc["_cubaj"]
    df_ui["_masa"] = df_calc["_masa"]
    df_ui["_qty"] = df_calc["qty_suggested"]
    df_ui["_segment"] = df_calc["segment"]

    df = df_ui

    
    # Toggle for extended details
    show_details = st.checkbox("📋 Detalii extinse", key="ob2_show_details", 
                               help="Afișează coloane suplimentare (tranzit, vânzări 360z, cubaj, detalii calcul)")
    
    # Primary columns (compact view) - now with Lead Time Alert columns
    primary_cols = ["Sel", "Cod", "Produs", "Seg", "Stoc", "V.4L", "Zile Ac.", "Lead", "Marja", "Cost", "Cant"]
    
    # Extended columns (all details)
    extended_cols = ["Sel", "Cod", "Denumire", "Seg", "Stoc", "Tranzit", "V.4L", "V.360", 
                     "Med/Zi", "Zile Ac.", "Lead", "Marja", "Cost", "PVanz", "Cubaj", "Masa", "Cant", "Detalii Calcul"]
    
    display_cols = extended_cols if show_details else primary_cols
    
    # WRAP IN FORM to prevent reruns on checkbox
    with st.form(key="ob2_article_selection_form"):
        edited_df = st.data_editor(
            df[display_cols],
            column_config={
                "Sel": st.column_config.CheckboxColumn("", default=False, width="small"),
                "Seg": st.column_config.TextColumn("Seg", width="small"),
                "Cant": st.column_config.NumberColumn("Cant", format="%d", width="small"),
                "Detalii Calcul": st.column_config.TextColumn("Detalii Calcul", width="medium", help="Explicatie calcul necesar"),
            },
            hide_index=True,
            height=400,
            key=f"ob2_articles_table_{show_details}"
        )
        
        # Submit button inside form
        submitted = st.form_submit_button("Adaugă Selectate în Comandă", type="primary")
    
    # Process selection only on form submit
    if submitted:
        selected_mask = edited_df["Sel"] == True
        selected_count = selected_mask.sum()
        
        if selected_count > 0:
            selected_df = df[selected_mask]
            items = []
            for idx in selected_df.index:
                row = df.iloc[idx]
                items.append(OrderItem(
                    cod=row["_cod"],
                    denumire=row["_denumire"],
                    qty_sugerata=int(row["_qty"]),
                    qty=int(row["_qty"]),
                    cost=row["_cost"],
                    cubaj=row["_cubaj"],
                    masa=row["_masa"],
                    subclasa=st.session_state.ob2_current_subclass,
                    furnizor=st.session_state.ob2_supplier,
                    segment=row["_segment"],
                ))
            add_to_order(items)
            st.success(f"✅ Adăugat {len(items)} articole!")
            st.rerun()
        else:
            st.warning("⚠️ Selectează cel puțin un articol.")
    
    # Show selection preview (outside form, updates on rerun)
    selected_mask = edited_df["Sel"] == True
    selected_count = selected_mask.sum()
    
    if selected_count > 0:
        selected_df = df[selected_mask]
        total_qty = int(selected_df["_qty"].sum())
        total_value = int((selected_df["_qty"] * selected_df["_cost"]).sum())
        
        st.markdown(f"""
        <div style="background: #f1f5f9; padding: 12px; border-radius: 4px; color: #0f172a; margin: 10px 0; border: 1px solid #cbd5e1;">
            <strong>{selected_count}</strong> selectate | 
            <strong>{total_qty}</strong> buc | 
            <strong>{total_value:,}</strong> RON
        </div>
        """, unsafe_allow_html=True)


def export_order_excel() -> bytes:
    """Export comanda ca Excel"""
    output = io.BytesIO()
    
    rows = []
    for item in st.session_state.ob2_order_items.values():
        rows.append({
            "Cod Articol": item.cod,
            "Denumire": item.denumire,
            "Furnizor": item.furnizor,
            "Subclasa": item.subclasa,
            "Segment": item.segment,
            "Cant. Sugerată": item.qty_sugerata,
            "Cantitate": item.qty,
            "Cost Unitar": item.cost,
            "Valoare": item.value,
            "Cubaj (m³)": item.total_cubaj,
            "Masa (kg)": item.total_masa,
        })
    
    if rows:
        df = pd.DataFrame(rows)
        df.to_excel(output, index=False, sheet_name="Comanda")
    
    return output.getvalue()


# ============================================================
# MAIN RENDER FUNCTION
# ============================================================

def render_order_builder_v2(config: dict, cubaj_data: dict = None):
    """
    Entry point pentru Order Builder v2.
    Renderizează întregul modul cu layout 2 coloane.
    
    Args:
        config: Configurație furnizori (lead time, etc)
        cubaj_data: Date cubaj pentru produse
    """
    from src.core.database import get_unique_suppliers, get_subclass_summary, load_subclass_products, get_supplier_priority_list
    
    init_order_state()
    
    # Fullscreen mode state
    if "ob2_fullscreen" not in st.session_state:
        st.session_state.ob2_fullscreen = False
    
    # Apply fullscreen CSS if enabled
    if st.session_state.ob2_fullscreen:
        st.markdown("""
        <style>
            /* Fullscreen mode - hide sidebar and expand content */
            [data-testid="stSidebar"] { display: none !important; }
            header { display: none !important; }
            .stTabs [data-baseweb="tab-list"] { display: none !important; }
            .main .block-container {
                max-width: 100% !important;
                padding: 0.5rem 1rem !important;
            }
        </style>
        """, unsafe_allow_html=True)
    
    # Header with fullscreen toggle
    col_title, col_fs = st.columns([6, 1])

    with col_title:
        st.markdown("## Order Builder")
        st.caption("Planșă rapidă pentru construirea comenzilor")
    with col_fs:
        fs_icon = "⊡ Exit" if st.session_state.ob2_fullscreen else "⛶ Full"
        if st.button(fs_icon, key="ob2_fullscreen_btn", help="Toggle Full Screen Mode"):
            st.session_state.ob2_fullscreen = not st.session_state.ob2_fullscreen
            st.rerun()

    # SIMULATION CONTROLS
    render_simulation_controls()

    
    # Header controls
    col_sup, col_search = st.columns([1, 2])
    
    with col_sup:
        # Get priority-sorted suppliers with segment counts
        supplier_list = get_supplier_priority_list()
        
        # Build options with formatted labels (badges)
        options = ["(alege)"]
        supplier_map = {}  # display_label -> furnizor name
        
        for s in supplier_list:
            label = s["furnizor"]
            badges = []
            if s["critical_count"] > 0:
                badges.append(f"🔴 {s['critical_count']}")
            if s["urgent_count"] > 0:
                badges.append(f"🟠 {s['urgent_count']}")
            if s["attention_count"] > 0:
                badges.append(f"🟡 {s['attention_count']}")
            
            if badges:
                label += "  " + "  ".join(badges)
            
            options.append(label)
            supplier_map[label] = s["furnizor"]
        
        selected_label = st.selectbox(
            "Furnizor",
            options,
            key="ob2_supplier_select"
        )
        
        if selected_label != "(alege)":
            st.session_state.ob2_supplier = supplier_map.get(selected_label, selected_label)
    
    with col_search:
        search_term = st.text_input(
            "Caută articol (cod sau denumire)",
            value=st.session_state.ob2_search,
            key="ob2_search_input",
            placeholder="Ex: COD123 sau PERSIAN"
        )
        st.session_state.ob2_search = search_term
    
    if not st.session_state.ob2_supplier:
        st.info("Selectează un furnizor pentru a începe.")
        return
    
    # Main layout: 2 columns
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        # Subclass list or articles table
        if st.session_state.ob2_current_subclass:
            # Show articles for selected subclass
            st.markdown(f"### {st.session_state.ob2_current_subclass}")
            
            if st.button("Înapoi", key="ob2_back"):
                st.session_state.ob2_current_subclass = None
                st.rerun()
            
            # Load products
            with st.spinner("Se încarcă..."):
                products_df = load_subclass_products(
                    st.session_state.ob2_supplier,
                    st.session_state.ob2_current_subclass
                )
            
            # Apply search filter if any
            if search_term:
                mask = (
                    products_df["cod_articol"].str.contains(search_term, case=False, na=False) |
                    products_df["denumire"].str.contains(search_term, case=False, na=False)
                )
                products_df = products_df[mask]
                st.caption(f"🔍 Filtrat: {len(products_df)} rezultate pentru '{search_term}'")
            
            render_articles_table(products_df, config, cubaj_data)
        
        else:
            # Show subclass list
            subclass_summaries = get_subclass_summary(st.session_state.ob2_supplier)
            
            # Apply search to subclass names too
            if search_term:
                subclass_summaries = [
                    s for s in subclass_summaries 
                    if search_term.lower() in s["subclasa"].lower()
                ]
            
            render_subclass_list(subclass_summaries)
    
    with col_right:
        render_order_panel()
