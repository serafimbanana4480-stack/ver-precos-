"""Normalize scraper source labels without inventing provenance.

The URL is the strongest authority when its host is one of the configured
sources.  A missing or unrecognised label is represented by ``UNKNOWN``;
legacy code must not silently turn it into OLX.
"""
from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

from database.models import Source


UNKNOWN_SOURCE = "UNKNOWN"


def _compact(value: str) -> str:
    """Fold harmless separator differences in source aliases."""
    return re.sub(r"[\s_.-]+", "", value.strip().casefold())


# Build aliases from both enum names and persisted values first.  This keeps
# newly added canonical enum members usable without duplicating every spelling.
_SOURCE_ALIASES = {}
for _member in Source:
    for _raw in (_member.name, _member.value):
        _SOURCE_ALIASES[_raw.casefold()] = _member
        _SOURCE_ALIASES[_compact(_raw)] = _member

# Explicit legacy spellings and domains whose punctuation carries meaning.
# ``AUTOUNCLE`` is the existing aggregator contract; the newer
# ``AUTOUNCLE_PT`` adapter uses the hyphenated ``auto-uncle.pt`` host.
_SOURCE_ALIASES.update({
    "auto sapo": Source.AUTOSAPO,
    "custo justo": Source.CUSTOJUSTO,
    "auto.pt": Source.AUTOPT,
    "autouncle.pt": Source.AUTO_UNCLE,
    "auto-uncle.pt": Source.AUTOUNCLE_PT,
    "auto uncle pt": Source.AUTOUNCLE_PT,
    "bcamarketplace": Source.BCA,
    "bca.pt": Source.BCA,
    "manheim.pt": Source.MANHEIM,
    "autorola.pt": Source.AUTOROLA,
    "pisca pisca": Source.PISCAPISCA,
})

_HOST_SOURCES = {
    # Portugal retail and aggregator sources.
    "olx.pt": Source.OLX,
    "standvirtual.com": Source.STANDVIRTUAL,
    "autosapo.pt": Source.AUTOSAPO,
    "custojusto.pt": Source.CUSTOJUSTO,
    "auto.pt": Source.AUTOPT,
    "autouncle.pt": Source.AUTO_UNCLE,
    "auto-uncle.pt": Source.AUTOUNCLE_PT,
    "piscapisca.pt": Source.PISCAPISCA,
    "carplus.pt": Source.CARPLUS,
    "autohub.pt": Source.AUTOHUB,
    "autoline.pt": Source.AUTOLINE,
    "martelo.pt": Source.MARTELO,
    "mcoutinho.pt": Source.MCOUTINHO,
    "penhorado.pt": Source.PENHORADO,
    "spoticar.pt": Source.SPOTICAR_PT,
    "autoscout24.pt": Source.AUTOSCOUT24_PT,
    # Auction and ground-truth sources.
    "vpauto.pt": Source.VPAUTO,
    "leilosoc.pt": Source.LEILOSOC,
    "leilosoc.com": Source.LEILOSOC,
    "bca.pt": Source.BCA,
    "manheim.pt": Source.MANHEIM,
    "autorola.pt": Source.AUTOROLA,
    # Foreign sources already represented by canonical enum values.
    "autoscout24.de": Source.AUTOSCOUT24_DE,
    "autoscout24.es": Source.AUTOSCOUT24_ES,
    "autoscout24.fr": Source.AUTOSCOUT24_FR,
    "autohero.com": Source.AUTOHERO,
    "spoticar.com": Source.SPOTICAR,
    "leboncoin.fr": Source.LEBONCOIN,
    "lacentrale.fr": Source.LACENTRALE,
    "milanuncios.com": Source.MILANUNCIOS,
    "wallapop.com": Source.WALLAPOP,
    "coches.net": Source.COCHES_NET,
    "idealista.com": Source.IDEALISTA_AUTOS,
}


def _hostname(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        raw = str(url).strip()
        # urlparse treats a scheme-less URL as a path; ``//`` preserves the
        # hostname without making a network request.
        parsed = urlparse(raw if "://" in raw else f"//{raw}")
        return (parsed.hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""


def source_from_url(url: Optional[str]) -> Optional[str]:
    """Return a canonical source only when the URL host is authoritative."""
    host = _hostname(url)
    if not host:
        return None
    for domain, source in sorted(_HOST_SOURCES.items(), key=lambda item: -len(item[0])):
        if host == domain or host.endswith(f".{domain}"):
            return source.value
    return None


def _source_from_label(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, Source):
        return value.value
    raw = str(value).strip()
    if not raw:
        return None
    alias = _SOURCE_ALIASES.get(raw.casefold())
    if alias is None:
        alias = _SOURCE_ALIASES.get(_compact(raw))
    return alias.value if alias is not None else None


def normalize_source(value: Optional[str], url: Optional[str] = None) -> str:
    """Return the canonical persisted source or ``UNKNOWN``.

    A recognised URL host overrides a stale adapter label, preventing for
    example an AutoUncle URL from being stored as Auto.pt.  When the host is
    not recognised, an explicit known label may still be used for legacy
    sources whose domains are not listed here; an absent/unknown label never
    falls back to OLX.
    """
    by_url = source_from_url(url)
    if by_url is not None:
        return by_url
    return _source_from_label(value) or UNKNOWN_SOURCE
