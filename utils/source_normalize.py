"""Normalize scraper source strings to database Source enum values."""
from __future__ import annotations
from typing import Optional

from database.models import Source

_SOURCE_ALIASES = {
    "olx": Source.OLX,
    "standvirtual": Source.STANDVIRTUAL,
    "autosapo": Source.AUTOSAPO,
    "auto sapo": Source.AUTOSAPO,
    "custojusto": Source.CUSTOJUSTO,
    "custo justo": Source.CUSTOJUSTO,
    "autopt": Source.AUTOPT,
    "auto.pt": Source.AUTOPT,
    "piscapisca": Source.PISCAPISCA,
    "pisca pisca": Source.PISCAPISCA,
    "carplus": Source.CARPLUS,
    "vpauto": Source.VPAUTO,
    "vpauto.pt": Source.VPAUTO,
    "leilosoc": Source.LEILOSOC,
    "leilosoc.pt": Source.LEILOSOC,
    "bca": Source.BCA,
    "bcamarketplace": Source.BCA,
    "bca.pt": Source.BCA,
    "manheim": Source.MANHEIM,
    "manheim.pt": Source.MANHEIM,
    "autorola": Source.AUTOROLA,
    "autorola.pt": Source.AUTOROLA,
}


def normalize_source(value: Optional[str]) -> str:
    """Return canonical Source enum value string (e.g. OLX)."""
    if value is None:
        return Source.OLX.value
    if isinstance(value, Source):
        return value.value
    raw = str(value).strip()
    if not raw:
        return Source.OLX.value
    upper = raw.upper()
    if upper in Source.__members__:
        return Source[upper].value
    alias = _SOURCE_ALIASES.get(raw.lower())
    if alias:
        return alias.value
    return upper
