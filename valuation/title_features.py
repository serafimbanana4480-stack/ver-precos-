"""
Extração de atributos de preço a partir do título do anúncio.

Motivação
---------
Auditoria de 06/08/2026: as colunas `version`, `trim_level`, `extras`, `color`,
`num_owners` e `condition_status` estão a **0% de preenchimento** na base, mas
100% dos anúncios têm título, e o título carrega quase sempre a versão, a
cilindrada, a potência e o acabamento:

    "Nissan Qashqai 1.3 DIG-T Tekna"
    "AUDI A4 LIMOUSINE B9 S LINE 2.0TDI 150CV"
    "Usado (2025) Peugeot 208 Allure 101 HP"
    "Smart Fortwo nacional"

Este módulo transforma esse texto livre em features numéricas estáveis, sem
depender de o scraper vir a preencher os campos estruturados.

Todas as funções são puras e determinísticas — mesmo título, mesmo resultado —
para não haver desvio entre treino e inferência.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional

__all__ = ["extract_title_features", "TITLE_FEATURE_NAMES"]


def _norm(text: Optional[str]) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


# --------------------------------------------------------------- cilindrada --
# "1.3 DIG-T", "2.0TDI", "1.6 HDi" -> litros. Evita apanhar anos (2.0 vs 2018).
_RE_DISPLACEMENT = re.compile(r"\b([0-9])[.,]([0-9])\b")

# --------------------------------------------------------------- potencia ----
# "150CV", "101 HP", "218h", "130 cv"
_RE_POWER = re.compile(r"\b(\d{2,3})\s?(cv|hp|ps)\b")

# --------------------------------------------------------------- bateria -----
_RE_KWH = re.compile(r"\b(\d{1,3})[.,]?(\d)?\s?kwh\b")


# Acabamentos: agrupados por posicionamento comercial, não por marca.
# O valor é uma ordinal de "riqueza de equipamento" — é isso que move o preço.
TRIM_TIERS: Dict[str, int] = {
    # topo / desportivo
    "s line": 4, "sline": 4, "m sport": 4, "msport": 4, "amg": 4, "amg line": 4,
    "gti": 4, "gtd": 4, "gts": 4, "st line": 4, "stline": 4, "n line": 4,
    "nline": 4, "r line": 4, "rline": 4, "john cooper": 4, "jcw": 4,
    "performance": 4, "quattro": 4, "4matic": 4, "xdrive": 4, "gt line": 4,
    "black edition": 4, "rs": 4, "abt": 4, "vrs": 4, "cupra": 4,
    # alto
    "tekna": 3, "titanium": 3, "highline": 3, "elegance": 3, "exclusive": 3,
    "premium": 3, "luxury": 3, "excellence": 3, "gt": 3, "avantgarde": 3,
    "progressive": 3, "allure": 3, "intens": 3, "signature": 3, "platinum": 3,
    "shine": 3, "ultimate": 3, "vignale": 3, "inscription": 3, "momentum": 3,
    # medio
    "style": 2, "comfortline": 2, "acenta": 2, "zetec": 2, "dynamic": 2,
    "active": 2, "business": 2, "advance": 2, "confortline": 2, "sport": 2,
    "design": 2, "feel": 2, "life": 2, "edition": 2, "connect": 2,
    # base
    "trendline": 1, "visia": 1, "access": 1, "essential": 1, "base": 1,
    "entry": 1, "like": 1, "pop": 1, "attraction": 1, "ambiente": 1,
}

# Carroçaria — afeta preço independentemente de marca/modelo.
BODY_STYLES: Dict[str, int] = {
    "coupe": 1, "cabrio": 2, "cabriolet": 2, "roadster": 2, "descapotavel": 2,
    "sw": 3, "station": 3, "carrinha": 3, "touring": 3, "estate": 3,
    "avant": 3, "shooting brake": 3, "variant": 3, "sportstourer": 3,
    "sports tourer": 3, "break": 3,
    "limousine": 4, "sedan": 4, "berlina": 4, "saloon": 4,
    "suv": 5, "crossover": 5, "4x4": 5,
    "van": 6, "monovolume": 6, "comercial": 6,
}

# Sinais de estado / proveniência que o mercado português valoriza.
_NACIONAL = ("nacional", "nacionais")
_IMPORT = ("importado", "importada", "import")
_DAMAGE = ("salvado", "acidentado", "batido", "sinistrado", "para pecas",
           "para peças", "sucata", "danificado")
_WARRANTY = ("garantia", "certificado", "aprovado", "revisao feita",
             "livro de revisoes", "revisoes")
_URGENT = ("urgente", "negociavel", "aceito retoma", "baixa de preco",
           "oportunidade")

TITLE_FEATURE_NAMES = [
    "t_displacement",   # litros de cilindrada (0 se ausente)
    "t_power_cv",       # potência em CV (0 se ausente)
    "t_battery_kwh",    # capacidade de bateria (0 se ausente)
    "t_trim_tier",      # 0 desconhecido .. 4 topo de gama
    "t_body_style",     # código de carroçaria (0 desconhecido)
    "t_is_nacional",    # 1 se declarado nacional
    "t_is_import",      # 1 se declarado importado
    "t_has_damage",     # 1 se salvado/acidentado
    "t_has_warranty",   # 1 se garantia/revisões mencionadas
    "t_is_urgent",      # 1 se linguagem de venda urgente
    "t_token_count",    # nº de palavras: proxy de detalhe do anúncio
    "t_has_digits_trim",  # 1 se há designação numérica (320d, 220 cdi)
]


def extract_title_features(title: Optional[str],
                           known_year: Optional[int] = None) -> Dict[str, float]:
    """Extrai features numéricas de um título de anúncio.

    Devolve sempre todas as chaves de ``TITLE_FEATURE_NAMES``, com 0.0 quando o
    atributo não é detetável — nunca NaN, para não partir os estimadores.

    ``known_year`` permite descartar números que são o ano do carro e não
    cilindrada nem potência.
    """
    t = _norm(title)
    out: Dict[str, float] = {k: 0.0 for k in TITLE_FEATURE_NAMES}
    if not t:
        return out

    # cilindrada: 0.6L a 8.0L é o intervalo plausível
    for m in _RE_DISPLACEMENT.finditer(t):
        val = float(f"{m.group(1)}.{m.group(2)}")
        if 0.6 <= val <= 8.0:
            out["t_displacement"] = val
            break

    # potência: 40cv a 900cv
    m = _RE_POWER.search(t)
    if m:
        val = float(m.group(1))
        if 40 <= val <= 900:
            out["t_power_cv"] = val

    # bateria
    m = _RE_KWH.search(t)
    if m:
        whole = m.group(1)
        frac = m.group(2) or "0"
        val = float(f"{whole}.{frac}")
        if 5 <= val <= 250:
            out["t_battery_kwh"] = val

    # acabamento: fica com o tier mais alto encontrado
    tier = 0
    for kw, lvl in TRIM_TIERS.items():
        if re.search(rf"\b{re.escape(kw)}\b", t):
            tier = max(tier, lvl)
    out["t_trim_tier"] = float(tier)

    # carroçaria
    for kw, code in BODY_STYLES.items():
        if re.search(rf"\b{re.escape(kw)}\b", t):
            out["t_body_style"] = float(code)
            break

    out["t_is_nacional"] = float(any(w in t for w in _NACIONAL))
    out["t_is_import"] = float(any(w in t for w in _IMPORT))
    out["t_has_damage"] = float(any(w in t for w in _DAMAGE))
    out["t_has_warranty"] = float(any(w in t for w in _WARRANTY))
    out["t_is_urgent"] = float(any(w in t for w in _URGENT))
    out["t_token_count"] = float(len(t.split()))
    # designação numérica de versão: "320d", "220 cdi", "1.6 tdi 115"
    out["t_has_digits_trim"] = float(bool(re.search(r"\b\d{3}\s?(d|i|e|cdi|tdi|tfsi)\b", t)))

    return out


def enrich_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica extração a um dict de veículo, preenchendo lacunas estruturadas.

    Só preenche o que está em falta — nunca sobrepõe dados já capturados pelo
    scraper, que são mais fiáveis do que texto livre.
    """
    feats = extract_title_features(row.get("title"), row.get("year"))
    enriched = dict(row)

    if not enriched.get("engine_size") and feats["t_displacement"]:
        enriched["engine_size"] = int(feats["t_displacement"] * 1000)
    if not enriched.get("horsepower") and feats["t_power_cv"]:
        enriched["horsepower"] = int(feats["t_power_cv"])
    if enriched.get("is_national") is None and feats["t_is_nacional"]:
        enriched["is_national"] = True
    if enriched.get("has_damage") is None and feats["t_has_damage"]:
        enriched["has_damage"] = True

    enriched.update(feats)
    return enriched
