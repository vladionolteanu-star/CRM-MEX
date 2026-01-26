import pandas as pd
from typing import List
from src.models.product import Product

class DataLoader:
    """Loads and parses BI export CSV into Product objects"""
    
    # Column mappings: CSV column name -> internal field
    COLUMN_MAP = {
        "NR ART": "nr_art",
        "COD ARTICOL": "cod_articol", 
        "DENUMIRE ARTICOL": "nume_produs",
        "FURNIZOR EXT": "furnizor",
        "CLASA DENUMIRE": "categorie",
        "STARE PM": "stare_pm",
        "Cost Achizitie Furnizor (ultimul NIR_cronologic)": "cost_achizitie",
        "Pret de Catalog cu TVA": "pret_catalog",
        "Stoc Disponibil Cantitativ Magazine Dep+Acc+Outlet": "stoc_disponibil_total",
        "Stoc Disponibil Cantitativ Magazine": "stoc_magazine",
        "Stoc Disponibil Cantitativ Furnizor": "stoc_furnizor",
        "CAFE cantitativ nereceptionat Furnizor": "stoc_in_tranzit",
        "Vanzari Cantitative Magazine_client final ult. 4 Luni": "vanzari_ultimele_4_luni",
        "Vanzari Cantitative Magazine 360z (client final)": "vanzari_ultimele_360_zile",
        "Vanzari Cantitative Magazine 2024 (client final)": "vanzari_2024",
        "Vanzari Cantitative Magazine 2025 (client final)": "vanzari_2025",
    }

    def __init__(self, file_path: str, lead_time: int = 30, safety_stock_days: float = 7.0, moq: float = 1.0):
        self.file_path = file_path
        self.lead_time = lead_time
        self.safety_stock_days = safety_stock_days
        self.moq = moq
        self.df = None

    def load_data(self) -> pd.DataFrame:
        """Load CSV with optimized dtypes for large files"""
        if self.file_path.endswith('.csv'):
            self.df = pd.read_csv(self.file_path, low_memory=False, encoding='utf-8')
        elif self.file_path.endswith(('.xls', '.xlsx')):
            self.df = pd.read_excel(self.file_path)
        else:
            raise ValueError("Unsupported file format. Use .csv or .xlsx")
        
        self.df.columns = [c.strip() for c in self.df.columns]
        return self.df

    def parse_products(self) -> List[Product]:
        """Parse DataFrame into Product objects with segmentation"""
        if self.df is None:
            self.load_data()

        products = []
        
        for _, row in self.df.iterrows():
            try:
                def get_float(col, default=0.0):
                    val = row.get(col, default)
                    try:
                        return float(val) if pd.notnull(val) else default
                    except:
                        return default

                def get_str(col, default=""):
                    val = row.get(col, default)
                    return str(val).strip() if pd.notnull(val) else default
                
                def get_int(col, default=0):
                    val = row.get(col, default)
                    try:
                        return int(float(val)) if pd.notnull(val) else default
                    except:
                        return default

                # Use NR ART if available, else COD ARTICOL
                nr_art = get_str("NR ART") or get_str("COD ARTICOL")
                if not nr_art:
                    continue
                
                p = Product(
                    nr_art=nr_art,
                    cod_articol=get_str("COD ARTICOL"),
                    nume_produs=get_str("DENUMIRE ARTICOL"),
                    furnizor=get_str("FURNIZOR EXT"),
                    categorie=get_str("CLASA DENUMIRE"),
                    stare_pm=get_str("STARE PM", "ACTIV"),
                    cost_achizitie=get_float("Cost Achizitie Furnizor (ultimul NIR_cronologic)"),
                    pret_catalog=get_float("Pret de Catalog cu TVA"),
                    stoc_disponibil_total=get_float("Stoc Disponibil Cantitativ Magazine Dep+Acc+Outlet"),
                    stoc_in_tranzit=get_float("CAFE cantitativ nereceptionat Furnizor"),
                    vanzari_ultimele_4_luni=get_float("Vanzari Cantitative Magazine_client final ult. 4 Luni"),
                    vanzari_ultimele_360_zile=get_float("Vanzari Cantitative Magazine 360z (client final)"),
                    vanzari_2024=get_float("Vanzari Cantitative Magazine 2024 (client final)"),
                    vanzari_2025=get_float("Vanzari Cantitative Magazine 2025 (client final)"),
                    lead_time_days=self.lead_time,
                    safety_stock_days=self.safety_stock_days,
                    moq=self.moq
                )
                products.append(p)
            except Exception as e:
                # Skip malformed rows silently
                continue
                
        return products

    def get_summary(self) -> dict:
        """Quick summary stats"""
        if self.df is None:
            self.load_data()
        return {
            "total_rows": len(self.df),
            "columns": list(self.df.columns),
            "suppliers": self.df["FURNIZOR EXT"].nunique() if "FURNIZOR EXT" in self.df.columns else 0
        }
