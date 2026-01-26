# Spec: Optimizare Viteză Order Builder v2

**Data:** 12.01.2026  
**Autor:** System Architect  
**Status:** În implementare

---

## Problema

Order Builder v2 se mișcă lent (3-5 sec per click) din cauza:

### Cauze Primare
1. **Bucla Python per-produs** în `render_articles_table()` (L244-274)
2. **Crearea obiectului `Product()`** pentru fiecare rând
3. **Calculul `suggested_order_qty`** la runtime (15+ formule)

### Cauze Secundare (Reruns Excesive)
4. **`st.number_input` trigger** (L143-150): Fiecare keystroke în câmpul de cantitate face rerun la toată pagina
5. **`st.data_editor` fără form** (L326-336): Fiecare bifare checkbox triggeruie rerun complet
6. **Recalculare la fiecare rerun**: Toate calculele Product() se refac de la zero

---

## Soluția

### Faza 1: Pre-calculare `suggested_qty` în DB
- Script: `precompute_segments.py`
- Adăugare coloană `suggested_qty` în tabela `products`

### Faza 2: Simplificare `render_articles_table()`
- Fișier: `src/ui/order_builder.py`
- Eliminare loop Python, folosire directă DataFrame din DB

### Faza 3: Paginare Server-Side
- Fișier: `src/core/database.py`
- Adăugare `LIMIT 100 OFFSET x` în query

### Faza 4: Wrap UI în `st.form()` (NOU)
- **Tabel articole**: `st.data_editor` într-un `st.form("article_selection")`
  - Bifele nu mai fac rerun
  - Buton "Aplică Selecție" pentru submit
- **Panel comandă**: Cantitățile editabile într-un `st.form("order_edit")`
  - Editarea nu mai face rerun per keystroke
  - Buton "Actualizează" pentru salvare

---

## Rezultat Așteptat

| Acțiune | Înainte | După |
|---------|---------|------|
| Click subclasă | 3-5 sec | < 200ms |
| Bifare produse | 2-3 sec rerun | **0 sec** (form) |
| Editare cantitate | rerun per keystroke | **0 sec** |
| Adaugă în Comandă | 2 sec | instant |

---

## Fișiere Modificate

- `scripts/precompute_segments.py` - adăugare calcul `suggested_qty`
- `src/core/database.py` - paginare `LIMIT/OFFSET`
- `src/ui/order_builder.py`:
  - Eliminare loop `Product()`
  - Wrap `st.data_editor` în `st.form()`
  - Wrap panel comandă în `st.form()`
