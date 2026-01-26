"""
Modul pentru încărcarea datelor de cubaj și masă din CUBAJ SI URL.csv
Calculează volumul cilindric pentru covoare (rulouri).

Formula: π × (D/2)² × H / 1.000.000 = m³
"""
import pandas as pd
import math
from typing import Dict, Optional
import os

class CubajLoader:
    """
    Încarcă datele de cubaj din CSV și le pregătește pentru îmbinare cu produsele.
    Toate covoarele sunt cilindrice (rulouri).
    """
    
    DEFAULT_PATH = "data/CUBAJ SI URL.csv"
    
    def __init__(self, csv_path: str = None):
        self.csv_path = csv_path or self.DEFAULT_PATH
        self._cubaj_map: Dict[str, dict] = {}
        self._loaded = False
        self._stats = {"total": 0, "with_cubaj": 0, "missing_data": 0}
    
    def load(self) -> Dict[str, dict]:
        """
        Citește CSV-ul și returnează un dict cu cubaj și masă per cod articol.
        
        Returns:
            Dict[cod_articol, {"cubaj_m3": float|None, "masa_kg": float|None}]
        """
        if self._loaded:
            return self._cubaj_map
        
        if not os.path.exists(self.csv_path):
            print(f"[CubajLoader] WARNING: File not found: {self.csv_path}")
            self._loaded = True
            return self._cubaj_map
            
        try:
            df = pd.read_csv(self.csv_path, low_memory=False, encoding='utf-8')
            df.columns = [c.strip() for c in df.columns]
        except Exception as e:
            print(f"[CubajLoader] ERROR: Failed to read CSV: {e}")
            self._loaded = True
            return self._cubaj_map
        
        for _, row in df.iterrows():
            cod = self._get_string(row, "COD ARTICOL")
            if not cod:
                continue
            
            self._stats["total"] += 1
            
            # Extrage dimensiuni pentru cilindru
            # Covoarele sunt rulouri: diametrul este lățimea ambalată, înălțimea ruloului este AMBALAT INALTIME
            diametru = self._get_float(row, "AMBALAT DIAMETRU")
            latime = self._get_float(row, "AMBALAT LATIME")
            inaltime = self._get_float(row, "AMBALAT INALTIME")  # Înălțimea ruloului = înălțimea cilindrului
            masa = self._get_float(row, "MASA")
            
            # Diametrul: preferă AMBALAT DIAMETRU, fallback la AMBALAT LATIME
            d = diametru if diametru else latime
            h = inaltime  # Înălțimea ruloului (nu lungimea covorului!)
            
            # Calculează cubaj cilindric
            if d and h:
                cubaj = self._calculate_cylinder_volume(d, h)
                self._stats["with_cubaj"] += 1
            else:
                cubaj = None
                self._stats["missing_data"] += 1
            
            self._cubaj_map[cod] = {
                "cubaj_m3": cubaj,
                "masa_kg": masa
            }
        
        self._loaded = True
        print(f"[CubajLoader] Loaded {self._stats['total']} products: "
              f"{self._stats['with_cubaj']} with cubaj, "
              f"{self._stats['missing_data']} missing data")
        return self._cubaj_map
    
    def get_stats(self) -> dict:
        """Returnează statistici despre încărcare."""
        return self._stats.copy()
    
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
            Volumul în metri cubi (m³), rotunjit la 6 zecimale
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
    
    Returns:
        Dict[cod_articol, {"cubaj_m3": float|None, "masa_kg": float|None}]
    """
    global _cubaj_loader_instance
    if _cubaj_loader_instance is None:
        _cubaj_loader_instance = CubajLoader()
    return _cubaj_loader_instance.load()


def get_cubaj_stats() -> dict:
    """Returnează statisticile de încărcare cubaj."""
    global _cubaj_loader_instance
    if _cubaj_loader_instance is None:
        get_cubaj_map()  # Force load
    return _cubaj_loader_instance.get_stats() if _cubaj_loader_instance else {}
