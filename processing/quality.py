"""
Camada de qualidade de anúncios (2026-08-01).

Classifica cada anúncio em três destinos, com regras determinísticas e
auditáveis (cada decisão guarda as regras ativadas):

* ``valid``           — anúncio aceite sem alertas de qualidade;
* ``valid_with_warning`` — anúncio elegível, mas com alerta auditável (por
  exemplo, um supercarro acima de €400k);
* ``quarantined``     — suspeito, excluído das avaliações/comparáveis até revisão;
* ``invalid``         — claramente inválido (dados impossíveis, não é um carro…).
Princípio: NUNCA eliminar um anúncio só porque o preço é alto ou fora da
distribuição. Carros legitimamente caros, raros ou novos ficam ``valid`` ou
``valid_with_warning`` conforme a evidência disponível.
A eliminação física é evitada — usa-se quarentena / soft delete.

Também inclui a canonização de marcas/modelos (Fase 9): mantém o valor
original e regista a confiança da normalização.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonização de marcas (Fase 9)
# ---------------------------------------------------------------------------

_BRAND_CANONICAL: Dict[str, str] = {
    "mercedes": "Mercedes-Benz", "mercedes benz": "Mercedes-Benz",
    "mercedes-benz": "Mercedes-Benz", "mb": "Mercedes-Benz",
    "bmw": "BMW", "vw": "Volkswagen", "volkswagen": "Volkswagen",
    "audi": "Audi", "renault": "Renault", "peugeot": "Peugeot",
    "citroen": "Citroën", "citroën": "Citroën",
    "toyota": "Toyota", "honda": "Honda", "hyundai": "Hyundai",
    "kia": "Kia", "nissan": "Nissan", "mazda": "Mazda",
    "ford": "Ford", "opel": "Opel", "fiat": "Fiat",
    "seat": "SEAT", "skoda": "Škoda", "škoda": "Škoda",
    "volvo": "Volvo", "tesla": "Tesla", "dacia": "Dacia",
    "alfa romeo": "Alfa Romeo", "alfa": "Alfa Romeo",
    "land rover": "Land Rover", "landrover": "Land Rover",
    "range rover": "Land Rover",
    "jaguar": "Jaguar", "porsche": "Porsche", "ferrari": "Ferrari",
    "lamborghini": "Lamborghini", "maserati": "Maserati",
    "mini": "MINI", "mini cooper": "MINI",
    "jeep": "Jeep", "mitsubishi": "Mitsubishi", "subaru": "Subaru",
    "suzuki": "Suzuki", "lexus": "Lexus", "infiniti": "Infiniti",
    "smart": "Smart", "cupra": "CUPRA", "ds": "DS",
    "yamaha": "Yamaha", "kawasaki": "Kawasaki", "ducati": "Ducati",
    "ktm": "KTM", "triumph": "Triumph", "piaggio": "Piaggio",
    "iveco": "Iveco", "man": "MAN",
}


def _strip_accents(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def normalize_brand(brand: Optional[str]) -> Dict[str, Any]:
    """Canoniza a marca. Devolve raw + normalizado + confiança.

    Nunca força uma correspondência incerta: se não há mapeamento fiável,
    o valor normalizado é o original limpo com confiança reduzida.
    """
    raw = (brand or "").strip()
    if not raw:
        return {"raw_brand": brand, "normalized_brand": None, "normalization_confidence": 0.0}
    key = _strip_accents(raw).lower().strip()
    key = re.sub(r"[_\-/]+", " ", key)
    key = re.sub(r"\s+", " ", key)
    if key in _BRAND_CANONICAL:
        return {
            "raw_brand": raw,
            "normalized_brand": _BRAND_CANONICAL[key],
            "normalization_confidence": 1.0 if raw == _BRAND_CANONICAL[key] else 0.95,
        }
    return {"raw_brand": raw, "normalized_brand": raw, "normalization_confidence": 0.5}


# ---------------------------------------------------------------------------
# Classificação de qualidade (Fase 10)
# ---------------------------------------------------------------------------

# Tokens que indicam que o anúncio não é a venda total de um veículo.
_PARTS_TOKENS = (
    "para pecas", "para peças", "pecas de", "peças de", "salvado",
    "motor para", "caixa para", "para abate", "sucata",
)
_LEASE_TOKENS = (
    "renting", "leasing", "ald", "aluguer de longa duracao",
    "aluguer de longa duração",
)
_MONTHLY_TOKENS = (
    "/mes", "/mês", "por mes", "por mês", "mensalidade", "prestacao",
    "prestação", "mensal", "desde ", "a partir de",
)
_ACCIDENT_TOKENS = (
    "acidentado", "batido", "sinistrado", "para restauro", "incendiado",
    "afundado", "capotado",
)
_NON_VEHICLE_TOKENS = (
    "trotinete", "bicicleta", "mota de agua", "barco", "atrelado",
    "reboque", "maquina agricola", "empilhador",
)
_AUCTION_SOURCES = {
    "leilosoc", "martelo", "penhorado", "autoline", "vpauto",
    "manheim", "autorola", "bca",
}


def _has_any(text: str, tokens) -> bool:
    return any(t in text for t in tokens)


def _enum_value(value: Any) -> str:
    """Return an enum's value without coupling quality to its defining module."""
    if hasattr(value, "value"):
        value = value.value
    return str(value or "").strip().lower()


def classify_listing(vehicle: Dict[str, Any],
                     reference_value: Optional[float] = None) -> Dict[str, Any]:
    """Classify an ad as ``valid``, ``valid_with_warning``, ``quarantined`` or ``invalid``.

    ``reference_value`` (referência externa ou estimativa) é usado apenas
    para detetar preços que não são totais (mensalidade/entrada).
    """
    reasons: List[str] = []
    status = "valid"

    price = vehicle.get("price")
    year = vehicle.get("year")
    km = vehicle.get("km")
    brand = (vehicle.get("brand") or "").strip()
    model = (vehicle.get("model") or "").strip()
    title = str(vehicle.get("title") or "")
    desc = str(vehicle.get("description") or "")
    text = _strip_accents((title + " " + desc).lower())
    vtype = str(vehicle.get("vehicle_type") or "carros")
    source = _enum_value(vehicle.get("source"))
    # Legacy rows have no provenance fields; preserve their historical
    # eligibility during migration. New parser output must be explicit.
    provenance_supplied = any(
        key in vehicle
        for key in ("price_raw", "price_kind", "currency", "price_evidence", "price_rejection_reason")
    )
    price_kind = _enum_value(vehicle.get("price_kind"))
    currency = _enum_value(vehicle.get("currency"))
    if currency and currency != "eur":
        reasons.append("moeda_nao_eur")
        status = "quarantined"
    if price_kind and price_kind not in ("unknown", "total"):
        reasons.append(f"preco_{price_kind}_nao_retail")
        status = "quarantined"
    elif provenance_supplied and price_kind == "unknown":
        reasons.append("preco_tipo_desconhecido")
        status = "quarantined"
    if vehicle.get("price_rejection_reason"):
        for reason in str(vehicle["price_rejection_reason"]).split(";"):
            reason = reason.strip()
            if reason and reason not in reasons:
                reasons.append(reason)
        if status == "valid":
            status = "quarantined"
    if source in _AUCTION_SOURCES and price and price > 0 and price_kind in ("", "unknown"):
        reasons.append("leilao_sem_tipo_de_preco_verificavel")
        status = "quarantined"


    # ---------------- regras de INVALID (determinísticas) ----------------
    if price is None or price <= 0:
        reasons.append("preco_zero_ou_ausente")
        if price_kind and price_kind not in ("unknown", "total"):
            # A non-retail observation has no valid Vehicle.price by design;
            # retain it for audit without allowing it into valuation.
            status = "quarantined"
        else:
            status = "invalid"
    elif price < 100 and vtype == "carros":
        reasons.append("preco_impossivel_carro(<100)")
        status = "invalid"
    elif price > 1500000 and vtype == "carros":
        reasons.append("preco_impossivel_carro(>1.5M)")
        status = "invalid"
    elif price > 400000 and vtype == "carros":
        # Supercarros exist: preserve value with an explicit warning state.
        reasons.append(f"preco_acima_de_400k_verificar({price:.0f})")
        if status == "valid":
            status = "valid_with_warning"
    if year is None:
        reasons.append("ano_ausente")
        if status in ("valid", "valid_with_warning"):
            status = "quarantined"
    if km is None:
        reasons.append("km_ausente")
        if status in ("valid", "valid_with_warning"):
            status = "quarantined"
    if year is not None:
        current = __import__("datetime").datetime.now().year
        if year < 1950 or year > current + 1:
            reasons.append(f"ano_impossivel({year})")
            status = "invalid"

    if km is not None and km < 0:
        reasons.append("km_negativo")
        status = "invalid"

    if not brand or brand.lower() in ("unknown", "outro", "other", "-"):
        reasons.append("marca_ausente")
        status = "invalid" if status != "invalid" else status

    if _has_any(text, _PARTS_TOKENS):
        reasons.append("anuncio_de_pecas_ou_salvado")
        status = "invalid"
    if _has_any(text, _NON_VEHICLE_TOKENS):
        reasons.append("anuncio_nao_e_veiculo")
        status = "invalid"

    if status == "invalid":
        return {"quality_status": status, "quality_reasons": reasons}

    # ---------------- regras de QUARANTINE ----------------
    if reference_value and price and reference_value > 4000:
        ratio = price / reference_value
        if ratio < 0.12:
            reasons.append(
                f"preco_provavel_mensalidade_ou_entrada(ratio={ratio:.2f})"
            )
            status = "quarantined"
        elif ratio < 0.30 and _has_any(text, _MONTHLY_TOKENS):
            reasons.append(f"preco_com_texto_mensal(ratio={ratio:.2f})")
            status = "quarantined"
        elif ratio > 4.0:
            reasons.append(f"preco_muito_acima_da_referencia(ratio={ratio:.2f})")
            status = "quarantined"

    if _has_any(text, _LEASE_TOKENS) and price and reference_value and price < 0.3 * reference_value:
        reasons.append("preco_de_leasing_renting")
        status = "quarantined"

    if _has_any(text, _ACCIDENT_TOKENS):
        # Não invalida: pode ser um salvado legítimo — mas não deve servir de
        # comparável nem receber score alto.
        reasons.append("viatura_acidentada_declarada")
        status = "quarantined"

    if km is not None and year is not None:
        age = max(1, __import__("datetime").datetime.now().year - year)
        if km > 80000 * age:
            reasons.append(f"km_incompativel_com_idade({km}km/{age}anos)")
            status = "quarantined"

    if _has_any(text, ("sem iva", "+ iva", "iva discriminado", "sem iva incluido")):
        reasons.append("preco_sem_iva_provavel")
        status = "quarantined"

    if not model:
        reasons.append("modelo_ausente")

    return {"quality_status": status, "quality_reasons": reasons}
