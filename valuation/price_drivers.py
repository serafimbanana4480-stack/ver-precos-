"""
Price drivers for the Portuguese used-vehicle market (2026).

Everything that pushes a vehicle's value **up** or **down** relative to the
plain brand/model/year/km baseline, expressed as explicit, auditable
multipliers instead of being buried inside an opaque model.

Design rules
------------
1. Every factor returns a multiplier and a human-readable reason, so any
   valuation can be explained line by line to a user.
2. Factors are multiplicative and individually clamped; the combined result is
   clamped to [0.45, 1.55] so no stack of small effects can produce a fantasy
   price.
3. Magnitudes come from observable PT market behaviour (2026): ZER Lisboa/Porto
   restrictions on old diesels, the automatic-gearbox premium, the collapse of
   value on salvados, seasonality of motorcycles and convertibles, and the
   liquidity gap between mainstream and niche brands.

Usage::

    from valuation.price_drivers import apply_price_drivers

    result = apply_price_drivers(base_value=12000, vehicle={...})
    result["adjusted_value"], result["factors"]
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

# Combined clamp — the sum of all drivers can never move value beyond this.
MIN_COMBINED = 0.45
MAX_COMBINED = 1.55

CURRENT_YEAR = datetime.now().year

# ─────────────────────────────────────────────────────────────────────────────
# Expected annual mileage in Portugal, by fuel (INE / market observation)
# ─────────────────────────────────────────────────────────────────────────────
EXPECTED_KM_PER_YEAR: Dict[str, int] = {
    "diesel": 18000,
    "gasolina": 12000,
    "hibrido": 14000,
    "phev": 14000,
    "eletrico": 13000,
    "gpl": 16000,
    "gnc": 16000,
}
EXPECTED_KM_PER_YEAR_MOTO = 5000

# ─────────────────────────────────────────────────────────────────────────────
# Brand liquidity — how fast the brand sells in PT and the premium/discount it
# carries. value = (price multiplier, typical days on market)
# ─────────────────────────────────────────────────────────────────────────────
BRAND_LIQUIDITY: Dict[str, Dict[str, float]] = {
    # Mainstream, very liquid
    "Renault": {"factor": 1.00, "days": 42},
    "Peugeot": {"factor": 1.00, "days": 44},
    "Citroën": {"factor": 0.98, "days": 50},
    "Volkswagen": {"factor": 1.03, "days": 38},
    "Toyota": {"factor": 1.05, "days": 33},
    "SEAT": {"factor": 1.01, "days": 41},
    "Opel": {"factor": 0.97, "days": 52},
    "Ford": {"factor": 0.97, "days": 52},
    "Nissan": {"factor": 0.99, "days": 47},
    "Hyundai": {"factor": 1.02, "days": 40},
    "Kia": {"factor": 1.02, "days": 40},
    "Dacia": {"factor": 1.03, "days": 35},
    "Skoda": {"factor": 1.02, "days": 40},
    "Fiat": {"factor": 0.96, "days": 55},
    "Mazda": {"factor": 1.00, "days": 46},
    "Honda": {"factor": 1.01, "days": 45},
    "Suzuki": {"factor": 0.99, "days": 50},
    "MINI": {"factor": 1.02, "days": 45},
    "CUPRA": {"factor": 1.02, "days": 42},
    # Premium — higher price, slower rotation, expensive maintenance
    "BMW": {"factor": 1.02, "days": 55},
    "Mercedes-Benz": {"factor": 1.02, "days": 57},
    "Audi": {"factor": 1.02, "days": 55},
    "Volvo": {"factor": 1.00, "days": 58},
    "Lexus": {"factor": 1.01, "days": 62},
    "Tesla": {"factor": 0.96, "days": 60},
    # Niche / illiquid — long stock time destroys margin
    "Alfa Romeo": {"factor": 0.93, "days": 78},
    "Jaguar": {"factor": 0.88, "days": 95},
    "Land Rover": {"factor": 0.92, "days": 85},
    "Jeep": {"factor": 0.95, "days": 70},
    "SsangYong": {"factor": 0.85, "days": 105},
    "Mitsubishi": {"factor": 0.94, "days": 72},
    "Subaru": {"factor": 0.90, "days": 90},
    "Chevrolet": {"factor": 0.88, "days": 92},
    "Smart": {"factor": 0.94, "days": 68},
    "DS": {"factor": 0.90, "days": 88},
    "MG": {"factor": 0.95, "days": 60},
    "BYD": {"factor": 0.93, "days": 65},
    # Motorcycle brands
    "Yamaha": {"factor": 1.03, "days": 38},
    "Kawasaki": {"factor": 1.01, "days": 45},
    "KTM": {"factor": 1.00, "days": 48},
    "Ducati": {"factor": 0.98, "days": 62},
    "Triumph": {"factor": 0.97, "days": 65},
    "Aprilia": {"factor": 0.95, "days": 70},
    "Harley-Davidson": {"factor": 0.94, "days": 80},
    "Vespa": {"factor": 1.05, "days": 32},
    "Piaggio": {"factor": 1.01, "days": 42},
    "SYM": {"factor": 0.97, "days": 50},
    "Kymco": {"factor": 0.97, "days": 50},
}
DEFAULT_LIQUIDITY = {"factor": 0.95, "days": 65}

# ─────────────────────────────────────────────────────────────────────────────
# Regional premium — Lisboa/Porto carry the highest prices, interior the lowest
# ─────────────────────────────────────────────────────────────────────────────
DISTRICT_PREMIUM: Dict[str, float] = {
    "lisboa": 1.04,
    "setubal": 1.02,
    "setúbal": 1.02,
    "porto": 1.03,
    "braga": 1.01,
    "aveiro": 1.01,
    "faro": 1.03,
    "coimbra": 1.00,
    "leiria": 1.00,
    "santarem": 0.99,
    "santarém": 0.99,
    "viseu": 0.98,
    "viana do castelo": 0.98,
    "vila real": 0.97,
    "guarda": 0.96,
    "castelo branco": 0.96,
    "braganca": 0.95,
    "bragança": 0.95,
    "portalegre": 0.95,
    "evora": 0.97,
    "évora": 0.97,
    "beja": 0.96,
    "madeira": 1.02,
    "acores": 1.02,
    "açores": 1.02,
}

# ─────────────────────────────────────────────────────────────────────────────
# Seasonality — month-of-year multiplier by body/vehicle type
# ─────────────────────────────────────────────────────────────────────────────
SEASONALITY: Dict[str, List[float]] = {
    # Jan  Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec
    "motos": [0.94, 0.96, 1.02, 1.05, 1.06, 1.05, 1.02, 0.99, 0.99, 0.97, 0.94, 0.93],
    "descapotavel": [0.93, 0.95, 1.02, 1.06, 1.08, 1.07, 1.04, 1.00, 0.98, 0.95, 0.93, 0.92],
    "4x4": [1.02, 1.01, 0.99, 0.98, 0.97, 0.97, 0.98, 0.99, 1.00, 1.02, 1.03, 1.03],
    "carros": [1.01, 1.01, 1.01, 1.00, 1.00, 1.00, 0.99, 0.98, 1.00, 1.01, 1.00, 0.99],
}

# ─────────────────────────────────────────────────────────────────────────────
# Text signals found in listing titles/descriptions
# ─────────────────────────────────────────────────────────────────────────────
_RE_SALVADO = re.compile(
    r"\b(salvado|sinistrad[oa]|para\s*pe[çc]as|acidentad[oa]|batid[oa]|"
    r"despiste|write[- ]?off|desmantelamento)\b", re.I
)
_RE_NO_DOCS = re.compile(
    r"\b(sem\s*documento|sem\s*livrete|documenta[çc][ãa]o\s*em\s*falta|"
    r"penhorad[oa]|sem\s*matr[íi]cula|apreendid[oa])\b", re.I
)
_RE_ENGINE_ISSUE = re.compile(
    r"\b(motor\s*(fundido|gripado|avariado|partido)|n[ãa]o\s*(pega|trabalha|anda)|"
    r"caixa\s*avariada|junta\s*de\s*culatra|para\s*arranjar|avariad[oa])\b", re.I
)
_RE_SERVICE_BOOK = re.compile(
    r"\b(livro\s*de\s*revis[õo]es|revis[õo]es\s*em\s*dia|hist[óo]rico\s*(completo|de\s*manuten)|"
    r"full\s*service|carimbos?\s*(da\s*marca)?|revis[ãa]o\s*feita)\b", re.I
)
_RE_TIMING_BELT = re.compile(
    r"\b(correia\s*(de\s*)?distribui[çc][ãa]o\s*(nova|feita|substitu[íi]da)|"
    r"kit\s*de\s*distribui[çc][ãa]o\s*(novo|feito))\b", re.I
)
_RE_WARRANTY = re.compile(r"\b(garantia\s*(de\s*)?\d+\s*(meses|anos)|com\s*garantia)\b", re.I)
_RE_NATIONAL = re.compile(r"\b(nacional|1\.?[ºo]?\s*dono|[úu]nic[oa]\s*dono)\b", re.I)
_RE_IMPORTED = re.compile(r"\b(importad[oa]|alem[ãa]o|vindo\s*da\s*alemanha|matr[íi]cula\s*estrangeira)\b", re.I)
_RE_URGENT = re.compile(r"\b(urgente|venda\s*r[áa]pida|preciso\s*de\s*vender|aceito\s*trocas?)\b", re.I)
_RE_AUTOMATIC = re.compile(r"\b(autom[áa]tic[oa]|dsg|edc|tiptronic|s[- ]?tronic|dct|cvt|steptronic|9g|7g)\b", re.I)
_RE_4X4 = re.compile(r"\b(4x4|awd|quattro|4motion|xdrive|4matic|all[- ]?wheel)\b", re.I)
_RE_CONVERTIBLE = re.compile(r"\b(descapot[áa]vel|cabrio|cabriolet|roadster|spider|spyder)\b", re.I)

# Popular high-demand trims that carry a real premium in PT
_RE_HOT_TRIM = re.compile(
    r"\b(gti|gtd|r[- ]?line|m\s?sport|msport|amg[- ]?line|s[- ]?line|st[- ]?line|"
    r"gt[- ]?line|n[- ]?line|fr\b|cupra|black\s*edition|rs\b|type[- ]?r|nismo)\b", re.I
)

# ─────────────────────────────────────────────────────────────────────────────
# Individual drivers
# ─────────────────────────────────────────────────────────────────────────────


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def km_driver(km: Optional[int], age: int, fuel: str, is_moto: bool) -> Dict[str, Any]:
    """
    Mileage vs. what the vehicle *should* have. The single strongest driver
    after age. Fuel-aware, because a diesel with 200.000 km is normal while a
    petrol city car with 200.000 km is not.
    """
    if not km or km <= 0 or age <= 0:
        return {"factor": 1.0, "reason": "km desconhecido ou veículo novo"}

    expected_year = (
        EXPECTED_KM_PER_YEAR_MOTO if is_moto else EXPECTED_KM_PER_YEAR.get(fuel, 14000)
    )
    expected = expected_year * age
    ratio = km / expected

    if ratio < 0.35:
        factor, label = 1.14, "km excecionalmente baixo"
    elif ratio < 0.55:
        factor, label = 1.09, "km muito baixo"
    elif ratio < 0.80:
        factor, label = 1.04, "km abaixo da média"
    elif ratio <= 1.20:
        factor, label = 1.00, "km na média"
    elif ratio <= 1.50:
        factor, label = 0.94, "km acima da média"
    elif ratio <= 2.00:
        factor, label = 0.86, "km muito elevado"
    else:
        factor, label = 0.76, "km extremo"

    # Psychological thresholds the PT market actually reacts to.
    if not is_moto:
        if km >= 300000:
            factor *= 0.92
            label += " (>300.000 km)"
        elif km >= 250000:
            factor *= 0.96
            label += " (>250.000 km)"

    return {
        "factor": round(_clamp(factor, 0.70, 1.18), 4),
        "reason": f"{label}: {km:,.0f} km vs. {expected:,.0f} km esperados".replace(",", "."),
    }


def fuel_demand_driver(fuel: str, age: int, engine_cc: int) -> Dict[str, Any]:
    """
    Demand pressure by fuel in 2026: ZER in Lisboa/Porto penalise old diesels,
    electrics are exempt from ISV and IUC, PHEVs keep strong incentives, and
    large-displacement petrol carries a heavy IUC.
    """
    factor, reason = 1.0, "combustível neutro"

    if fuel == "diesel":
        if age >= 15:
            factor, reason = 0.86, "diesel muito antigo: restrições ZER e IUC agravado"
        elif age >= 10:
            factor, reason = 0.93, "diesel antigo: procura em queda, restrições urbanas"
        else:
            factor, reason = 0.98, "diesel recente: ainda líquido em alta quilometragem"
    elif fuel == "eletrico":
        factor, reason = 1.04, "elétrico: isento de ISV e IUC, procura crescente"
        if age >= 8:
            factor, reason = 0.90, "elétrico antigo: incerteza sobre saúde da bateria"
    elif fuel == "phev":
        factor, reason = 1.06, "plug-in híbrido: ISV a 25% e forte procura"
    elif fuel == "hibrido":
        factor, reason = 1.05, "híbrido: segmento mais procurado do usado em 2026"
    elif fuel == "gpl":
        factor, reason = 0.94, "GPL: nicho, revenda mais lenta"
    elif fuel == "gnc":
        factor, reason = 0.93, "gás natural: rede de abastecimento limitada"

    # Large petrol engines are punished by IUC and fuel cost.
    if fuel in ("gasolina", "hibrido") and engine_cc and engine_cc > 2500:
        factor *= 0.93
        reason += " | cilindrada >2.500 cc: IUC elevado"

    return {"factor": round(_clamp(factor, 0.80, 1.10), 4), "reason": reason}


def condition_driver(
    condition_score: Optional[float],
    has_damage: bool,
    text: str,
) -> Dict[str, Any]:
    """Physical condition, including catastrophic text signals."""
    if _RE_SALVADO.search(text):
        return {"factor": 0.55, "reason": "salvado/sinistrado: mercado desconta 40-50%"}
    if _RE_ENGINE_ISSUE.search(text):
        return {"factor": 0.60, "reason": "avaria mecânica grave declarada"}
    if _RE_NO_DOCS.search(text):
        return {"factor": 0.65, "reason": "documentação em falta / penhorado"}

    factor, reason = 1.0, "estado normal"
    if condition_score is not None:
        # 6.0 is neutral; each point is worth ~4%.
        factor = 1.0 + (float(condition_score) - 6.0) * 0.04
        reason = f"score de condição {condition_score:.1f}/10"
    if has_damage:
        factor *= 0.88
        reason += " | danos assinalados"

    return {"factor": round(_clamp(factor, 0.60, 1.14), 4), "reason": reason}


def history_driver(
    num_owners: Optional[int],
    is_national: Optional[bool],
    text: str,
) -> Dict[str, Any]:
    """Ownership history, provenance and maintenance records."""
    factor = 1.0
    parts: List[str] = []

    if is_national is True or _RE_NATIONAL.search(text):
        factor *= 1.03
        parts.append("nacional")
    elif is_national is False or _RE_IMPORTED.search(text):
        factor *= 0.95
        parts.append("importado (histórico menos verificável)")

    if num_owners is not None:
        if num_owners <= 1:
            factor *= 1.04
            parts.append("1.º dono")
        elif num_owners == 2:
            factor *= 1.0
        elif num_owners <= 4:
            factor *= 0.97
            parts.append(f"{num_owners} donos")
        else:
            factor *= 0.93
            parts.append(f"{num_owners} donos")

    if _RE_SERVICE_BOOK.search(text):
        factor *= 1.04
        parts.append("livro de revisões")
    if _RE_TIMING_BELT.search(text):
        factor *= 1.03
        parts.append("distribuição feita")

    return {
        "factor": round(_clamp(factor, 0.88, 1.12), 4),
        "reason": ", ".join(parts) if parts else "histórico sem sinais relevantes",
    }


def maintenance_liability_driver(
    age: int, km: Optional[int], text: str, is_moto: bool
) -> Dict[str, Any]:
    """
    Imminent maintenance the buyer will have to pay for. A car due for a timing
    belt is worth its price minus that belt — this is the most common reason a
    'cheap' listing is not actually cheap.
    """
    if is_moto:
        return {"factor": 1.0, "reason": "n/a para motociclos"}
    if _RE_TIMING_BELT.search(text):
        return {"factor": 1.0, "reason": "distribuição declarada como feita"}

    km = km or 0
    # Typical interval in PT: 120.000 km or 8 years.
    due_by_km = km > 0 and (km % 120000) > 95000
    due_by_age = age >= 8 and age % 8 >= 6
    if km >= 110000 and km < 130000:
        due_by_km = True

    if due_by_km or due_by_age:
        return {
            "factor": 0.96,
            "reason": "correia de distribuição provavelmente em fim de vida (400-800 €)",
        }
    if age >= 12:
        return {"factor": 0.97, "reason": "idade elevada: manutenção mais frequente"}
    return {"factor": 1.0, "reason": "sem manutenção iminente identificada"}


def equipment_driver(
    transmission: Optional[str], text: str, horsepower: Optional[int], is_moto: bool
) -> Dict[str, Any]:
    """Gearbox, drivetrain and trim level."""
    factor = 1.0
    parts: List[str] = []

    tr = (transmission or "").lower()
    if not is_moto and ("autom" in tr or _RE_AUTOMATIC.search(text)):
        factor *= 1.05
        parts.append("caixa automática (+5% em PT)")

    if _RE_4X4.search(text):
        factor *= 1.03
        parts.append("tração integral")

    if _RE_HOT_TRIM.search(text):
        factor *= 1.04
        parts.append("versão desportiva/topo de gama")

    if horsepower and not is_moto:
        if horsepower >= 300:
            factor *= 0.97
            parts.append("potência elevada: seguro e IUC penalizam a revenda")
        elif horsepower <= 70:
            factor *= 0.97
            parts.append("potência baixa: procura reduzida")

    return {
        "factor": round(_clamp(factor, 0.90, 1.14), 4),
        "reason": ", ".join(parts) if parts else "equipamento padrão",
    }


def liquidity_driver(brand: Optional[str]) -> Dict[str, Any]:
    """Brand liquidity: how long capital stays tied up."""
    info = BRAND_LIQUIDITY.get((brand or "").strip(), DEFAULT_LIQUIDITY)
    return {
        "factor": round(info["factor"], 4),
        "days_to_sell": info["days"],
        "reason": f"liquidez da marca: ~{int(info['days'])} dias em stock",
    }


def region_driver(district: Optional[str], location: Optional[str] = None) -> Dict[str, Any]:
    """Regional price level."""
    key = (district or location or "").strip().lower()
    for name, factor in DISTRICT_PREMIUM.items():
        if name and name in key:
            return {"factor": factor, "reason": f"distrito {name.title()}"}
    return {"factor": 1.0, "reason": "distrito desconhecido"}


def seasonality_driver(
    vehicle_type: str, text: str, month: Optional[int] = None
) -> Dict[str, Any]:
    """Month-of-year demand. Motorcycles and convertibles are highly seasonal."""
    month = month or datetime.now().month
    idx = max(0, min(11, month - 1))
    if str(vehicle_type).lower().startswith("moto"):
        key = "motos"
    elif _RE_CONVERTIBLE.search(text):
        key = "descapotavel"
    elif _RE_4X4.search(text):
        key = "4x4"
    else:
        key = "carros"
    factor = SEASONALITY[key][idx]
    return {"factor": factor, "reason": f"sazonalidade {key} (mês {month})"}


def seller_urgency_driver(text: str, seller_type: Optional[str]) -> Dict[str, Any]:
    """
    Not a value driver — a *negotiation* driver. An urgent private seller is
    where the margin actually comes from, so it is surfaced separately.
    """
    urgent = bool(_RE_URGENT.search(text))
    st = (seller_type or "").lower()
    is_private = st in ("particular", "private")
    negotiation_room = 0.03
    if is_private:
        negotiation_room += 0.04
    if urgent:
        negotiation_room += 0.05
    return {
        "factor": 1.0,  # does not change market value
        "negotiation_room": round(min(negotiation_room, 0.12), 3),
        "reason": (
            f"margem de negociação estimada {min(negotiation_room, 0.12) * 100:.0f}%"
            + (" (venda urgente)" if urgent else "")
            + (" (particular)" if is_private else "")
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────


def apply_price_drivers(
    base_value: float,
    vehicle: Dict[str, Any],
    *,
    month: Optional[int] = None,
    include_seasonality: bool = True,
) -> Dict[str, Any]:
    """
    Adjust a baseline market value with every observable driver.

    Args:
        base_value: value from the ML model / statistical comparables.
        vehicle: listing dict (brand, model, year, km, fuel_type, transmission,
            district, title, description, condition_score, num_owners,
            is_national, has_damage, horsepower, engine_size, vehicle_type,
            seller_type).

    Returns:
        ``adjusted_value``, the combined multiplier, every individual factor
        with its reason, an estimated days-to-sell and the negotiation room.
    """
    from valuation.pt_fiscal import normalize_fuel  # local import: avoids cycles

    base_value = float(base_value or 0.0)
    if base_value <= 0:
        return {
            "base_value": 0.0,
            "adjusted_value": 0.0,
            "combined_factor": 1.0,
            "factors": {},
            "warnings": ["base_value inválido"],
        }

    year = int(vehicle.get("year") or CURRENT_YEAR)
    age = max(0, CURRENT_YEAR - year)
    km = vehicle.get("km")
    km = int(km) if km else None
    fuel = normalize_fuel(vehicle.get("fuel_type"))
    vehicle_type = str(vehicle.get("vehicle_type") or "carros")
    is_moto = vehicle_type.lower().startswith("moto")
    engine_cc = int(vehicle.get("engine_size") or 0)
    text = " ".join(
        str(vehicle.get(k) or "") for k in ("title", "description", "version", "trim_level")
    )

    factors: Dict[str, Dict[str, Any]] = {
        "km": km_driver(km, age, fuel, is_moto),
        "combustivel": fuel_demand_driver(fuel, age, engine_cc),
        "condicao": condition_driver(
            vehicle.get("condition_score"), bool(vehicle.get("has_damage")), text
        ),
        "historico": history_driver(
            vehicle.get("num_owners"), vehicle.get("is_national"), text
        ),
        "manutencao": maintenance_liability_driver(age, km, text, is_moto),
        "equipamento": equipment_driver(
            vehicle.get("transmission"), text, vehicle.get("horsepower"), is_moto
        ),
        "liquidez": liquidity_driver(vehicle.get("brand")),
        "regiao": region_driver(vehicle.get("district"), vehicle.get("location")),
    }
    if include_seasonality:
        factors["sazonalidade"] = seasonality_driver(vehicle_type, text, month)

    negotiation = seller_urgency_driver(text, vehicle.get("seller_type"))

    combined = 1.0
    for f in factors.values():
        combined *= float(f.get("factor", 1.0))
    combined_clamped = _clamp(combined, MIN_COMBINED, MAX_COMBINED)

    warnings: List[str] = []
    if combined != combined_clamped:
        warnings.append(
            f"Fator combinado {combined:.3f} limitado a {combined_clamped:.3f} "
            "para evitar valores irrealistas."
        )
    if km is None:
        warnings.append("Quilometragem em falta: estimativa com menor confiança.")
    if not engine_cc:
        warnings.append("Cilindrada em falta: ISV/IUC estimados por defeito.")

    adjusted = base_value * combined_clamped

    # Rank the drivers by absolute impact so the UI can show "why".
    impact = sorted(
        (
            {
                "driver": name,
                "factor": f["factor"],
                "impact_eur": round(base_value * (f["factor"] - 1.0), 2),
                "reason": f["reason"],
            }
            for name, f in factors.items()
        ),
        key=lambda d: abs(d["impact_eur"]),
        reverse=True,
    )

    return {
        "base_value": round(base_value, 2),
        "adjusted_value": round(adjusted, 2),
        "combined_factor": round(combined_clamped, 4),
        "factors": factors,
        "top_drivers": impact[:5],
        "days_to_sell": factors["liquidez"].get("days_to_sell", 60),
        "negotiation_room": negotiation["negotiation_room"],
        "negotiation_reason": negotiation["reason"],
        "warnings": warnings,
    }


__all__ = [
    "apply_price_drivers",
    "km_driver",
    "fuel_demand_driver",
    "condition_driver",
    "history_driver",
    "maintenance_liability_driver",
    "equipment_driver",
    "liquidity_driver",
    "region_driver",
    "seasonality_driver",
    "seller_urgency_driver",
    "BRAND_LIQUIDITY",
    "EXPECTED_KM_PER_YEAR",
]
