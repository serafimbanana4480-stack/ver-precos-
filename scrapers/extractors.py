"""
Biblioteca partilhada de extração para todos os scrapers (2026-08).

Motivação
---------
Cada scraper tinha a sua própria regex para preço, km, ano, potência e
cilindrada. O resultado era inconsistência entre fontes: o mesmo anúncio
podia ficar com ``km=120`` numa fonte e ``km=120000`` noutra, e campos
como CO2, cilindrada, nº de proprietários ou garantia simplesmente não
eram capturados em lado nenhum — apesar de o schema os prever e de o
motor fiscal (ISV/IUC) depender deles.

Este módulo é a **fonte única** de extração de campos a partir de texto
livre em português. É puro (sem I/O, sem rede), o que o torna
integralmente testável — ver ``tests/test_extractors.py``.

Todas as funções devolvem ``None`` quando não há evidência suficiente.
Nunca inventam valores: um campo em falta é preferível a um campo errado,
porque o motor de avaliação penaliza a confiança quando faltam dados mas
é enganado silenciosamente por dados errados.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

__all__ = [
    "fold",
    "parse_pt_number",
    "extract_km",
    "extract_year",
    "extract_registration_date",
    "extract_horsepower",
    "extract_engine_size",
    "extract_co2",
    "extract_fuel",
    "extract_transmission",
    "extract_doors",
    "extract_seats",
    "extract_color",
    "extract_seller_type",
    "extract_owners",
    "extract_warranty_months",
    "extract_battery_kwh",
    "extract_electric_range",
    "detect_damage",
    "detect_national",
    "detect_vat_deductible",
    "extract_plate",
    "extract_vin",
    "iter_jsonld",
    "extract_next_data",
    "from_jsonld_vehicle",
    "enrich_listing",
    "field_coverage",
]

CURRENT_YEAR = datetime.now().year

# ─────────────────────────────────────────────────────────────────────────────
# Normalização de texto
# ─────────────────────────────────────────────────────────────────────────────


def fold(text: Optional[str]) -> str:
    """Minúsculas sem acentos, espaços colapsados. Base de toda a deteção."""
    if not text:
        return ""
    out = unicodedata.normalize("NFKD", str(text))
    out = out.encode("ascii", "ignore").decode("ascii").lower()
    out = out.replace("\xa0", " ")
    return re.sub(r"\s+", " ", out).strip()


def parse_pt_number(raw: Any) -> Optional[float]:
    """Interpreta um número escrito à portuguesa (ou à inglesa).

    Regras de desambiguação:
      * ``1.234,56`` → 1234.56  (ponto=milhar, vírgula=decimal)
      * ``1,234.56`` → 1234.56  (formato inglês)
      * ``120.000``  → 120000   (3 dígitos após ponto ⇒ milhar)
      * ``1.9``      → 1.9      (1-2 dígitos após ponto ⇒ decimal)
      * ``120 000``  → 120000   (espaço é sempre separador de milhar)
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace("\xa0", " ")
    if not text:
        return None
    negative = text.lstrip().startswith("-")
    match = re.search(r"\d[\d\s.,]*", text)
    if not match:
        return None
    token = match.group(0).strip().rstrip(".,")
    token = token.replace(" ", "")
    if not token:
        return None

    if "." in token and "," in token:
        # O separador mais à direita é o decimal.
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        parts = token.split(",")
        # ``1,234`` com exatamente 3 dígitos finais é milhar, não decimal.
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            token = token.replace(",", "")
        else:
            token = token.replace(",", ".")
    elif "." in token:
        parts = token.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            token = token.replace(".", "")
    try:
        value = float(token)
    except ValueError:
        return None
    return -value if negative else value


# ─────────────────────────────────────────────────────────────────────────────
# Quilometragem
# ─────────────────────────────────────────────────────────────────────────────

# Um número com separadores de milhar ("210.450", "120 000") ou simples
# ("120000"). Deliberadamente NÃO permite que um espaço/ponto solto ligue
# dois números distintos: em "2015 · 210.450 km" o ano não pode ser
# absorvido para dentro da quilometragem.
_NUMBER_GROUPED = r"\d{1,3}(?:[.\s]\d{3})+|\d+(?:,\d+)?"
# Impede que a leitura comece a meio de outro número: em "2015 210.450 km"
# sem esta guarda o motor de regex casaria "015 210.450".
_NUM_START = r"(?<![\d.,])"

_KM_PATTERNS = (
    # "120.000 km", "120 000 kms", "120000 Km"
    re.compile(rf"{_NUM_START}({_NUMBER_GROUPED})\s*(?:kms?|quilometros?)\b"),
    # "km: 120.000", "quilometragem 120000"
    re.compile(
        rf"(?:kms?|quilometragem|quilometros?)\s*[:\-]?\s*{_NUM_START}({_NUMBER_GROUPED})"
    ),
)
# "120 mil km" — usado com frequência em anúncios de particulares.
_KM_THOUSANDS_RE = re.compile(r"(\d{1,4})\s*mil\s*(?:kms?|quilometros?)")

KM_MAX = 1_500_000


def extract_km(text: Optional[str]) -> Optional[int]:
    """Quilometragem em km. Rejeita valores impossíveis em vez de os truncar."""
    folded = fold(text)
    if not folded:
        return None

    thousand = _KM_THOUSANDS_RE.search(folded)
    if thousand:
        value = int(thousand.group(1)) * 1000
        return value if 0 < value <= KM_MAX else None

    for pattern in _KM_PATTERNS:
        for match in pattern.finditer(folded):
            number = parse_pt_number(match.group(1))
            if number is None:
                continue
            value = int(round(number))
            # "0 km" é legítimo (viatura nova) mas não informativo para nós.
            if value <= 0 or value > KM_MAX:
                continue
            # Um "12,5 mil" mal escrito vira 12.5 → assume milhares.
            if 0 < number < 1000 and "." not in match.group(1) and "," not in match.group(1):
                # "500 km" pode ser real (carro novo). Aceita tal e qual.
                return value
            return value
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Ano / data de registo
# ─────────────────────────────────────────────────────────────────────────────

_MONTHS_PT = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}
YEAR_MIN = 1950

_DATE_NUMERIC_RE = re.compile(r"\b(0?[1-9]|1[0-2])\s*[/\-.]\s*((?:19|20)\d{2})\b")
_DATE_MONTH_RE = re.compile(
    r"\b(" + "|".join(_MONTHS_PT) + r")[a-z]*\.?\s*[/\- ]\s*((?:19|20)\d{2})\b"
)
_YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def extract_registration_date(text: Optional[str]) -> Optional[Tuple[int, Optional[int]]]:
    """Devolve ``(ano, mes)`` da primeira matrícula, se detetável.

    O mês importa: o ISV de importados usa anos *completos* de uso, pelo que
    um carro de 12/2019 e outro de 01/2019 caem em escalões diferentes.
    """
    folded = fold(text)
    if not folded:
        return None
    numeric = _DATE_NUMERIC_RE.search(folded)
    if numeric:
        year = int(numeric.group(2))
        if YEAR_MIN <= year <= CURRENT_YEAR + 1:
            return year, int(numeric.group(1))
    named = _DATE_MONTH_RE.search(folded)
    if named:
        year = int(named.group(2))
        if YEAR_MIN <= year <= CURRENT_YEAR + 1:
            return year, _MONTHS_PT[named.group(1)[:3]]
    year = extract_year(folded)
    return (year, None) if year else None


def extract_year(text: Optional[str]) -> Optional[int]:
    """Ano do veículo. Ignora anos futuros e números que são cilindrada/preço."""
    folded = fold(text)
    if not folded:
        return None
    numeric = _DATE_NUMERIC_RE.search(folded)
    if numeric:
        year = int(numeric.group(2))
        if YEAR_MIN <= year <= CURRENT_YEAR + 1:
            return year
    candidates = [int(m) for m in _YEAR_RE.findall(folded)]
    candidates = [y for y in candidates if YEAR_MIN <= y <= CURRENT_YEAR + 1]
    if not candidates:
        return None
    # Vários anos no texto (ex.: "revisão 2024, matrícula 2015") → o mais
    # antigo é quase sempre o ano do veículo.
    return min(candidates)


# ─────────────────────────────────────────────────────────────────────────────
# Motor: potência, cilindrada, CO2
# ─────────────────────────────────────────────────────────────────────────────

_HP_CV_RE = re.compile(r"(\d{2,4})\s*(?:cv|cvs|hp|bhp|cavalos?)\b")
_HP_KW_RE = re.compile(r"(\d{2,3})\s*kw\b")
HP_MIN, HP_MAX = 15, 1600


def extract_horsepower(text: Optional[str]) -> Optional[int]:
    """Potência em CV. Converte kW quando só há kW (1 kW = 1,35962 CV)."""
    folded = fold(text)
    if not folded:
        return None
    match = _HP_CV_RE.search(folded)
    if match:
        value = int(match.group(1))
        if HP_MIN <= value <= HP_MAX:
            return value
    match = _HP_KW_RE.search(folded)
    if match:
        value = int(round(int(match.group(1)) * 1.35962))
        if HP_MIN <= value <= HP_MAX:
            return value
    return None


_CC_EXPLICIT_RE = re.compile(r"(\d{2,5})\s*(?:cm3|cm³|cc|centimetros cubicos)\b")

# "2.0 TDI", "1.6 HDi", "1,9 dCi" — designação comercial seguida de um sufixo
# de motorização conhecido. É a leitura de maior confiança.
_CC_LITRES_TAGGED_RE = re.compile(
    r"\b(\d)[.,](\d)\b\s*"
    r"(?:l\b|litros?\b|tdi|tsi|tfsi|hdi|dci|crdi|cdti|jtd|multijet|d4d|blue|"
    r"thp|vti|puretech|ecoboost|mpi|fsi|gti|gtd|cdi|bluehdi|bluetec|skyactiv|"
    r"turbo|16v|8v|v6|v8|i-vtec|vtec|dohc|hybrid|hibrido|e-tech)"
)

# "BMW 320d Touring 2.0 190cv" — o par X.Y aparece sozinho. Em títulos de
# automóvel é quase sempre a cilindrada, mas há que excluir os casos em que
# o número é outra grandeza (4.5 estrelas, 8.5 m, 2,5 %, 1.5 kg…).
_CC_LITRES_BARE_RE = re.compile(
    r"(?<![\w.,])([0-7])[.,](\d)(?![\d.,])"
    r"(?!\s*(?:%|km|kms|kg|m\b|mm|cm\b|s\b|seg|estrelas?|eur|€|milhoes|mil\b|"
    r"anos?|meses|/|x\b))"
)
CC_MIN, CC_MAX = 49, 8500
# Cilindradas comerciais plausíveis em litros. Fora deste intervalo, um par
# "X.Y" solto não é cilindrada.
_CC_LITRES_MIN, _CC_LITRES_MAX = 0.6, 7.5


def extract_engine_size(text: Optional[str], vehicle_type: str = "carros") -> Optional[int]:
    """Cilindrada em cm3. Essencial para o ISV (componente cilindrada)."""
    folded = fold(text)
    if not folded:
        return None
    for match in _CC_EXPLICIT_RE.finditer(folded):
        value = int(match.group(1))
        if CC_MIN <= value <= CC_MAX:
            return value

    for pattern in (_CC_LITRES_TAGGED_RE, _CC_LITRES_BARE_RE):
        for match in pattern.finditer(folded):
            litres = float(f"{match.group(1)}.{match.group(2)}")
            if not (_CC_LITRES_MIN <= litres <= _CC_LITRES_MAX):
                continue
            value = int(round(litres * 1000))
            if CC_MIN <= value <= CC_MAX:
                # Arredonda para a designação comercial (1.9 → 1900),
                # suficiente para o escalão de ISV; a cilindrada exata vem
                # da página de detalhe quando disponível.
                return value
    return None


_CO2_RE = re.compile(r"(\d{1,3})\s*(?:g\s*/\s*km|gr?/km|g km|gramas?/km)")
_CO2_LABEL_RE = re.compile(r"co\s?2\s*[:\-]?\s*(\d{1,3})")
CO2_MAX = 600


def extract_co2(text: Optional[str]) -> Optional[float]:
    """Emissões de CO2 em g/km. Sem isto o ISV de importados é um palpite."""
    folded = fold(text)
    if not folded:
        return None
    for pattern in (_CO2_RE, _CO2_LABEL_RE):
        match = pattern.search(folded)
        if match:
            value = float(match.group(1))
            if 0 < value <= CO2_MAX:
                return value
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Combustível / caixa
# ─────────────────────────────────────────────────────────────────────────────

# Ordem importa: "hibrido plug-in" tem de ser testado antes de "hibrido",
# e "gasolina" antes de "gas" para não classificar gasolina como GPL.
_FUEL_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("phev", ("plug-in", "plug in", "plugin", "phev", "hibrido plug", "hibrido recarregavel")),
    ("eletrico", ("eletrico", "electrico", "electric", "100% electr", " bev", "bateria eletrica")),
    ("hibrido", ("hibrido", "hybrid", "hev", "mhev", "micro-hibrido", "hibrido leve")),
    ("diesel", ("diesel", "gasoleo", "tdi", "hdi", "dci", "crdi", "cdti", "bluehdi", "jtd", "d4d")),
    ("gpl", ("gpl", "lpg", "glp", "auto-gas", "bi-fuel gpl")),
    ("gnc", ("gas natural", "gnc", "gnv", "cng", "metano")),
    ("gasolina", ("gasolina", "petrol", "gasoline", "tsi", "tfsi", "mpi", "vti", "puretech", "ecoboost")),
)

# Nomenclatura alemã: "320d"/"520d"/"30d" é gasóleo, "320i"/"118i" é gasolina.
# Metade do parque BMW/Mercedes anunciado em Portugal só indica o combustível
# desta forma, pelo que sem esta regra o campo fica vazio nesses anúncios.
_FUEL_SUFFIX_RULES: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("diesel", re.compile(r"\b(?:[1-8]\d{2}|[1-4]\d)\s?d\b")),
    ("gasolina", re.compile(r"\b(?:[1-8]\d{2}|[1-4]\d)\s?i\b")),
)


def extract_fuel(text: Optional[str]) -> Optional[str]:
    """Combustível canónico: gasolina|diesel|eletrico|hibrido|phev|gpl|gnc."""
    folded = fold(text)
    if not folded:
        return None
    for canonical, tokens in _FUEL_RULES:
        if any(token in folded for token in tokens):
            return canonical
    for canonical, pattern in _FUEL_SUFFIX_RULES:
        if pattern.search(folded):
            return canonical
    return None


_TRANSMISSION_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("automatico", (
        "automatic", "automatico", "auto.", "caixa auto", "dsg", "s-tronic",
        "stronic", "tiptronic", "steptronic", "cvt", "edc", "eat6", "eat8",
        "powershift", "dct", "pdk", "g-tronic", "9g-tronic", "multitronic",
        "sequencial",
    )),
    ("semi-automatico", ("semi-automatic", "semi automatico", "semiautomatico", "robotizada")),
    ("manual", ("manual", "caixa manual", "5 velocidades", "6 velocidades")),
)


def extract_transmission(text: Optional[str]) -> Optional[str]:
    """Caixa canónica: manual|automatico|semi-automatico."""
    folded = fold(text)
    if not folded:
        return None
    for canonical, tokens in _TRANSMISSION_RULES:
        if any(token in folded for token in tokens):
            return canonical
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Carroçaria / conforto
# ─────────────────────────────────────────────────────────────────────────────

_DOORS_RE = re.compile(r"\b([2-5])\s*(?:portas?|p\b|-portas)")
_SEATS_RE = re.compile(r"\b([2-9])\s*(?:lugares?|assentos?|passageiros?)")


def extract_doors(text: Optional[str]) -> Optional[int]:
    match = _DOORS_RE.search(fold(text))
    return int(match.group(1)) if match else None


def extract_seats(text: Optional[str]) -> Optional[int]:
    match = _SEATS_RE.search(fold(text))
    return int(match.group(1)) if match else None


_COLORS = {
    "preto": "preto", "black": "preto", "negro": "preto",
    "branco": "branco", "white": "branco",
    "cinzento": "cinzento", "cinza": "cinzento", "grey": "cinzento", "gray": "cinzento",
    "prateado": "prateado", "prata": "prateado", "silver": "prateado",
    "azul": "azul", "blue": "azul",
    "vermelho": "vermelho", "red": "vermelho", "encarnado": "vermelho",
    "verde": "verde", "green": "verde",
    "amarelo": "amarelo", "yellow": "amarelo",
    "castanho": "castanho", "brown": "castanho", "bege": "bege", "beige": "bege",
    "laranja": "laranja", "orange": "laranja",
    "dourado": "dourado", "gold": "dourado",
    "bordeaux": "bordeaux", "violeta": "violeta", "roxo": "violeta",
}


def extract_color(text: Optional[str]) -> Optional[str]:
    folded = fold(text)
    if not folded:
        return None
    # Preferir a cor anunciada explicitamente ("cor: azul").
    labelled = re.search(r"\bcor\s*[:\-]\s*([a-z]+)", folded)
    if labelled and labelled.group(1) in _COLORS:
        return _COLORS[labelled.group(1)]
    for token, canonical in _COLORS.items():
        if re.search(rf"\b{re.escape(token)}\b", folded):
            return canonical
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Vendedor, histórico, risco
# ─────────────────────────────────────────────────────────────────────────────

_DEALER_TOKENS = (
    "stand", "concessionario", "concessionaria", "comercio de automoveis",
    "automoveis lda", "auto lda", "unipessoal", ", lda", " lda.", "s.a.",
    "profissional", "dealer", "garagem", "motors", "car center", "automotive",
    "rent a car", "retoma", "viatura de empresa", "multimarcas",
)
_PRIVATE_TOKENS = (
    "particular", "vendedor particular", "private seller", "unico dono particular",
)


def extract_seller_type(*texts: Optional[str]) -> Optional[str]:
    """``profissional`` | ``particular`` | ``None``.

    A margem de negociação difere fortemente: um stand já embute 15-25% de
    margem no preço pedido, um particular 5-15%. Classificar mal o vendedor
    desloca a avaliação do negócio na mesma proporção.
    """
    folded = fold(" ".join(t for t in texts if t))
    if not folded:
        return None
    if any(token in folded for token in _PRIVATE_TOKENS):
        return "particular"
    if any(token in folded for token in _DEALER_TOKENS):
        return "profissional"
    return None


_OWNERS_RE = re.compile(
    r"\b(\d|um|dois|tres|quatro)\s*(?:unico\s+)?(?:proprietarios?|donos?)\b"
)
_SINGLE_OWNER_TOKENS = ("unico dono", "unico proprietario", "1o dono", "primeiro dono")
_WORD_NUMBERS = {"um": 1, "dois": 2, "tres": 3, "quatro": 4}


def extract_owners(text: Optional[str]) -> Optional[int]:
    folded = fold(text)
    if not folded:
        return None
    if any(token in folded for token in _SINGLE_OWNER_TOKENS):
        return 1
    match = _OWNERS_RE.search(folded)
    if match:
        token = match.group(1)
        value = _WORD_NUMBERS.get(token, None)
        if value is None and token.isdigit():
            value = int(token)
        if value and 1 <= value <= 9:
            return value
    return None


_WARRANTY_MONTHS_RE = re.compile(r"garantia\s*(?:de\s*)?(\d{1,2})\s*(?:meses|m\b)")
_WARRANTY_YEARS_RE = re.compile(r"garantia\s*(?:de\s*)?(\d)\s*anos?")


def extract_warranty_months(text: Optional[str]) -> Optional[int]:
    folded = fold(text)
    if not folded:
        return None
    match = _WARRANTY_MONTHS_RE.search(folded)
    if match:
        value = int(match.group(1))
        return value if 0 < value <= 60 else None
    match = _WARRANTY_YEARS_RE.search(folded)
    if match:
        return int(match.group(1)) * 12
    return None


_BATTERY_RE = re.compile(r"(\d{1,3}(?:[.,]\d)?)\s*kwh")
_RANGE_RE = re.compile(r"(?:autonomia|range)\D{0,12}(\d{2,3})\s*km")


def extract_battery_kwh(text: Optional[str]) -> Optional[float]:
    match = _BATTERY_RE.search(fold(text))
    if not match:
        return None
    value = parse_pt_number(match.group(1))
    return value if value and 1 <= value <= 250 else None


def extract_electric_range(text: Optional[str]) -> Optional[int]:
    match = _RANGE_RE.search(fold(text))
    if not match:
        return None
    value = int(match.group(1))
    return value if 10 <= value <= 900 else None


_DAMAGE_TOKENS = (
    "salvado", "acidentado", "batido", "sinistrado", "para pecas", "para peca",
    "para abate", "sucata", "avariado", "motor fundido", "nao pega",
    "nao trabalha", "para restauro", "incendiado", "capotado", "afundado",
    "sem motor", "caixa avariada", "danos", "amolgad", "riscado", "chapa",
)
_DAMAGE_STRONG = (
    "salvado", "acidentado", "sinistrado", "para pecas", "para abate",
    "sucata", "motor fundido", "incendiado", "capotado",
)


def detect_damage(text: Optional[str]) -> Dict[str, Any]:
    """Deteta indícios de dano e distingue gravidade.

    Um "riscado" custa €300 de reparação; um "salvado" muda a natureza do
    negócio. Tratá-los como o mesmo sinal binário destrói o cálculo de
    recondicionamento.
    """
    folded = fold(text)
    if not folded:
        return {"has_damage": False, "severity": None, "tokens": []}
    found = [token for token in _DAMAGE_TOKENS if token in folded]
    if not found:
        return {"has_damage": False, "severity": None, "tokens": []}
    severe = any(token in _DAMAGE_STRONG for token in found)
    return {
        "has_damage": True,
        "severity": "total" if severe else "cosmetico",
        "tokens": found,
    }


_IMPORT_TOKENS = (
    "importado", "importada", "nacionalizado", "nacionalizada", "legalizado",
    "por legalizar", "matricula alema", "matricula francesa", "matricula belga",
    "vindo da alemanha", "importacao", "isv pago", "isv por pagar",
)
_NATIONAL_TOKENS = ("nacional", "sempre nacional", "matricula nacional", "1a mao nacional")


def detect_national(text: Optional[str]) -> Optional[bool]:
    """``True`` nacional, ``False`` importado, ``None`` desconhecido.

    Determina se há ISV a pagar — a maior componente de custo num importado
    e a diferença entre um negócio e um prejuízo.
    """
    folded = fold(text)
    if not folded:
        return None
    has_import = any(token in folded for token in _IMPORT_TOKENS)
    has_national = any(token in folded for token in _NATIONAL_TOKENS)
    if has_import and not has_national:
        return False
    if has_national and not has_import:
        return True
    return None


_VAT_TOKENS = ("iva dedutivel", "iva discriminado", "com iva", "iva incluido a 23")


def detect_vat_deductible(text: Optional[str]) -> Optional[bool]:
    """IVA dedutível muda o preço efetivo em 23% para um comprador com NIF."""
    folded = fold(text)
    if not folded:
        return None
    return True if any(token in folded for token in _VAT_TOKENS) else None


# Matrícula PT: AA-00-00 / 00-AA-00 / 00-00-AA / AA-00-AA (novo formato)
_PLATE_RE = re.compile(
    r"\b([A-Z]{2}-\d{2}-\d{2}|\d{2}-[A-Z]{2}-\d{2}|\d{2}-\d{2}-[A-Z]{2}|"
    r"[A-Z]{2}-\d{2}-[A-Z]{2})\b"
)
_VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")


def extract_plate(text: Optional[str]) -> Optional[str]:
    match = _PLATE_RE.search((text or "").upper())
    return match.group(1) if match else None


def extract_vin(text: Optional[str]) -> Optional[str]:
    """VIN de 17 caracteres (sem I, O, Q). Chave forte de deduplicação."""
    candidate = _VIN_RE.search((text or "").upper())
    if not candidate:
        return None
    vin = candidate.group(1)
    # Um VIN real tem letras e dígitos; 17 dígitos seguidos é outra coisa.
    if vin.isdigit() or vin.isalpha():
        return None
    return vin


# ─────────────────────────────────────────────────────────────────────────────
# Extração estruturada: JSON-LD e __NEXT_DATA__
# ─────────────────────────────────────────────────────────────────────────────

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def iter_jsonld(html: str) -> Iterable[Dict[str, Any]]:
    """Percorre todos os blocos JSON-LD, incluindo ``@graph`` e listas.

    Dados estruturados são sempre preferíveis a regex sobre HTML: não
    quebram quando o site muda classes CSS, o que é a causa nº1 de
    scrapers que passam a devolver zero anúncios silenciosamente.
    """
    for block in _JSONLD_RE.findall(html or ""):
        text = block.strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            continue
        stack: List[Any] = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                if "@graph" in node:
                    stack.append(node["@graph"])
                yield node


def extract_next_data(html: str) -> Optional[Dict[str, Any]]:
    """Payload do Next.js (``__NEXT_DATA__``) — usado por OLX e Standvirtual."""
    match = _NEXT_DATA_RE.search(html or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (ValueError, TypeError):
        return None


_JSONLD_VEHICLE_TYPES = {"car", "vehicle", "motorcycle", "product", "offer", "motorizedvehicle"}


def from_jsonld_vehicle(node: Dict[str, Any]) -> Dict[str, Any]:
    """Converte um nó JSON-LD schema.org/Vehicle no nosso dicionário."""
    node_type = node.get("@type", "")
    types = {fold(t) for t in (node_type if isinstance(node_type, list) else [node_type])}
    if not types & _JSONLD_VEHICLE_TYPES:
        return {}

    out: Dict[str, Any] = {}
    if node.get("name"):
        out["title"] = str(node["name"])[:500]
    if node.get("url"):
        out["url"] = str(node["url"])
    if node.get("brand"):
        brand = node["brand"]
        out["brand"] = str(brand.get("name") if isinstance(brand, dict) else brand)
    if node.get("model"):
        model = node["model"]
        out["model"] = str(model.get("name") if isinstance(model, dict) else model)
    if node.get("description"):
        out["description"] = str(node["description"])[:2000]

    offer = node.get("offers")
    if isinstance(offer, list):
        offer = offer[0] if offer else None
    if isinstance(offer, dict):
        if offer.get("price") is not None:
            out["price_raw"] = str(offer["price"])
            out["price"] = parse_pt_number(offer["price"])
        if offer.get("priceCurrency"):
            out["currency"] = str(offer["priceCurrency"]).upper()

    for key, field in (
        ("mileageFromOdometer", "km"),
        ("vehicleEngine", None),
        ("numberOfDoors", "doors"),
        ("seatingCapacity", "seats"),
        ("color", "color"),
        ("vehicleIdentificationNumber", "vin"),
    ):
        value = node.get(key)
        if value is None or field is None:
            continue
        if isinstance(value, dict):
            value = value.get("value")
        parsed = parse_pt_number(value) if field in ("km", "doors", "seats") else value
        if parsed is not None:
            out[field] = int(parsed) if field in ("km", "doors", "seats") else str(parsed)

    engine = node.get("vehicleEngine")
    if isinstance(engine, dict):
        displacement = engine.get("engineDisplacement")
        if isinstance(displacement, dict):
            displacement = displacement.get("value")
        cc = parse_pt_number(displacement)
        if cc:
            # schema.org aceita litros ou cm3; normalizar para cm3.
            out["engine_size"] = int(cc * 1000) if cc < 20 else int(cc)
        power = engine.get("enginePower")
        if isinstance(power, dict):
            unit = fold(power.get("unitCode") or power.get("unitText") or "")
            raw_power = parse_pt_number(power.get("value"))
            if raw_power:
                out["horsepower"] = int(round(raw_power * 1.35962)) if "kw" in unit else int(raw_power)
        fuel = engine.get("fuelType")
        if fuel:
            out["fuel_type"] = extract_fuel(str(fuel)) or None

    for key, field in (
        ("modelDate", "year"),
        ("productionDate", "year"),
        ("vehicleModelDate", "year"),
        ("releaseDate", "year"),
    ):
        if out.get("year"):
            break
        year = extract_year(str(node.get(key) or ""))
        if year:
            out[field] = year

    transmission = node.get("vehicleTransmission")
    if transmission:
        out["transmission"] = extract_transmission(str(transmission))
    fuel = node.get("fuelType")
    if fuel and not out.get("fuel_type"):
        out["fuel_type"] = extract_fuel(str(fuel))

    images = node.get("image")
    if images:
        out["images"] = [str(i) for i in (images if isinstance(images, list) else [images])][:20]

    return {k: v for k, v in out.items() if v not in (None, "", [])}


# ─────────────────────────────────────────────────────────────────────────────
# Enriquecimento genérico
# ─────────────────────────────────────────────────────────────────────────────

# Só estes campos são preenchidos por inferência textual. Campos como o
# preço nunca entram aqui: um preço tem de vir de um elemento identificado,
# nunca de uma regex sobre o corpo do anúncio (risco de apanhar mensalidades).
_TEXT_EXTRACTORS = {
    "year": lambda text, _: extract_year(text),
    "km": lambda text, _: extract_km(text),
    "horsepower": lambda text, _: extract_horsepower(text),
    "engine_size": lambda text, vtype: extract_engine_size(text, vtype),
    "co2_gkm": lambda text, _: extract_co2(text),
    "fuel_type": lambda text, _: extract_fuel(text),
    "transmission": lambda text, _: extract_transmission(text),
    "doors": lambda text, _: extract_doors(text),
    "seats": lambda text, _: extract_seats(text),
    "color": lambda text, _: extract_color(text),
    "num_owners": lambda text, _: extract_owners(text),
    "warranty_months": lambda text, _: extract_warranty_months(text),
    "battery_kwh": lambda text, _: extract_battery_kwh(text),
    "electric_range_km": lambda text, _: extract_electric_range(text),
    "vin": lambda text, _: extract_vin(text),
    "plate": lambda text, _: extract_plate(text),
}

#: Campos que o motor de avaliação e o motor fiscal precisam para produzir
#: uma estimativa com confiança alta. Usado por :func:`field_coverage`.
CRITICAL_FIELDS = (
    "brand", "model", "year", "km", "fuel_type", "transmission",
    "horsepower", "engine_size", "price",
)
FISCAL_FIELDS = ("engine_size", "co2_gkm", "fuel_type", "year", "is_national")


def enrich_listing(
    listing: Dict[str, Any],
    *,
    extra_text: str = "",
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Preenche campos em falta a partir do texto do próprio anúncio.

    Não sobrepõe (por omissão) o que o scraper já extraiu de um campo
    estruturado da página: um valor lido de um ``<dt>Combustível</dt>`` é
    sempre mais fiável do que o mesmo valor inferido do título.

    Args:
        listing: dicionário do anúncio, modificado in-place e devolvido.
        extra_text: texto adicional (corpo do anúncio, tabela de specs).
        overwrite: se ``True``, sobrepõe valores existentes.
    """
    text = " ".join(
        str(listing.get(key) or "")
        for key in ("title", "description", "model", "version", "subtitle")
    )
    if extra_text:
        text = f"{text} {extra_text}"
    if not text.strip():
        return listing

    vtype = str(listing.get("vehicle_type") or "carros")
    for field, extractor in _TEXT_EXTRACTORS.items():
        if not overwrite and listing.get(field) not in (None, "", 0):
            continue
        try:
            value = extractor(text, vtype)
        except Exception:  # noqa: BLE001 — extração nunca pode partir o scrape
            value = None
        if value is not None:
            listing[field] = value

    damage = detect_damage(text)
    if damage["has_damage"] and (overwrite or listing.get("has_damage") is None):
        listing["has_damage"] = True
        listing["damage_severity"] = damage["severity"]
        listing["damage_tokens"] = damage["tokens"]

    if overwrite or listing.get("is_national") is None:
        national = detect_national(text)
        if national is not None:
            listing["is_national"] = national

    if overwrite or listing.get("vat_deductible") is None:
        vat = detect_vat_deductible(text)
        if vat is not None:
            listing["vat_deductible"] = vat

    if overwrite or not listing.get("seller_type"):
        seller = extract_seller_type(listing.get("seller_name"), text)
        if seller:
            listing["seller_type"] = seller

    if overwrite or not listing.get("registration_month"):
        registration = extract_registration_date(text)
        if registration:
            year, month = registration
            listing.setdefault("year", year)
            if month:
                listing["registration_month"] = month

    return listing


def field_coverage(listings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Percentagem de anúncios com cada campo preenchido.

    Serve de teste de regressão operacional: se a cobertura de ``km`` numa
    fonte cair de 95% para 4%, o site mudou o HTML e o scraper está partido
    — mesmo que continue a devolver anúncios e a não lançar exceções.
    """
    total = len(listings)
    if not total:
        return {"total": 0, "coverage": {}, "critical_ok": False}
    fields = set(CRITICAL_FIELDS) | set(FISCAL_FIELDS) | {
        "url", "title", "location", "images", "seller_type", "num_owners",
        "doors", "seats", "color", "warranty_months", "vin",
    }
    coverage = {
        field: round(
            sum(1 for row in listings if row.get(field) not in (None, "", [], 0)) * 100 / total, 1
        )
        for field in sorted(fields)
    }
    critical = {f: coverage.get(f, 0.0) for f in CRITICAL_FIELDS}
    return {
        "total": total,
        "coverage": coverage,
        "critical": critical,
        # Uma fonte é considerada saudável se os campos que determinam a
        # avaliação estiverem presentes na esmagadora maioria dos anúncios.
        "critical_ok": all(v >= 60.0 for v in critical.values()),
    }
