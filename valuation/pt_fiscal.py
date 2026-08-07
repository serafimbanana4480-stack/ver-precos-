"""
Portuguese vehicle fiscal engine (2026) — ISV, IUC and real transaction costs.

Single source of truth for every legally-defined cost involved in buying,
registering and holding a vehicle in Portugal.

IMPORTANT CORRECTION vs. previous implementation
------------------------------------------------
The legacy ``deal_scorer_unified.calculate_transfer_taxes`` charged **IMT**
(Imposto Municipal sobre Transmissões) on vehicle purchases using the
*real-estate* brackets, plus a 0.6% stamp duty. Neither exists for vehicles in
Portugal:

* IMT applies exclusively to real-estate transfers (CIMT art. 1.º).
* Imposto do Selo on a car only appears inside a *car-credit contract*
  (verba 17 TGIS), never on the sale itself.
* Buying a second-hand car already registered in Portugal costs the buyer a
  **registo de propriedade** fee: 55,30 € online (Automóvel Online) or 65 €
  in person. Nothing else.
* ISV is a *registration* tax, paid once, only when the vehicle receives its
  first Portuguese plate (new or imported). A national used car pays 0 €.

That bug inflated acquisition cost by 6,5–8 % of the asking price on every
national vehicle, which systematically destroyed real margins and hid good
deals. This module replaces it with the official 2026 tables.

Sources (2026 rates, unchanged from 2024/2025 by the Orçamento do Estado):
  - ISV tables A/C, CO2 NEDC/WLTP, particle surcharge, age reduction:
    https://impostosobreveiculos.info/isv/imposto-sobre-veiculos-isv-2026/
  - IUC categories A/B/E, age coefficient, diesel surcharge:
    https://impostosobreveiculos.info/iuc/imposto-unico-circulacao-iuc-2026/
  - Registo de propriedade fees:
    https://www.standvirtual.com/diarioautomovel/quanto-custa-mudar-o-registo-de-propriedade-em-2026
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Rates are those in force for the 2026 tax year.
FISCAL_YEAR = 2026
SOURCE_ISV = "https://impostosobreveiculos.info/isv/imposto-sobre-veiculos-isv-2026/"
SOURCE_IUC = "https://impostosobreveiculos.info/iuc/imposto-unico-circulacao-iuc-2026/"
SOURCE_REGISTO = (
    "https://www.standvirtual.com/diarioautomovel/"
    "quanto-custa-mudar-o-registo-de-propriedade-em-2026"
)

# ─────────────────────────────────────────────────────────────────────────────
# Fuel normalisation
# ─────────────────────────────────────────────────────────────────────────────

_PETROL = {"gasolina", "petrol", "gasoline", "benzina"}
_DIESEL = {"diesel", "gasoleo", "gasóleo"}
_ELECTRIC = {"eletrico", "elétrico", "electrico", "electric", "ev", "bev"}
_HYBRID = {"hibrido", "híbrido", "hybrid", "hev", "mhev", "micro-hibrido"}
_PHEV = {"plug_in_hybrid", "plug-in", "plugin", "phev", "hibrido plug-in", "híbrido plug-in"}
_LPG = {"gpl", "lpg", "glp"}
_CNG = {"gas natural", "gn", "gnc", "gnl", "cng"}


def normalize_fuel(fuel: Optional[str]) -> str:
    """Map any free-text fuel label to a canonical token."""
    f = (fuel or "").strip().lower()
    if f in _PHEV or "plug" in f:
        return "phev"
    if f in _ELECTRIC:
        return "eletrico"
    if f in _HYBRID or "hibrid" in f or "hybrid" in f:
        return "hibrido"
    if f in _DIESEL:
        return "diesel"
    if f in _LPG:
        return "gpl"
    if f in _CNG:
        return "gnc"
    if f in _PETROL:
        return "gasolina"
    return "gasolina"


def _bracket(value: float, table: List[Tuple[float, float, float]]) -> Tuple[float, float]:
    """Return (rate, deduction) for the first bracket whose ceiling covers value."""
    for ceiling, rate, deduction in table:
        if value <= ceiling:
            return rate, deduction
    return table[-1][1], table[-1][2]


# ─────────────────────────────────────────────────────────────────────────────
# ISV — Imposto Sobre Veículos (2026)
# ─────────────────────────────────────────────────────────────────────────────

# Tabela A · componente cilindrada · (ceiling_cm3, €/cm3, parcela a abater)
ISV_A_CILINDRADA: List[Tuple[float, float, float]] = [
    (1000, 1.09, 849.03),
    (1250, 1.18, 850.69),
    (float("inf"), 5.61, 6194.88),
]

# Tabela A · componente ambiental · (ceiling_g_km, €/g/km, parcela a abater)
ISV_A_CO2_PETROL_NEDC: List[Tuple[float, float, float]] = [
    (99, 4.62, 427.00),
    (115, 8.09, 750.99),
    (145, 52.56, 5903.94),
    (175, 61.24, 7140.17),
    (195, 155.97, 23627.27),
    (float("inf"), 205.65, 33390.12),
]

ISV_A_CO2_PETROL_WLTP: List[Tuple[float, float, float]] = [
    (110, 0.44, 43.02),
    (115, 1.10, 115.80),
    (120, 1.38, 147.79),
    (130, 5.27, 619.17),
    (145, 6.38, 762.73),
    (175, 41.54, 5819.56),
    (195, 51.38, 7247.39),
    (235, 193.01, 34190.52),
    (float("inf"), 233.81, 41910.96),
]

ISV_A_CO2_DIESEL_NEDC: List[Tuple[float, float, float]] = [
    (79, 5.78, 439.04),
    (95, 23.45, 1848.58),
    (120, 79.22, 7195.63),
    (140, 175.73, 18924.92),
    (160, 195.43, 21720.92),
    (float("inf"), 268.42, 33447.90),
]

ISV_A_CO2_DIESEL_WLTP: List[Tuple[float, float, float]] = [
    (110, 1.72, 11.50),
    (120, 18.96, 1906.19),
    (140, 65.04, 7360.85),
    (150, 127.40, 16080.57),
    (160, 160.81, 21176.06),
    (170, 221.69, 29227.38),
    (190, 274.08, 36987.98),
    (float("inf"), 282.35, 38271.32),
]

# Agravamento partículas (gasóleo, ligeiros de passageiros)
ISV_PARTICLE_SURCHARGE_PASSENGER = 500.00
ISV_PARTICLE_SURCHARGE_COMMERCIAL = 250.00

# Tabela C · motociclos, triciclos, quadriciclos · taxa única por cilindrada
ISV_C_MOTOS: List[Tuple[float, float]] = [
    (119, 0.00),      # ciclomotores < 120 cm3: fora do âmbito
    (250, 73.78),
    (350, 91.63),
    (500, 122.57),
    (750, 184.45),
    (float("inf"), 245.14),
]

# Redução por anos de uso (importados usados UE/EEE). Desde 2025 a tabela é
# única e aplica-se à totalidade do imposto (cilindrada + ambiental).
ISV_AGE_REDUCTION: List[Tuple[float, float]] = [
    (1, 0.10),
    (2, 0.20),
    (3, 0.28),
    (4, 0.35),
    (5, 0.43),
    (6, 0.52),
    (7, 0.60),
    (8, 0.65),
    (9, 0.70),
    (10, 0.75),
    (float("inf"), 0.80),
]

# Benefícios fiscais (percentagem de ISV a pagar)
ISV_BENEFIT_HYBRID = 0.60        # híbrido: autonomia elétrica >= 50 km, CO2 < 50
ISV_BENEFIT_PHEV = 0.25          # plug-in: mesmas condições
ISV_BENEFIT_CNG = 0.40           # gás natural (bifuel excluído)
ISV_BENEFIT_7_SEATS = 0.40       # ligeiro misto, >2500 kg, min. 7 lugares


def isv_age_reduction(age_years: float) -> float:
    """Percentage reduction on total ISV for an EU/EEA used import."""
    if age_years is None or age_years <= 0:
        return 0.0
    for ceiling, reduction in ISV_AGE_REDUCTION:
        if age_years <= ceiling:
            return reduction
    return 0.80


def calculate_isv(
    engine_cc: int,
    co2_gkm: Optional[float] = None,
    fuel_type: str = "gasolina",
    age_years: float = 0.0,
    vehicle_type: str = "carros",
    homologation: str = "auto",
    first_registration_year: Optional[int] = None,
    from_eu: bool = True,
    has_particle_filter: Optional[bool] = None,
    electric_range_km: Optional[float] = None,
    seats: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Compute ISV (registration tax) using the official 2026 tables.

    ISV is only due when the vehicle gets its **first Portuguese plate**.
    Callers must not apply it to a car already registered in Portugal.

    Args:
        engine_cc: displacement in cm³.
        co2_gkm: official CO2 emissions. Ignored for motorcycles.
        fuel_type: free text; normalised internally.
        age_years: years since first registration in the origin country.
        vehicle_type: "carros" | "motos" | "comerciais".
        homologation: "nedc" | "wltp" | "auto" (inferred from the year).
        first_registration_year: used to infer NEDC/WLTP when homologation="auto".
        from_eu: EU/EEA origin — only then does the age reduction apply.
        has_particle_filter: diesel particle surcharge. ``None`` is treated as
            "no official data", which by law triggers the surcharge.
        electric_range_km: electric range, needed for hybrid/PHEV benefits.
        seats: number of seats, for the 7-seat benefit.

    Returns:
        Full breakdown with ``total``.
    """
    fuel = normalize_fuel(fuel_type)
    engine_cc = int(engine_cc or 0)

    out: Dict[str, Any] = {
        "cylinder_component": 0.0,
        "co2_component": 0.0,
        "particle_surcharge": 0.0,
        "gross": 0.0,
        "age_reduction_pct": 0.0,
        "age_reduction_value": 0.0,
        "benefit_pct_payable": 1.0,
        "benefit_value": 0.0,
        "total": 0.0,
        "exempt_reason": None,
        "fiscal_year": FISCAL_YEAR,
        "source": SOURCE_ISV,
    }

    # Battery-electric vehicles are exempt from ISV (and IUC).
    if fuel == "eletrico":
        out["exempt_reason"] = "veiculo_exclusivamente_eletrico"
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}

    # ── Motorcycles: Tabela C, displacement only ──
    if str(vehicle_type).lower().startswith("moto"):
        if engine_cc < 120:
            out["exempt_reason"] = "cilindrada_inferior_120cc"
            return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}
        flat = 245.14
        for ceiling, value in ISV_C_MOTOS:
            if engine_cc <= ceiling:
                flat = value
                break
        out["cylinder_component"] = flat
        out["gross"] = flat
    else:
        # ── Cars: Tabela A = componente cilindrada + componente ambiental ──
        rate, deduction = _bracket(engine_cc, ISV_A_CILINDRADA)
        cylinder = max(0.0, engine_cc * rate - deduction)
        out["cylinder_component"] = cylinder

        # NEDC vs WLTP: from 2020 onwards everything is WLTP.
        mode = str(homologation).lower()
        if mode not in ("nedc", "wltp"):
            year = first_registration_year or (datetime.now().year - int(age_years or 0))
            mode = "wltp" if year >= 2020 else "nedc"

        if co2_gkm is not None and co2_gkm > 0:
            if fuel == "diesel":
                table = ISV_A_CO2_DIESEL_WLTP if mode == "wltp" else ISV_A_CO2_DIESEL_NEDC
            else:
                table = ISV_A_CO2_PETROL_WLTP if mode == "wltp" else ISV_A_CO2_PETROL_NEDC
            c_rate, c_ded = _bracket(co2_gkm, table)
            out["co2_component"] = max(0.0, co2_gkm * c_rate - c_ded)
        out["homologation"] = mode

        # Diesel particle surcharge: applied when emissions >= 0,001 g/km OR
        # when there is no official figure at all.
        if fuel == "diesel" and has_particle_filter is not False:
            out["particle_surcharge"] = (
                ISV_PARTICLE_SURCHARGE_COMMERCIAL
                if str(vehicle_type).lower().startswith("comerc")
                else ISV_PARTICLE_SURCHARGE_PASSENGER
            )

        out["gross"] = (
            out["cylinder_component"] + out["co2_component"] + out["particle_surcharge"]
        )

    # ── Age reduction (EU/EEA used imports only) ──
    if from_eu and age_years and age_years > 0:
        pct = isv_age_reduction(age_years)
        out["age_reduction_pct"] = pct
        out["age_reduction_value"] = out["gross"] * pct

    after_age = out["gross"] - out["age_reduction_value"]

    # ── Fiscal benefits ──
    payable = 1.0
    range_ok = electric_range_km is None or electric_range_km >= 50
    low_co2 = co2_gkm is None or co2_gkm < 50
    if fuel == "phev" and range_ok and low_co2:
        payable = ISV_BENEFIT_PHEV
    elif fuel == "hibrido" and range_ok and low_co2:
        payable = ISV_BENEFIT_HYBRID
    elif fuel == "gnc":
        payable = ISV_BENEFIT_CNG
    elif seats is not None and seats >= 7:
        payable = min(payable, ISV_BENEFIT_7_SEATS)

    out["benefit_pct_payable"] = payable
    out["benefit_value"] = after_age * (1 - payable)
    out["total"] = max(0.0, after_age * payable)

    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}


# ─────────────────────────────────────────────────────────────────────────────
# IUC — Imposto Único de Circulação (2026, annual)
# ─────────────────────────────────────────────────────────────────────────────

# Categoria A (1.ª matrícula PT/UE/EEE até 30-06-2007), gasolina
IUC_A_PETROL: List[Tuple[float, Dict[str, float]]] = [
    (1000, {"1996_2007": 19.90, "1990_1995": 12.20, "1981_1989": 8.80}),
    (1300, {"1996_2007": 39.95, "1990_1995": 22.45, "1981_1989": 12.55}),
    (1750, {"1996_2007": 62.40, "1990_1995": 34.87, "1981_1989": 17.49}),
    (2600, {"1996_2007": 158.31, "1990_1995": 83.49, "1981_1989": 36.09}),
    (3500, {"1996_2007": 287.49, "1990_1995": 156.54, "1981_1989": 79.72}),
    (float("inf"), {"1996_2007": 512.23, "1990_1995": 263.11, "1981_1989": 120.90}),
]

# Categoria A, gasóleo (taxa adicional já incluída)
IUC_A_DIESEL: List[Tuple[float, Dict[str, float]]] = [
    (1500, {"1996_2007": 22.48, "1990_1995": 14.18, "1981_1989": 10.19}),
    (2000, {"1996_2007": 45.13, "1990_1995": 25.37, "1981_1989": 14.18}),
    (3000, {"1996_2007": 70.50, "1990_1995": 39.40, "1981_1989": 19.76}),
    (float("inf"), {"1996_2007": 178.86, "1990_1995": 94.33, "1981_1989": 40.77}),
]

# Categoria B (1.ª matrícula a partir de 01-07-2007) · passo 1: cilindrada
IUC_B_CILINDRADA: List[Tuple[float, float]] = [
    (1250, 31.77),
    (1750, 63.74),
    (2500, 127.35),
    (float("inf"), 435.84),
]

# Passo 2: CO2 · (ceiling_nedc, ceiling_wltp, taxa, taxa adicional >=2017)
IUC_B_CO2: List[Tuple[float, float, float, float]] = [
    (120, 140, 65.15, 0.0),
    (180, 205, 97.63, 0.0),
    (250, 260, 212.04, 31.77),
    (float("inf"), float("inf"), 363.25, 63.74),
]

# Passo 3: coeficiente do ano da 1.ª matrícula
IUC_B_YEAR_COEFFICIENT: Dict[int, float] = {2007: 1.00, 2008: 1.05, 2009: 1.10}
IUC_B_YEAR_COEFFICIENT_DEFAULT = 1.15  # 2010 e seguintes

# Passo 4: taxa adicional gasóleo
IUC_B_DIESEL_SURCHARGE: List[Tuple[float, float]] = [
    (1250, 5.02),
    (1750, 10.07),
    (2500, 20.12),
    (float("inf"), 68.85),
]

# Categoria E · motociclos e similares
IUC_E_MOTOS: List[Tuple[float, Dict[str, float]]] = [
    (119, {"1997_2026": 0.0, "1992_1996": 0.0}),
    (250, {"1997_2026": 6.19, "1992_1996": 0.0}),
    (350, {"1997_2026": 8.76, "1992_1996": 6.19}),
    (500, {"1997_2026": 21.18, "1992_1996": 12.53}),
    (750, {"1997_2026": 63.62, "1992_1996": 37.47}),
    (float("inf"), {"1997_2026": 138.15, "1992_1996": 67.76}),
]

IUC_MINIMUM_CHARGE = 10.00  # abaixo deste valor há isenção


def calculate_iuc(
    engine_cc: int,
    first_registration_year: int,
    fuel_type: str = "gasolina",
    co2_gkm: Optional[float] = None,
    vehicle_type: str = "carros",
    homologation: str = "auto",
    first_registration_month: int = 1,
) -> Dict[str, Any]:
    """
    Annual IUC for 2026.

    Materially affects resale demand: a 3.0 V6 with 250 g/km can cost 700 €+ per
    year, which is exactly why such cars trade at a discount in Portugal. The
    valuation engine uses this as a demand/liquidity signal.
    """
    fuel = normalize_fuel(fuel_type)
    engine_cc = int(engine_cc or 0)
    year = int(first_registration_year or datetime.now().year)

    out: Dict[str, Any] = {
        "category": None,
        "cylinder_component": 0.0,
        "co2_component": 0.0,
        "co2_surcharge": 0.0,
        "year_coefficient": 1.0,
        "diesel_surcharge": 0.0,
        "total": 0.0,
        "exempt_reason": None,
        "fiscal_year": FISCAL_YEAR,
        "source": SOURCE_IUC,
    }

    if fuel == "eletrico":
        out["exempt_reason"] = "veiculo_exclusivamente_eletrico"
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}

    # ── Category E: motorcycles ──
    if str(vehicle_type).lower().startswith("moto"):
        out["category"] = "E"
        col = "1997_2026" if year >= 1997 else "1992_1996"
        if year < 1992:
            out["exempt_reason"] = "matricula_anterior_1992"
            return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}
        value = 138.15
        for ceiling, cols in IUC_E_MOTOS:
            if engine_cc <= ceiling:
                value = cols[col]
                break
        out["cylinder_component"] = value
        out["total"] = value if value >= IUC_MINIMUM_CHARGE else 0.0
        if out["total"] == 0.0 and value > 0:
            out["exempt_reason"] = "valor_inferior_10_euros"
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}

    # ── Category A: first registration up to 30-06-2007 ──
    is_cat_a = year < 2007 or (year == 2007 and first_registration_month <= 6)
    if is_cat_a:
        out["category"] = "A"
        if year < 1981:
            out["exempt_reason"] = "matricula_anterior_1981"
            return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}
        col = "1996_2007" if year >= 1996 else ("1990_1995" if year >= 1990 else "1981_1989")
        table = IUC_A_DIESEL if fuel == "diesel" else IUC_A_PETROL
        value = table[-1][1][col]
        for ceiling, cols in table:
            if engine_cc <= ceiling:
                value = cols[col]
                break
        out["cylinder_component"] = value
        out["total"] = value if value >= IUC_MINIMUM_CHARGE else 0.0
        if out["total"] == 0.0 and value > 0:
            out["exempt_reason"] = "valor_inferior_10_euros"
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}

    # ── Category B: first registration from 01-07-2007 ──
    out["category"] = "B"
    cyl = IUC_B_CILINDRADA[-1][1]
    for ceiling, value in IUC_B_CILINDRADA:
        if engine_cc <= ceiling:
            cyl = value
            break
    out["cylinder_component"] = cyl

    mode = str(homologation).lower()
    if mode not in ("nedc", "wltp"):
        mode = "wltp" if year >= 2020 else "nedc"

    if co2_gkm is not None and co2_gkm > 0:
        for ceil_nedc, ceil_wltp, taxa, extra in IUC_B_CO2:
            ceiling = ceil_wltp if mode == "wltp" else ceil_nedc
            if co2_gkm <= ceiling:
                out["co2_component"] = taxa
                if year >= 2017:
                    out["co2_surcharge"] = extra
                break
    else:
        # No official CO2 → assume the middle bracket, the most common one.
        out["co2_component"] = 97.63
        out["co2_estimated"] = True

    coef = IUC_B_YEAR_COEFFICIENT.get(year, IUC_B_YEAR_COEFFICIENT_DEFAULT)
    out["year_coefficient"] = coef

    if fuel == "diesel":
        surcharge = IUC_B_DIESEL_SURCHARGE[-1][1]
        for ceiling, value in IUC_B_DIESEL_SURCHARGE:
            if engine_cc <= ceiling:
                surcharge = value
                break
        out["diesel_surcharge"] = surcharge

    total = (
        out["cylinder_component"] + out["co2_component"] + out["co2_surcharge"]
    ) * coef + out["diesel_surcharge"]

    out["total"] = total if total >= IUC_MINIMUM_CHARGE else 0.0
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Real transaction costs
# ─────────────────────────────────────────────────────────────────────────────

REGISTO_PROPRIEDADE_ONLINE = 55.30
REGISTO_PROPRIEDADE_PRESENCIAL = 65.00

# Inspeção periódica obrigatória (IPO) — ligeiros ~ 32 €, motos ~ 22 €
IPO_CAR = 32.00
IPO_MOTO = 22.00

# Legalisation of an EU import: DAV/customs paperwork, matrícula, IPO,
# homologation certificate. Market rate charged by despachantes in 2026.
LEGALIZATION_IMPORT = 550.00

# Typical reconditioning before resale, by condition score (0-10).
RECONDITIONING_BY_CONDITION: List[Tuple[float, float]] = [
    (8.5, 150.0),    # detailing only
    (7.0, 400.0),    # tyres/brakes touch-up
    (5.5, 900.0),    # service + minor bodywork
    (4.0, 1800.0),   # timing belt, clutch or paintwork
    (2.5, 3200.0),   # mechanical repair
    (0.0, 5500.0),   # major intervention
]

# Motorcycles are cheaper to recondition.
RECONDITIONING_MOTO_FACTOR = 0.45


def estimate_reconditioning(
    condition_score: Optional[float],
    vehicle_type: str = "carros",
    price: Optional[float] = None,
) -> float:
    """Estimate reconditioning cost, capped at a sane share of the price."""
    score = 6.0 if condition_score is None else float(condition_score)
    cost = RECONDITIONING_BY_CONDITION[-1][1]
    for threshold, value in RECONDITIONING_BY_CONDITION:
        if score >= threshold:
            cost = value
            break
    if str(vehicle_type).lower().startswith("moto"):
        cost *= RECONDITIONING_MOTO_FACTOR
    # Nobody spends 5.500 € reconditioning a 2.000 € car.
    if price and price > 0:
        cost = min(cost, price * 0.45)
    return round(cost, 2)


@dataclass
class TransactionCosts:
    """Every euro between "asking price" and "car in my name, ready to sell"."""

    asking_price: float = 0.0
    registo_propriedade: float = 0.0
    isv: float = 0.0
    legalization: float = 0.0
    ipo: float = 0.0
    reconditioning: float = 0.0
    transport: float = 0.0
    iuc_year: float = 0.0
    other: float = 0.0
    breakdown_isv: Dict[str, Any] = field(default_factory=dict)
    breakdown_iuc: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def acquisition_costs(self) -> float:
        """Costs on top of the asking price to own and resell the vehicle."""
        return round(
            self.registo_propriedade
            + self.isv
            + self.legalization
            + self.ipo
            + self.reconditioning
            + self.transport
            + self.other,
            2,
        )

    @property
    def total_cost(self) -> float:
        return round(self.asking_price + self.acquisition_costs, 2)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["acquisition_costs"] = self.acquisition_costs
        d["total_cost"] = self.total_cost
        return d


def calculate_transaction_costs(
    asking_price: float,
    *,
    engine_cc: int = 1500,
    co2_gkm: Optional[float] = None,
    fuel_type: str = "gasolina",
    year: Optional[int] = None,
    vehicle_type: str = "carros",
    is_national: bool = True,
    from_eu: bool = True,
    condition_score: Optional[float] = None,
    needs_ipo: bool = True,
    transport_cost: float = 0.0,
    online_registration: bool = True,
    repair_costs: Optional[float] = None,
    seats: Optional[int] = None,
    electric_range_km: Optional[float] = None,
) -> TransactionCosts:
    """
    Full, realistic cost of acquiring a vehicle in Portugal in 2026.

    No IMT and no stamp duty — neither applies to vehicle sales.
    """
    now_year = datetime.now().year
    year = int(year or now_year)
    age = max(0, now_year - year)
    is_moto = str(vehicle_type).lower().startswith("moto")

    tc = TransactionCosts(asking_price=float(asking_price or 0.0))

    tc.registo_propriedade = (
        REGISTO_PROPRIEDADE_ONLINE if online_registration else REGISTO_PROPRIEDADE_PRESENCIAL
    )

    if is_national:
        tc.notes.append("Veículo nacional: sem ISV (imposto já pago na 1.ª matrícula).")
    else:
        isv = calculate_isv(
            engine_cc=engine_cc,
            co2_gkm=co2_gkm,
            fuel_type=fuel_type,
            age_years=age,
            vehicle_type=vehicle_type,
            first_registration_year=year,
            from_eu=from_eu,
            seats=seats,
            electric_range_km=electric_range_km,
        )
        tc.isv = isv["total"]
        tc.breakdown_isv = isv
        tc.legalization = LEGALIZATION_IMPORT
        tc.notes.append(
            f"Importado {'UE' if from_eu else 'fora UE'}: ISV {isv['total']:.0f} € "
            f"(redução idade {isv['age_reduction_pct'] * 100:.0f}%) + legalização."
        )
        if not from_eu:
            tc.notes.append("Origem fora da UE/EEE: sem redução por anos de uso.")

    if needs_ipo:
        tc.ipo = IPO_MOTO if is_moto else IPO_CAR

    tc.reconditioning = (
        float(repair_costs)
        if repair_costs is not None
        else estimate_reconditioning(condition_score, vehicle_type, asking_price)
    )

    tc.transport = float(transport_cost or 0.0)

    iuc = calculate_iuc(
        engine_cc=engine_cc,
        first_registration_year=year,
        fuel_type=fuel_type,
        co2_gkm=co2_gkm,
        vehicle_type=vehicle_type,
    )
    tc.iuc_year = iuc["total"]
    tc.breakdown_iuc = iuc

    return tc


def calculate_selling_costs(
    sale_price: float,
    *,
    days_to_sell: int = 45,
    listing_fees: float = 0.0,
    warranty_provision: bool = True,
    vehicle_type: str = "carros",
) -> Dict[str, float]:
    """
    Costs incurred while selling, which most naive margin models ignore.

    * A professional seller owes a statutory warranty on used vehicles
      (Decreto-Lei 84/2021: 3 years, reducible to 18 months by agreement).
      A provision of ~2.5% of the sale price is the market practice.
    * Capital is tied up while the car sits in stock.
    """
    sale_price = float(sale_price or 0.0)
    warranty = sale_price * (0.025 if warranty_provision else 0.0)
    if str(vehicle_type).lower().startswith("moto"):
        warranty *= 0.6
    # Opportunity cost of capital, ~6%/year.
    holding = sale_price * 0.06 * (max(0, days_to_sell) / 365.0)
    total = warranty + holding + float(listing_fees or 0.0)
    return {
        "warranty_provision": round(warranty, 2),
        "holding_cost": round(holding, 2),
        "listing_fees": round(float(listing_fees or 0.0), 2),
        "total": round(total, 2),
    }


__all__ = [
    "FISCAL_YEAR",
    "normalize_fuel",
    "calculate_isv",
    "calculate_iuc",
    "isv_age_reduction",
    "estimate_reconditioning",
    "calculate_transaction_costs",
    "calculate_selling_costs",
    "TransactionCosts",
    "REGISTO_PROPRIEDADE_ONLINE",
    "REGISTO_PROPRIEDADE_PRESENCIAL",
]
