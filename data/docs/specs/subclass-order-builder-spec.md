# 📦 SPECIFICAȚIE TEHNICĂ: Subclass Order Builder

**Versiune:** 1.1  
**Data:** 12.01.2026  
**Autor:** System Architect  
**Status:** ✅ READY FOR DEVELOPMENT  

---

## 1. CONTEXT BUSINESS

### 1.1 Problemă
> "Când rămâi fără 4-5 covoare de la un furnizor, nu ai cum să le comanzi doar pe alea - trebuie să faci 1 camion întreg și să mai iei și altele de la acel furnizor ca să nu transporti aer."

### 1.2 Soluție
**Subclass Order Builder** = mod de a vedea **toată subclasa** (toate articolele) cu **toate coloanele** din "detalii extinse", unde buyer-ul bifează individual ce adaugă în comandă.

---

## 2. DECIZII CONFIRMATE

| # | Întrebare | Răspuns |
|---|-----------|---------|
| Q1 | UI Selection | **Buton "+"** pe fiecare subclass card |
| Q2 | Editare | **B)** Poate vedea/edita fiecare SKU individual |
| Q3 | MOQ | Se aplică **per articol** |
| Q4 | Export | **Excel** |
| Q5 | Persistență | **Session only** (se pierde la închidere) |
| Q6 | Top Urgențe | **Sortare în Order Builder** (nu dashboard separat) |

---

## 3. FLUX UI/UX

```
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Selectează Furnizor → Dropdown                                  │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Subclase Disponibile (sortate by urgență)                       │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 🔴 COVOARE PERSANE (12 art)                               [+ ADD] │  │
│  │    CRITICAL: 5 | URGENT: 3 | Val: 12,500 RON | 2.3 m³             │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 🟠 COVOARE KILIM (8 art)                                  [+ ADD] │  │
│  │    CRITICAL: 0 | URGENT: 6 | Val: 8,200 RON | 1.8 m³              │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓ (Click + ADD)
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 3: ARTICOLE DIN SUBCLASĂ (toate coloanele din "detalii extinse")   │
├─────────────────────────────────────────────────────────────────────────┤
│ ☑️ Selectează pentru comandă                                            │
│ ─────────────────────────────────────────────────────────────────────── │
│ │☐│Cod     │Produs        │Cost│Stoc│V.3L│Oct│Nov│Dec│Status │Cant.Sug│ │
│ │☑│COD123  │PERSIAN 200x30│450 │  5 │  8 │ 2 │ 3 │ 3 │CRITICAL│   12   │ │
│ │☑│COD124  │PERSIAN 150x20│320 │  3 │  5 │ 1 │ 2 │ 2 │URGENT  │    8   │ │
│ │☐│COD125  │PERSIAN 120x18│280 │ 15 │  2 │ 0 │ 1 │ 1 │OK      │    0   │ │
│ │☑│COD126  │PERSIAN 080x12│180 │  0 │  4 │ 1 │ 2 │ 1 │CRITICAL│    6   │ │
│ └─┴────────┴──────────────┴────┴────┴────┴───┴───┴───┴───────┴────────┘ │
│                                                                          │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ 📊 LIVE TOTALS (actualizare automată la bifare)                      │ │
│ │ ──────────────────────────────────────────────────────────────────── │ │
│ │  ☑ SELECTATE: 3 articole                                            │ │
│ │  📦 CANTITATE: 26 buc                                                │ │
│ │  💰 VALOARE: 8,760 RON                                               │ │
│ │  📐 CUBAJ: 0.82 m³                                                   │ │
│ │  ⚖️ MASĂ: 45.2 kg                                                    │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ [✓ Adaugă în Comandă]  [← Înapoi la Subclase]                            │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 4: COMANDĂ CURENTĂ (sumar)                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ ✓ COVOARE PERSANE: 3 art | 26 buc | 8,760 RON       [Editează] [❌]     │
│ ✓ COVOARE KILIM: 5 art | 18 buc | 5,400 RON         [Editează] [❌]     │
│ ─────────────────────────────────────────────────────────────────────── │
│ TOTAL: 8 articole | 44 bucăți | 14,160 RON | 2.6 m³                     │
│                                                                          │
│ [📤 Export Excel]                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. COMPONENTE TEHNICE

### 4.1 Database Functions (în `database.py`)

```python
def get_unique_subclasses(furnizor: str = None) -> List[str]:
    """Lista subclase (opțional filtrată pe furnizor)."""

def get_subclass_summary(furnizor: str) -> List[dict]:
    """
    Sumar pe subclase pentru un furnizor.
    
    Returns: [{
        "subclasa": str,
        "article_count": int,
        "critical_count": int,
        "urgent_count": int,
        "total_value": float,
        "urgency_score": float  # pentru sortare
    }]
    """

def load_subclass_products(furnizor: str, subclasa: str) -> pd.DataFrame:
    """Toate articolele dintr-o subclasă cu toate coloanele."""
```

### 4.2 UI Components (în `app.py`)

```python
# Tab nou sau secțiune în main()
def render_order_builder():
    """Renderizează Order Builder complet."""
    
def render_subclass_cards(summaries: List[dict]):
    """Carduri subclase cu buton +."""
    
def render_subclass_articles(products: List[Product]):
    """Tabel articole cu checkbox selecție."""
    
def render_order_summary():
    """Sumar comandă curentă cu export."""
```

### 4.3 Session State

```python
# st.session_state
{
    "order_builder_supplier": str,           # Furnizor selectat
    "order_builder_current_subclass": str,   # Subclasă în editare
    "order_items": {                          # Comandă în construcție
        "SUBCLASA_1": [
            {"cod": "X", "qty": 10, "cost": 450, ...},
            ...
        ],
        "SUBCLASA_2": [...],
    }
}
```

---

## 5. IMPLEMENTARE DETALIATĂ

### 5.1 Structura Tab-ului Order Builder

```python
with tab_order_builder:
    st.markdown("### 📦 Order Builder")
    
    # 1. Furnizor selector
    suppliers = get_unique_suppliers()
    selected_supplier = st.selectbox("Furnizor", suppliers)
    
    if selected_supplier:
        # 2. Subclass cards (sorted by urgency)
        subclass_summaries = get_subclass_summary(selected_supplier)
        subclass_summaries.sort(key=lambda x: -x["urgency_score"])
        
        for sub in subclass_summaries:
            col1, col2 = st.columns([5, 1])
            with col1:
                # Card info
                badge = "🔴" if sub["critical_count"] > 0 else ("🟠" if sub["urgent_count"] > 0 else "🟢")
                st.markdown(f"""
                **{badge} {sub["subclasa"]}** ({sub["article_count"]} art)
                CRITICAL: {sub["critical_count"]} | URGENT: {sub["urgent_count"]} | {sub["total_value"]:,.0f} RON
                """)
            with col2:
                if st.button("➕", key=f"add_{sub['subclasa']}"):
                    st.session_state["current_subclass"] = sub["subclasa"]
        
        # 3. If subclass selected → show articles table
        if st.session_state.get("current_subclass"):
            subclass = st.session_state["current_subclass"]
            products = load_subclass_products(selected_supplier, subclass)
            
            # Parsare în Product objects, apoi render cu render_interactive_table
            # sau versiune simplificată cu checkbox
            
            # ... (reutilizare logică din render_interactive_table)
    
    # 4. Order summary panel
    render_order_summary()
```

---

## 6. FUNCȚII EXPORT

### 6.1 Export Excel

```python
def export_order_to_excel(order_items: dict) -> bytes:
    """
    Generează Excel cu toate articolele din comandă.
    
    Coloane:
    - Cod Articol, Denumire, Furnizor, Subclasă
    - Cantitate Comandată, Cost Unitar, Valoare Totală
    - Stoc Curent, Vânzări 4L, Status
    """
    import io
    output = io.BytesIO()
    
    # Flatten order_items to DataFrame
    rows = []
    for subclass, items in order_items.items():
        for item in items:
            rows.append({
                "Cod": item["cod"],
                "Denumire": item["name"],
                "Subclasa": subclass,
                "Cantitate": item["qty"],
                "Cost": item["cost"],
                "Valoare": item["qty"] * item["cost"],
                ...
            })
    
    df = pd.DataFrame(rows)
    df.to_excel(output, index=False)
    return output.getvalue()
```

---

## 7. TIMELINE IMPLEMENTARE

| Task | Efort | Prioritate |
|------|-------|------------|
| Database functions (3 funcții) | 2h | 🔴 |
| Subclass cards UI | 2h | 🔴 |
| Articles table cu selecție | 3h | 🔴 |
| Order summary panel | 2h | 🟡 |
| Export Excel | 1h | 🟡 |
| Session state management | 1h | 🔴 |
| Testing | 2h | 🟡 |
| **TOTAL** | **13h** | |

---

## 8. DEPENDENȚE

- ✅ Modul Cubaj (pentru afișare volum)
- ✅ `render_interactive_table()` logică (reutilizabilă)
- ✅ Segment pre-calculat în DB

---

> [!NOTE]
> **Spec FINALIZATĂ** - Ready for Developer.
