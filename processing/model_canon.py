"""
Canonização de marca/modelo na ingestão (Fase 14).

Problemas tratados (observados em produção):
* Preço colado ao nome do modelo — AUTOPT: "TT 15 350 €" → modelo "TT",
  preço 15 350 € (extraído se o campo price estiver em falta ou divergir).
* Número de lote no fim do modelo — AUTOLINE: "C3 28", "525i 46" → "C3", "525i".
* Sufixos de leilão — MARTELO: "A4 Avant 1.9 TDI · Lance Atual",
  "TRANSIT COURIER - 2014" → parte antes do separador.
* Aliases de marca — "VW" → "Volkswagen" (via processing.quality).
* Nome canónico do modelo — quando o par marca/modelo casa com a referência
  de mercado (confiança ≥ 0.8), o modelo passa a usar a forma canónica da
  referência ("bmw 320d" → "Serie 3"); melhora agrupamento, comparáveis e
  treino. Caso contrário fica o texto limpo original.

API: ``canon_listing(brand, model, title, price, source)`` — pura, sem I/O
de BD (a referência de mercado é carregada em memória pelo market_reference).
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, Optional

from processing.quality import normalize_brand
from scrapers.schema import PriceKind, parse_price_evidence


logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(
    r"(?<![\w])("
    r"\d{1,3}(?:[ .]\d{3})+(?:[.,]\d{2})?"
    r"|\d{1,3}(?:,\d{3})+(?:\.\d{2})?"
    r"|\d+(?:[.,]\d{1,2})?"
    r")\s*(?:€|euros?\b|eur\b)",
    re.IGNORECASE,
)


def extract_price_from_text(text: str) -> tuple[Optional[float], str]:
    """Extrai o primeiro preço monetário com evidência no texto."""
    if not text:
        return None, text
    m = _PRICE_RE.search(text)
    if not m:
        return None, text
    evidence = parse_price_evidence(m.group(0), context=text)
    if evidence.kind is not PriceKind.TOTAL or evidence.value is None:
        return None, text
    cleaned = (text[: m.start()] + text[m.end():]).strip(" -·|,")
    return evidence.value, cleaned


# ── Ruído de leilões ──────────────────────────────────────────────────────────
# " · Lance Atual", "· Ano 2018", " - 2014", " | ..."
_SUFFIX_RE = re.compile(r"\s*[·|]\s.*$")
_TRAILING_YEAR_RE = re.compile(r"\s*[-–—]\s*(19|20)\d{2}\s*$")
# Número de lote de 1-2 dígitos no fim ("C3 28") — só removido se o resto
# continuar a ter letras e não for um nameplate legítimo (Model 3, XC 90…).
_LOT_RE = re.compile(r"^(?P<body>.*?[A-Za-z])\s+(?P<lot>\d{1,2})$")


def _strip_accents(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )


# Nameplates legítimos que acabam em número solto — nunca cortar.
_KEEP_TRAILING_NUM = re.compile(
    r"(model\s+\d|xc\s?\d+|type\s+\d|ioniq\s?\d+|atto\s?\d+|serie\s?\d|classe\s?[abces]|"
    r"^\d{3,4}[a-z]{0,3}$|z4|x[1-7]|q[2-8]|a[1-8]|e-tron\s?\d*|i[3458x]\d*|911|718|"
    r"c\s?\d{2,3}|e\s?\d{2,3}|s\s?\d{2,3}|gl[aces]\s?\d{0,3})",
    re.IGNORECASE,
)


def clean_model_text(model: str, source: str = "") -> str:
    """Remove sufixos de leilão, preço colado e número de lote do modelo."""
    m = (model or "").strip()
    if not m:
        return m
    # 1) sufixos " · Lance Atual" / " | ..." / " - 2014"
    m = _SUFFIX_RE.sub("", m).strip()
    m = _TRAILING_YEAR_RE.sub("", m).strip()
    # 2) preço colado ("TT 15 350 €")
    _, m2 = extract_price_from_text(m)
    if m2:
        m = m2
    # 3) número de lote final ("C3 28", "525i 46") — com proteção de nameplates
    #    (verificação accent-insensitive: "série 1" também é nameplate legítimo)
    lot = _LOT_RE.match(m)
    if lot:
        m_norm = _strip_accents(m).lower()
        body_norm = _strip_accents(lot.group("body")).lower()
        if not _KEEP_TRAILING_NUM.search(body_norm) \
                and not _KEEP_TRAILING_NUM.search(m_norm):
            body = lot.group("body").strip()
            if len(body) >= 2:
                m = body
    return re.sub(r"\s+", " ", m).strip()


# ── Nome canónico via referência de mercado ───────────────────────────────────
def _display_case(canon: str) -> str:
    """Capitalização de apresentação: 'tt'→'TT', 'c3'→'C3', 'serie 5'→'Serie 5'."""
    out = []
    for tok in canon.split():
        if re.fullmatch(r"[a-z]{1,4}\d{0,3}", tok) and any(c.isdigit() for c in tok):
            out.append(tok.upper())  # c3, a4, glc300…
        elif re.fullmatch(r"[a-z]{1,2}", tok):
            out.append(tok.upper())  # tt, z4…
        else:
            out.append(tok.capitalize())
    return " ".join(out)


def canonical_model_name(brand: str, model: str) -> tuple[str, float]:
    """Devolve (modelo_canónico, confiança). Fallback: texto limpo original."""
    from valuation.market_reference import find_model_entry  # import tardio (cache interno)

    entry, key, conf = find_model_entry(brand, model)
    if entry and key and conf >= 0.8:
        # key é "brand modelo" normalizado; a forma canónica é o sufixo do modelo
        bnorm = _strip_accents(brand).lower().strip()
        canon = key[len(bnorm):].strip() if key.startswith(bnorm) else key
        if canon:
            return _display_case(canon), conf
    return model, 0.0


def canon_listing(
    brand: Optional[str],
    model: Optional[str],
    title: Optional[str] = None,
    price: Optional[float] = None,
    source: str = "",
) -> Dict[str, Any]:
    """Canoniza um anúncio na ingestão. Função pura (sem escrita na BD).

    Devolve dict com brand/model/price canonizados + flags de auditoria:
    ``price_from_text``, ``model_cleaned``, ``model_canonicalized``.
    """
    out: Dict[str, Any] = {
        "brand": (brand or "").strip(),
        "model": (model or "").strip(),
        "price": price,
        "price_from_text": False,
        "model_cleaned": False,
        "model_canonicalized": False,
    }

    # Marca canónica (VW → Volkswagen, Mercedes → Mercedes-Benz, …)
    nb = normalize_brand(out["brand"])
    if nb.get("normalized_brand") and nb["normalization_confidence"] >= 0.9:
        out["brand"] = nb["normalized_brand"]

    # Preço em falta? Tenta o modelo e depois o título.
    if not out["price"] or float(out["price"] or 0) <= 0:
        for text in (out["model"], title or ""):
            p, _ = extract_price_from_text(text or "")
            if p:
                out["price"] = p
                out["price_from_text"] = True
                break

    # Modelo limpo (lote, sufixos, preço colado)
    cleaned = clean_model_text(out["model"], source)
    if cleaned != out["model"]:
        out["model_cleaned"] = True
        out["model"] = cleaned

    # Forma canónica da referência de mercado
    canon, conf = canonical_model_name(out["brand"], out["model"])
    if conf >= 0.8 and canon and canon.lower() != out["model"].lower():
        out["model"] = canon
        out["model_canonicalized"] = True

    return out
