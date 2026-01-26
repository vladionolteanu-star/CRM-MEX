# 📦 SPECIFICAȚIE TEHNICĂ: Modul Calcul Cubaj

**Versiune:** 1.0  
**Data:** 2026-01-09  
**Autor:** System Architect  
**Status:** 📋 READY FOR DEVELOPMENT  

---

## 1. CONTEXT ȘI OBIECTIV

### 1.1 Problemă
Sistemul actual de aprovizionare nu calculează **cubajul (volumul)** comenzilor. Acest lucru este necesar pentru:
- Planificarea logistică (câte camioane/containere)
- Estimarea costurilor de transport
- Optimizarea comenzilor pe furnizor

### 1.2 Sursă Date
**Fișier:** `data/CUBAJ SI URL.csv`  
**Înregistrări:** ~57.000 articole  
**Cheie de îmbinare:** `COD ARTICOL`

### 1.3 Coloane Disponibile

| Coloană | Tip | Exemplu | Descriere |
|---------|-----|---------|-----------|
| `COD ARTICOL` | string | `GIPUFFYGR080` | Cheie unică produs |
| `AMBALAT DIMENSIUNI` | string | `L.80 l.80 H.14` | Format text (nu se folosește) |
| `AMBALAT INALTIME` | numeric | `14` | Înălțimea în cm |
| `AMBALAT LUNGIME` | numeric | `80` | Lungimea în cm |
| `AMBALAT LATIME` | numeric | `80` | Lățimea în cm |
| `AMBALAT DIAMETRU` | numeric | `#null` sau valoare | Diametru pentru cilindru |
| `MASA` | numeric | `3.24` | Masa în kg |

---

## 2. SPECIFICAȚII FUNCȚIONALE

### 2.1 Formula Calcul Cubaj

> [!IMPORTANT]
> **TOATE produsele sunt CILINDRICE** (covoare rulouri). Formula de bază:

```
Cubaj (m³) = π × (D/2)² × H / 1.000.000
```

Unde:
- **D** = Diametru în cm (din `AMBALAT DIAMETRU` sau calculat din `AMBALAT LATIME`)
- **H** = Înălțime cilindrului = `AMBALAT LUNGIME` (lungimea covorului rulat)
- Împărțim la 1.000.000 pentru conversie cm³ → m³

**Alternativ** (dacă diametrul nu e disponibil dar avem lățimea):
```
Diametru estimat = AMBALAT LATIME (presupunem că ruloul are lățime ≈ diametru)
```

### 2.2 Tratare Date Lipsă

> [!WARNING]
> **Multe produse au `#null` în câmpurile de dimensiuni!**

**Comportament cerut:**
1. Dacă dimensiunile sunt `#null` sau invalide → `cubaj_m3 = None` (nu 0)
2. În UI, afișăm **"⚠️ LIPSĂ DATE"** pentru aceste produse
3. La totalul comenzii, menționăm: *"X produse fără cubaj calculabil"*

### 2.3 Afișare în UI

#### A) Pe fiecare rând din tabel
Coloană nouă: **"Cubaj (m³)"**
- Valoare numerică cu 3 zecimale (ex: `0.089`)
- Sau text: `⚠️ N/A` dacă lipsesc date

#### B) La calculul comenzii (total selectat)
```
📦 Cubaj Total: 2.345 m³
⚖️ Masă Totală: 156.8 kg
⚠️ Atenție: 3 produse fără date de cubaj
```

---

## 3. ARHITECTURĂ TEHNICĂ

### 3.1 Structura Fișierelor

```
src/
├── core/
│   ├── cubaj_loader.py     # [NOU] Încarcă și procesează CUBAJ SI URL.csv
│   └── loader.py           # [EXISTENT] - nu se modifică
├── models/
│   └── product.py          # [MODIFICARE] Adaugă cubaj_m3, masa_kg
└── ui/
    └── app.py              # [MODIFICARE] Afișare cubaj în tabel + total
```

### 3.2 Flux Date

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FLUX CUBAJ                                   │
└─────────────────────────────────────────────────────────────────────┘

    [STARTUP]
         │
         ▼
┌─────────────────────┐
│ CubajLoader.load()  │ ◄── Citește CUBAJ SI URL.csv
│ la pornire app      │     Calculează cubaj pt fiecare COD ARTICOL
└──────────┬──────────┘     Returnează Dict[cod_articol] → {cubaj, masa}
           │
           ▼
┌─────────────────────┐
│ st.session_state    │ ◄── Cache-uiește cubaj_map (o singură citire)
│ ["cubaj_map"]       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ parse_from_postgres() / parse_with_config()                         │
│                                                                      │
│ Pentru fiecare Product creat:                                       │
│   if cod_articol in cubaj_map:                                      │
│       product.cubaj_m3 = cubaj_map[cod_articol]["cubaj_m3"]         │
│       product.masa_kg = cubaj_map[cod_articol]["masa_kg"]           │
│   else:                                                             │
│       product.cubaj_m3 = None  # Marcat ca lipsă date               │
│       product.masa_kg = None                                        │
└──────────┬──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ render_interactive_table()                                           │
│                                                                      │
│ • Coloană "Cubaj (m³)" pentru fiecare produs                        │
│ • La "Calcul Cantități Sugerate" → afișare total cubaj + masă       │
│ • Warning dacă există produse fără date                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. SPECIFICAȚII DETALIATE

### 4.1 `src/core/cubaj_loader.py` [FIȘIER NOU]

```python
"""
Modul pentru încărcarea datelor de cubaj și masă din CUBAJ SI URL.csv
"""
import pandas as pd
import math
from typing import Dict, Optional

class CubajLoader:
    """
    Încarcă datele de cubaj din CSV și le pregătește pentru îmbinare cu produsele.
    """
    
    DEFAULT_PATH = "data/CUBAJ SI URL.csv"
    
    def __init__(self, csv_path: str = None):
        self.csv_path = csv_path or self.DEFAULT_PATH
        self._cubaj_map: Dict[str, dict] = {}
        self._loaded = False
    
    def load(self) -> Dict[str, dict]:
        """
        Citește CSV-ul și returnează un dict cu cubaj și masă per cod articol.
        
        Returns:
            Dict[cod_articol, {"cubaj_m3": float|None, "masa_kg": float|None}]
        """
        if self._loaded:
            return self._cubaj_map
            
        df = pd.read_csv(self.csv_path, low_memory=False, encoding='utf-8')
        df.columns = [c.strip() for c in df.columns]
        
        for _, row in df.iterrows():
            cod = self._get_string(row, "COD ARTICOL")
            if not cod:
                continue
            
            # Extrage dimensiuni
            diametru = self._get_float(row, "AMBALAT DIAMETRU")
            latime = self._get_float(row, "AMBALAT LATIME")
            lungime = self._get_float(row, "AMBALAT LUNGIME")  # Înălțimea cilindrului
            masa = self._get_float(row, "MASA")
            
            # Calculează cubaj cilindric
            d = diametru if diametru else latime  # Fallback la lățime
            h = lungime
            
            cubaj = self._calculate_cylinder_volume(d, h) if d and h else None
            
            self._cubaj_map[cod] = {
                "cubaj_m3": cubaj,
                "masa_kg": masa
            }
        
        self._loaded = True
        return self._cubaj_map
    
    @staticmethod
    def _calculate_cylinder_volume(diameter_cm: float, height_cm: float) -> float:
        """
        Calculează volumul unui cilindru în metri cubi.
        
        Formula: π × r² × h
        Unde r = diameter / 2, totul în cm, convertit la m³
        
        Args:
            diameter_cm: Diametrul cilindrului în centimetri
            height_cm: Înălțimea cilindrului în centimetri
            
        Returns:
            Volumul în metri cubi (m³)
        """
        radius_cm = diameter_cm / 2
        volume_cm3 = math.pi * (radius_cm ** 2) * height_cm
        volume_m3 = volume_cm3 / 1_000_000  # cm³ → m³
        return round(volume_m3, 6)
    
    @staticmethod
    def _get_float(row, col: str) -> Optional[float]:
        """Extrage valoare float din row, returnează None dacă invalid."""
        val = row.get(col)
        if pd.isna(val) or str(val).strip().lower() in ('#null', '', 'nan', 'none'):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _get_string(row, col: str) -> str:
        """Extrage string din row."""
        val = row.get(col, "")
        if pd.isna(val):
            return ""
        return str(val).strip()


# Singleton instance pentru refolosire
_cubaj_loader_instance: Optional[CubajLoader] = None

def get_cubaj_map() -> Dict[str, dict]:
    """
    Returnează cubaj map-ul (singleton, încărcat o singură dată).
    """
    global _cubaj_loader_instance
    if _cubaj_loader_instance is None:
        _cubaj_loader_instance = CubajLoader()
    return _cubaj_loader_instance.load()
```

---

### 4.2 `src/models/product.py` [MODIFICARE]

Adaugă câmpurile:

```python
# Adăugare în clasa Product (dataclass sau Pydantic)

# Date cubaj/logistică
cubaj_m3: Optional[float] = None      # Volum ambalat în m³ (None = date lipsă)
masa_kg: Optional[float] = None       # Masă ambalat în kg (None = date lipsă)
```

---

### 4.3 `src/ui/app.py` [MODIFICĂRI]

#### A) Import și inițializare (la începutul fișierului)

```python
from src.core.cubaj_loader import get_cubaj_map
```

#### B) La încărcarea produselor (funcția `main()` sau `parse_from_postgres`)

```python
# După crearea listei de produse, înainte de afișare
cubaj_map = get_cubaj_map()

for product in products:
    cubaj_data = cubaj_map.get(product.cod_articol, {})
    product.cubaj_m3 = cubaj_data.get("cubaj_m3")
    product.masa_kg = cubaj_data.get("masa_kg")
```

#### C) În `render_interactive_table()` - coloană nouă

```python
# În zona de construire DataFrame pentru afișare
# Adaugă coloană "Cubaj"

def format_cubaj(p):
    if p.cubaj_m3 is None:
        return "⚠️ N/A"
    return f"{p.cubaj_m3:.3f}"

# La construirea display_df:
display_df["Cubaj (m³)"] = [format_cubaj(p) for p in sorted_products]
```

#### D) În zona de calcul comandă - total cubaj

```python
# După calculul cantităților sugerate, afișează totaluri:

selected_products = [p for p in products if p.cod_articol in selected_codes]

# Calcul totale
total_cubaj = sum(
    (p.cubaj_m3 or 0) * p.cantitate_sugerata 
    for p in selected_products
)
total_masa = sum(
    (p.masa_kg or 0) * p.cantitate_sugerata 
    for p in selected_products
)
produse_fara_cubaj = sum(
    1 for p in selected_products if p.cubaj_m3 is None
)

# Afișare
st.markdown(f"""
<div style="background: #1e293b; padding: 12px; border-radius: 8px; margin-top: 16px;">
    <div style="display: flex; gap: 32px; color: white;">
        <div>
            <span style="color: #94a3b8; font-size: 0.8rem;">📦 CUBAJ TOTAL</span><br>
            <span style="font-size: 1.4rem; font-weight: 600;">{total_cubaj:.3f} m³</span>
        </div>
        <div>
            <span style="color: #94a3b8; font-size: 0.8rem;">⚖️ MASĂ TOTALĂ</span><br>
            <span style="font-size: 1.4rem; font-weight: 600;">{total_masa:.1f} kg</span>
        </div>
    </div>
    {"<div style='color: #fbbf24; margin-top: 8px; font-size: 0.85rem;'>⚠️ " + str(produse_fara_cubaj) + " produse fără date de cubaj</div>" if produse_fara_cubaj > 0 else ""}
</div>
""", unsafe_allow_html=True)
```

---

## 5. VALIDARE ȘI TESTARE

### 5.1 Teste Unitare (pentru Developer)

```python
# test_cubaj_loader.py

def test_cylinder_volume_calculation():
    """Test formula π × r² × h"""
    # Diametru 80cm, înălțime 100cm
    # V = π × 40² × 100 = π × 1600 × 100 = 502654.82 cm³ = 0.502655 m³
    result = CubajLoader._calculate_cylinder_volume(80, 100)
    assert abs(result - 0.502655) < 0.001

def test_null_handling():
    """Verifică că #null e tratat corect"""
    loader = CubajLoader()
    row = {"AMBALAT DIAMETRU": "#null", "AMBALAT LUNGIME": "100"}
    assert loader._get_float(row, "AMBALAT DIAMETRU") is None
    
def test_cubaj_map_structure():
    """Verifică structura output-ului"""
    cubaj_map = get_cubaj_map()
    assert isinstance(cubaj_map, dict)
    if "GIPUFFYGR080" in cubaj_map:
        assert "cubaj_m3" in cubaj_map["GIPUFFYGR080"]
        assert "masa_kg" in cubaj_map["GIPUFFYGR080"]
```

### 5.2 Validare Manuală

1. **Produs test:** `GIPUFFYGR080` 
   - Dimensiuni din CSV: L.80 l.80 H.14 (diametru 80, înălțime 80?)
   - Verifică calculul manual vs. afișat în UI

2. **Verifică produse fără date:**
   - Alege un produs cu `#null` în dimensiuni
   - Verifică că afișează "⚠️ N/A"

3. **Verifică total comandă:**
   - Selectează 5 produse mixte (cu și fără cubaj)
   - Verifică că totalul e corect și warning-ul apare

---

## 6. DEPENDENȚE

- **pandas** (deja existent)
- **math** (built-in Python)
- Nu sunt necesare librării noi

---

## 7. CHECKLIST IMPLEMENTARE

- [ ] Creează `src/core/cubaj_loader.py`
- [ ] Modifică `src/models/product.py` - adaugă câmpuri
- [ ] Modifică `src/ui/app.py`:
  - [ ] Import cubaj_loader
  - [ ] Îmbogățire produse la încărcare
  - [ ] Coloană "Cubaj (m³)" în tabel
  - [ ] Secțiune total cubaj la comandă
- [ ] Testare manuală în UI
- [ ] Code review

---

## 8. TIMELINE ESTIMAT

| Task | Efort |
|------|-------|
| `cubaj_loader.py` | 1h |
| Modificări `product.py` | 15min |
| Modificări `app.py` | 2h |
| Testare | 1h |
| **TOTAL** | **~4-5h** |

---

> [!NOTE]
> **Document pregătit pentru Developer.** 
> Așteaptă GO de la Product Owner înainte de implementare.
