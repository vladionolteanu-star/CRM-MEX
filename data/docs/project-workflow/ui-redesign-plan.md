# 🎨 UI Redesign Plan: Enterprise Minimalism

**Data:** 13.01.2026  
**Autor:** QA Reviewer + System Architect  
**Problemă:** UI se simte "amator vibe coder", prea mult scroll vertical, butoane prea mari

---

## ❌ Probleme Identificate

| Problemă | Unde | Severitate |
|----------|------|------------|
| Scroll vertical excesiv | Toate tab-urile | 🔴 MAJOR |
| Butoane/inputs prea mari | Sidebar + forms | 🔴 MAJOR |
| Spațiere inconsistentă | Între componente | 🟠 MED |
| Prea multe expanders | În fiecare tab | 🟠 MED |
| Fonturi default Streamlit | Headers, body | 🟡 LOW |
| Lipsa breathing room | Totul e înghesuit vertical | 🔴 MAJOR |

---

## ✅ Design Goals (Enterprise Feel)

1. **Density over verbosity** - mai multă informație pe ecran, mai puține cuvinte
2. **Actions în context** - butoane lângă datele relevante, nu în sidebar
3. **Progressive disclosure** - arată puțin, expandează la cerere
4. **Consistent spacing** - grilă de 8px pentru tot
5. **Neutral color palette** - gri/albastru enterprise, nu culori vii

---

## 🛠️ Plan de Implementare

### Faza 1: Reduce Vertical Footprint (2-3 ore)

#### 1.1 Elimină "Help" expanderuri din fiecare tab
**Înainte:**
```
▶ ℹ️ Cum se calculează CRITICAL? (click pentru detalii)
   [30 linii de text explicativ]
```
**După:** Mută într-un singur "❓ Help Center" în Settings

---

#### 1.2 Sidebar mai compact
**Înainte:**
- Toggle PostgreSQL (height: 50px)
- Dropdown Furnizor (height: 60px)
- Dropdown Status (height: 60px)
- Expander Config (height: variable)

**După:**
```css
/* Compact sidebar */
section[data-testid="stSidebar"] .stSelectbox { margin-bottom: 4px !important; }
section[data-testid="stSidebar"] label { font-size: 0.75rem !important; }
```

---

#### 1.3 KPI Bar mai compact
**Înainte:** 5 st.metric cu delta, ~100px height  
**După:** Custom HTML bar, 40px height max

```python
# Replace st.metric cu custom HTML
st.markdown("""
<div style="display:flex; gap:12px; font-size:0.85rem;">
  <span>🔴 CRITICAL: <b>1,685</b></span>
  <span>🟠 URGENT: <b>18</b></span>
  ...
</div>
""", unsafe_allow_html=True)
```

---

### Faza 2: Buttons & Controls (2 ore)

#### 2.1 Butoane mai mici
```css
/* Compact buttons */
.stButton > button {
    padding: 4px 12px !important;
    font-size: 0.8rem !important;
    min-height: 32px !important;
}
```

---

#### 2.2 Inline actions (nu buton separat)
**Înainte:**
```
[Selectează produse]
          ↓
[Calculează Comandă] ← buton mare, separat
```

**După:**
```
[✓] Selectat  |  Cod  |  Denumire  |  [📊 Calculează]  ← inline button
```

---

### Faza 3: Layout Grid (3-4 ore)

#### 3.1 Two-column layout pentru Order Builder
**Înainte:** Tot pe o coloană, scroll down  
**După:** 
```
┌─────────────────────────┬──────────────────┐
│  Subclase (scrollable)  │  Comandă Curentă │
│                         │  (fixed)         │
└─────────────────────────┴──────────────────┘
```

---

#### 3.2 Fixed height tables
```python
st.dataframe(df, height=400)  # Fixed, nu mai crește cu datele
```

---

### Faza 4: Typography & Spacing (1-2 ore)

#### 4.1 Font enterprise
```css
.stApp {
    font-family: 'Inter', 'Segoe UI', -apple-system, sans-serif !important;
}
```

#### 4.2 Reduced padding
```css
.main .block-container {
    padding: 1rem 2rem !important;  /* de la 5rem */
    max-width: 1400px !important;
}
```

---

## 📐 Design Tokens (Propunere)

| Token | Valoare | Utilizare |
|-------|---------|-----------|
| `--space-xs` | 4px | Între elemente inline |
| `--space-sm` | 8px | Între controale |
| `--space-md` | 16px | Între secțiuni |
| `--space-lg` | 24px | Între module |
| `--color-text` | #374151 | Text primary |
| `--color-muted` | #9CA3AF | Text secondary |
| `--color-border` | #E5E7EB | Borders |
| `--font-size-sm` | 0.75rem | Labels, captions |
| `--font-size-base` | 0.875rem | Body text |
| `--font-size-lg` | 1rem | Headers |

---

## 📋 Checklist Implementare

### Quick Wins (1-2 ore)
- [ ] Elimină help expanders din tabs
- [ ] Reduce CSS padding în block-container
- [ ] Compact KPI bar cu custom HTML
- [ ] Font-size mai mic pentru labels

### Medium Effort (3-4 ore)
- [ ] Sidebar compact CSS
- [ ] Fixed height pentru tables
- [ ] Inline action buttons

### Major Refactor (6-8 ore)
- [ ] Two-column layout pentru Order Builder
- [ ] Unified design tokens în CSS
- [ ] Help Center centralizat în Settings

---

## ⚠️ Riscuri

> [!WARNING]
> Streamlit are limitări pentru customizare avansată.
> Unele modificări pot necesita workaround-uri CSS hacky.

> [!NOTE]
> Dacă se dorește un look 100% enterprise, considerarea migrării la React + FastAPI pe termen lung.
