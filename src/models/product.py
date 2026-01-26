from pydantic import BaseModel, Field, computed_field
from typing import Optional, Literal
import re

# Segment thresholds (in days relative to lead_time)
SEGMENT_URGENT_BUFFER = 7    # Lead time + 7 days
SEGMENT_ATTENTION_BUFFER = 21  # Lead time + 21 days
SEGMENT_OVERSTOCK_DAYS = 90   # More than 90 days coverage

# Dimension coefficients for balanced stock
# Small dimensions sell faster -> need more safety buffer
# Large dimensions sell slower -> need less safety buffer (capital intensive)
DIMENSION_COEFFICIENTS = {
    "060": 1.15,  # +15% safety
    "080": 1.15,  # +15% safety  
    "140": 1.0,   # standard
    "160": 1.0,   # standard
    "200": 0.80,  # -20% safety
    "250": 0.80,  # -20% safety
    "300": 0.80,  # -20% safety
}


def extract_family_dimension(product_name: str) -> tuple:
    """Extract family and dimension from product name like 'COVOR FLORENCE 080x150cm'"""
    if not product_name:
        return "", ""
    match = re.match(r'COVOR\s+(\w+)\s+(\d+)x(\d+)', product_name, re.IGNORECASE)
    if match:
        return match.group(1).upper(), f"{match.group(2)}x{match.group(3)}"
    return "", ""


def get_sales_ref_month_yoy(sales_history: dict, target_month: int, current_year: int = 2024) -> dict:
    """
    Calculate YoY trend for a specific target month.
    
    Args:
        sales_history: Dict with monthly sales {YYYY-MM: qty}
        target_month: Month number (1-12), e.g., 10 for October
        current_year: Current/reference year (default 2024)
        
    Returns:
        dict with current_year_sales, prior_year_sales, yoy_pct
    """
    current_key = f"{current_year}-{target_month:02d}"
    prior_key = f"{current_year - 1}-{target_month:02d}"
    
    current_sales = sales_history.get(current_key, 0)
    prior_sales = sales_history.get(prior_key, 0)
    
    yoy_pct = 0.0
    if prior_sales > 0:
        yoy_pct = ((current_sales / prior_sales) - 1) * 100
    
    return {
        "current_year_sales": current_sales,
        "prior_year_sales": prior_sales,
        "yoy_pct": round(yoy_pct, 1)
    }


class Product(BaseModel):
    """
    Product model with stock segmentation logic.
    Segments: CRITICAL | URGENT | ATTENTION | OK | OVERSTOCK
    """
    model_config = {"arbitrary_types_allowed": True}
    
    nr_art: str = Field(..., description="Unique Article Number")
    cod_articol: str = Field("", description="Product Code")
    nume_produs: str = Field("", description="Product Name")
    furnizor: str = Field("", description="Supplier")
    categorie: str = Field("", description="Category")
    stare_pm: str = Field("ACTIV", description="PM Status (ACTIV/OUT)")
    
    # Classification
    clasa: str = Field("", description="Product Class")
    subclasa: str = Field("", description="Product Subclass")
    pm: str = Field("", description="Product Manager")
    
    # Costs & Prices
    cost_achizitie: float = Field(0.0, description="Cost Achizitie Furnizor")
    pret_catalog: float = Field(0.0, description="Catalog Price with VAT")
    pret_vanzare: float = Field(0.0, description="Actual Sale Price with VAT")
    pret_retea: float = Field(0.0, description="Network Sale Price")
    
    # Stock - Total
    stoc_disponibil_total: float = Field(0.0, description="Stoc Disponibil Total")
    stoc_in_tranzit: float = Field(0.0, description="CAFE - In Transit")
    stoc_magazin_total: float = Field(0.0, description="Stock in all stores")
    
    # Stock - Per Store
    stoc_baneasa: float = Field(0.0, description="Stock Baneasa")
    stoc_pipera: float = Field(0.0, description="Stock Pipera")
    stoc_militari: float = Field(0.0, description="Stock Militari")
    stoc_pantelimon: float = Field(0.0, description="Stock Pantelimon")
    stoc_iasi: float = Field(0.0, description="Stock Iasi")
    stoc_brasov: float = Field(0.0, description="Stock Brasov")
    stoc_pitesti: float = Field(0.0, description="Stock Pitesti")
    stoc_sibiu: float = Field(0.0, description="Stock Sibiu")
    stoc_oradea: float = Field(0.0, description="Stock Oradea")
    stoc_constanta: float = Field(0.0, description="Stock Constanta")
    stoc_outlet_constanta: float = Field(0.0, description="Stock Outlet Constanta")
    stoc_outlet_pipera: float = Field(0.0, description="Stock Outlet Pipera")
    
    # Sales
    vanzari_ultimele_4_luni: float = Field(0.0, description="Sales last 4 months")
    vanzari_ultimele_360_zile: float = Field(0.0, description="Sales 360 days")
    vanzari_2024: float = Field(0.0, description="Sales 2024")
    vanzari_2025: float = Field(0.0, description="Sales 2025")
    vanzari_m16: float = Field(0.0, description="Sales to M16 network")
    vanzari_fara_m16: float = Field(0.0, description="Sales excluding M16")
    
    # Supplier params (manual input defaults)
    lead_time_days: int = Field(30, description="Lead time in days")
    moq: float = Field(1.0, description="Minimum Order Quantity")
    safety_stock_days: float = Field(7.0, description="Safety stock in days")
    
    # Seasonality & Intelligence (injected from compute_seasonality.py)
    seasonality_index: float = Field(1.0, description="Seasonality multiplier (>1 = peak coming)")
    is_rising_star: bool = Field(False, description="Product with consistent 3-year growth")
    trend: str = Field("STABLE", description="HOT/COLD/STABLE classification")
    
    # Advanced Trends (injected from compute_advanced_trends.py)
    yoy_growth: float = Field(0.0, description="Year-over-Year growth % (same months)")
    acceleration: float = Field(0.0, description="Last 3 months vs previous 3 months %")
    volatility: float = Field(1.0, description="Coefficient of Variation (lower=stable)")
    repeat_rate: float = Field(0.0, description="% of clients who bought multiple times")
    peak_month: int = Field(0, description="Best selling month for this product")
    
    # NEW: Monthly Sales History (for granular YoY comparison)
    # Format: {"2024-10": 50, "2024-11": 45, "2023-10": 40, "2023-11": 42, ...}
    sales_history: dict = Field(default_factory=dict, description="Monthly sales history per YYYY-MM")
    
    # NEW: Sales Last 3 Months (sum of last 3 completed months)
    sales_last_3m: float = Field(0.0, description="Total sales in last 3 completed months")
    
    # Cubaj & Logistics (injected from cubaj_loader.py)
    cubaj_m3: Optional[float] = Field(None, description="Volume m³ (cylinder: π×r²×h) - None = missing data")
    masa_kg: Optional[float] = Field(None, description="Weight in kg - None = missing data")

    @computed_field
    @property
    def familie(self) -> str:
        """Extract product family from name (e.g., 'COVOR FLORENCE 080x150' -> 'FLORENCE')"""
        fam, _ = extract_family_dimension(self.nume_produs)
        return fam
    
    @computed_field
    @property
    def dimensiune(self) -> str:
        """Extract dimension from name (e.g., 'COVOR FLORENCE 080x150cm' -> '080x150')"""
        _, dim = extract_family_dimension(self.nume_produs)
        return dim
    
    @computed_field
    @property
    def dimension_coefficient(self) -> float:
        """Get safety stock coefficient based on dimension size"""
        if self.dimensiune:
            # Extract first part (width) to determine size category
            width = self.dimensiune.split('x')[0] if 'x' in self.dimensiune else ""
            return DIMENSION_COEFFICIENTS.get(width, 1.0)
        return 1.0

    @computed_field
    @property
    def avg_daily_sales(self) -> float:
        """Average daily sales - uses 4mo if available, else yearly"""
        if self.vanzari_ultimele_4_luni > 0:
            return self.vanzari_ultimele_4_luni / 120.0
        elif self.vanzari_ultimele_360_zile > 0:
            return self.vanzari_ultimele_360_zile / 360.0
        return 0.0

    @computed_field
    @property
    def stoc_indomex(self) -> float:
        """
        'Stoc Indomex' = Stoc Disponibil Cantitativ Magazine Dep+Acc+Outlet
        This is the key 'Available to Dispatch' metric.
        Different from stoc_magazin_total which is physical store stock.
        """
        return self.stoc_disponibil_total

    @computed_field
    @property
    def total_stock(self) -> float:
        """Total available = on hand + in transit"""
        return self.stoc_disponibil_total + self.stoc_in_tranzit

    @computed_field
    @property
    def days_of_coverage(self) -> float:
        """How many days current stock covers at avg sales rate"""
        if self.avg_daily_sales <= 0:
            return 999.0 if self.total_stock > 0 else 0.0
        return self.total_stock / self.avg_daily_sales

    @computed_field
    @property
    def reorder_point_days(self) -> float:
        """Threshold in days: lead_time + safety_stock"""
        return self.lead_time_days + self.safety_stock_days

    @computed_field
    @property
    def segment(self) -> str:
        """
        Segmentation logic per documentation:
        - CRITICAL: coverage < lead_time (stockout before resupply)
        - URGENT: coverage < lead_time + safety_stock
        - ATTENTION: coverage < lead_time + safety + 14 days
        - OK: normal
        - OVERSTOCK: coverage > 90 days or 2x normal
        """
        cov = self.days_of_coverage
        lt = self.lead_time_days
        
        # No sales = check stock level only
        if self.avg_daily_sales <= 0:
            if self.total_stock > 0:
                return "OVERSTOCK"
            return "OK"
        
        if cov < lt:
            return "CRITICAL"
        elif cov < lt + self.safety_stock_days:
            return "URGENT"
        elif cov < lt + self.safety_stock_days + 14:
            return "ATTENTION"
        elif cov > SEGMENT_OVERSTOCK_DAYS:
            return "OVERSTOCK"
        return "OK"

    @computed_field
    @property
    def segment_color(self) -> str:
        """Hex color for segment"""
        colors = {
            "CRITICAL": "#dc2626",   # Red
            "URGENT": "#f97316",     # Orange
            "ATTENTION": "#eab308",  # Yellow
            "OK": "#22c55e",         # Green
            "OVERSTOCK": "#3b82f6"   # Blue
        }
        return colors.get(self.segment, "#6b7280")

    @computed_field
    @property
    def sales_trend(self) -> float:
        """
        Sales Velocity Trend (Sell-Out).
        Compares recent daily sales velocity (last 4 months) vs annual daily sales velocity (last 360 days).
        
        Formula: (vanzari_4luni / 120) / (vanzari_360z / 360)
        
        > 1.0 = Accelerating (selling faster recently)
        < 1.0 = Decelerating (selling slower recently)
        
        FIXED: Requires minimum volume to avoid false positives (+200% on 1 sale)
        """
        # FIXED: Minimum volume required to trust trend calculation
        MIN_VOLUME_FOR_TREND = 5
        
        # Low volume = stable (can't trust trend on small numbers)
        if self.vanzari_ultimele_360_zile < MIN_VOLUME_FOR_TREND and self.vanzari_ultimele_4_luni < MIN_VOLUME_FOR_TREND:
            return 1.0  # Not enough data
            
        # Avoid division by zero
        if self.vanzari_ultimele_360_zile <= 0:
            if self.vanzari_ultimele_4_luni > MIN_VOLUME_FOR_TREND:
                return 2.0 # Maximum growth indication (from 0 to something meaningful)
            return 1.0 # Stable (0 to 0 or low volume)
            
        daily_recent = self.vanzari_ultimele_4_luni / 120.0
        daily_annual = self.vanzari_ultimele_360_zile / 360.0
        
        if daily_annual == 0:
            return 1.0
        
        # Calculate trend with cap to avoid extreme values  
        trend = daily_recent / daily_annual
        return min(trend, 3.0)  # Cap at 3x to avoid unrealistic +200%

    @computed_field
    @property
    def is_dead_stock(self) -> bool:
        """Dead Stock = less than 3 units sold in 360 days"""
        return self.vanzari_ultimele_360_zile < 3

    @computed_field
    @property
    def suggested_order_qty(self) -> float:
        """
        Formula 3.0: Integrates ALL calculated metrics into decision.
        
        FIXES APPLIED:
        - Trend Adjustment: Uses yoy_growth to adjust base calculation
        - Family Rescue: Dead stock in active family gets 1 unit (assortment)
        - COLD products: Reduced order by 30%
        - High Volatility: More conservative (extra safety)
        """
        # ============================================================
        # DEAD STOCK RULE with FAMILY RESCUE
        # ============================================================
        if self.is_dead_stock:
            # Family Rescue: If product is in a family, order 1 unit for assortment
            if self.familie and len(self.familie) > 0:
                return 1.0  # Keep 1 unit for complete family assortment
            return 0.0  # No family = no rescue
        
        if self.avg_daily_sales <= 0:
            return 0.0
        
        # ============================================================
        # DYNAMIC BUFFER (based on velocity)
        # ============================================================
        buffer_days = 30 if self.avg_daily_sales > 0.2 else 21
        
        # ============================================================
        # SAFETY STOCK ADJUSTMENTS
        # ============================================================
        adjusted_safety = self.safety_stock_days * self.dimension_coefficient
        
        # Rising Star gets +50% safety (growth expected)
        if self.is_rising_star:
            adjusted_safety *= 1.5
        
        # High volatility gets +30% safety (unpredictable demand)
        if self.volatility > 1.0:
            adjusted_safety *= 1.3
        
        # ============================================================
        # TREND ADJUSTMENT MULTIPLIER (uses YoY if available)
        # ============================================================
        trend_multiplier = 1.0
        
        # Apply YoY growth adjustment if significant
        if self.yoy_growth > 20:
            # Growing product: increase order by up to 20%
            trend_multiplier = 1.0 + min(self.yoy_growth / 100 * 0.5, 0.3)  # Cap at +30%
        elif self.yoy_growth < -30:
            # Declining product: reduce order by up to 30%
            trend_multiplier = max(0.7, 1.0 + self.yoy_growth / 100 * 0.5)
        
        # COLD trend: additional 20% reduction
        if self.trend == "COLD":
            trend_multiplier *= 0.8
        
        # ============================================================
        # CALCULATE NEEDED QUANTITY
        # ============================================================
        coverage_days = self.lead_time_days + buffer_days + adjusted_safety
        base_needed = self.avg_daily_sales * self.seasonality_index * coverage_days
        adjusted_needed = base_needed * trend_multiplier - self.total_stock
        
        if adjusted_needed <= 0:
            return 0.0
        
        # ============================================================
        # MOQ ROUNDING
        # ============================================================
        if self.moq > 1:
            return max(self.moq, ((adjusted_needed // self.moq) + 1) * self.moq)
        return round(adjusted_needed, 0)

    @computed_field
    @property
    def stock_value(self) -> float:
        """Total stock value at acquisition cost"""
        return self.total_stock * self.cost_achizitie
