"""
Portuguese market reference (2026).

Independent, data-driven sanity layer for every valuation.

Why this exists
---------------
The ML models are trained on scraped *asking* prices. When the database is thin
(or a segment is under-represented) the model happily produces values such as
"1992 Honda worth 75.000 €" or "PCX 125 worth 10.000 €". Those numbers then
propagate into deal scores and profit estimates, and the whole system stops
being trustworthy.

This module provides a second, fully explainable opinion built from:

* new-price (PVP) anchors per model,
* segment-specific depreciation curves calibrated against observed PT prices
  in 2026,
* mileage correction,
* hard sanity bounds per vehicle type.

It is used for three things:
1. **Fallback** when there are not enough comparables in the database.
2. **Sanity check** of any ML output (``validate_estimate``).
3. **Plausibility of the listing itself** — a price far below reference is
   either a real deal or a scam/salvado, and the caller must know which.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "market_reference_pt_2026.json"

_CACHE: Optional[Dict[str, Any]] = None

CURRENT_YEAR = datetime.now().year

# Same expected-mileage assumptions as price_drivers, kept local to avoid a
# hard dependency cycle.
_EXPECTED_KM = {"diesel": 18000, "gasolina": 12000, "hibrido": 14000, "eletrico": 13000}
_EXPECTED_KM_MOTO = 5000


def _strip_accents(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _norm(text: Optional[str]) -> str:
    """Normalise a brand/model string for lookup."""
    t = _strip_accents(str(text or "")).lower().strip()
    t = re.sub(r"[^a-z0-9\s\.\-+]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def load_reference() -> Dict[str, Any]:
    """Load (and cache) the market reference file."""
    global _CACHE
    if _CACHE is None:
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as fh:
                _CACHE = json.load(fh)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Não foi possível carregar %s: %s", _DATA_FILE, exc)
            _CACHE = {
                "depreciation_curves": {},
                "models": {},
                "absolute_floors": {"carros": 700, "motos": 350},
                "sanity_bounds": {
                    "carros": {"min": 300, "max": 250000},
                    "motos": {"min": 200, "max": 60000},
                },
                "brand_default_segment": {},
                "_meta": {},
            }
    return _CACHE


def reload_reference() -> Dict[str, Any]:
    """Force a reload (used after updating the JSON from live scrapes)."""
    global _CACHE
    _CACHE = None
    return load_reference()


# ─────────────────────────────────────────────────────────────────────────────
# Model lookup
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Trim-level aliases
# ─────────────────────────────────────────────────────────────────────────────
# Real listings almost never say "bmw serie 3" — they say "320d", "318i",
# "c220 cdi", "e 220 d". Map those trim-level badges to the anchor nameplate
# so they hit the exact entry instead of fuzzy-matching a wrong model
# (e.g. "bmw 320d" was fuzzy-matched to "bmw x1" with confidence 0.6).

_BMW_SERIE = {"1": "serie 1", "2": "serie 2", "3": "serie 3", "4": "serie 4",
              "5": "serie 5", "6": "serie 6", "7": "serie 7", "8": "serie 8"}
_MERC_CLASS = {"a": "classe a", "b": "classe b", "c": "classe c",
               "e": "classe e", "s": "classe s"}


def _canonical_key(brand_norm: str, model_norm: str) -> Optional[str]:
    """Map a trim-level model badge to its anchor key, e.g. bmw 320d → bmw serie 3."""
    m = model_norm.strip()
    first = m.split()[0] if m else ""

    if brand_norm == "bmw":
        # "320d", "318i", "116d", "530e" → serie N
        hit = re.match(r"^(\d)\d{2}[a-z]{0,3}$", first)
        if hit and hit.group(1) in _BMW_SERIE:
            return f"bmw {_BMW_SERIE[hit.group(1)]}"
        # "serie 3" variants already normalise to the anchor
        hit = re.match(r"^serie\s*(\d)$", first)
        if hit:
            return f"bmw serie {hit.group(1)}"
    elif brand_norm == "mercedes-benz":
        # "c220", "e220d", "a180", "c 220 cdi" → classe C/E/A
        hit = re.match(r"^([abces])\s?\d{3}[a-z]{0,4}$", first)
        if hit:
            return f"mercedes-benz {_MERC_CLASS[hit.group(1)]}"
        if first in ("gla", "cla", "vito", "glc", "gle"):
            return f"mercedes-benz {first}"
    return None


def find_model_entry(
    brand: Optional[str], model: Optional[str]
) -> Tuple[Optional[Dict[str, Any]], str, float]:
    """
    Find the best reference entry for a brand/model pair.

    Returns:
        (entry, matched_key, match_confidence 0-1)
    """
    ref = load_reference()
    models: Dict[str, Any] = ref.get("models", {})
    b, m = _norm(brand), _norm(model)

    if not b and not m:
        return None, "", 0.0

    # 1. Exact "brand model"
    key = f"{b} {m}".strip()
    if key in models:
        return models[key], key, 1.0

    # 2. The model string already contains the brand ("bmw serie 3")
    if m in models:
        return models[m], m, 0.95

    # 3. Trim-level alias: "bmw 320d" → "bmw serie 3", "mercedes c220" → classe c
    alias = _canonical_key(b, m)
    if alias and alias in models:
        return models[alias], alias, 0.9

    # 4. Prefix match: "renault megane sport tourer" → "renault megane"
    #    Exige fronteira de palavra após o prefixo: sem isto,
    #    "mercedes-benz classe cla 200d" caía em "classe c" ("cla" começa por "c").
    candidates = [
        k for k in models
        if len(k) > 4 and key.startswith(k)
        and (len(key) == len(k) or key[len(k)] == " ")
    ]
    if candidates:
        best = max(candidates, key=len)
        return models[best], best, 0.85

    # 5. Token containment: handles "megane 1.5 blue dci intens".
    # Require the brand token (or no brand given) so "bmw 320d" can never land
    # on an anchor of a different brand/family by accident.
    best_key, best_score = None, 0.0
    key_tokens = set(key.split())
    for k in models:
        k_tokens = set(k.split())
        if not k_tokens:
            continue
        if b and b not in k_tokens:
            continue
        overlap = len(k_tokens & key_tokens) / len(k_tokens)
        if overlap > best_score:
            best_key, best_score = k, overlap
    if best_key and best_score >= 0.99:
        return models[best_key], best_key, 0.8
    if best_key and best_score >= 0.5:
        return models[best_key], best_key, 0.6

    return None, "", 0.0


def resolve_segment(
    brand: Optional[str],
    model: Optional[str],
    vehicle_type: str = "carros",
    fuel_type: Optional[str] = None,
    engine_cc: Optional[int] = None,
) -> str:
    """Pick a depreciation segment even when the model is unknown."""
    entry, _, _ = find_model_entry(brand, model)
    if entry and entry.get("segment"):
        return entry["segment"]

    ref = load_reference()
    is_moto = str(vehicle_type).lower().startswith("moto")

    if is_moto:
        if engine_cc and engine_cc <= 150:
            return "scooter"
        return "moto"

    fuel = _norm(fuel_type)
    if fuel in ("eletrico", "electrico", "electric", "bev"):
        return "eletrico"

    by_brand = ref.get("brand_default_segment", {})
    canonical = str(brand or "").strip()
    if canonical in by_brand:
        seg = by_brand[canonical]
        if seg in ("moto", "scooter") and not is_moto:
            return "media"
        return seg

    if str(vehicle_type).lower().startswith("comerc"):
        return "comercial"
    return "media"


def residual_factor(segment: str, age: int) -> float:
    """Residual value (fraction of PVP) for a segment at a given age."""
    ref = load_reference()
    curves = ref.get("depreciation_curves", {})
    curve = curves.get(segment) or curves.get("media") or {}
    table: Dict[str, float] = curve.get("residual_by_age", {})
    floor = float(curve.get("floor", 0.12))

    if not table:
        return max(floor, 0.85 ** max(0, age))

    age = max(0, int(age))
    if str(age) in table:
        return float(table[str(age)])

    known = sorted(int(k) for k in table)
    if age > known[-1]:
        last = float(table[str(known[-1])])
        # Slow linear decay beyond the table, never below the floor.
        return max(floor, last - (age - known[-1]) * 0.012)
    return float(table[str(known[0])])


def _km_correction(
    km: Optional[int], age: int, fuel: str, is_moto: bool
) -> Tuple[float, str]:
    """Mileage correction applied on top of the age-based residual."""
    if not km or km <= 0 or age <= 0:
        return 1.0, "km não considerado"
    expected_year = _EXPECTED_KM_MOTO if is_moto else _EXPECTED_KM.get(fuel, 14000)
    expected = expected_year * age
    ratio = km / expected
    if ratio < 0.4:
        return 1.12, "km muito abaixo do esperado"
    if ratio < 0.7:
        return 1.06, "km abaixo do esperado"
    if ratio <= 1.3:
        return 1.0, "km dentro do esperado"
    if ratio <= 1.8:
        return 0.91, "km acima do esperado"
    if ratio <= 2.5:
        return 0.83, "km muito acima do esperado"
    return 0.74, "km extremo"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def estimate_reference_value(
    brand: Optional[str],
    model: Optional[str],
    year: Optional[int],
    km: Optional[int] = None,
    fuel_type: Optional[str] = None,
    vehicle_type: str = "carros",
    engine_cc: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Reference market value for a vehicle, independent of the ML model.

    Returns a dict with ``value``, a plausible ``range`` (low/high), the
    ``segment``, the ``method`` used and a ``confidence`` in [0, 1].
    """
    ref = load_reference()
    is_moto = str(vehicle_type).lower().startswith("moto")
    year = int(year) if year else None
    age = max(0, CURRENT_YEAR - year) if year else 10

    entry, matched_key, match_conf = find_model_entry(brand, model)
    segment = resolve_segment(brand, model, vehicle_type, fuel_type, engine_cc)

    if not entry or not entry.get("new_price"):
        return {
            "value": None,
            "low": None,
            "high": None,
            "segment": segment,
            "method": "sem_referencia",
            "confidence": 0.0,
            "matched_model": None,
            "notes": ["Modelo sem âncora de PVP na base de referência."],
        }

    new_price = float(entry["new_price"])
    residual = residual_factor(segment, age)
    fuel = _norm(fuel_type) or "gasolina"
    km_factor, km_note = _km_correction(km, age, fuel, is_moto)

    # Model-specific retention: some nameplates systematically beat (or miss)
    # their segment curve in Portugal — Dacia and Toyota hybrids hold value
    # far better than the segment average, oversupplied scooters hold worse.
    retention = float(entry.get("retention", 1.0))

    value = new_price * residual * km_factor * retention

    floors = ref.get("absolute_floors", {})
    floor = float(floors.get("motos" if is_moto else "carros", 500))
    value = max(value, floor)

    entry_conf = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(
        entry.get("confidence", "medium"), 0.6
    )
    confidence = round(entry_conf * match_conf * (0.85 if km is None else 1.0), 3)

    # Impossible model year — the nameplate did not exist yet. Almost always a
    # scraping error (year picked from the ad text, not the vehicle).
    year_warnings: List[str] = []
    from_year = entry.get("from_year")
    if from_year and year and year < int(from_year):
        year_warnings.append(
            f"Ano {year} anterior ao lançamento do modelo ({from_year}): "
            "dado provavelmente incorreto."
        )
        confidence = round(confidence * 0.3, 3)
    if year and year > CURRENT_YEAR + 1:
        year_warnings.append(f"Ano {year} no futuro: dado inválido.")
        confidence = round(confidence * 0.2, 3)

    # The band widens with age and shrinks when we know the mileage.
    spread = 0.15 + min(0.15, age * 0.008) + (0.05 if km is None else 0.0)

    return {
        "value": round(value, 2),
        "low": round(value * (1 - spread), 2),
        "high": round(value * (1 + spread), 2),
        "segment": segment,
        "method": "referencia_pvp_depreciacao",
        "confidence": confidence,
        "matched_model": matched_key,
        "new_price": new_price,
        "residual_factor": round(residual, 4),
        "km_factor": km_factor,
        "retention": retention,
        "age": age,
        "notes": [
            f"Âncora: {matched_key} (PVP novo {new_price:,.0f} €)".replace(",", "."),
            f"Residual segmento '{segment}' aos {age} anos: {residual * 100:.0f}%",
            km_note,
        ]
        + (
            [f"Retenção específica do modelo: {retention:+.0%}".replace("+1", "+")]
            if retention != 1.0
            else []
        ),
    }


def validate_estimate(
    estimated_value: Optional[float],
    vehicle: Dict[str, Any],
    asking_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Sanity-check any valuation against the market reference and hard bounds.

    This is the guard that stops absurd values from reaching the user.

    Returns:
        ``is_valid``, a possibly ``corrected_value``, the list of ``issues``
        and a ``severity`` in {ok, warning, critical}.
    """
    ref = load_reference()
    vehicle_type = str(vehicle.get("vehicle_type") or "carros")
    is_moto = vehicle_type.lower().startswith("moto")
    bounds = ref.get("sanity_bounds", {}).get(
        "motos" if is_moto else "carros", {"min": 300, "max": 250000}
    )

    issues: List[str] = []
    severity = "ok"
    corrected = estimated_value

    if estimated_value is None or estimated_value <= 0:
        return {
            "is_valid": False,
            "corrected_value": None,
            "issues": ["Valor estimado ausente ou não positivo."],
            "severity": "critical",
            "reference": None,
        }

    # 1. Hard bounds
    if estimated_value < bounds["min"]:
        issues.append(
            f"Valor {estimated_value:.0f} € abaixo do mínimo plausível "
            f"({bounds['min']} €) para {vehicle_type}."
        )
        corrected = float(bounds["min"])
        severity = "critical"
    elif estimated_value > bounds["max"]:
        issues.append(
            f"Valor {estimated_value:.0f} € acima do máximo plausível "
            f"({bounds['max']} €) para {vehicle_type}."
        )
        corrected = float(bounds["max"])
        severity = "critical"

    # 2. Against the reference band
    reference = estimate_reference_value(
        brand=vehicle.get("brand"),
        model=vehicle.get("model"),
        year=vehicle.get("year"),
        km=vehicle.get("km"),
        fuel_type=vehicle.get("fuel_type"),
        vehicle_type=vehicle_type,
        engine_cc=vehicle.get("engine_size"),
    )

    if reference["value"] and reference["confidence"] >= 0.4:
        ratio = estimated_value / reference["value"]
        if ratio > 2.0:
            issues.append(
                f"Estimativa {estimated_value:.0f} € é {ratio:.1f}x a referência "
                f"de mercado ({reference['value']:.0f} €)."
            )
            corrected = reference["high"]
            severity = "critical"
        elif ratio > 1.45:
            issues.append(
                f"Estimativa {ratio:.0%} acima da referência de mercado "
                f"({reference['value']:.0f} €)."
            )
            corrected = min(float(corrected), float(reference["high"]))
            severity = "warning" if severity == "ok" else severity
        elif ratio < 0.5:
            issues.append(
                f"Estimativa {estimated_value:.0f} € é apenas {ratio:.0%} da "
                f"referência ({reference['value']:.0f} €)."
            )
            corrected = max(float(corrected), float(reference["low"]))
            severity = "warning" if severity == "ok" else severity

    # 3. Against the asking price — the model should never claim a vehicle is
    #    worth several times what anyone is asking for it.
    if asking_price and asking_price > 0:
        ratio_ask = estimated_value / asking_price
        cap = 2.2 if is_moto else 2.5
        if ratio_ask > cap:
            issues.append(
                f"Estimativa é {ratio_ask:.1f}x o preço pedido — implausível "
                f"num mercado líquido; provável erro do modelo ou anúncio anómalo."
            )
            corrected = min(float(corrected), asking_price * cap)
            severity = "critical"

    return {
        "is_valid": severity == "ok",
        "corrected_value": round(float(corrected), 2) if corrected else None,
        "issues": issues,
        "severity": severity,
        "reference": reference,
    }


def price_plausibility(
    asking_price: float, vehicle: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Is the *listing* price itself plausible?

    A price far below the reference is either the deal you are looking for or a
    scam / salvado / wrong data. The pipeline must distinguish the two.
    """
    reference = estimate_reference_value(
        brand=vehicle.get("brand"),
        model=vehicle.get("model"),
        year=vehicle.get("year"),
        km=vehicle.get("km"),
        fuel_type=vehicle.get("fuel_type"),
        vehicle_type=str(vehicle.get("vehicle_type") or "carros"),
        engine_cc=vehicle.get("engine_size"),
    )

    if not reference["value"] or reference["confidence"] < 0.35:
        return {
            "verdict": "indeterminado",
            "ratio": None,
            "reference": reference,
            "flags": ["Sem referência fiável para este modelo."],
        }

    ratio = asking_price / reference["value"]
    flags: List[str] = []

    if ratio < 0.35:
        verdict = "suspeito"
        flags.append(
            "Preço abaixo de 35% da referência: risco elevado de fraude, "
            "salvado, penhora ou anúncio com preço de entrada/sinal."
        )
    elif ratio < 0.60:
        verdict = "oportunidade_a_verificar"
        flags.append(
            "Preço bem abaixo do mercado: verificar histórico, sinistro e "
            "documentação antes de avançar."
        )
    elif ratio < 0.85:
        verdict = "bom_negocio"
    elif ratio <= 1.15:
        verdict = "preco_de_mercado"
    elif ratio <= 1.4:
        verdict = "caro"
    else:
        verdict = "muito_caro"
        flags.append("Preço muito acima da referência de mercado.")

    return {
        "verdict": verdict,
        "ratio": round(ratio, 3),
        "reference_value": reference["value"],
        "reference_range": [reference["low"], reference["high"]],
        "confidence": reference["confidence"],
        "reference": reference,
        "flags": flags,
    }


def market_context() -> Dict[str, Any]:
    """Macro context of the PT used-vehicle market (for dashboards/reports)."""
    return load_reference().get("_meta", {}).get("market_context", {})


__all__ = [
    "load_reference",
    "reload_reference",
    "estimate_reference_value",
    "validate_estimate",
    "price_plausibility",
    "resolve_segment",
    "residual_factor",
    "find_model_entry",
    "market_context",
]
