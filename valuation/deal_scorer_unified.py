"""
Unified Deal Scorer for Portuguese Used Vehicle Market
Single source of truth for deal score calculation.
Replaces: predict.py calculate_deal_score, hybrid_valuator.py, deal_scorer.py
"""
from typing import Dict, Optional

# ── Market Margins by Seller Type ──
# Based on Portuguese market reality (2026)
# Stands: 15-25% gross margin (warranty, inspection, financing)
# Particulares: 5-15% (no added value)
# Unknown: default to professional

_SELLER_MARGINS = {
    "profissional": 1.15,
    "professional": 1.15,
    "stand": 1.15,
    "dealer": 1.15,
    "particular": 1.08,
    "private": 1.08,
    "unknown": 1.12,
}

# ── Fuel Market Adjustments (PT 2026) ──
# Relative to gasoline baseline
_FUEL_ADJUSTMENTS = {
    "diesel": -0.15,           # ZAL restrictions, higher circulation taxes
    "gasolina": 0.0,           # baseline
    "gasoleo": -0.15,          # same as diesel
    "eletrico": 0.10,          # growing market, incentives
    "electric": 0.10,
    "hibrido": 0.08,           # partial IMT exemption
    "hybrid": 0.08,
    "plug_in_hybrid": 0.15,    # subsidies, exemptions
    "plug-in": 0.15,
    "gpl": -0.12,              # niche, ZAL restrictions
    "gas natural": -0.05,
}

# ── Depreciation Curve (Non-linear, PT reality) ──
# Cumulative depreciation % from new value
_DEPRECIATION = {
    0: 1.00,   # new
    1: 0.78,   # -22%
    2: 0.62,   # -38%
    3: 0.52,   # -48%
    4: 0.47,   # -53%
    5: 0.42,   # -58%
    6: 0.39,   # -61%
    7: 0.36,   # -64%
    8: 0.33,   # -67%
    9: 0.31,   # -69%
    10: 0.29,  # -71%
    11: 0.27,  # -73%
    12: 0.25,  # -75%
}


def _depreciation_factor(age: int) -> float:
    """Return non-linear depreciation factor for PT market."""
    if age < 0:
        return 1.0
    if age in _DEPRECIATION:
        return _DEPRECIATION[age]
    # Beyond 12 years: gradual decline to floor of 10%
    return max(0.10, 0.25 - (age - 12) * 0.01)


def _km_adjustment(km: int, age: int) -> float:
    """KM adjustment factor. PT average: ~17,000 km/year."""
    if age <= 0 or km <= 0:
        return 1.0
    expected_km = age * 17000
    if expected_km <= 0:
        return 1.0
    ratio = km / expected_km
    if ratio < 0.5:
        return 1.08   # very low KM: +8%
    elif ratio < 0.8:
        return 1.03   # low KM: +3%
    elif ratio < 1.2:
        return 1.00   # normal
    elif ratio < 1.5:
        return 0.95   # high KM: -5%
    elif ratio < 2.0:
        return 0.88   # very high KM: -12%
    else:
        return 0.80   # extreme KM: -20%


def calculate_deal_score(
    estimated_value: float,
    asking_price: float,
    seller_type: str = "unknown",
    km: int = 0,
    age: int = 0,
    fuel_type: str = "gasolina",
    condition_score: Optional[float] = None,
    has_damage: bool = False,
    is_national: Optional[bool] = None,
    num_owners: Optional[int] = None,
    warranty_months: Optional[int] = None,
) -> Dict:
    """
    Calculate a unified deal score (0-10) for the Portuguese used vehicle market.

    Args:
        estimated_value: market transaction value (what the car is actually worth)
        asking_price: price asked by the seller
        seller_type: 'profissional', 'particular', 'unknown'
        km: mileage in km
        age: age in years
        fuel_type: fuel type string
        condition_score: 0-10 condition score (optional)
        has_damage: whether vehicle has known damage
        is_national: whether vehicle was originally registered in PT
        num_owners: number of previous owners
        warranty_months: remaining warranty in months

    Returns:
        dict with deal_score, grade, and breakdown
    """
    if estimated_value <= 0 or asking_price <= 0:
        return {
            "deal_score": 0.0,
            "grade": "invalid",
            "asking_benchmark": 0.0,
            "discount_vs_benchmark": 0.0,
            "estimated_value": round(estimated_value, 2),
            "asking_price": asking_price,
            "adjustments": {},
        }

    # 1. Apply market margin by seller type
    margin = _SELLER_MARGINS.get(seller_type.lower(), 1.12)
    asking_benchmark = estimated_value * margin

    # 2. Calculate discount vs benchmark
    discount = (asking_benchmark - asking_price) / asking_benchmark

    # 3. Base score: 5.0 = neutral (at benchmark)
    #    10.0 = 30% below benchmark (exceptional)
    #    0.0 = 25% above benchmark (very poor)
    raw_score = 5.0 + (discount * 16.67)
    deal_score = max(0.0, min(10.0, raw_score))

    adjustments = {}

    # 4. KM adjustment (±0.5 points)
    km_factor = _km_adjustment(km, age)
    if km_factor != 1.0:
        km_adj = (km_factor - 1.0) * 5.0  # scale to ±0.5 points
        deal_score += km_adj
        adjustments["km"] = round(km_adj, 2)

    # 5. Fuel type adjustment (±0.3 points)
    fuel_adj = _FUEL_ADJUSTMENTS.get(fuel_type.lower(), 0.0)
    deal_score += fuel_adj
    if fuel_adj != 0.0:
        adjustments["fuel"] = round(fuel_adj, 2)

    # 6. Condition adjustment (±0.5 points)
    if condition_score is not None:
        # condition_score 5 = neutral, 10 = perfect, 0 = wreck
        cond_adj = (condition_score - 5.0) * 0.1
        deal_score += cond_adj
        adjustments["condition"] = round(cond_adj, 2)

    # 7. Damage penalty (-0.5 points)
    if has_damage:
        deal_score -= 0.5
        adjustments["damage"] = -0.5

    # 8. National vs imported (+0.2 for national)
    if is_national is True:
        deal_score += 0.2
        adjustments["national"] = 0.2
    elif is_national is False:
        deal_score -= 0.1
        adjustments["imported"] = -0.1

    # 9. Number of owners (-0.2 per owner above 1, max -0.6)
    if num_owners is not None and num_owners > 1:
        owners_adj = -0.2 * min(num_owners - 1, 3)
        deal_score += owners_adj
        adjustments["owners"] = round(owners_adj, 2)

    # 10. Warranty bonus (+0.1 per 6 months, max +0.5)
    if warranty_months is not None and warranty_months > 0:
        warranty_adj = min(0.5, warranty_months * 0.1 / 6)
        deal_score += warranty_adj
        adjustments["warranty"] = round(warranty_adj, 2)

    # Final cap
    deal_score = max(0.0, min(10.0, deal_score))

    # Grade
    if deal_score >= 8.5:
        grade = "exceptional"
    elif deal_score >= 7.5:
        grade = "excellent"
    elif deal_score >= 6.0:
        grade = "good"
    elif deal_score >= 4.5:
        grade = "fair"
    else:
        grade = "poor"

    return {
        "deal_score": round(deal_score, 1),
        "grade": grade,
        "asking_benchmark": round(asking_benchmark, 2),
        "discount_vs_benchmark": round(discount, 3),
        "estimated_value": round(estimated_value, 2),
        "asking_price": asking_price,
        "margin_applied": margin,
        "adjustments": adjustments,
    }


def calculate_transfer_taxes(
    price: float,
    engine_cc: int = 1500,
    co2_gkm: float = 120.0,
    fuel_type: str = "gasolina",
    age_years: int = 5,
    is_national: bool = True,
) -> Dict:
    """
    Calculate realistic vehicle transfer taxes for Portugal (2026).

    Args:
        price: vehicle price in EUR
        engine_cc: engine displacement in cm³
        co2_gkm: CO2 emissions in g/km
        fuel_type: fuel type
        age_years: vehicle age
        is_national: whether first registered in Portugal

    Returns:
        dict with IMT, ISV, stamp duty, fixed costs, total
    """
    taxes = {
        "imt": 0.0,
        "isv": 0.0,
        "stamp_duty": 0.0,
        "fixed_costs": 0.0,
        "total": 0.0,
    }

    # ── IMT (escalonado) ──
    if price <= 1000:
        taxes["imt"] = 0.0
    elif price <= 1250:
        taxes["imt"] = (price - 1000) * 0.02
    elif price <= 1734:
        taxes["imt"] = 5.0 + (price - 1250) * 0.035
    elif price <= 2499:
        taxes["imt"] = 21.79 + (price - 1734) * 0.045
    elif price <= 3623:
        taxes["imt"] = 56.72 + (price - 2499) * 0.055
    else:
        base_rate = 0.065 if price <= 25000 else 0.08
        if fuel_type.lower() in ("diesel", "gasoleo"):
            base_rate += 0.01
        elif fuel_type.lower() in ("eletrico", "electric", "hibrido", "hybrid", "plug_in_hybrid", "plug-in"):
            base_rate = max(0.0, base_rate - 0.02)
        taxes["imt"] = price * base_rate

    # ── ISV (only for imports or first registration) ──
    if not is_national:
        # Simplified ISV = (cc * rate_cc) + (co2 * rate_co2)
        # Age reduction: 10% per year up to 80% (max 10 years)
        reduction = min(0.80, age_years * 0.10)
        taxa_cc = 0.50   # €/cm³ (simplified, varies by bracket)
        taxa_co2 = 2.0   # €/g/km (simplified)
        isv_base = (engine_cc * taxa_cc) + (co2_gkm * taxa_co2)
        taxes["isv"] = isv_base * (1 - reduction)

    # ── Imposto de Selo: 0.6% ──
    taxes["stamp_duty"] = price * 0.006

    # ── Fixed costs (notary, registration, IPO, etc.) ──
    taxes["fixed_costs"] = 250.0  # escritura + matrícula + despesas

    taxes["total"] = sum(taxes.values())
    return {k: round(v, 2) for k, v in taxes.items()}


def calculate_profit_potential(
    estimated_value: float,
    asking_price: float,
    engine_cc: int = 1500,
    co2_gkm: float = 120.0,
    fuel_type: str = "gasolina",
    age_years: int = 5,
    is_national: bool = True,
    repair_costs: float = 0.0,
) -> Dict:
    """
    Calculate realistic profit potential including all Portuguese transfer costs.
    """
    taxes = calculate_transfer_taxes(
        price=asking_price,
        engine_cc=engine_cc,
        co2_gkm=co2_gkm,
        fuel_type=fuel_type,
        age_years=age_years,
        is_national=is_national,
    )

    total_cost = asking_price + taxes["total"] + repair_costs
    gross_profit = estimated_value - total_cost
    profit_percentage = (gross_profit / asking_price * 100.0) if asking_price > 0 else 0.0

    return {
        "gross_profit": round(gross_profit, 2),
        "profit_percentage": round(profit_percentage, 2),
        "total_cost": round(total_cost, 2),
        "asking_price": asking_price,
        "estimated_value": round(estimated_value, 2),
        "taxes": taxes,
        "repair_costs": repair_costs,
    }


# ── Brand Canonicalization ──
_BRAND_ALIASES = {
    "bmw": "BMW", "bwm": "BMW",
    "mercedes": "Mercedes-Benz", "mercedes-benz": "Mercedes-Benz", "mb": "Mercedes-Benz",
    "vw": "Volkswagen", "volkswagen": "Volkswagen", "volks": "Volkswagen",
    "seat": "SEAT",
    "citroen": "Citroën", "citroën": "Citroën",
    "kia": "Kia", "kya": "Kia",
    "hyundai": "Hyundai", "hiundai": "Hyundai",
    "mazda": "Mazda", "mazada": "Mazda",
    "nissan": "Nissan", "nisan": "Nissan",
    "toyota": "Toyota", "toyotta": "Toyota",
    "ford": "Ford",
    "opel": "Opel",
    "renault": "Renault", "reno": "Renault",
    "peugeot": "Peugeot", "pegeot": "Peugeot",
    "audi": "Audi",
    "porsche": "Porsche",
    "ferrari": "Ferrari",
    "lamborghini": "Lamborghini",
    "jaguar": "Jaguar",
    "land rover": "Land Rover", "landrover": "Land Rover",
    "volvo": "Volvo",
    "tesla": "Tesla",
    "mini": "MINI",
    "smart": "Smart",
    "alfa romeo": "Alfa Romeo", "alfaromeo": "Alfa Romeo",
    "dacia": "Dacia",
    "suzuki": "Suzuki", "susuki": "Suzuki",
    "kawasaki": "Kawasaki", "kawazak": "Kawasaki",
    "honda": "Honda",
    "yamaha": "Yamaha",
    "ktm": "KTM",
    "ducati": "Ducati",
    "harley": "Harley-Davidson", "harley-davidson": "Harley-Davidson",
    "triumph": "Triumph",
    "bmw motorrad": "BMW",
    "aprilia": "Aprilia",
    "vespa": "Vespa", "piaggio": "Piaggio",
}


def canonicalize_brand(brand_raw: str) -> str:
    """Canonicalize brand name to single standard form."""
    if not brand_raw:
        return "Unknown"
    import unicodedata
    brand = brand_raw.strip().lower()
    brand = unicodedata.normalize("NFKD", brand).encode("ascii", "ignore").decode("ascii")
    return _BRAND_ALIASES.get(brand, brand_raw.strip().title())


# ── Rejection Rules for Data Quality ──
_REJECTION_RULES = [
    (lambda v: v.get("price", 0) < 50 and v.get("year", 0) > 1990, "price_too_low"),
    (lambda v: v.get("price", 0) > 200000 and v.get("brand") not in [
        "Ferrari", "Lamborghini", "Porsche", "McLaren", "Aston Martin", "Bugatti", "Rolls-Royce", "Bentley"
    ], "fantasy_price"),
    (lambda v: v.get("brand", "").lower() in ("unknown", "venda", "vendo", "mota", "moto", "185.000") or
                v.get("brand", "").replace(".", "").isdigit(), "invalid_brand"),
    (lambda v: v.get("km", 0) > 800000 and v.get("year", 0) > 1980, "unrealistic_km"),
    (lambda v: any(x in v.get("title", "").lower() for x in ("pneu", "vinil", "spray", "capa", "jante")), "not_vehicle"),
]


def validate_vehicle_data(vehicle: dict) -> tuple:
    """
    Validate scraped vehicle data against business rules.

    Returns:
        (is_valid: bool, reason: str or None)
    """
    for rule_fn, reason in _REJECTION_RULES:
        try:
            if rule_fn(vehicle):
                return False, reason
        except Exception:
            continue
    return True, None
