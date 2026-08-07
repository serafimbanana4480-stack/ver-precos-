"""Deteção de anúncios impossíveis, suspeitos e duplicados.

Um comparável mau contamina a mediana de todos os outros anúncios do mesmo
modelo. Este módulo é a porta de entrada: classifica cada anúncio antes de
ele poder servir de comparável ou de ser apresentado como oportunidade.

Três responsabilidades
----------------------
1. :func:`inspect_listing` — sinais de que o preço **não é** o preço total de
   um carro pronto a rolar (mensalidade, entrada, sem IVA, salvado, peças,
   leilão, fraude) e dados fisicamente impossíveis (km/idade, ano futuro,
   potência incompatível).
2. :func:`fingerprint` — impressão digital de conteúdo para deduplicação
   entre plataformas (OLX, Standvirtual, PiscaPisca, AutoUncle e o site do
   próprio stand publicam o mesmo carro).
3. :func:`dedupe` — agrupa e escolhe um registo principal.

Regra: um anúncio ``blocking`` nunca é comparável e nunca é oportunidade. Um
anúncio ``suspicious`` pode ser mostrado, mas sempre com aviso e nunca no
topo do ranking sem validação manual.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from valuation.market_math import (
    MAX_PLAUSIBLE_PRICE,
    MIN_PLAUSIBLE_PRICE,
    finite,
)

__all__ = [
    "ListingFlags",
    "inspect_listing",
    "fingerprint",
    "dedupe",
    "DuplicateGroup",
]


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _norm(value: Any) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw or raw.lower() in ("nan", "none", "null"):
        return ""
    return re.sub(r"\s+", " ", _strip_accents(raw).lower())


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


# ---------------------------------------------------------------------------
# Léxico de risco
# ---------------------------------------------------------------------------

#: O preço apresentado não é o preço total da viatura.
_NOT_TOTAL_PRICE = (
    ("mensalidade", "preco_mensalidade"),
    ("/mes", "preco_mensalidade"),
    ("/mês", "preco_mensalidade"),
    ("por mes", "preco_mensalidade"),
    ("euros/mes", "preco_mensalidade"),
    ("prestacao", "preco_prestacao"),
    ("prestação", "preco_prestacao"),
    ("mensal", "preco_mensalidade"),
    ("entrada de", "preco_entrada"),
    ("entrada inicial", "preco_entrada"),
    ("valor de entrada", "preco_entrada"),
    ("sinal de", "preco_sinal"),
    ("desde ", "preco_desde"),
    ("a partir de", "preco_desde"),
    ("sob consulta", "preco_sob_consulta"),
    ("sob-consulta", "preco_sob_consulta"),
    ("preco a combinar", "preco_sob_consulta"),
    ("sem iva", "preco_sem_iva"),
    ("s/ iva", "preco_sem_iva"),
    ("s/iva", "preco_sem_iva"),
    ("+ iva", "preco_sem_iva"),
    ("mais iva", "preco_sem_iva"),
    ("iva dedutivel", "preco_sem_iva"),
    ("iva discriminado", "preco_sem_iva"),
    ("renting", "preco_renting"),
    ("leasing", "preco_leasing"),
    ("aluguer", "preco_aluguer"),
    ("ald ", "preco_renting"),
    ("credito obrigatorio", "credito_obrigatorio"),
    ("financiamento obrigatorio", "credito_obrigatorio"),
    ("retoma obrigatoria", "retoma_obrigatoria"),
)

#: A viatura não está em estado normal de venda.
_DAMAGED = (
    ("salvado", "salvado"),
    ("para pecas", "para_pecas"),
    ("para peças", "para_pecas"),
    ("pecas de", "para_pecas"),
    ("peças de", "para_pecas"),
    ("desmantelamento", "para_pecas"),
    ("sucata", "para_pecas"),
    ("para abate", "para_pecas"),
    ("acidentado", "acidentado"),
    ("batido", "acidentado"),
    ("sinistrado", "acidentado"),
    ("capotado", "acidentado"),
    ("incendiado", "acidentado"),
    ("afundado", "acidentado"),
    ("motor fundido", "avaria_grave"),
    ("motor gripado", "avaria_grave"),
    ("nao pega", "avaria_grave"),
    ("não pega", "avaria_grave"),
    ("nao trabalha", "avaria_grave"),
    ("avariado", "avaria_grave"),
    ("para restauro", "para_restauro"),
    ("sem documentos", "sem_documentos"),
    ("sem livrete", "sem_documentos"),
    ("documentos em falta", "sem_documentos"),
    ("penhora", "penhora"),
    ("penhorado", "penhora"),
    ("apreendido", "penhora"),
    ("sem legalizacao", "sem_legalizacao"),
    ("por legalizar", "sem_legalizacao"),
    ("nao legalizado", "sem_legalizacao"),
    ("matricula estrangeira", "sem_legalizacao"),
)

#: Não é um automóvel ligeiro de passageiros normal.
_NOT_A_CAR = (
    ("trotinete", "nao_e_automovel"),
    ("bicicleta", "nao_e_automovel"),
    ("mota de agua", "nao_e_automovel"),
    ("jet ski", "nao_e_automovel"),
    ("barco", "nao_e_automovel"),
    ("atrelado", "nao_e_automovel"),
    ("reboque", "nao_e_automovel"),
    ("maquina agricola", "nao_e_automovel"),
    ("trator", "nao_e_automovel"),
    ("empilhador", "nao_e_automovel"),
    ("quadriciclo", "quadriciclo_ou_microcarro"),
    ("microcarro", "quadriciclo_ou_microcarro"),
    ("sem carta", "quadriciclo_ou_microcarro"),
    ("ligeiro de mercadorias", "comercial_nao_ligeiro"),
    ("caixa aberta", "comercial_nao_ligeiro"),
)

#: Preços redondos que quase nunca são preços reais de venda.
_PLACEHOLDER_PRICES = frozenset({1.0, 10.0, 99.0, 100.0, 111.0, 123.0, 500.0,
                                 999.0, 1000.0, 1111.0, 12345.0, 99999.0})

#: Títulos que não identificam o veículo.
_GENERIC_TITLE = re.compile(
    r"^(carro|viatura|automovel|vendo carro|carro usado|oportunidade|"
    r"varios|diversos|nacional|bom estado)[\s\W]*$"
)

_CURRENT_YEAR = datetime.now().year


@dataclass(frozen=True)
class ListingFlags:
    """Veredito estrutural sobre um anúncio.

    Attributes:
        blocking: motivos que impedem o anúncio de ser comparável **e** de
            ser apresentado como oportunidade.
        suspicious: motivos que exigem validação humana antes de confiar.
        warnings: observações que apenas reduzem confiança.
        price_is_total: ``False`` quando há evidência de que o preço não é o
            preço total da viatura.
    """

    blocking: Tuple[str, ...] = ()
    suspicious: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    price_is_total: bool = True

    @property
    def usable_as_comparable(self) -> bool:
        """Só anúncios limpos entram no cálculo da mediana de mercado."""
        return not self.blocking and not self.suspicious and self.price_is_total

    @property
    def publishable(self) -> bool:
        """Pode ser mostrado como oportunidade (com avisos, se houver)."""
        return not self.blocking and self.price_is_total

    @property
    def exclusion_reason(self) -> Optional[str]:
        if self.blocking:
            return ";".join(self.blocking)
        if not self.price_is_total:
            return "preco_nao_total"
        if self.suspicious:
            return ";".join(self.suspicious)
        return None

    def to_dict(self) -> Dict[str, Any]:
        d = {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(self).items()}
        d["usable_as_comparable"] = self.usable_as_comparable
        d["publishable"] = self.publishable
        d["exclusion_reason"] = self.exclusion_reason
        return d


def _scan(text: str, table: Sequence[Tuple[str, str]]) -> List[str]:
    return sorted({label for token, label in table if token in text})


def inspect_listing(
    vehicle: Dict[str, Any], *, reference_value: Optional[float] = None
) -> ListingFlags:
    """Audita um anúncio e devolve os seus sinais de risco.

    ``reference_value`` (uma estimativa independente, se existir) permite
    detetar preços que são uma fração implausível do valor real — tipicamente
    mensalidades ou entradas apresentadas como preço.

    >>> inspect_listing({"brand": "BMW", "price": 249,
    ...                  "title": "BMW 320d desde 249€/mês"}).price_is_total
    False
    >>> inspect_listing({"brand": "Audi", "price": 15000,
    ...                  "title": "Audi A4 salvado"}).blocking
    ('salvado',)
    >>> inspect_listing({"brand": "VW", "price": 18000, "year": 2019,
    ...                  "km": 90000, "location": "Porto",
    ...                  "title": "VW Golf 2.0 TDI"}).usable_as_comparable
    True
    """
    blocking: List[str] = []
    suspicious: List[str] = []
    warnings: List[str] = []
    price_is_total = True

    title = _norm(vehicle.get("title"))
    desc = _norm(vehicle.get("description"))
    text = f"{title} {desc}".strip()
    price = finite(vehicle.get("price"))
    year = finite(vehicle.get("year"))
    km = finite(vehicle.get("km"))
    hp = finite(vehicle.get("horsepower"))

    # ── proveniência do preço declarada pelo scraper ────────────────────────
    price_kind = _norm(_enum_value(vehicle.get("price_kind")))
    if price_kind and price_kind not in ("total", "unknown"):
        price_is_total = False
        blocking.append(f"price_kind_{price_kind}")
    currency = _norm(vehicle.get("currency"))
    if currency and currency != "eur":
        blocking.append("moeda_nao_eur")
    if vehicle.get("price_rejection_reason"):
        suspicious.append("preco_rejeitado_na_origem")

    # ── o preço não é o preço total ─────────────────────────────────────────
    for label in _scan(text, _NOT_TOTAL_PRICE):
        price_is_total = False
        blocking.append(label)

    # ── viatura danificada / irregular ──────────────────────────────────────
    damage = _scan(text, _DAMAGED)
    for label in damage:
        # Salvado/peças/documentos são bloqueio: não são carros de retalho.
        if label in ("salvado", "para_pecas", "sem_documentos", "penhora"):
            blocking.append(label)
        else:
            suspicious.append(label)
    if vehicle.get("has_accident") or vehicle.get("has_damage"):
        if "acidentado" not in suspicious:
            suspicious.append("acidentado")

    # ── não é um automóvel normal ───────────────────────────────────────────
    for label in _scan(text, _NOT_A_CAR):
        blocking.append(label)

    # ── preço fisicamente implausível ───────────────────────────────────────
    if price is None or price <= 0:
        blocking.append("preco_ausente")
        price_is_total = False
    else:
        if price in _PLACEHOLDER_PRICES:
            blocking.append(f"preco_placeholder({price:.0f})")
            price_is_total = False
        elif price < MIN_PLAUSIBLE_PRICE:
            blocking.append(f"preco_abaixo_do_minimo({price:.0f})")
            price_is_total = False
        elif price > MAX_PLAUSIBLE_PRICE:
            blocking.append(f"preco_acima_do_maximo({price:.0f})")
            price_is_total = False
        elif price > 400_000:
            warnings.append(f"preco_muito_elevado_verificar({price:.0f})")

        ref = finite(reference_value)
        if ref and ref > 4000 and price > 0:
            ratio = price / ref
            if ratio < 0.12:
                price_is_total = False
                blocking.append(f"preco_e_fracao_do_valor(ratio={ratio:.2f})")
            elif ratio < 0.35:
                suspicious.append(f"preco_muito_abaixo_da_referencia(ratio={ratio:.2f})")
            elif ratio > 4.0:
                suspicious.append(f"preco_muito_acima_da_referencia(ratio={ratio:.2f})")

    # ── dados fisicamente impossíveis ───────────────────────────────────────
    if year is None:
        warnings.append("ano_ausente")
    else:
        y = int(year)
        if y < 1950 or y > _CURRENT_YEAR + 1:
            blocking.append(f"ano_impossivel({y})")
        elif km is not None:
            age = max(1, _CURRENT_YEAR - y)
            if km < 0:
                blocking.append("km_negativo")
            elif km > 90_000 * age:
                suspicious.append(f"km_incompativel_com_idade({int(km)}km/{age}a)")
            elif age >= 8 and km < 1000:
                suspicious.append("km_implausivelmente_baixo_para_a_idade")
    if km is None:
        warnings.append("km_ausente")
    elif km > 1_500_000:
        blocking.append(f"km_impossivel({int(km)})")

    if hp is not None and (hp < 15 or hp > 1600):
        warnings.append(f"potencia_implausivel({int(hp)}cv)")

    # ── identificação do anúncio ────────────────────────────────────────────
    brand = _norm(vehicle.get("normalized_brand") or vehicle.get("brand"))
    if not brand or brand in ("unknown", "outro", "other"):
        blocking.append("marca_ausente")
    elif brand.isdigit():
        # Casos reais na base: brand == "520" (o badge lido como marca).
        blocking.append(f"marca_numerica({brand})")
    if not _norm(vehicle.get("model")):
        warnings.append("modelo_ausente")
    if title and _GENERIC_TITLE.match(title):
        suspicious.append("titulo_generico")
    if not title:
        warnings.append("titulo_ausente")
    if not _norm(vehicle.get("location")) and not _norm(vehicle.get("district")):
        warnings.append("localizacao_ausente")

    return ListingFlags(
        blocking=tuple(dict.fromkeys(blocking)),
        suspicious=tuple(dict.fromkeys(suspicious)),
        warnings=tuple(dict.fromkeys(warnings)),
        price_is_total=price_is_total,
    )


# ---------------------------------------------------------------------------
# Deduplicação
# ---------------------------------------------------------------------------

_TITLE_NOISE = re.compile(
    r"\b(usado|novo|semi\s*novo|oportunidade|super\s*preco|nacional|garantia|"
    r"financiamento|ipo|impecavel|como\s*novo|full\s*extras|aceito\s*retoma|"
    r"\d{4,6}\s*km|\d{4}|€|eur)\b"
)


def _title_signature(title: str) -> str:
    """Assinatura estável do título: tokens ordenados, ruído comercial fora."""
    clean = _TITLE_NOISE.sub(" ", _norm(title))
    tokens = sorted({t for t in re.split(r"[^a-z0-9]+", clean) if len(t) > 2})
    return " ".join(tokens[:12])


def fingerprint(vehicle: Dict[str, Any]) -> str:
    """Impressão digital de conteúdo para detetar o mesmo carro em N sites.

    Combina os atributos que um vendedor não altera ao republicar: marca,
    família, ano, quilometragem arredondada a 5 000 km, preço arredondado a
    250 € e assinatura do título. Não usa a fonte nem o URL — o objetivo é
    exatamente cruzar plataformas.

    >>> a = {"brand": "BMW", "model": "iX", "year": 2025, "km": 43580,
    ...      "price": 41000, "title": "Usado (2025) BMW iX 204 HP"}
    >>> b = {"brand": "BMW", "model": "iX", "year": 2025, "km": 43700,
    ...      "price": 41000, "title": "BMW iX 204 HP | Super Preço"}
    >>> fingerprint(a) == fingerprint(b)
    True
    """
    from valuation.canonical_vehicle import canonicalize

    canon = canonicalize(vehicle)
    price = finite(vehicle.get("price")) or 0.0
    km = finite(vehicle.get("km"))
    parts = (
        canon.brand,
        canon.model_family,
        canon.performance_class,
        canon.fuel,
        str(canon.year or "?"),
        str(int(round(km / 5000.0)) if km is not None else "?"),
        str(int(round(price / 250.0))),
        _title_signature(str(vehicle.get("title") or "")),
    )
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


@dataclass
class DuplicateGroup:
    """Conjunto de anúncios que representam o mesmo veículo físico."""

    fingerprint: str
    primary_id: Any
    duplicate_ids: List[Any] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return 1 + len(self.duplicate_ids)


def _identity_keys(vehicle: Dict[str, Any]) -> List[str]:
    """Chaves de identidade forte: URL, id externo, matrícula."""
    keys = []
    url = _norm(vehicle.get("url"))
    if url:
        keys.append("url:" + url.split("?")[0].rstrip("/"))
    source = _norm(_enum_value(vehicle.get("source")))
    sid = _norm(vehicle.get("source_id"))
    if source and sid:
        keys.append(f"sid:{source}:{sid}")
    plate = _norm(vehicle.get("license_plate") or vehicle.get("plate"))
    if plate and len(plate) >= 6:
        keys.append("plate:" + re.sub(r"[^a-z0-9]", "", plate))
    return keys


def dedupe(vehicles: Iterable[Dict[str, Any]]) -> List[DuplicateGroup]:
    """Agrupa anúncios duplicados e elege um registo principal.

    Estratégia em duas camadas:

    1. **Identidade forte** — URL, ``source:source_id``, matrícula. Une
       registos com certeza absoluta.
    2. **Impressão digital de conteúdo** — :func:`fingerprint`. Apanha o
       mesmo carro publicado em plataformas diferentes.

    O registo principal é o mais antigo (``first_seen``), com desempate pelo
    ``id`` mais baixo: é o que tem mais histórico de preço.

    Returns:
        Apenas os grupos com mais de um membro.
    """
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    rows = list(vehicles)
    node_of: Dict[int, str] = {}
    for i, v in enumerate(rows):
        node = f"row:{i}"
        parent.setdefault(node, node)
        node_of[i] = node
        for key in _identity_keys(v) + ["fp:" + fingerprint(v)]:
            parent.setdefault(key, key)
            union(node, key)

    clusters: Dict[str, List[int]] = {}
    for i in range(len(rows)):
        clusters.setdefault(find(node_of[i]), []).append(i)

    def sort_key(i: int):
        v = rows[i]
        seen = v.get("first_seen")
        return (str(seen) if seen else "9999", str(v.get("id") or ""))

    groups: List[DuplicateGroup] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        members.sort(key=sort_key)
        primary = rows[members[0]]
        groups.append(
            DuplicateGroup(
                fingerprint=fingerprint(primary),
                primary_id=primary.get("id"),
                duplicate_ids=[rows[i].get("id") for i in members[1:]],
                sources=sorted(
                    {str(_enum_value(rows[i].get("source")) or "?") for i in members}
                ),
            )
        )
    return groups
