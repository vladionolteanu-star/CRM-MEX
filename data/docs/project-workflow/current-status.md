# Status Proiect: TCIOARA Acquisition Forecast System

**Ultima Actualizare:** 13.01.2026, 11:53

---

## 🎯 Obiectiv Principal
Sistem de monitorizare stocuri și suport decizii pentru aprovizionarea covoarelor Mobexpert (INDOMEX).

---

## 👥 Echipa (Roluri Agenți)

| Rol | Fișier |
|-----|--------|
| 🏗️ System Architect | `architect.md` |
| 📦 Supply Chain Strategist | `supply-chain-strategist.md` |
| 🐍 Python Developer | `developer.md` |
| 🔍 QA Reviewer | `qa-reviewer.md` |

---

## 🚦 Status Board

### Core Features - ✅ IMPLEMENTATE

| Componentă | Status | Detalii |
|------------|--------|---------|
| Streamlit Dashboard | ✅ Done | `src/ui/app.py` - ~2200 linii |
| PostgreSQL Backend | ✅ Done | Toggle în sidebar |
| Segmentare Stoc | ✅ Done | CRITICAL/URGENT/ATTENTION/OK/OVERSTOCK |
| Config per Furnizor | ✅ Done | Lead Time, Safety Stock, MOQ |
| Gemini AI Integration | ✅ Done | Analiză furnizor cu AI |
| Family View | ✅ Done | Tab separat |
| Supplier Audit | ✅ Done | Tab audit per furnizor |
| **Modul Cubaj** | ✅ Done | Volum cilindric + masă din CSV |
| **Order Builder** | ✅ Done | Construire comandă pe subclasă |
| **🆕 Supplier Priority Dropdown** | ✅ Done | Sortare furnizori după urgență + badge-uri 🔴🟠🟡 |
| **🆕 Red Alert 🚨** | ✅ Done | Indicator roșu în coloana Status pentru CRITICAL |
| **🆕 Fullscreen Mode** | ✅ Done | Buton ⛶ Full în Order Builder v2 |
| **🆕 Tab Cleanup** | ✅ Done | Ascunse 4 tab-uri nefolosite |

---

## ⏳ Features În Așteptare (din Analiza 29 Dec)

| # | Feature | Status | Spec |
|---|---------|--------|------|
| 1 | Alertă Acoperire (Font Roșu) | ✅ Done | 🚨 indicator în Status |
| 2 | Cubaj / MP în tabel | ✅ Done | `cubaj-module-spec.md` |
| 3 | Vedere Trimestrială | ⏳ Pending | - |
| 4 | Import Comenzi Tranzit | ⏳ Pending | - |
| 5 | Calcul Cantități Sugerate | ✅ Done | Formula 3.0 |
| 6 | Data Chat (OPUS) | ⏳ Pending | - |
| 7 | **Order Builder pe Subclasă** | ✅ Done | `subclass-order-builder-spec.md` |
| 8 | Top Urgențe Vizualizare | ✅ Done | Integrat în Order Builder |
| 9 | Dead Stock Flag | ✅ Done | `is_dead_stock` în Product |

---

## 📂 Structura Cod Sursă

```
src/
├── core/
│   ├── database.py       # PostgreSQL + subclass functions
│   ├── loader.py         # CSV DataLoader
│   └── cubaj_loader.py   # Cubaj din CSV
├── models/
│   └── product.py        # Pydantic Product model
└── ui/
    └── app.py            # Streamlit dashboard (~2200 linii)

data/docs/specs/
├── cubaj-module-spec.md
└── subclass-order-builder-spec.md
```

---

## 🆕 Order Builder v2 (Ultima actualizare: 13.01.2026)

**Tab:** "📦 ORDER v2"

**Flux:**
1. **Selectează furnizor → dropdown PRIORITIZAT** (🔴🟠🟡 badge-uri)
2. Furnizorii sunt sortați după urgență (CRITICAL first)
3. Vezi subclase sortate după urgență
4. Click ➕ → tabel COMPLET cu articole
5. **Live Totals** - actualizare automată (articole, buc, RON, cubaj, masă)
6. Adaugă în comandă → Export Excel

**Database functions:**
- `get_supplier_priority_list()` - **NOU 13.01** - sortare + contoare per segment
- `get_subclass_summary(furnizor)`
- `load_subclass_products(furnizor, subclasa)`

---

## 📝 Next Steps

### Faza 1: Advanced Features (În Așteptare)
- [ ] **Import comenzi în tranzit** (Settings) - structură: cod, cantitate, data comandă, ETA
- [ ] **Data Chat (OPUS)** - interogări în limbaj natural + chat AI interactiv
- [ ] **Vedere Trimestrială** - agregate Q1/Q2/Q3/Q4 în UI
- [ ] **Data Primei Intrări** - coloană nouă în tabel (date lipsă în DB)

### Faza 1.5: Performance Optimization (✅ DONE)
- [x] Spec Created (`docs/specs/order-builder-performance-spec.md`)
- [x] Bugfix: Cubaj Missing Data (Fixed key mismatch)
- [x] Pre-calculare `suggested_qty` în DB
- [x] Eliminat loop `Product()` din UI
- [x] Wrap UI în `st.form()` (nu mai face rerun la fiecare click)
- [x] **Supplier Priority Dropdown** - sortare + badge-uri urgență (13.01.2026)

### Faza 2: Polish & UX (✅ PARTIAL - 13.01.2026)
- [x] **Alertă Font Roșu 🚨** - indicator în coloana Status pentru CRITICAL/urgent
- [x] **Fullscreen Mode** - buton ⛶ Full în Order Builder v2
- [x] **Tab Cleanup** - ascunse 4 tab-uri nefolosite
- [ ] Cantitate Sugerată editabilă (stil Excel)
- [ ] Mobile optimization

### Faza 3: Performance (NEXT)
- [ ] ⚡ Optimizare viteză generală - app-ul se mișcă greu

---

## 📋 Backlog din Analiza 29 Dec - Status

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Cubaj / MP în tabel | ✅ Done | `cubaj-module-spec.md` |
| 2 | Alertă Font Roșu (<10 zile) | ✅ Done | 🚨 indicator |
| 3 | Vedere Trimestrială | ⏳ Pending | Q1/Q2/Q3/Q4 agregat |
| 4 | Import Comenzi Tranzit | ⏳ Pending | Settings + impact formule |
| 5 | Cantitate Sugerată (cu/fără tranzit) | ⚠️ Partial | Există fără tranzit |
| 6 | Data Chat (OPUS) | ⏳ Pending | Chat AI interactiv |
| 7 | Order Builder pe Subclasă | ✅ Done | Tab ORDER v2 |
| 8 | Top Urgențe per Furnizor | ✅ Done | **Dropdown prioritizat** |
| 9 | Dead Stock Flag | ✅ Done | `is_dead_stock` în Product |
| 10 | Data Primei Intrări | ⏳ Pending | Date lipsă în sursă |
