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
    st.markdown("### 📋 Comandă Curentă")
    
    order_items = st.session_state.ob2_order_items
    
    if not order_items:
        st.info("🛒 Comandă goală. Selectează articole din lista din stânga.")
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
            st.markdown(f"**📦 {subclass}** ({len(items)} art)")
            
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
                    if st.checkbox("🗑️", key=f"del_{item.cod}", help="Marchează pentru ștergere"):
                        items_to_delete.append(item.cod)
            
            st.markdown("---")
        
        # Submit button for quantity updates
        submitted = st.form_submit_button("💾 Actualizează Cantități", type="secondary")
    
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
            st.success(f"🗑️ Șters {len(items_to_delete)} articole")
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
        if st.button("📤 Export Excel", key="ob2_export", type="primary"):
            excel_data = export_order_excel()
            st.download_button(
                "⬇️ Descarcă",
                excel_data,
                f"comanda_{st.session_state.ob2_supplier or 'export'}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="ob2_download"
            )
    
    with col_clear:
        if st.button("🗑️ Golește Tot", key="ob2_clear"):
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
            label = f"{badge} **{sub['subclasa']}** ({sub['article_count']})"
            stats = f"C:{sub['critical_count']} U:{sub['urgent_count']} | {sub['total_value']:,.0f} RON"
            st.markdown(label)
            st.caption(stats)
        
        with col2:
            if st.button("➕", key=f"ob2_sub_{sub['subclasa'][:20]}", help="Deschide"):
                st.session_state.ob2_current_subclass = sub['subclasa']
                st.rerun()
        
        st.markdown("---")


def render_simulation_controls():
    """Panou control pentru simulare parametrii calcul"""
    with st.expander("🧮 Configurare Calcul Necesar (Simulare)", expanded=False):
        st.markdown("Aici poți 'pitroci' formula prin modificarea parametrilor în timp real.")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.session_state.sim_order_freq = st.number_input(
                "Frecvență Comenzi (zile)", 
                min_value=1, max_value=365, 
                value=st.session_state.sim_order_freq,
                help="La câte zile dai comandă? (Standard: 30)"
            )
        with c2:
            st.session_state.sim_safety_buffer = st.number_input(
                "Buffer Siguranță (zile)", 
                value=st.session_state.sim_safety_buffer,
                help="Zile extra adăugate la stocul de siguranță (Standard: 0)"
            )
        with c3:
            st.info(
                "**Formula:**\\n"
                "`Necesar = (MedieZi * (LeadTime + Freq + Safety + Buffer)) - (Stoc + Tranzit)`"
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

    # Build table data directly from DataFrame (NO Product() loop!)
    data = []
    for _, row in products_df.iterrows():
        cod = str(row.get("cod_articol", ""))
        cubaj_info = cubaj_data.get(cod, {})
        
        # Raw Data extraction
        avg_daily = float(row.get("avg_daily_sales", 0) or 0)
        lead_time = float(row.get("lead_time_days", 30) or 30)
        safety_stock = float(row.get("safety_stock_days", 7) or 7)
        stock_total = float(row.get("stoc_total", 0) or 0)
        transit = float(row.get("stoc_tranzit", 0) or 0)
        moq = float(row.get("moq", 1) or 1) # Avoid division by zero
        if moq < 1: moq = 1
        sales_360 = float(row.get("vanzari_360z", 0) or 0)
        segment = str(row.get("segment", "OK"))
        days_cov = float(row.get("days_of_coverage", 999) or 999)

        # ----------------------------------------------------------------
        # REAL-TIME CALCULATION (SIMULATION)
        # ----------------------------------------------------------------
        calc_details = ""
        suggested_qty = 0
        
        # Dead Stock Rule
        if sales_360 < 3:
            suggested_qty = 0
            calc_details = "Dead Stock (<3 vanzari/an)"
        else:
            # Target Stock (Days) = LeadTime + OrderFreq + SafetyStock + Buffer
            target_days = lead_time + sim_freq + safety_stock + sim_buffer
            
            # Target Quantity
            target_qty = avg_daily * target_days
            
            # Net Need
            needed = target_qty - (stock_total + transit)
            needed = max(0, needed)
            
            # MOQ Rounding
            suggested_qty = math.ceil(needed / moq) * moq
            suggested_qty = int(suggested_qty)
            
            # Detailed explanation for tooltip/column
            # Formula: (Avg * Days) - Stock
            calc_details = (f"Target: {target_qty:.1f} buc (Acoperire {target_days:.0f} zile)\\n"
                            f"Formula: ({avg_daily:.2f}/zi * ({lead_time:.0f} LT + {sim_freq:.0f} Freq + {safety_stock + sim_buffer:.0f} Safe)) - ({stock_total:.0f} Stoc + {transit:.0f} Tranzit)")

        
        data.append({
            "☑️": False,
            # PRIMARY COLUMNS
            "Cod": cod,
            "Produs": (str(row.get("denumire", ""))[:25] + ".." 
                      if len(str(row.get("denumire", ""))) > 25 
                      else str(row.get("denumire", ""))),
            "Seg": segment,
            "Stoc": int(stock_total),
            "V.4L": int(row.get("vanzari_4luni", 0) or 0),
            "Cost": int(row.get("cost_achizitie", 0) or 0),
            "Cant": suggested_qty,
            # EXTENDED COLUMNS
            "Denumire": str(row.get("denumire", "")),
            "Tranzit": int(transit),
            "V.360": int(sales_360),
            "Med/Zi": round(avg_daily, 2),
            "Zile Ac.": round(days_cov, 1) if days_cov < 999 else 999.0,
            "Lead": int(lead_time),
            "Cubaj": f"{cubaj_info.get('cubaj_m3', 0):.3f}" if cubaj_info.get('cubaj_m3') else "-",
            "Masa": f"{cubaj_info.get('masa_kg', 0):.1f}" if cubaj_info.get('masa_kg') else "-",
            "PVanz": int(row.get("pret_vanzare", 0) or 0),
            "Detalii Calcul": calc_details,
            # Hidden for calculations
            "_cod": cod,
            "_denumire": str(row.get("denumire", "")),
            "_cost": float(row.get("cost_achizitie", 0) or 0),
            "_cubaj": cubaj_info.get("cubaj_m3"),
            "_masa": cubaj_info.get("masa_kg"),
            "_qty": suggested_qty,
            "_segment": segment,
        })
    
    df = pd.DataFrame(data)
    
    # Toggle for extended details
    show_details = st.checkbox("📋 Detalii extinse", key="ob2_show_details", 
                               help="Afișează coloane suplimentare (tranzit, vânzări 360z, cubaj, detalii calcul)")
    
    # Primary columns (compact view)
    primary_cols = ["☑️", "Cod", "Produs", "Seg", "Stoc", "V.4L", "Cost", "Cant"]
    
    # Extended columns (all details)
    extended_cols = ["☑️", "Cod", "Denumire", "Seg", "Stoc", "Tranzit", "V.4L", "V.360", 
                     "Med/Zi", "Zile Ac.", "Lead", "Cost", "PVanz", "Cubaj", "Masa", "Cant", "Detalii Calcul"]
    
    display_cols = extended_cols if show_details else primary_cols
    
    # WRAP IN FORM to prevent reruns on checkbox
    with st.form(key="ob2_article_selection_form"):
        edited_df = st.data_editor(
            df[display_cols],
            column_config={
                "☑️": st.column_config.CheckboxColumn("", default=False, width="small"),
                "Seg": st.column_config.TextColumn("Seg", width="small"),
                "Cant": st.column_config.NumberColumn("Cant", format="%d", width="small"),
                "Detalii Calcul": st.column_config.TextColumn("Detalii Calcul", width="medium", help="Explicatie calcul necesar"),
            },
            hide_index=True,
            height=400,
            key=f"ob2_articles_table_{show_details}"
        )
        
        # Submit button inside form
        submitted = st.form_submit_button("✅ Adaugă Selectate în Comandă", type="primary")
    
    # Process selection only on form submit
    if submitted:
        selected_mask = edited_df["☑️"] == True
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
    selected_mask = edited_df["☑️"] == True
    selected_count = selected_mask.sum()
    
    if selected_count > 0:
        selected_df = df[selected_mask]
        total_qty = int(selected_df["_qty"].sum())
        total_value = int((selected_df["_qty"] * selected_df["_cost"]).sum())
        
        st.markdown(f"""
        <div style="background: #1e293b; padding: 12px; border-radius: 8px; color: white; margin: 10px 0;">
            ☑️ <strong>{selected_count}</strong> selectate | 
            📦 <strong>{total_qty}</strong> buc | 
            💰 <strong>{total_value:,}</strong> RON
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
        st.markdown("## 📦 Order Builder v2")
        st.markdown("*Planșă rapidă pentru construirea comenzilor*")
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
            "🏭 Furnizor",
            options,
            key="ob2_supplier_select"
        )
        
        if selected_label != "(alege)":
            st.session_state.ob2_supplier = supplier_map.get(selected_label, selected_label)
    
    with col_search:
        search_term = st.text_input(
            "🔍 Caută articol (cod sau denumire)",
            value=st.session_state.ob2_search,
            key="ob2_search_input",
            placeholder="Ex: COD123 sau PERSIAN"
        )
        st.session_state.ob2_search = search_term
    
    if not st.session_state.ob2_supplier:
        st.info("👆 Selectează un furnizor pentru a începe.")
        return
    
    # Main layout: 2 columns
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        # Subclass list or articles table
        if st.session_state.ob2_current_subclass:
            # Show articles for selected subclass
            st.markdown(f"### 📋 {st.session_state.ob2_current_subclass}")
            
            if st.button("← Înapoi la Subclase", key="ob2_back"):
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
