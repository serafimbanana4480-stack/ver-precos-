from enum import Enum
from math import isfinite
from typing import Optional, List, Any
import re
import unicodedata

from pydantic import BaseModel, Field, field_validator, model_validator

class PriceKind(str, Enum):
    TOTAL = "total"
    MONTHLY = "monthly"
    ENTRY = "entry"
    INSTALLMENT = "installment"
    AUCTION_START = "auction_start"
    AUCTION_CURRENT = "auction_current"
    AUCTION_ADJUDICATED = "auction_adjudicated"
    UNKNOWN = "unknown"


class PriceEvidence(BaseModel):
    raw: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    kind: PriceKind = PriceKind.UNKNOWN
    evidence: Optional[str] = None
    rejection_reason: Optional[str] = None


_AMOUNT_TOKEN = (
    r"[-+]?(?:\d{1,3}(?:[\s.,]\d{3})+(?:[.,]\d{2})?"
    r"|\d+(?:[.,]\d{1,2})?)"
)
_CURRENCY_TOKEN = r"(?:€|EUR|EUROS?|£|GBP|USD|SEK|DKK|CHF|NOK|\$)"
_PRICE_AFTER_CURRENCY_RE = re.compile(
    rf"(?<![\w])(?P<number>{_AMOUNT_TOKEN})\s*"
    rf"(?P<currency>{_CURRENCY_TOKEN})(?!\w)",
    re.IGNORECASE,
)
_PRICE_BEFORE_CURRENCY_RE = re.compile(
    rf"(?P<currency>{_CURRENCY_TOKEN})\s*"
    rf"(?P<number>{_AMOUNT_TOKEN})(?!\w)",
    re.IGNORECASE,
)
_PLAIN_AMOUNT_RE = re.compile(rf"^\s*(?P<number>{_AMOUNT_TOKEN})\s*$")


def _fold_text(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _parse_localized_number(value: str) -> Optional[float]:
    cleaned = (value or "").replace("\xa0", " ").replace(" ", "")
    if not cleaned:
        return None
    sign = -1 if cleaned.startswith("-") else 1
    cleaned = cleaned.lstrip("+-")
    if "." in cleaned and "," in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) == 3:
            cleaned = "".join(parts)
        else:
            cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            cleaned = "".join(parts)
    try:
        number = sign * float(cleaned)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _currency_code(token: Optional[str]) -> Optional[str]:
    if not token:
        return "EUR"
    normalized = token.upper()
    if token == "€" or normalized in {"EUR", "EURO", "EUROS"}:
        return "EUR"
    if token == "£" or normalized == "GBP":
        return "GBP"
    if token == "$" or normalized == "USD":
        return "USD"
    if normalized in {"SEK", "DKK", "CHF", "NOK"}:
        return normalized
    return normalized


def _infer_price_kind(text: str) -> PriceKind:
    normalized = _fold_text(text)
    if any(token in normalized for token in (
        "licitacao inicial", "lance inicial", "preco de saida",
        "preco de partida", "preco minimo", "valor de partida",
        "valor base", "valor de abertura", "v abertura", "v. abertura",
        "v minimo", "v. minimo", "starting bid", "opening bid",
        "leilao", "auction", "penhorado", "leilosoc", "martelo", "autoline",
        "vpauto", "manheim", "autorola", "bca",
    )):
        return PriceKind.AUCTION_START
    if any(token in normalized for token in (
        "lance atual", "licitacao atual", "current bid",
    )):
        return PriceKind.AUCTION_CURRENT
    if any(token in normalized for token in (
        "adjudicacao", "adjudicado", "preco final", "hammer price",
    )):
        return PriceKind.AUCTION_ADJUDICATED
    if any(token in normalized for token in (
        "/mes", "por mes", "mensalidade", "prestacao",
        "mensal", "desde ", "a partir de",
    )):
        return PriceKind.MONTHLY
    if any(token in normalized for token in (
        "entrada", "sinal", "down payment", "initial payment",
    )):
        return PriceKind.ENTRY
    if any(token in normalized for token in ("parcel", "installment")):
        return PriceKind.INSTALLMENT
    return PriceKind.TOTAL


def parse_price_evidence(
    value: Any,
    *,
    context: str = "",
    declared_currency: Optional[str] = None,
    declared_kind: Optional[Any] = None,
) -> PriceEvidence:
    """Parse a price while retaining its source text and semantic meaning."""
    if value is None:
        return PriceEvidence(rejection_reason="preco_ausente")
    raw = value if isinstance(value, str) else str(value)
    text = raw.strip()
    if not text:
        return PriceEvidence(raw=raw, rejection_reason="preco_ausente")

    combined = f"{text} {context or ''}"
    kind = _infer_price_kind(combined)
    match = _PRICE_AFTER_CURRENCY_RE.search(text)
    if match is None:
        match = _PRICE_BEFORE_CURRENCY_RE.search(text)
    currency = _currency_code(match.group("currency")) if match else None
    evidence = "currency_bound"
    number_text = match.group("number") if match else None

    if match is None:
        plain = _PLAIN_AMOUNT_RE.fullmatch(text)
        if plain is None:
            return PriceEvidence(
                raw=raw,
                kind=PriceKind.UNKNOWN,
                rejection_reason="preco_sem_evidencia_monetaria",
            )
        number_text = plain.group("number")
        currency = "EUR"
        evidence = "numeric_value_without_currency"

    parsed = _parse_localized_number(number_text)
    if parsed is None:
        return PriceEvidence(
            raw=raw,
            currency=currency,
            kind=PriceKind.UNKNOWN,
            evidence=evidence,
            rejection_reason="preco_numero_invalido",
        )
    if parsed <= 0:
        return PriceEvidence(
            raw=raw,
            value=parsed,
            currency=currency,
            kind=kind,
            evidence=evidence,
            rejection_reason="preco_zero_ou_negativo",
        )
    # Numeric scraper fields do not carry currency/kind evidence. Honour an
    # explicit declaration in that case, while retaining an auditable conflict
    # when the text itself says something different.
    declared_code = _currency_code(str(declared_currency)) if declared_currency else None
    provenance_reasons = []
    if declared_code:
        if currency in (None, "EUR") and evidence == "numeric_value_without_currency":
            currency = declared_code
        elif currency != declared_code:
            provenance_reasons.append("proveniencia_moeda_inconsistente")
    if declared_kind not in (None, "", PriceKind.UNKNOWN, "unknown"):
        try:
            declared_price_kind = PriceKind(declared_kind)
        except ValueError:
            provenance_reasons.append("proveniencia_tipo_preco_invalido")
        else:
            if kind is PriceKind.TOTAL and evidence == "numeric_value_without_currency":
                kind = declared_price_kind
            elif kind is not declared_price_kind:
                provenance_reasons.append("proveniencia_tipo_preco_inconsistente")

    if currency != "EUR":
        reason = "moeda_nao_eur"
    elif kind is not PriceKind.TOTAL:
        reason = f"preco_{kind.value}_nao_retail"
    else:
        reason = None
    if provenance_reasons:
        reason = ";".join([r for r in (reason, *provenance_reasons) if r])
    return PriceEvidence(
        raw=raw,
        value=parsed,
        currency=currency,
        kind=kind,
        evidence=evidence,
        rejection_reason=reason,
    )

class VehicleListing(BaseModel):
    title: str
    price: Optional[float] = None
    price_raw: Optional[str] = None
    price_observed_value: Optional[float] = None
    currency: Optional[str] = None
    price_kind: PriceKind = PriceKind.UNKNOWN
    price_evidence: Optional[str] = None
    price_rejection_reason: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_price_contract(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        values = dict(data)
        raw = values.get("price")
        if raw is None and "price_raw" in values:
            raw = values.get("price_raw")
        if raw is None:
            return values
        context = " ".join(
            str(values.get(key) or "")
            for key in ("title", "description", "brand", "model")
        )
        result = parse_price_evidence(raw, context=context)
        conflicts = []
        supplied_currency = values.get("currency")
        if supplied_currency and result.currency:
            if str(supplied_currency).upper() != result.currency:
                conflicts.append("proveniencia_moeda_inconsistente")
        supplied_kind = values.get("price_kind")
        if supplied_kind:
            try:
                supplied_kind = PriceKind(supplied_kind)
            except ValueError:
                conflicts.append("proveniencia_tipo_preco_invalido")
            else:
                if supplied_kind is not PriceKind.UNKNOWN and supplied_kind is not result.kind:
                    conflicts.append("proveniencia_tipo_preco_inconsistente")
        values["price"] = (
            result.value
            if result.kind is PriceKind.TOTAL and result.currency == "EUR"
            else None
        )
        values["price_raw"] = result.raw
        values["price_observed_value"] = result.value
        values["currency"] = result.currency
        values["price_kind"] = result.kind
        values["price_evidence"] = result.evidence
        reasons = [reason for reason in (result.rejection_reason, *conflicts) if reason]
        values["price_rejection_reason"] = ";".join(reasons) or None
        return values

    url: Optional[str] = None
    year: Optional[int] = None
    km: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    location: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    source_id: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    horsepower: Optional[int] = None
    engine_size: Optional[int] = None
    doors: Optional[int] = None
    seats: Optional[int] = None
    color: Optional[str] = None
    seller_name: Optional[str] = None
    seller_type: Optional[str] = None
    extras: List[str] = Field(default_factory=list)
    is_national: Optional[bool] = None
    num_owners: Optional[int] = None
    warranty_months: Optional[int] = None
    condition_status: Optional[str] = None
    # Motorcycle-specific fields
    engine_type: Optional[str] = None  # single, twin, triple, four-cylinder
    riding_style: Optional[str] = None  # sport, touring, adventure, cruiser, naked
    has_abs: Optional[bool] = None
    has_traction_control: Optional[bool] = None
    aftermarket_mods: List[str] = Field(default_factory=list)
    seat_height: Optional[int] = None  # in mm
    wet_weight: Optional[int] = None  # in kg
    license_category: Optional[str] = None  # A1, A2, A

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        result = parse_price_evidence(v)
        if result.kind is PriceKind.TOTAL and result.currency == "EUR":
            return result.value
        return None

    @field_validator("km", mode="before")
    @classmethod
    def parse_km(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            # Remove "km" and separators
            v = re.sub(r"[^\d]", "", v)
            try:
                return int(v)
            except ValueError:
                return None
        return None

    @field_validator("year", mode="before")
    @classmethod
    def parse_year(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            # Try to find a 4-digit number that looks like a year
            match = re.search(r"\b(19|20)\d{2}\b", v)
            if match:
                return int(match.group(0))
            
            # Fallback to just digits if it's a short string
            v_digits = re.sub(r"[^\d]", "", v)
            if len(v_digits) == 4:
                try:
                    return int(v_digits)
                except ValueError:
                    return None
        return None

    @field_validator("horsepower", "engine_size", "doors", "seats", "num_owners", "warranty_months", mode="before")
    @classmethod
    def parse_int_fields(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            # Remove common units that might contain numbers (like cm3)
            v = re.sub(r"cm3|cc", "", v, flags=re.IGNORECASE)
            # Extract digits (this also handles thousands separators like . or , or space)
            v_digits = re.sub(r"[^\d]", "", v)
            if v_digits:
                try:
                    return int(v_digits)
                except ValueError:
                    return None
        return None


class ListingSchema(VehicleListing):
    """Legacy compatibility wrapper with permissive defaults."""

    title: str = ""


# Legacy compatibility alias expected by historical tests.
ScrapedVehicle = VehicleListing
