"""
Extração de especificações (ano, km, combustível, transmissão, cv) a partir de
texto livre — títulos e descrições de anúncios (Fase 15).

Motivação: fontes como AUTOLINE guardam tudo no título
("BMW 525i 1 124 € 8 400 DKK Carro 1985 136 018 km Potência 191 cv")
sem preencher os campos estruturados. Este módulo recupera esses dados com
regras conservadoras: na dúvida NÃO preenche (um campo vazio é melhor que um
valor errado — a avaliação já trata campos em falta com confiança reduzida).

API: ``extract_specs(text)`` → dict só com os campos detetados.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional

_CURRENT_YEAR_MAX = 2027  # aceita anúncios do próximo ano-modelo


def _norm(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


# ── Ano ───────────────────────────────────────────────────────────────────────
_YEAR_EXPLICIT = re.compile(r"(?:ano|año|carro|mota)\s+((?:19|20)\d{2})", re.IGNORECASE)
_YEAR_AFTER_BODY = re.compile(
    r"(?:hatchback|suv|berlina|carrinha|monovolume|compacto|utilitario|conversivel|"
    r"coupe|cabrio|roadster|familiar|citadino|crossover|break|furgao|van|estate|"
    r"pick[\s-]?up|todo[\s-]?o[\s-]?terreno|sedan|station|executive|sport)\s+((?:19|20)\d{2})",
    re.IGNORECASE,
)
_YEAR_BEFORE_EURO = re.compile(r"((?:19|20)\d{2})\s+euro\s?[456]", re.IGNORECASE)
_YEAR_GENERIC = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\b")


def extract_year(text: str) -> Optional[int]:
    if not text:
        return None
    for rx in (_YEAR_EXPLICIT, _YEAR_AFTER_BODY, _YEAR_BEFORE_EURO):
        m = rx.search(text)
        if m:
            y = int(m.group(1))
            if 1950 <= y <= _CURRENT_YEAR_MAX:
                return y
    # Genérico: só se o ano NÃO estiver colado a €/km/cv nem for parte do modelo
    # ("Peugeot 2008" — ano imediatamente precedido por palavra com letras).
    for m in _YEAR_GENERIC.finditer(text):
        y = int(m.group(1))
        if not (1950 <= y <= _CURRENT_YEAR_MAX):
            continue
        after = text[m.end():m.end() + 12].strip().lower()
        before = text[max(0, m.start() - 12):m.start()]
        if after.startswith(("€", "eur", "km", "cv", "hp")):
            continue
        word_before = re.search(r"([a-zA-ZÀ-ú]{2,})\s*$", before)
        if word_before and word_before.group(1).lower() not in (
                "de", "em", "ano", "año", "carro", "mota"):
            # "Peugeot 2008" / "BMW 2020"? — se a palavra anterior é uma marca/
            # modelo (tem letras), é provável nº de modelo, não ano.
            continue
        return y
    return None


# ── Quilómetros ───────────────────────────────────────────────────────────────
_KM_NUM = re.compile(r"(?<!\d)(\d{1,3}(?:[ .\xa0]\d{3})+|\d{2,6})\s*km\b", re.IGNORECASE)
_KM_MIL = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*mil\s*km\b", re.IGNORECASE)


def extract_km(text: str) -> Optional[int]:
    if not text:
        return None
    m = _KM_MIL.search(text)
    if m:
        try:
            km = int(float(m.group(1).replace(",", ".")) * 1000)
            if 0 < km <= 1_000_000:
                return km
        except ValueError:
            pass
    m = _KM_NUM.search(text)
    if m:
        raw = re.sub(r"[ .\xa0]", "", m.group(1))
        try:
            km = int(raw)
            if 100 < km <= 1_000_000:
                return km
        except ValueError:
            pass
    return None


# ── Potência ─────────────────────────────────────────────────────────────────
_CV_RE = re.compile(r"\b(\d{2,3})\s?(?:cv|hp|ps|cavalos)\b", re.IGNORECASE)


def extract_horsepower(text: str) -> Optional[int]:
    if not text:
        return None
    m = _CV_RE.search(text)
    if m:
        cv = int(m.group(1))
        if 20 <= cv <= 1200:
            return cv
    return None


# ── Combustível (ordem importa: elétrico → híbrido → GPL → gás → diesel → gasolina)
_FUEL_RULES = [
    ("eletrico", [
        "electric", "eletric", "eletrico", "electrico", "e-tron", "etron",
        " bev", "ev60",
        "eqa", "eqb", "eqc", "eqe", "mach-e", "e-208", "e-2008", "e208", "e2008",
        "e-tech electric", " zoe", " leaf", "id.3", "id.4", "id3", "id4",
        "kona electric", "niro ev", "ev6", "ioniq 5", "ioniq5", "model 3",
        "model s", "model x", "model y", "spring electric", "dacia spring",
        "taycan", "e-golf", "egolf", "bmw ix", " ix3", " i3 ", " i4 ", " i5 ",
        " ix ", "iX ", "fortwo electric", "eq fortwo", "citigo-e", "mii electric",
        "e-up", "fiat 500e", "500 electric", "megane e-tech electric",
    ]),
    ("hibrido", [
        "hybrid", "hibrido", "phev", "plug-in", "plug in", "plugin", " hev",
        "mhev", "mild hybrid", " e-tech", " etech", " t4 hybrid", " t8 ", "330e",
        "530e", "225xe", " c 300 e", " c350e", " e 300 e", "gle 350", " 45 tfsi e",
        " 55 tfsi e", "tfsi e", " e-hybrid", "yhbrid",
    ]),
    ("gpl", ["gpl", "glp", "bi-fuel", "bifuel", "autogas", "bicombustivel"]),
    ("gas natural", ["cng", "gnc", "gnv", " tgi", "gas natural", "metano"]),
    ("diesel", [
        "diesel", "diésel", " tdi", "cdti", " dci", "hdi", "bluehdi", "blue hdi",
        " crdi", "crd ", " d4d", "d-4d", "multijet", "multi jet", "jtd", "jtdm",
        "ecoblue", " td ", " td5", "sd4", " td4", " d2 ", " d3 ", " d4 ", " d5 ",
        " tdd", "cdi", " 1.5 d ", " 1.6 d ", " 1.9 d ", " 2.0 d ", " 2.2 d ",
    ]),
    ("gasolina", [
        "gasolina", " tfsi", " tsi", " gti", "tsi ", "puretech", "pure tech",
        " vti", " tce", " mpi", "ecoboost", "boost", " v6 ", " v8 ", " t3 ",
        " t4 ", " t5 ", " t6 ", " b4 ", " b5 ", " b6 ",
    ]),
]


def extract_fuel(text: str) -> Optional[str]:
    if not text:
        return None
    t = _norm(text)
    t_pad = f" {t} "  # facilita tokens com espaços delimitadores
    for fuel, tokens in _FUEL_RULES:
        for tok in tokens:
            if tok in t_pad:
                return fuel
    # Badges diesel BMW/Mercedes por regex: "320d", "220 d" — com fronteira
    # à direita para não apanhar "400 DKK" / moedas. Só se não houve match acima.
    t_norm = _norm(text)
    if re.search(r"\b\d{2,3}\s?d\b", t_norm) or re.search(r"\bxdrive\s?\d{2,3}d\b", t_norm):
        return "diesel"
    return None


# ── Transmissão ───────────────────────────────────────────────────────────────
_AUTO_TOKENS = [
    "automatic", "automatica", "automático", "automatico", "dct", "dsg", "pdk",
    "cvt", "e-cvt", "ecvt", "s-tronic", "stronic", "tiptronic", "steptronic",
    "powershift", "easyn", "eat6", "eat8", "etg", "auto9", " aut.", " aut ",
    "x-tronic", "xtronic", "multitronic",
]
_MANUAL_TOKENS = ["manual", " man.", " man ", "caixa manual", "6mt", "5mt"]


def extract_transmission(text: str) -> Optional[str]:
    """Devolve o valor do enum Transmission: 'manual' | 'automatico'."""
    if not text:
        return None
    t = _norm(text)
    t_pad = f" {t} "
    for tok in _AUTO_TOKENS:
        if _norm(tok) in t_pad:
            return "automatico"
    for tok in _MANUAL_TOKENS:
        if _norm(tok) in t_pad:
            return "manual"
    return None


# ── API agregada ─────────────────────────────────────────────────────────────
def extract_specs(text: str) -> Dict[str, Any]:
    """Extrai todas as specs detetáveis de um texto. Só inclui campos detetados."""
    out: Dict[str, Any] = {}
    if not text:
        return out
    y = extract_year(text)
    if y:
        out["year"] = y
    km = extract_km(text)
    if km:
        out["km"] = km
    f = extract_fuel(text)
    if f:
        out["fuel_type"] = f
    tr = extract_transmission(text)
    if tr:
        out["transmission"] = tr
    cv = extract_horsepower(text)
    if cv:
        out["horsepower"] = cv
    return out
