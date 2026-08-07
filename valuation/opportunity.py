"""Classificação de oportunidades consciente da incerteza.

Um carro não é uma boa oportunidade porque o valor **central** estimado é
superior ao preço pedido. É uma oportunidade quando o preço está abaixo do
**limite inferior** do intervalo plausível — ou seja, quando o desconto
sobrevive à incerteza da própria estimativa.

Categorias
----------
=========================  ==========================================
``excelente_oportunidade`` preço < limite inferior, desconto forte,
                           confiança ≥ média, ≥ 6 comparáveis
``boa_oportunidade``       preço < limite inferior, confiança ≥ baixa
``dentro_do_mercado``      preço dentro do intervalo
``ligeiramente_acima``     preço até 10 % acima do limite superior
``muito_acima_do_mercado`` preço mais de 10 % acima do limite superior
``requer_validacao``       desconto grande mas confiança fraca, ou
                           desconto acima do máximo plausível
``anuncio_suspeito``       sinais de risco no anúncio
``dados_insuficientes``    sem estimativa defensável
=========================  ==========================================

Invariantes garantidos (testados em ``tests/test_opportunity.py``):

* zero comparáveis ⇒ nunca ``excelente_oportunidade``;
* confiança baixa ⇒ nunca ``excelente_oportunidade``;
* ``discount_eur <= 0`` ⇒ nunca categoria de oportunidade;
* nenhum campo devolvido é ``NaN`` ou infinito.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from valuation.market_math import PriceDelta, compute_delta, finite, json_safe

__all__ = [
    "Opportunity",
    "OpportunityLabel",
    "classify",
    "MAX_PLAUSIBLE_DISCOUNT_PCT",
]

#: Acima deste desconto, um anúncio deixa de ser "barato" e passa a ser
#: "estranho". Nada é promovido automaticamente ao topo com um desconto
#: destes: exige validação humana.
MAX_PLAUSIBLE_DISCOUNT_PCT: float = 30.0

#: Desconto a partir do qual, com dados fortes, se justifica "excelente".
EXCELLENT_DISCOUNT_PCT: float = 12.0

#: Mínimos de evidência para o escalão máximo.
EXCELLENT_MIN_COMPARABLES: int = 6
EXCELLENT_MIN_CONFIDENCE: float = 0.45


class OpportunityLabel:
    EXCELLENT = "excelente_oportunidade"
    GOOD = "boa_oportunidade"
    FAIR = "dentro_do_mercado"
    SLIGHTLY_ABOVE = "ligeiramente_acima_do_mercado"
    WELL_ABOVE = "muito_acima_do_mercado"
    NEEDS_REVIEW = "requer_validacao_manual"
    SUSPICIOUS = "anuncio_suspeito"
    INSUFFICIENT = "dados_insuficientes"


#: Rótulos legíveis para UI/relatórios.
LABEL_PT: Dict[str, str] = {
    OpportunityLabel.EXCELLENT: "Excelente oportunidade",
    OpportunityLabel.GOOD: "Boa oportunidade",
    OpportunityLabel.FAIR: "Dentro do mercado",
    OpportunityLabel.SLIGHTLY_ABOVE: "Ligeiramente acima do mercado",
    OpportunityLabel.WELL_ABOVE: "Muito acima do mercado",
    OpportunityLabel.NEEDS_REVIEW: "Possível oportunidade — requer validação",
    OpportunityLabel.SUSPICIOUS: "Anúncio suspeito",
    OpportunityLabel.INSUFFICIENT: "Dados insuficientes",
}

#: Categorias que representam uma vantagem para o comprador.
POSITIVE_LABELS = frozenset({OpportunityLabel.EXCELLENT, OpportunityLabel.GOOD})


@dataclass(frozen=True)
class Opportunity:
    """Veredito final sobre um anúncio, pronto a mostrar."""

    label: str
    label_pt: str
    listing_price: Optional[float]
    market_value: Optional[float]
    market_low: Optional[float]
    market_high: Optional[float]
    discount_eur: Optional[float]
    discount_pct: Optional[float]
    above_market_pct: Optional[float]
    confidence: float
    confidence_label: str
    comparables_count: int
    reasons: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)

    @property
    def is_opportunity(self) -> bool:
        return self.label in POSITIVE_LABELS

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["is_opportunity"] = self.is_opportunity
        return json_safe(d)


def classify(
    *,
    listing_price: Any,
    market_value: Any,
    market_low: Any = None,
    market_high: Any = None,
    confidence: Any = 0.0,
    confidence_label: str = "sem_dados",
    comparables_count: Any = 0,
    risk_flags: Optional[List[str]] = None,
    blocking_flags: Optional[List[str]] = None,
) -> Opportunity:
    """Classifica um anúncio a partir de valores **atuais**.

    Nada aqui é lido da base de dados: todos os campos derivados são
    recalculados a partir do preço e da estimativa passados.

    >>> o = classify(listing_price=36_900, market_value=34_728,
    ...              market_low=32_000, market_high=37_500,
    ...              confidence=0.6, comparables_count=9)
    >>> o.discount_eur, o.label
    (-2172.0, 'dentro_do_mercado')
    >>> classify(listing_price=39_900, market_value=None,
    ...          comparables_count=0).label
    'dados_insuficientes'
    """
    risks = list(risk_flags or [])
    blocking = list(blocking_flags or [])
    reasons: List[str] = []
    conf = finite(confidence) or 0.0
    n_comp = int(finite(comparables_count) or 0)
    price = finite(listing_price)

    def build(label: str, delta: PriceDelta) -> Opportunity:
        return Opportunity(
            label=label,
            label_pt=LABEL_PT[label],
            listing_price=delta.listing_price if delta.listing_price is not None else price,
            market_value=delta.market_value,
            market_low=finite(market_low),
            market_high=finite(market_high),
            discount_eur=delta.discount_eur,
            discount_pct=delta.discount_pct,
            above_market_pct=delta.above_market_pct,
            confidence=round(conf, 3),
            confidence_label=confidence_label,
            comparables_count=n_comp,
            reasons=reasons,
            risk_flags=risks,
        )

    delta = compute_delta(listing_price, market_value)

    # ── porta 0: anúncio bloqueado (preço não total, salvado, peças…) ───────
    if blocking:
        reasons.append(
            "Anúncio excluído da avaliação: " + ", ".join(blocking[:4]) + "."
        )
        return build(OpportunityLabel.SUSPICIOUS, compute_delta(listing_price, None))

    # ── porta 1: sem estimativa defensável ──────────────────────────────────
    if not delta.ok:
        if delta.reason == "sem_estimativa":
            reasons.append(
                f"Sem estimativa fiável ({n_comp} comparáveis válidos): "
                "o sistema não classifica este anúncio."
            )
        else:
            reasons.append(f"Comparação impossível: {delta.reason}.")
        return build(OpportunityLabel.INSUFFICIENT, delta)

    if n_comp < 1:
        reasons.append(
            "Estimativa sem comparáveis válidos — não é apresentada como oportunidade."
        )
        return build(OpportunityLabel.INSUFFICIENT, delta)

    # ── porta 2: o intervalo é o critério, não o valor central ──────────────
    low = finite(market_low)
    high = finite(market_high)
    value = delta.market_value or 0.0
    if low is None or low <= 0 or low > value:
        low = value * 0.9
    if high is None or high <= 0 or high < value:
        high = value * 1.1

    discount_pct = delta.discount_pct or 0.0

    # ── porta 3: sinais de risco no anúncio ─────────────────────────────────
    if risks:
        reasons.append("Sinais de risco detetados: " + ", ".join(risks[:4]) + ".")
        return build(OpportunityLabel.SUSPICIOUS, delta)

    # ─the interval is the criterion ──
    if price is not None and price < low:
        below_low_pct = (low - price) / low * 100.0
        # O desconto face ao LIMITE INFERIOR é que determina a plausibilidade:
        # um preço dentro do intervalo (mesmo abaixo do valor central) NUNCA é
        # "implausível". Só um preço muito abaixo do próprio limite inferior
        # merece validação humana.
        if below_low_pct > MAX_PLAUSIBLE_DISCOUNT_PCT:
            reasons.append(
                f"Preço {price:,.0f} € está {below_low_pct:.0f}% abaixo do limite "
                f"inferior do intervalo ({low:,.0f} €), acima do máximo plausível "
                f"({MAX_PLAUSIBLE_DISCOUNT_PCT:.0f}%): verificar salvado, "
                "financiamento, erro de extração ou fraude.".replace(",", ".")
            )
            risks.append("desconto_implausivel")
            return build(OpportunityLabel.NEEDS_REVIEW, delta)
        reasons.append(
            f"Preço {price:,.0f} € abaixo do limite inferior do intervalo "
            f"({low:,.0f} €), ou seja −{below_low_pct:.1f}%.".replace(",", ".")
        )
        strong = (
            discount_pct >= EXCELLENT_DISCOUNT_PCT
            and conf >= EXCELLENT_MIN_CONFIDENCE
            and n_comp >= EXCELLENT_MIN_COMPARABLES
        )
        if strong:
            return build(OpportunityLabel.EXCELLENT, delta)
        if conf < 0.25 or n_comp < 3:
            reasons.append(
                f"Confiança {confidence_label} com {n_comp} comparáveis: "
                "oportunidade possível, mas exige validação manual."
            )
            return build(OpportunityLabel.NEEDS_REVIEW, delta)
        return build(OpportunityLabel.GOOD, delta)

    if price is not None and price > high:
        above_pct = (price - high) / high * 100.0
        reasons.append(
            f"Preço {price:,.0f} € acima do limite superior do intervalo "
            f"({high:,.0f} €).".replace(",", ".")
        )
        if above_pct > 10.0:
            return build(OpportunityLabel.WELL_ABOVE, delta)
        return build(OpportunityLabel.SLIGHTLY_ABOVE, delta)

    # ── preço dentro do intervalo ────────────────────────────────────────────
    # Com evidência muito fraca (poucos comparáveis / confiança muito baixa) o
    # intervalo é estreito mas a estimativa central pode estar errada; não se
    # afirma "dentro do mercado" — exige validação.
    if n_comp < 3 or conf < 0.2:
        reasons.append(
            f"Preço entre limites, mas confiança {confidence_label} com "
            f"{n_comp} comparáveis: classificação retida como 'requer validação'."
        )
        return build(OpportunityLabel.NEEDS_REVIEW, delta)
    reasons.append(
        f"Preço dentro do intervalo plausível "
        f"({low:,.0f} €–{high:,.0f} €).".replace(",", ".")
    )
    return build(OpportunityLabel.FAIR, delta)
