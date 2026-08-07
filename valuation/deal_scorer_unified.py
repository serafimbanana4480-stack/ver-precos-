"""
Unified Deal Scorer for Portuguese Used Vehicle Market
Single source of truth for deal score calculation.
Replaces: predict.py calculate_deal_score, hybrid_valuator.py, deal_scorer.py

2026 revision
-------------
* Transfer taxes now delegate to :mod:`valuation.pt_fiscal`, which implements
  the official ISV/IUC tables. The previous implementation charged **IMT**
  (a real-estate tax that does not exist for vehicles) plus a 0.6% stamp duty,
  inflating acquisition cost by 6.5-8% of the price on every national car and
  hiding real deals.
* The fuel adjustment used to add a *percentage* directly to a 0-10 score
  (a -0.15 price effect became -0.15 points). It is now converted explicitly.
* Profit potential now accounts for reconditioning, IPO, registration and
  selling costs — not just taxes.
"""
from typing import Dict, Optional

from valuation.pt_fiscal import (
    calculate_iuc,
    calculate_isv,
    calculate_selling_costs,
    calculate_transaction_costs,
    estimate_reconditioning,
    normalize_fuel,
)

# ── Market Margins by Seller Type ──
# Gap between the transaction value and the price actually asked, observed in
# the Portuguese market (2026).
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
# Expressed as a **price** effect relative to the petrol baseline. Converted to
# score points via _FUEL_SCORE_WEIGHT below — never added to the score raw.
_FUEL_ADJUSTMENTS = {
    "diesel": -0.06,           # ZER Lisboa/Porto, IUC agravado, procura em queda
    "gasolina": 0.0,           # baseline
    "gasoleo": -0.06,          # same as diesel
    "eletrico": 0.04,          # isento de ISV e IUC, procura crescente
    "electric": 0.04,
    "hibrido": 0.05,           # segmento mais procurado do usado em 2026
    "hybrid": 0.05,
    "plug_in_hybrid": 0.06,    # ISV a 25%, incentivos
    "plug-in": 0.06,
    "gpl": -0.06,              # nicho, revenda lenta
    "gas natural": -0.07,      # rede de abastecimento limitada
}

# A 1% price effect is worth this many points on the 0-10 deal score, so the
# fuel signal can move the score by at most ±0.4 points.
_FUEL_SCORE_WEIGHT = 6.0

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


def _km_adjustment(km: int, age: int, fuel_type: str = "gasolina") -> float:
    """
    KM adjustment factor, fuel-aware.

    Portuguese annual mileage differs sharply by fuel: a diesel doing 18.000
    km/year is normal, a petrol city car doing the same is not. Using a single
    17.000 km/year figure systematically over-penalised diesels and
    under-penalised petrol cars.
    """
    if age <= 0 or km <= 0:
        return 1.0
    expected_per_year = {
        "diesel": 18000,
        "gasolina": 12000,
        "hibrido": 14000,
        "phev": 14000,
        "eletrico": 13000,
        "gpl": 16000,
        "gnc": 16000,
    }.get(normalize_fuel(fuel_type), 14000)
    expected_km = age * expected_per_year
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
    km_factor = _km_adjustment(km, age, fuel_type)
    if km_factor != 1.0:
        km_adj = (km_factor - 1.0) * 5.0  # scale to ±0.5 points
        deal_score += km_adj
        adjustments["km"] = round(km_adj, 2)

    # 5. Fuel type adjustment (±0.4 points)
    # _FUEL_ADJUSTMENTS holds a *price* effect; convert it to score points
    # instead of adding a percentage straight onto a 0-10 scale.
    fuel_price_effect = _FUEL_ADJUSTMENTS.get(fuel_type.lower(), 0.0)
    if fuel_price_effect == 0.0:
        fuel_price_effect = _FUEL_ADJUSTMENTS.get(normalize_fuel(fuel_type), 0.0)
    fuel_adj = fuel_price_effect * _FUEL_SCORE_WEIGHT
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
    vehicle_type: str = "carros",
    from_eu: bool = True,
    online_registration: bool = True,
) -> Dict:
    """
    Real cost of transferring a vehicle in Portugal (2026).

    .. warning::
       There is **no IMT and no stamp duty** on a vehicle sale in Portugal.
       IMT applies only to real estate; stamp duty only appears inside a car
       *credit* contract. Both keys are kept in the payload (always 0.0) so
       existing callers and stored records do not break, but they no longer
       inflate the total.

    What a buyer actually pays on top of the price:
      * registo de propriedade — 55,30 € online / 65 € presencial;
      * ISV — only when the vehicle receives its first Portuguese plate
        (i.e. imports), computed from the official 2026 tables with the
        age reduction for EU/EEA vehicles;
      * legalização — despachante/customs paperwork on imports.

    Returns:
        dict with ``registo``, ``isv``, ``legalization``, ``imt`` (0),
        ``stamp_duty`` (0), ``fixed_costs``, ``total`` and ``iuc_annual``.
    """
    year_now = __import__("datetime").datetime.now().year
    first_reg_year = year_now - int(age_years or 0)

    costs = calculate_transaction_costs(
        asking_price=price,
        engine_cc=engine_cc,
        co2_gkm=co2_gkm,
        fuel_type=fuel_type,
        year=first_reg_year,
        vehicle_type=vehicle_type,
        is_national=is_national,
        from_eu=from_eu,
        online_registration=online_registration,
        repair_costs=0.0,       # reconditioning is accounted separately
        needs_ipo=True,
    )

    taxes = {
        # Legally zero for vehicles — kept for backwards compatibility.
        "imt": 0.0,
        "stamp_duty": 0.0,
        # Real costs
        "isv": costs.isv,
        "registo": costs.registo_propriedade,
        "legalization": costs.legalization,
        "ipo": costs.ipo,
        "fixed_costs": round(costs.registo_propriedade + costs.ipo, 2),
        "iuc_annual": costs.iuc_year,
        "notes": costs.notes,
        "isv_breakdown": costs.breakdown_isv,
        "iuc_breakdown": costs.breakdown_iuc,
    }
    taxes["total"] = round(
        costs.isv + costs.registo_propriedade + costs.legalization + costs.ipo, 2
    )
    return taxes


def calculate_profit_potential(
    estimated_value: float,
    asking_price: float,
    engine_cc: int = 1500,
    co2_gkm: float = 120.0,
    fuel_type: str = "gasolina",
    age_years: int = 5,
    is_national: bool = True,
    repair_costs: float = 0.0,
    vehicle_type: str = "carros",
    condition_score: Optional[float] = None,
    from_eu: bool = True,
    days_to_sell: int = 45,
    transport_cost: float = 0.0,
    include_selling_costs: bool = True,
) -> Dict:
    """
    Realistic profit potential, buy-side **and** sell-side.

    Three figures are returned because they answer different questions:

    ``gross_spread``
        estimated_value − asking_price. What naive tools call "profit".
    ``net_profit``
        after acquisition costs (registo, ISV, legalização, IPO,
        recondicionamento, transporte).
    ``net_profit_after_sale``
        also after the cost of selling: statutory warranty provision and the
        capital tied up while the vehicle sits in stock. This is the number a
        reseller actually banks.
    """
    year_now = __import__("datetime").datetime.now().year
    first_reg_year = year_now - int(age_years or 0)

    recon = (
        float(repair_costs)
        if repair_costs
        else estimate_reconditioning(condition_score, vehicle_type, asking_price)
    )

    costs = calculate_transaction_costs(
        asking_price=asking_price,
        engine_cc=engine_cc,
        co2_gkm=co2_gkm,
        fuel_type=fuel_type,
        year=first_reg_year,
        vehicle_type=vehicle_type,
        is_national=is_national,
        from_eu=from_eu,
        condition_score=condition_score,
        repair_costs=recon,
        transport_cost=transport_cost,
    )

    selling = (
        calculate_selling_costs(
            estimated_value, days_to_sell=days_to_sell, vehicle_type=vehicle_type
        )
        if include_selling_costs
        else {"total": 0.0, "warranty_provision": 0.0, "holding_cost": 0.0, "listing_fees": 0.0}
    )

    gross_spread = estimated_value - asking_price
    net_profit = estimated_value - costs.total_cost
    net_after_sale = net_profit - selling["total"]

    invested = costs.total_cost
    roi = (net_after_sale / invested * 100.0) if invested > 0 else 0.0

    # Annualised return: capital recycled every `days_to_sell` days.
    turns_per_year = 365.0 / max(1, days_to_sell)
    roi_annualized = roi * turns_per_year

    return {
        "gross_spread": round(gross_spread, 2),
        "gross_profit": round(net_profit, 2),  # backwards-compatible key
        "net_profit": round(net_profit, 2),
        "net_profit_after_sale": round(net_after_sale, 2),
        "profit_percentage": round(
            (net_after_sale / asking_price * 100.0) if asking_price > 0 else 0.0, 2
        ),
        "roi_percentage": round(roi, 2),
        "roi_annualized_percentage": round(roi_annualized, 2),
        "total_cost": costs.total_cost,
        "acquisition_costs": costs.acquisition_costs,
        "asking_price": asking_price,
        "estimated_value": round(estimated_value, 2),
        "taxes": {
            "imt": 0.0,
            "stamp_duty": 0.0,
            "isv": costs.isv,
            "registo": costs.registo_propriedade,
            "legalization": costs.legalization,
            "ipo": costs.ipo,
            "total": round(costs.isv + costs.registo_propriedade + costs.legalization + costs.ipo, 2),
        },
        "repair_costs": costs.reconditioning,
        "selling_costs": selling,
        "iuc_annual": costs.iuc_year,
        "days_to_sell": days_to_sell,
        "notes": costs.notes,
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
