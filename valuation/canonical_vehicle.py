"""Representação canónica de um veículo para efeitos de comparação.

Problema que este módulo resolve
--------------------------------
Antes desta correção, os comparáveis eram escolhidos por
``(marca, modelo, ano)`` a partir de campos livres. Como ``version`` e
``trim_level`` estavam preenchidos em 0 de 5755 anúncios, um **Mercedes A 35
AMG** e um **Mercedes A 180 d** eram o mesmo "Classe A", e um **BMW M3** era
uma "Série 3". A mediana resultante não representa nenhum dos dois: inflaciona
o carro normal e subavalia o desportivo.

O que este módulo faz
---------------------
Deriva, a partir do título/modelo/versão (que é onde a informação
verdadeiramente está), uma :class:`CanonicalVehicle` com:

* marca canónica, família de modelo, badge de motorização;
* **classe de performance** (``base`` … ``supercar``) via taxonomia explícita;
* combustível canónico distinguindo ``hibrido``, ``mild_hybrid`` e ``phev``;
* carroçaria, tração, transmissão, potência, cilindrada;
* uma ``trim_confidence`` — quando não conseguimos identificar a versão com
  confiança, quem consome deve **baixar a confiança da estimativa**, não
  inventar equivalência.

Regra estrutural: dois veículos só são comparáveis se pertencerem à mesma
:meth:`CanonicalVehicle.comparability_key`. Um Panamera Turbo nunca entra na
mediana de um Panamera base.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Tuple

__all__ = [
    "PerformanceClass",
    "FuelClass",
    "CanonicalVehicle",
    "canonicalize",
    "normalize_fuel",
    "detect_performance_class",
    "PERFORMANCE_RANK",
]


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _norm(text: Any) -> str:
    """Minúsculas, sem acentos, espaços colapsados. ``None``/``nan`` → ``""``."""
    if text is None:
        return ""
    raw = str(text).strip()
    if not raw or raw.lower() in ("nan", "none", "null", "unknown", "n/a", "-"):
        return ""
    return re.sub(r"\s+", " ", _strip_accents(raw).lower())


# ---------------------------------------------------------------------------
# Taxonomia de performance / luxo
# ---------------------------------------------------------------------------


class PerformanceClass:
    """Escalões de posicionamento. A ordem é a que move o preço."""

    BASE = "base"
    SPORT_TRIM = "sport_trim"      # pacote estético: AMG Line, M Sport, S line
    PERFORMANCE = "performance"    # motor genuinamente mais potente: A 35, S3, GTI
    HIGH_PERFORMANCE = "high_performance"  # M3, RS6, A 45, GTS, Quadrifoglio
    SUPERCAR = "supercar"          # Turbo S, GT3, GT2, SVR, AMG GT R


PERFORMANCE_RANK: Dict[str, int] = {
    PerformanceClass.BASE: 0,
    PerformanceClass.SPORT_TRIM: 1,
    PerformanceClass.PERFORMANCE: 2,
    PerformanceClass.HIGH_PERFORMANCE: 3,
    PerformanceClass.SUPERCAR: 4,
}

# Ordem importa: o primeiro padrão que casar decide. Padrões mais específicos
# (Turbo S antes de Turbo, A 45 antes de AMG Line) vêm primeiro.
#
# Cada entrada é (regex, classe). Usam-se fronteiras de palavra para nunca
# apanhar "amg" dentro de outra palavra nem "rs" dentro de "cars".
_PERFORMANCE_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = tuple(
    (re.compile(pattern), klass)
    for pattern, klass in (
        # ── supercar / topo absoluto ──────────────────────────────────────
        (r"\bturbo\s*s\b", PerformanceClass.SUPERCAR),
        (r"\bgt2\b|\bgt3\b|\bgt4\b", PerformanceClass.SUPERCAR),
        (r"\bgt\s*r\b|\bamg\s*gt\b", PerformanceClass.SUPERCAR),
        (r"\bsvr\b|\bsvo\b", PerformanceClass.SUPERCAR),
        (r"\brs\s*[36]\s*performance\b", PerformanceClass.SUPERCAR),
        (r"\bblack\s*series\b", PerformanceClass.SUPERCAR),
        (r"\bcompetizione\b|\bpista\b|\bspeciale\b", PerformanceClass.SUPERCAR),
        # ── high performance ──────────────────────────────────────────────
        (r"\ba\s*45\b|\bc\s*63\b|\be\s*63\b|\bg\s*63\b|\bs\s*63\b|\bs\s*65\b",
         PerformanceClass.HIGH_PERFORMANCE),
        (r"\bgla\s*45\b|\bcla\s*45\b|\bglc\s*63\b|\bgle\s*63\b",
         PerformanceClass.HIGH_PERFORMANCE),
        # BMW M puro: "M3", "M4", "M5", "X5 M" — mas NÃO "M Sport"/"M Line".
        (r"\bm[2-8]\b(?!\s*sport)", PerformanceClass.HIGH_PERFORMANCE),
        (r"\bx[3-6]\s*m\b(?!\s*sport)", PerformanceClass.HIGH_PERFORMANCE),
        (r"\bm\s*competition\b", PerformanceClass.HIGH_PERFORMANCE),
        (r"\brs\s*\d\b|\brs\d\b", PerformanceClass.HIGH_PERFORMANCE),   # RS3, RS6
        (r"\bgts\b", PerformanceClass.HIGH_PERFORMANCE),
        (r"\bturbo\b(?!\s*diesel|\s*d\b)", PerformanceClass.HIGH_PERFORMANCE),
        (r"\bquadrifoglio\b|\bqv\b", PerformanceClass.HIGH_PERFORMANCE),
        (r"\btype\s*r\b|\bnismo\b", PerformanceClass.HIGH_PERFORMANCE),
        (r"\bpolestar\s*engineered\b", PerformanceClass.HIGH_PERFORMANCE),
        (r"\btrophy\b|\bmegane\s*rs\b", PerformanceClass.HIGH_PERFORMANCE),
        # ── performance (motor superior, mas não topo) ────────────────────
        (r"\ba\s*35\b|\bc\s*43\b|\be\s*53\b|\bcla\s*35\b|\bglc\s*43\b",
         PerformanceClass.PERFORMANCE),
        (r"\bm135\b|\bm140\b|\bm235\b|\bm240\b|\bm340\b|\bm440\b|\bm550\b",
         PerformanceClass.PERFORMANCE),
        (r"\bs[1-8]\b(?!\s*line)", PerformanceClass.PERFORMANCE),        # Audi S3/S4
        (r"\bgti\b|\bgtd\b|\bgte\b|\bgt\s*i\b", PerformanceClass.PERFORMANCE),
        (r"\bcupra\b", PerformanceClass.PERFORMANCE),
        (r"\bjohn\s*cooper\b|\bjcw\b", PerformanceClass.PERFORMANCE),
        (r"\bst\b(?!\s*line)", PerformanceClass.PERFORMANCE),            # Ford ST
        (r"\bveloce\b", PerformanceClass.PERFORMANCE),
        (r"\bn\s*performance\b|\bhyundai\s*n\b", PerformanceClass.PERFORMANCE),
        (r"\bgse\b|\bopc\b", PerformanceClass.PERFORMANCE),
        (r"\bcarrera\s*s\b|\bcarrera\s*4s\b", PerformanceClass.PERFORMANCE),
        # ── pacote estético (NÃO é mais motor) ────────────────────────────
        (r"\bamg\s*line\b|\bamg\s*pack\b|\bpack\s*amg\b|\bjantes\s*amg\b",
         PerformanceClass.SPORT_TRIM),
        (r"\bm\s*sport\b|\bmsport\b|\bm\s*line\b|\bpack\s*m\b|\bdesportivo\s*m\b",
         PerformanceClass.SPORT_TRIM),
        (r"\bs\s*line\b|\bsline\b", PerformanceClass.SPORT_TRIM),
        (r"\bst\s*line\b|\bn\s*line\b|\br\s*line\b|\bgt\s*line\b",
         PerformanceClass.SPORT_TRIM),
        (r"\bblack\s*edition\b|\bsport\s*edition\b", PerformanceClass.SPORT_TRIM),
        # "AMG" solto, depois de todas as variantes acima terem falhado:
        # é quase sempre o pacote, não o motor.
        (r"\bamg\b", PerformanceClass.SPORT_TRIM),
    )
)

#: Marcas cujo catálogo inteiro é desportivo — o modelo base já é premium e
#: não deve ser comparado com utilitários mesmo sem badge.
_PERFORMANCE_BRANDS = {
    "porsche", "ferrari", "lamborghini", "maserati", "aston martin",
    "mclaren", "bentley", "rolls-royce", "lotus", "alpine",
}


def detect_performance_class(*texts: Any) -> Tuple[str, float]:
    """Classifica o posicionamento a partir de texto livre.

    Returns:
        ``(classe, confiança)``. A confiança é 0.9 quando um padrão explícito
        casou, 0.55 quando só a marca sugere posicionamento, e 0.35 quando
        nada foi identificado (o consumidor deve penalizar a estimativa).

    >>> detect_performance_class("Mercedes-Benz A 35 AMG 4Matic")[0]
    'performance'
    >>> detect_performance_class("Mercedes-Benz A 180 d AMG Line")[0]
    'sport_trim'
    >>> detect_performance_class("Porsche Panamera Sport Turismo Turbo 4.0 V8")[0]
    'high_performance'
    >>> detect_performance_class("BMW Serie 3 320d Touring")[0]
    'base'
    """
    blob = " ".join(_norm(t) for t in texts if t)
    if not blob:
        return PerformanceClass.BASE, 0.35
    for pattern, klass in _PERFORMANCE_PATTERNS:
        if pattern.search(blob):
            return klass, 0.9
    for brand in _PERFORMANCE_BRANDS:
        if brand in blob:
            # Um Porsche "sem badge" é um Carrera/base — mas continua a ser
            # um desportivo. Confiança média: pode faltar-nos o badge.
            return PerformanceClass.PERFORMANCE, 0.55
    return PerformanceClass.BASE, 0.6


# ---------------------------------------------------------------------------
# Combustível
# ---------------------------------------------------------------------------


class FuelClass:
    """Combustíveis canónicos. Distingue os três tipos de híbrido."""

    GASOLINE = "gasolina"
    DIESEL = "diesel"
    ELECTRIC = "eletrico"
    HYBRID = "hibrido"          # HEV — híbrido convencional (autorrecarregável)
    MILD_HYBRID = "mild_hybrid"  # MHEV — 48 V, não anda em elétrico
    PHEV = "phev"               # plug-in
    LPG = "gpl"
    CNG = "gas natural"
    UNKNOWN = "unknown"


#: Ordem crítica: plug-in → mild → híbrido → elétrico. Testar "eletrico"
#: primeiro era o bug que classificava «Hibrido (Gasolina/Eletrico)» como
#: elétrico puro (18 Toyota afetados na base).
_FUEL_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = tuple(
    (re.compile(pattern), fuel)
    for pattern, fuel in (
        (r"plug[\s\-]?in|phev|\bp?hev\s*plug|recarregavel|e[\s\-]?hybrid|"
         r"\be\s*tense\b|\bplugin\b", FuelClass.PHEV),
        (r"\bmhev\b|mild[\s\-]?hybrid|micro[\s\-]?hibrido|\b48\s*v\b|"
         r"\behybrid\s*48\b|\bmild\b", FuelClass.MILD_HYBRID),
        (r"hibrid|hybrid|\bhev\b|e[\s\-]?tech(?!.*eletric)|\bself\s*charg",
         FuelClass.HYBRID),
        (r"eletric|electric|\bbev\b|\bev\b|100%\s*eletric|\bepower\b",
         FuelClass.ELECTRIC),
        (r"\bgpl\b|\blpg\b|autogas", FuelClass.LPG),
        (r"gas\s*natural|\bgnc\b|\bcng\b|\bgnv\b", FuelClass.CNG),
        (r"diesel|gasoleo|\btdi\b|\bhdi\b|\bcdi\b|\bdci\b|\bcrdi\b|\bbluetec\b|"
         r"\btdci\b|\bjtd\b|\bd4d\b", FuelClass.DIESEL),
        (r"gasolina|petrol|gasoline|\btsi\b|\btfsi\b|\bvti\b|\bmpi\b|\bgdi\b|"
         r"\bvvt\b|\bthp\b", FuelClass.GASOLINE),
    )
)

#: Sufixos de badge que revelam o combustível quando o campo está vazio:
#: "320d" → diesel, "118i" → gasolina, "C 220 d" → diesel.
_FUEL_BADGE_DIESEL = re.compile(r"\b\d{3}\s?d\b|\b\d{2,3}\s?cdi\b|\bd\s?4d\b")
_FUEL_BADGE_PETROL = re.compile(r"\b\d{3}\s?i\b")


def normalize_fuel(*texts: Any) -> str:
    """Combustível canónico a partir de um ou mais campos de texto.

    Os argumentos são avaliados por ordem: o primeiro que produzir um
    resultado conclusivo ganha. Passe o campo estruturado primeiro e o
    título depois.

    >>> normalize_fuel("Hibrido (Gasolina/Eletrico)")
    'hibrido'
    >>> normalize_fuel("Hibrido Plug-In (Gasolina/Eletrico)")
    'phev'
    >>> normalize_fuel(None, "Mercedes C 220 d AMG Line")
    'diesel'
    >>> normalize_fuel("nan")
    'unknown'
    """
    for text in texts:
        blob = _norm(text)
        if not blob:
            continue
        for pattern, fuel in _FUEL_PATTERNS:
            if pattern.search(blob):
                return fuel
    for text in texts:
        blob = _norm(text)
        if not blob:
            continue
        if _FUEL_BADGE_DIESEL.search(blob):
            return FuelClass.DIESEL
        if _FUEL_BADGE_PETROL.search(blob):
            return FuelClass.GASOLINE
    return FuelClass.UNKNOWN


#: Combustíveis que competem no mesmo mercado (podem ser comparados com
#: penalização). Fora destes grupos a comparação é proibida.
_FUEL_NEIGHBOURS: Dict[str, frozenset] = {
    FuelClass.GASOLINE: frozenset({FuelClass.GASOLINE, FuelClass.MILD_HYBRID}),
    FuelClass.DIESEL: frozenset({FuelClass.DIESEL, FuelClass.MILD_HYBRID}),
    FuelClass.MILD_HYBRID: frozenset(
        {FuelClass.MILD_HYBRID, FuelClass.GASOLINE, FuelClass.DIESEL, FuelClass.HYBRID}
    ),
    FuelClass.HYBRID: frozenset({FuelClass.HYBRID, FuelClass.MILD_HYBRID}),
    FuelClass.PHEV: frozenset({FuelClass.PHEV}),
    FuelClass.ELECTRIC: frozenset({FuelClass.ELECTRIC}),
    FuelClass.LPG: frozenset({FuelClass.LPG, FuelClass.GASOLINE}),
    FuelClass.CNG: frozenset({FuelClass.CNG, FuelClass.GASOLINE}),
}


def fuel_compatible(a: str, b: str) -> bool:
    """``True`` se dois combustíveis podem servir de comparável um do outro."""
    if a == b:
        return True
    if a == FuelClass.UNKNOWN or b == FuelClass.UNKNOWN:
        return False
    return b in _FUEL_NEIGHBOURS.get(a, frozenset())


# ---------------------------------------------------------------------------
# Transmissão / tração / carroçaria
# ---------------------------------------------------------------------------

_TRANSMISSION_PATTERNS = (
    (re.compile(r"\bmanual\b|\bcaixa\s*manual\b|\b[56]\s*velocidades\s*manual\b"), "manual"),
    (re.compile(r"\bautomat|\bauto\b|\bdsg\b|\bpdk\b|\bs\s*tronic\b|\btiptronic\b|"
                r"\bedc\b|\bdct\b|\bg\s*tronic\b|\b7g\b|\b8g\b|\b9g\b|\bxtronic\b|"
                r"\bcvt\b|\bsteptronic\b|\bmultitronic\b|\bpowershift\b|\beat[68]\b"), "automatico"),
)

_DRIVETRAIN_PATTERNS = (
    (re.compile(r"\b4matic\b|\bquattro\b|\bxdrive\b|\b4motion\b|\bawd\b|\b4x4\b|"
                r"\b4wd\b|\ballrad\b|\bsh\s*awd\b|\b4\s*matic\b"), "awd"),
    (re.compile(r"\brwd\b|\bpropulsao\b|\bsdrive\b"), "rwd"),
)

_BODY_PATTERNS = (
    (re.compile(r"\bshooting\s*brake\b|\bsport\s*turismo\b|\bsportbrake\b"), "shooting_brake"),
    (re.compile(r"\bstation\b|\bcarrinha\b|\btouring\b|\bavant\b|\bvariant\b|"
                r"\bestate\b|\bsw\b|\bbreak\b|\bsports?\s*tourer\b"), "station"),
    (re.compile(r"\bcoupe\b|\bcoupé\b"), "coupe"),
    (re.compile(r"\bcabrio|\bdescapotavel\b|\broadster\b|\bspyder\b|\bspider\b"), "cabrio"),
    (re.compile(r"\bsuv\b|\bcrossover\b"), "suv"),
    (re.compile(r"\bmonovolume\b|\bvan\b|\bmpv\b|\bcombi\b"), "van"),
    (re.compile(r"\blimousine\b|\bsedan\b|\bberlina\b|\bsaloon\b|\bsedã\b"), "sedan"),
    (re.compile(r"\bhatchback\b|\b5\s*portas\b|\b3\s*portas\b"), "hatchback"),
)

# ---------------------------------------------------------------------------
# Extração de versão / motorização a partir do título
# ---------------------------------------------------------------------------

_ENGINE_DISP = re.compile(r"\b(\d[\d.,]?\d)\s*(?:t|tsi|tdi|tfsi|tdci|dci|hdi|cdi|gdi|"
                          r"ecoboost|puretech|bluehdi|d|i|cdi|jtd|mjet|tsi)\b", re.I)
_CV_PATTERN = re.compile(r"(\d{2,3})\s*cv\b")
_TRIM_WORDS = re.compile(
    r"\b(urban|style|comfort|exclusive|premium|line|trendline|highline|advance|"
    r"attraction|edition|business|sport|gtc|gt\s*line|st\s*line|xcellence|"
    r"iekona|spirit|active|allure|gti|gtd|amg\s*line|m\s*line|s\s*line|"
    r"executive|luxury|signature|intens|zen|connect|life|techline|"
    r"performance|first\s*edition|launch\s*edition)\b", re.I)


def extract_version(*texts: Any) -> str:
    """Deriva uma versão/motorização legível do título ou campos.

    A base guarda ``version``/``trim_level`` vazios em ~100 % das linhas, mas o
    título traz tudo ("CLA 200d DCT Urban", "Tiguan 1.6 TDI 115cv Trendline").
    Extrair isto na canonização dá ao motor de comparáveis poder hedónico real:
    um "CLA 200d" vale menos que um "CLA 250", e "Urban" ≠ "AMG Line".
    """
    blob = " ".join(_norm(t) for t in texts if t)
    if not blob:
        return ""
    parts: list = []
    m = _ENGINE_DISP.search(blob)
    if m:
        parts.append(m.group(0))
    m = _CV_PATTERN.search(blob)
    if m:
        parts.append(f"{m.group(1)}cv")
    for tm in _TRIM_WORDS.finditer(blob):
        parts.append(tm.group(1).lower())
    # badge de performance explícito (180/200/250/35/45/63) isolado
    for bm in re.finditer(r"\b(\d{3}|[1-9]\d)\b", blob):
        tok = bm.group(1)
        if tok in ("180", "200", "220", "250", "300", "320", "35", "45", "63"):
            # evitar colisão com ano
            if abs(int(tok) - 2000) > 30:
                parts.append(tok)
    # dedupe mantendo ordem
    seen = set()
    out = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return " ".join(out)


def _first_match(patterns, blob: str, default: str) -> str:
    for pattern, label in patterns:
        if pattern.search(blob):
            return label
    return default


# ---------------------------------------------------------------------------
# Família de modelo
# ---------------------------------------------------------------------------

#: Badges de motorização → família. Sem isto, "320d", "318i" e "330e" são
#: três modelos distintos e nenhum tem comparáveis suficientes.
#:
#: BMW i-serie: cada modelo é uma família distinta (i4 ≠ i5 ≠ i7 ≠ iX1).
#: Colapsar tudo para "ix" era o bug que fazia um BMW i7 ser avaliado contra
#: i4/iX1 (estimativa 43k € para um carro de 120k+).
_MODEL_FAMILY_RULES: Tuple[Tuple[re.Pattern, str], ...] = tuple(
    (re.compile(pattern), family)
    for pattern, family in (
        (r"^(?:serie\s*)?([1-8])\s*(?:serie|series)?\b.*", r"serie \1"),
        (r"^([1-8])\d{2}\s*[a-z]{0,3}\b", r"serie \1"),
        (r"^x\s*([1-7])\b", r"x\1"),
        # BMW i-elétricos: família por modelo exato.
        (r"^i\s*([1-7])\s*(?:edrive|m\s*power|xdrive)?\b", r"i\1"),
        (r"^ix\s*([1-7])\b", r"ix\1"),
        (r"^ix\b", r"ix"),
        (r"^classe\s*([abcegs])\b", r"classe \1"),
        (r"^([abcegs])\s*\d{2,3}\b", r"classe \1"),
        # Mercedes-AMG: "GT" é apenas a desportiva pura; "GT 43/53/63" são
        # corpos de classe (C/E/S) — não entram na família do AMG GT.
        (r"^amg\s*gt\s*(?:4[0-9]|5[0-9]|6[0-9])\b", r"amg_gt_53"),
        (r"^(cla|cls|gla|glb|glc|gle|gls|eqa|eqb|eqc|eqe|eqs|slk|sl|amg\s*gt)\b", r"\1"),
        (r"^(a|q|rs\s*q|s)\s*([1-8])\b", r"\1\2"),
    )
)


def _model_family(brand: str, model: str, title: str) -> str:
    """Família comercial estável (Série 3, Classe C, Panamera, …)."""
    m = _norm(model)
    if not m:
        m = _norm(title).replace(_norm(brand), "", 1).strip()
    if not m:
        return ""
    b = _norm(brand)
    if b in ("bmw", "mercedes-benz", "mercedes", "audi"):
        for pattern, repl in _MODEL_FAMILY_RULES:
            match = pattern.match(m)
            if match:
                try:
                    return match.expand(repl).strip()
                except re.error:  # pragma: no cover - repl estático
                    return repl
    # Caso geral: primeiras duas palavras chegam para a família
    # ("panamera sport turismo" → "panamera sport").
    tokens = [t for t in m.split() if not re.fullmatch(r"[\d.,]+", t)]
    return " ".join(tokens[:2]) if tokens else m


# ---------------------------------------------------------------------------
# Estrutura canónica
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalVehicle:
    """Forma canónica e comparável de um anúncio."""

    brand: str
    model_family: str
    model_raw: str
    performance_class: str
    trim_confidence: float
    fuel: str
    transmission: str
    drivetrain: str
    body: str
    year: Optional[int]
    km: Optional[int]
    horsepower: Optional[int]
    engine_cc: Optional[int]
    doors: Optional[int]
    is_national: Optional[bool]
    seller_type: Optional[str]
    vehicle_type: str
    source: str
    notes: Tuple[str, ...] = field(default=())

    def comparability_key(self) -> Tuple[str, str, str, str]:
        """Chave mínima que dois veículos têm de partilhar para se compararem.

        Marca, família, escalão de performance e combustível. Um Classe A
        base e um A 35 AMG têm chaves diferentes — por construção.
        """
        return (self.brand, self.model_family, self.performance_class, self.fuel)

    @property
    def performance_rank(self) -> int:
        return PERFORMANCE_RANK.get(self.performance_class, 0)

    @property
    def is_performance(self) -> bool:
        """Versões que não podem ser misturadas com o modelo normal."""
        return self.performance_rank >= PERFORMANCE_RANK[PerformanceClass.PERFORMANCE]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["notes"] = list(self.notes)
        d["comparability_key"] = "|".join(self.comparability_key())
        return d


def _as_int(value: Any, lo: int, hi: int) -> Optional[int]:
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        out = int(float(value))
    except (TypeError, ValueError):
        return None
    return out if lo <= out <= hi else None


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def canonicalize(vehicle: Dict[str, Any]) -> CanonicalVehicle:
    """Constrói a forma canónica de um anúncio (dict do ORM ou do scraper).

    Aceita chaves em falta, ``None``, ``"nan"`` e enums SQLAlchemy. Nunca
    levanta exceção: dados maus produzem campos ``unknown`` e uma
    ``trim_confidence`` baixa, que é o sinal correto a jusante.

    >>> v = canonicalize({"brand": "Mercedes-Benz", "model": "A 35 AMG",
    ...                   "title": "Mercedes-Benz A 35 AMG 4Matic", "year": 2019})
    >>> v.performance_class, v.model_family
    ('performance', 'classe a')
    """
    brand = _norm(vehicle.get("normalized_brand") or vehicle.get("brand"))
    model_raw = _norm(vehicle.get("model"))
    version = _norm(vehicle.get("version"))
    trim = _norm(vehicle.get("trim_level"))
    title = _norm(vehicle.get("title"))
    # A base quase nunca tem version/trim_level preenchidos; deriva do título.
    if not version and title:
        version = extract_version(title)
    if not trim and title:
        tm = _TRIM_WORDS.search(title)
        if tm:
            trim = tm.group(1).lower()
    blob = " ".join(t for t in (model_raw, version, trim, title) if t)
    perf_class, perf_conf = detect_performance_class(model_raw, version, trim, title)
    fuel = normalize_fuel(
        _enum_value(vehicle.get("fuel_type")), version, model_raw, title
    )
    # Coerência: um "elétrico" cujo texto diz híbrido é um híbrido mal
    declared = _norm(_enum_value(vehicle.get("fuel_type")))
    if declared in ("eletrico", "electric") and fuel in (
        FuelClass.HYBRID, FuelClass.PHEV, FuelClass.MILD_HYBRID
    ):
        notes.append(f"combustivel_corrigido_eletrico_para_{fuel}")

    transmission = _first_match(
        _TRANSMISSION_PATTERNS,
        " ".join((_norm(_enum_value(vehicle.get("transmission"))), blob)),
        "unknown",
    )
    drivetrain = _first_match(_DRIVETRAIN_PATTERNS, blob, "fwd_or_unknown")
    body = _first_match(_BODY_PATTERNS, blob, "unknown")
    family = _model_family(brand, model_raw, title)
    notes: list = []
    if not family:
        notes.append("familia_de_modelo_desconhecida")
        perf_conf = min(perf_conf, 0.3)
    if fuel == FuelClass.UNKNOWN:
        notes.append("combustivel_desconhecido")
        perf_conf = min(perf_conf, 0.5)

    seller_type = _norm(vehicle.get("seller_type")) or None
    is_national = vehicle.get("is_national")
    if is_national is None and title:
        if "nacional" in title:
            is_national = True
        elif "importad" in title:
            is_national = False

    return CanonicalVehicle(
        brand=brand or "unknown",
        model_family=family or "unknown",
        model_raw=model_raw,
        performance_class=perf_class,
        trim_confidence=round(perf_conf, 3),
        fuel=fuel,
        transmission=transmission,
        drivetrain=drivetrain,
        body=body,
        year=_as_int(vehicle.get("year"), 1950, 2100),
        km=_as_int(vehicle.get("km"), 0, 2_000_000),
        horsepower=_as_int(vehicle.get("horsepower"), 15, 1600),
        engine_cc=_as_int(vehicle.get("engine_size"), 500, 8500),
        doors=_as_int(vehicle.get("doors"), 2, 7),
        is_national=bool(is_national) if is_national is not None else None,
        seller_type=seller_type,
        vehicle_type=_norm(_enum_value(vehicle.get("vehicle_type"))) or "carros",
        source=str(_enum_value(vehicle.get("source")) or "").upper(),
        notes=tuple(notes),
    )
