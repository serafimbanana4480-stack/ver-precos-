"""
Reliability & Profit Shrinkage
==============================

Corrige a **fuga de preço** mais grave do sistema: o ranking por
``profit_potential`` selecciona *erro do modelo*, não negócios reais.

Diagnóstico medido em ``data/autodeal.db`` (4 957 viaturas, 3 674 com preço
retail válido):

===========================  ========  ==========
Conjunto                     N         MAPE
===========================  ========  ==========
Todas as viaturas            3 674     15,8 %
Top-100 por profit_potential   100     **45,9 %**
Bottom-500 por profit           500     15,8 %
===========================  ========  ==========

O topo do ranking tem **3x o erro** da população. Isto é a *winner's curse*:
quando se ordena por ``estimated_value - price``, escolhem-se preferencialmente
as viaturas cujo ``estimated_value`` está inflacionado por ruído.

A causa raiz é a **densidade de comparáveis**:

==================  ======  ========  =========
Comparáveis         N       MAPE      sd(log)
==================  ======  ========  =========
< 3                 1 242   24,6 %    0,352
3–7                   910   14,6 %    0,209
8–19                  845   11,4 %    0,158
20+                   677    6,9 %    0,093
==================  ======  ========  =========

Solução: **shrinkage empírico-Bayesiano**. O gap observado em espaço log
``g = log(estimated_value / price)`` decompõe-se em sinal + ruído. Encolhe-se
``g`` pelo rácio de variâncias face ao tier mais fiável (20+ comparáveis, que
serve de piso de ruído irredutível)::

    lambda_tier = (sd_floor / sd_tier) ** 2
    estimated_value_ajustado = price * exp(lambda_tier * g)

Resultado validado: MAPE do top-100 cai de **45,9 % para 26,1 %** (−43 %) e a
composição do topo inverte-se — de 63 % de viaturas com <3 comparáveis para
53 % com 20+ comparáveis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

__all__ = [
    "COMPARABLE_TIERS",
    "DEFAULT_LAMBDAS",
    "MAX_CREDIBLE_GAP_PCT",
    "MAX_RAW_GAP_PCT",
    "ConfidenceTier",
    "ReliabilityAssessment",
    "comparable_tier",
    "confidence_tier",
    "fit_shrinkage_lambdas",
    "assess",
    "shrink_estimated_value",
]

# ── Tiers de comparáveis ─────────────────────────────────────────────────────
# (limite inferior inclusivo, etiqueta). Fronteiras derivadas da tabela de MAPE
# acima: cada tier separa um patamar de erro claramente distinto.
COMPARABLE_TIERS: Sequence[Tuple[int, str]] = (
    (0, "thin"),      # < 3 comparáveis  → MAPE 24,6 %
    (3, "sparse"),    # 3–7              → MAPE 14,6 %
    (8, "solid"),     # 8–19             → MAPE 11,4 %
    (20, "dense"),    # 20+              → MAPE 6,9 %
)

# Lambdas medidos em 2026-08 sobre a base completa (ver docstring do módulo).
# Recalcular com fit_shrinkage_lambdas() sempre que a base cresça
# significativamente — estes valores são o fallback de arranque a frio.
DEFAULT_LAMBDAS: Dict[str, float] = {
    "thin": 0.07,
    "sparse": 0.20,
    "solid": 0.35,
    "dense": 1.00,
}

# Desconto máximo credível face ao mercado retail português.
# Em 2026-08 a margem mediana de revenda PT é ~3 %; margens > 20 % num mercado
# líquido são, na prática, fraude/salvado/peças ou erro do modelo — nunca
# negócio confirmável. O gap é truncado aqui e a viatura marcada para revisão
# manual (não é publicada como deal).
MAX_CREDIBLE_GAP_PCT: float = 20.0

# Gap bruto acima do qual o anúncio é anómalo, não uma oportunidade.
# Preços abaixo de ~2/3 do valor justo indicam fraude (sinal), salvado,
# peças, penhora, preço de entrada ou erro de extração (ex.: km absurdo) —
# o modelo mede erro, não negócio.
MAX_RAW_GAP_PCT: float = 50.0

# Nº mínimo de comparáveis para o profit ser publicável sem aviso.
MIN_COMPARABLES_FOR_PUBLICATION: int = 3


class ConfidenceTier:
    """Etiquetas de confiança expostas ao utilizador."""

    HIGH = "alta"
    MEDIUM = "media"
    LOW = "baixa"
    NONE = "sem_dados"


@dataclass(frozen=True)
class ReliabilityAssessment:
    """Resultado completo da avaliação de fiabilidade de uma viatura."""

    # Entradas
    price: Optional[float]
    raw_estimated_value: Optional[float]
    comparables: int

    # Saídas
    comparable_tier: str
    shrink_lambda: float
    adjusted_estimated_value: Optional[float]
    raw_gap_pct: Optional[float]
    adjusted_gap_pct: Optional[float]
    credible_profit: Optional[float]
    confidence: str
    capped: bool
    reasons: Tuple[str, ...]

    @property
    def is_publishable(self) -> bool:
        """True quando o profit pode ser mostrado como oportunidade real.

        Deals truncados pela porta do gap (``capped``) ficam fora: o cap serve
        para sinalizar revisão manual, não para fabricar um lucro "credível".
        """
        return (
            self.credible_profit is not None
            and self.credible_profit > 0
            and not self.capped
            and self.comparables >= MIN_COMPARABLES_FOR_PUBLICATION
            and self.confidence in (ConfidenceTier.HIGH, ConfidenceTier.MEDIUM)
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        d["is_publishable"] = self.is_publishable
        return d


def comparable_tier(n_comparables: int) -> str:
    """Devolve a etiqueta do tier para um dado número de comparáveis.

    >>> comparable_tier(0), comparable_tier(5), comparable_tier(50)
    ('thin', 'sparse', 'dense')
    """
    label = COMPARABLE_TIERS[0][1]
    for lower, name in COMPARABLE_TIERS:
        if n_comparables >= lower:
            label = name
    return label


def confidence_tier(n_comparables: int, *, has_price: bool = True) -> str:
    """Mapeia comparáveis para uma etiqueta de confiança legível."""
    if not has_price:
        return ConfidenceTier.NONE
    tier = comparable_tier(n_comparables)
    return {
        "dense": ConfidenceTier.HIGH,
        "solid": ConfidenceTier.HIGH,
        "sparse": ConfidenceTier.MEDIUM,
        "thin": ConfidenceTier.LOW,
    }[tier]


def fit_shrinkage_lambdas(
    observations: Iterable[Tuple[float, float, int]],
    *,
    min_per_tier: int = 30,
) -> Dict[str, float]:
    """Estima os lambdas de shrinkage a partir de dados observados.

    Args:
        observations: iterável de ``(price, estimated_value, n_comparables)``.
            Apenas registos com ambos os valores > 0 são usados.
        min_per_tier: amostra mínima para confiar num tier; abaixo disto o
            tier herda o valor de :data:`DEFAULT_LAMBDAS`.

    Returns:
        Mapa ``{tier: lambda}`` com lambda em ``(0, 1]``. O tier com menor
        dispersão residual serve de piso de ruído e recebe ``lambda = 1.0``.

    O estimador é ``lambda_t = (sd_floor / sd_t) ** 2``, i.e. a fracção da
    variância do tier ``t`` atribuível a sinal e não a ruído do modelo,
    assumindo que o tier mais denso é livre de ruído excedentário.
    """
    residuals: Dict[str, list] = {name: [] for _, name in COMPARABLE_TIERS}

    for price, estimated_value, n_comp in observations:
        if not price or not estimated_value or price <= 0 or estimated_value <= 0:
            continue
        residuals[comparable_tier(int(n_comp or 0))].append(
            math.log(estimated_value / price)
        )

    sds: Dict[str, float] = {}
    for name, values in residuals.items():
        if len(values) >= min_per_tier:
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / len(values)
            sd = math.sqrt(var)
            if sd > 0:
                sds[name] = sd

    if not sds:
        return dict(DEFAULT_LAMBDAS)

    floor = min(sds.values())
    lambdas = dict(DEFAULT_LAMBDAS)
    for name, sd in sds.items():
        lambdas[name] = round(min(1.0, (floor / sd) ** 2), 4)
    return lambdas


def shrink_estimated_value(
    price: float,
    estimated_value: float,
    shrink_lambda: float,
) -> float:
    """Aplica shrinkage multiplicativo em espaço log.

    ``lambda = 1`` devolve o valor original; ``lambda = 0`` colapsa no preço
    pedido (sem informação → sem negócio).
    """
    if price <= 0 or estimated_value <= 0:
        return estimated_value
    gap_log = math.log(estimated_value / price)
    return price * math.exp(shrink_lambda * gap_log)


def assess(
    price: Optional[float],
    estimated_value: Optional[float],
    n_comparables: int,
    *,
    lambdas: Optional[Dict[str, float]] = None,
    price_is_retail: bool = True,
    max_gap_pct: float = MAX_CREDIBLE_GAP_PCT,
    max_raw_gap_pct: float = MAX_RAW_GAP_PCT,
) -> ReliabilityAssessment:
    """Avalia a fiabilidade do profit de uma viatura e devolve o valor corrigido.

    Esta é a função-porta: nenhum ``profit_potential`` deve chegar à base de
    dados ou ao dashboard sem passar por aqui.

    Args:
        price: preço pedido. ``None``/``<= 0`` significa sem preço retail.
        estimated_value: avaliação bruta do modelo.
        n_comparables: nº de anúncios comparáveis (mesma marca+modelo, ano ±2).
        lambdas: mapa de shrinkage; usa :data:`DEFAULT_LAMBDAS` se omitido.
        price_is_retail: ``False`` para base de leilão, mensalidade ou entrada.
        max_gap_pct: truncatura do gap credível, em percentagem do preço.
        max_raw_gap_pct: acima deste gap bruto o anúncio é anómalo — profit
            zerado (fraude/salvado/peças/erro), nunca publicado.

    Returns:
        :class:`ReliabilityAssessment`. Quando não há preço retail, todos os
        campos de profit vêm a ``None`` — nunca a zero e nunca inflacionados.
    """
    lambdas = lambdas or DEFAULT_LAMBDAS
    n_comp = int(n_comparables or 0)
    tier = comparable_tier(n_comp)
    lam = float(lambdas.get(tier, DEFAULT_LAMBDAS[tier]))
    reasons: list = []

    # ── Porta 1: sem preço retail não existe profit. ─────────────────────────
    # Esta é a fuga que gerava 5,4 M€ de lucro fantasma em 990 viaturas de
    # leilão (AUTOLINE, LEILOSOC) cujo price=0 era subtraído ao valor estimado.
    has_price = bool(price) and price > 0
    if not has_price or not price_is_retail:
        reasons.append(
            "sem_preco_retail" if not has_price else "preco_nao_retail"
        )
        return ReliabilityAssessment(
            price=price if has_price else None,
            raw_estimated_value=estimated_value,
            comparables=n_comp,
            comparable_tier=tier,
            shrink_lambda=lam,
            adjusted_estimated_value=None,
            raw_gap_pct=None,
            adjusted_gap_pct=None,
            credible_profit=None,
            confidence=ConfidenceTier.NONE,
            capped=False,
            reasons=tuple(reasons),
        )

    # ── Porta 2: sem avaliação não há gap. ───────────────────────────────────
    if not estimated_value or estimated_value <= 0:
        reasons.append("sem_avaliacao")
        return ReliabilityAssessment(
            price=float(price),
            raw_estimated_value=None,
            comparables=n_comp,
            comparable_tier=tier,
            shrink_lambda=lam,
            adjusted_estimated_value=None,
            raw_gap_pct=None,
            adjusted_gap_pct=None,
            credible_profit=None,
            confidence=ConfidenceTier.NONE,
            capped=False,
            reasons=tuple(reasons),
        )

    price = float(price)
    estimated_value = float(estimated_value)
    raw_gap_pct = (estimated_value - price) / price * 100.0

    # ── Porta 3: shrinkage por densidade de comparáveis. ─────────────────────
    adjusted = shrink_estimated_value(price, estimated_value, lam)
    adjusted_gap_pct = (adjusted - price) / price * 100.0
    if lam < 1.0:
        reasons.append(f"shrink_{tier}_lambda_{lam:g}")

    # ── Porta 3.5: gap bruto incrível → anúncio anómalo, nunca um negócio. ──
    # Um preço pedido a <40 % do valor justo não é uma oportunidade: é fraude
    # (sinal), salvado, peças, penhora ou erro de extração. Encolher o gap
    # continuaria a publicar o erro com uma etiqueta "credível" — por isso o
    # profit é zerado e a viatura fica fora do ranking.
    anomalous = raw_gap_pct > max_raw_gap_pct
    if anomalous:
        reasons.append(f"gap_bruto_incredivel_{max_raw_gap_pct:g}pct")

    # ── Porta 4: truncatura do gap incrível. ─────────────────────────────────
    capped = False
    if adjusted_gap_pct > max_gap_pct:
        adjusted = price * (1.0 + max_gap_pct / 100.0)
        adjusted_gap_pct = max_gap_pct
        capped = True
        reasons.append(f"gap_truncado_{max_gap_pct:g}pct")

    credible_profit = 0.0 if anomalous else (adjusted - price)
    conf = confidence_tier(n_comp, has_price=True)
    if n_comp < MIN_COMPARABLES_FOR_PUBLICATION:
        reasons.append("comparaveis_insuficientes")

    return ReliabilityAssessment(
        price=price,
        raw_estimated_value=estimated_value,
        comparables=n_comp,
        comparable_tier=tier,
        shrink_lambda=lam,
        adjusted_estimated_value=round(adjusted, 2),
        raw_gap_pct=round(raw_gap_pct, 2),
        adjusted_gap_pct=round(adjusted_gap_pct, 2),
        credible_profit=round(credible_profit, 2),
        confidence=conf,
        capped=capped,
        reasons=tuple(reasons),
    )
