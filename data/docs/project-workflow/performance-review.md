# 🔍 QA Review: Performance Optimization Analysis

**Data:** 13.01.2026  
**Reviewer:** QA Agent  
**Problemă:** Aplicația se mișcă foarte greu pe resursele actuale

---

## 📊 Diagnostic - Unde se pierde timpul?

### Bottleneck-uri Identificate

| Zonă | Cauză probabilă | Impact |
|------|-----------------|--------|
| **1. Reruns Streamlit** | La fiecare interacțiune, Streamlit re-execută tot scriptul | 🔴 MAJOR |
| **2. Parse Product()** | Loop ~57K produse × creare obiecte Python | 🔴 MAJOR |
| **3. UI Tables** | `st.data_editor` pe mii de rânduri | 🟠 MEDIUM |
| **4. CSS Injection** | `st.markdown(CSS)` la fiecare rerun | 🟡 LOW |
| **5. DB Queries** | Multiple query-uri separate pentru segment counts | 🟠 MEDIUM |

---

## ⚡ Propuneri de Optimizare

### 🔴 HIGH IMPACT

#### 1. `st.fragment` pentru componente izolate
**Problemă:** Orice click face rerun la tot app.py  
**Soluție:** Wrap componente în `@st.fragment` (Streamlit 1.33+)

```python
@st.fragment
def render_articles_table(...):
    # Această funcție nu mai cauzează rerun global
    ...
```

**Efort:** 2-4 ore  
**Impact:** 50-70% reducere reruns

---

#### 2. Eliminare loop `Product()` - folosește DataFrame direct
**Problemă:** `parse_from_postgres()` creează ~57K obiecte Python  
**Soluție:** Lucrează direct cu DataFrame, fără conversie la obiecte

**Cod actual:**
```python
products = parse_from_postgres(raw_df, ...)  # LENT
```

**Cod optimizat:**
```python
# Folosește raw_df direct, calcule vectorizate cu pandas
df['segment'] = ...  # deja calculat în DB
df['status_display'] = df.apply(lambda r: f"🚨 {r['segment']}" if ..., axis=1)
```

**Efort:** 4-6 ore  
**Impact:** 60-80% reducere timp procesare

---

#### 3. Pagination server-side obligatorie
**Problemă:** Se încarcă 1000+ rânduri deodată în UI  
**Soluție:** Maximum 100 rânduri per pagină, lazy load

```python
# În database.py
def load_segment_from_db(..., limit=100, offset=0):
```

**Efort:** 2 ore  
**Impact:** 40-50% reducere memorie UI

---

### 🟠 MEDIUM IMPACT

#### 4. Batch query pentru segment counts
**Problemă:** Multiple query-uri separate pentru fiecare segment  
**Soluție:** Un singur query care returnează toate counts

**Cod actual:**
```python
critical = get_segment_counts("CRITICAL")
urgent = get_segment_counts("URGENT")
# ...4 apeluri separate
```

**Cod optimizat:**
```python
# Un singur query
all_counts = get_all_segment_counts()  # returnează dict cu toate
```

**Efort:** 1 oră  
**Impact:** 20-30% reducere timp DB

---

#### 5. Reduce coloane în DataFrame
**Problemă:** Se încarcă toate 35+ coloane chiar dacă nu sunt afișate  
**Soluție:** Load doar coloanele necesare per view

```sql
-- Pentru lista subclase (nu e nevoie de stocuri per magazin)
SELECT cod_articol, denumire, segment, suggested_qty
FROM products WHERE ...
```

**Efort:** 2 ore  
**Impact:** 30-40% reducere memorie

---

#### 6. Cache CSS în session_state
**Problemă:** `st.markdown(CSS)` se execută la fiecare rerun  
**Soluție:** Inject CSS o singură dată

```python
if "css_loaded" not in st.session_state:
    st.markdown("""<style>...</style>""", unsafe_allow_html=True)
    st.session_state.css_loaded = True
```

**Efort:** 30 min  
**Impact:** 5-10% reducere timp render

---

### 🟡 LOW IMPACT (Nice to have)

#### 7. Lazy load tabs
**Problemă:** Toate tab-urile se renderizează chiar dacă nu sunt vizibile  
**Soluție:** Renderizează doar tab-ul activ

```python
selected_tab = st.session_state.get("active_tab", "CRITICAL")
if selected_tab == "CRITICAL":
    render_critical_tab()
# ...
```

**Efort:** 3-4 ore (refactoring major)  
**Impact:** 20-30% reducere timp inițial

---

#### 8. WebSocket pentru updates în timp real
**Problemă:** Polling / rerun la fiecare acțiune  
**Soluție:** Streamlit callbacks + state management eficient

**Efort:** 8+ ore (complex)  
**Impact:** UX îmbunătățit, nu neapărat viteză

---

## 📋 Prioritate Implementare Recomandată

| Prio | Optimizare | Efort | Impact | Quick Win? |
|------|------------|-------|--------|------------|
| 1 | `st.fragment` wrapping | 2-4h | 🔴 HIGH | ✅ Da |
| 2 | Pagination 100 rânduri | 2h | 🔴 HIGH | ✅ Da |
| 3 | Reduce coloane query | 2h | 🟠 MED | ✅ Da |
| 4 | Batch segment counts | 1h | 🟠 MED | ✅ Da |
| 5 | Eliminare Product() loop | 4-6h | 🔴 HIGH | ❌ Nu |
| 6 | Cache CSS | 30min | 🟡 LOW | ✅ Da |
| 7 | Lazy tabs | 3-4h | 🟡 LOW | ❌ Nu |
| 8 | WebSocket | 8h+ | 🟡 LOW | ❌ Nu |

---

## 🎯 Recomandare Quick Wins

Începe cu **items 1-4** (total ~7-9 ore) pentru cel mai mare impact imediat:

1. ✅ Wrap `render_interactive_table` în `@st.fragment`
2. ✅ Forțează paginare 100 rânduri
3. ✅ Reduce coloane în query-uri
4. ✅ Batch segment counts

**Rezultat așteptat:** 40-60% îmbunătățire percepută

---

## ⚠️ Atenționări

> [!CAUTION]
> **Nu modifica logica de business** în timpul optimizărilor performance.
> Fiecare optimizare trebuie testată separat.

> [!NOTE]
> Streamlit are limitări inerente pentru aplicații mari.
> Pentru scalare pe termen lung, consideră migrare la **FastAPI + React/Vue**.
