"""
Auditoria de realismo de preço e de lucro (2026-08).

O problema que este módulo resolve
----------------------------------
O pipeline produzia um ``net_profit_after_sale`` a partir de
``estimated_value - custos``. Três pressupostos silenciosos tornavam esse
número sistematicamente otimista:

1. **``estimated_value`` é uma mediana de preços PEDIDOS**, não de preços
   transacionados. Em Portugal um usado fecha 5-12% abaixo do anúncio.
   Usar o pedido como receita infla a margem em ~8% do valor do carro —
   frequentemente mais do que a margem inteira.

2. **O IVA do regime da margem não era descontado.** Um revendedor
   profissional entrega 23% sobre a diferença entre compra e venda
   (art. 308.º CIVA). Isso é quase um quarto do lucro bruto.

3. **A confiança da estimativa não limitava o lucro.** Um lucro de €4.000
   calculado a partir de 2 comparáveis com dispersão de 40% não é um lucro:
   é ruído com unidades monetárias.

Aqui a estimativa de retalho é convertida em **receita líquida realista**,
os custos são os do :mod:`valuation.pt_fiscal`, e o resultado vem sempre
acompanhado de um veredito e das razões que o sustentam. Quando não há
evidência suficiente, o veredito é ``indeterminado`` — nunca um número
inventado com ar de precisão.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from valuation.pt_fiscal import (
    calculate_selling_costs,
    calculate_transaction_costs,
    estimate_reconditioning,
    normalize_fuel,
)

logger = logging.getLogger(__name__)

REALISM_VERSION = "2026.08"

# ─────────────────────────────────────────────────────────────────────────────
# Conversão pedido → transação
# ─────────────────────────────────────────────────────────────────────────────

#: Desconto médio entre o preço pedido e o preço fechado, por tipo de
#: vendedor. Um stand tem margem para negociar e desconta mais; um
#: particular já anuncia perto do que aceita.
#:
#: Fonte: dispersão observada entre preço de anúncio e preço de retoma
#: praticada no mercado português; valores conservadores por construção,
#: porque errar por otimismo custa dinheiro e errar por pessimismo custa
#: apenas uma oportunidade.
_ASK_TO_DEAL_DISCOUNT = {
    "profissional": 0.07,
    "particular": 0.05,
    "unknown": 0.06,
}

#: Desconto adicional quando o carro é difícil de escoar. Um segmento com
#: pouca procura não se vende ao preço mediano — vende-se abaixo, ou não se
#: vende. ``days_to_sell`` é o proxy disponível.
def _liquidity_discount(days_to_sell: int) -> float:
    if days_to_sell <= 30:
        return 0.0
    if days_to_sell <= 60:
        return 0.02
    if days_to_sell <= 90:
        return 0.04
    return 0.07


#: IVA do regime especial da margem (art. 308.º CIVA). Aplica-se apenas a
#: revenda profissional: um particular que venda o seu carro não liquida IVA.
IVA_RATE = 0.23

#: Custo de transporte típico para importação rodoviária até Portugal.
#: Só entra quando o veículo vem de fora e o custo não foi informado.
_TRANSPORT_BY_COUNTRY = {
    "DE": 950.0,
    "FR": 750.0,
    "ES": 450.0,
    "IT": 950.0,
    "BE": 900.0,
    "NL": 950.0,
    "LU": 900.0,
    "AT": 1050.0,
    "PT": 0.0,
}

#: Acima deste ROI líquido, um "negócio" é quase sempre um erro de dados,
#: uma fraude ou um salvado não declarado — não uma oportunidade. Serve de
#: travão: em vez de reportar €15.000 de lucro num Golf, marca-se suspeito.
_IMPLAUSIBLE_ROI = 60.0
#: Lucro líquido mínimo para valer o trabalho de comprar, legalizar e vender.
_MIN_VIABLE_PROFIT = 750.0
#: Nº mínimo de comparáveis para que uma estimativa suporte uma decisão.
_MIN_COMPARABLES = 5
#: Largura máxima aceitável do intervalo de estimativa, em fração do valor.
_MAX_INTERVAL_WIDTH = 0.45


@dataclass
class ProfitAudit:
    """Resultado da auditoria de um negócio potencial."""

    verdict: str = "indeterminado"
    confidence: float = 0.0
    #: Preço pedido pelo vendedor.
    asking_price: float = 0.0
    #: Valor de retalho estimado (preço a que carros iguais são ANUNCIADOS).
    retail_estimate: float = 0.0
    #: Receita realista de venda, já descontada a negociação e a liquidez.
    realistic_sale_price: float = 0.0
    #: Preço realista de compra, se houver margem de negociação do lado da compra.
    realistic_buy_price: float = 0.0
    total_acquisition_cost: float = 0.0
    selling_cost: float = 0.0
    iva_margem: float = 0.0
    gross_spread: float = 0.0
    net_profit: float = 0.0
    net_margin_pct: float = 0.0
    roi_pct: float = 0.0
    roi_annualized_pct: float = 0.0
    days_to_sell: int = 60
    break_even_price: float = 0.0
    #: Lucro no cenário pessimista (limite inferior do intervalo de estimativa).
    net_profit_worst_case: float = 0.0
    cost_breakdown: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    realism_version: str = REALISM_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _round_costs(costs: Any) -> Dict[str, float]:
    return {
        "registo_propriedade": round(costs.registo_propriedade, 2),
        "isv": round(costs.isv, 2),
        "legalizacao": round(costs.legalization, 2),
        "ipo": round(costs.ipo, 2),
        "recondicionamento": round(costs.reconditioning, 2),
        "transporte": round(costs.transport, 2),
        "outros": round(costs.other, 2),
        "iuc_anual": round(costs.iuc_year, 2),
    }


def realistic_sale_price(
    retail_estimate: float,
    *,
    seller_type: str = "unknown",
    days_to_sell: int = 60,
    has_damage: bool = False,
    damage_severity: Optional[str] = None,
) -> float:
    """Converte uma estimativa de preço PEDIDO em receita realista de venda.

    Os comparáveis do mercado são anúncios, não escrituras. Vender ao preço
    mediano anunciado não acontece: há negociação e há o custo de esperar.
    Esta função aplica esses dois descontos, e ainda o efeito do dano
    declarado — um carro com histórico visível não atinge o preço mediano
    mesmo depois de reparado.

    Args:
        retail_estimate: mediana/estimativa de preço pedido para o modelo.
        seller_type: quem vende no fim (define a margem de negociação).
        days_to_sell: dias esperados em stock.
        has_damage: se há dano declarado.
        damage_severity: ``"total"`` (salvado) ou ``"cosmetico"``.

    Returns:
        Receita esperada, em euros, antes de custos de venda.
    """
    if retail_estimate <= 0:
        return 0.0
    discount = _ASK_TO_DEAL_DISCOUNT.get(
        str(seller_type or "unknown").lower(), _ASK_TO_DEAL_DISCOUNT["unknown"]
    )
    discount += _liquidity_discount(days_to_sell)
    if has_damage:
        # Um salvado transacciona muito abaixo do equivalente sem histórico,
        # mesmo reparado: o registo fica associado à matrícula.
        discount += 0.30 if damage_severity == "total" else 0.05
    return round(retail_estimate * max(0.25, 1.0 - discount), 2)


def audit_deal(
    *,
    asking_price: float,
    retail_estimate: float,
    retail_low: Optional[float] = None,
    retail_high: Optional[float] = None,
    valuation_confidence: float = 0.0,
    comparables_count: int = 0,
    year: Optional[int] = None,
    km: Optional[int] = None,
    engine_cc: Optional[int] = None,
    co2_gkm: Optional[float] = None,
    fuel_type: str = "gasolina",
    vehicle_type: str = "carros",
    is_national: Optional[bool] = None,
    country: str = "PT",
    seller_type: str = "unknown",
    condition_score: Optional[float] = None,
    has_damage: bool = False,
    damage_severity: Optional[str] = None,
    days_to_sell: int = 60,
    repair_costs: Optional[float] = None,
    transport_cost: Optional[float] = None,
    professional_reseller: bool = True,
    from_eu: bool = True,
) -> ProfitAudit:
    """Audita um negócio: o preço é realista, e o lucro sobrevive aos custos?

    Devolve sempre um :class:`ProfitAudit`. O veredito é um de:

    ``negocio``
        Lucro líquido positivo e material, sustentado por evidência
        suficiente.
    ``marginal``
        Lucro positivo mas abaixo do que compensa o risco e o trabalho.
    ``sem_margem``
        Depois de custos reais, não sobra nada.
    ``suspeito``
        O desconto é grande demais para ser verdade — erro de dados,
        salvado não declarado ou fraude.
    ``indeterminado``
        Não há evidência para decidir. Não é um "não"; é um "não sei",
        que é uma resposta diferente e honesta.
    """
    audit = ProfitAudit(
        asking_price=round(float(asking_price or 0.0), 2),
        retail_estimate=round(float(retail_estimate or 0.0), 2),
        days_to_sell=max(1, int(days_to_sell or 60)),
    )

    # ── 1. Pré-condições ────────────────────────────────────────────────
    if asking_price <= 0:
        audit.reasons.append("Preço pedido ausente ou inválido.")
        return audit
    if retail_estimate <= 0:
        audit.reasons.append("Sem estimativa de valor de mercado.")
        return audit

    # Evidência insuficiente não produz um número; produz uma abstenção.
    weak_evidence: List[str] = []
    if comparables_count and comparables_count < _MIN_COMPARABLES:
        weak_evidence.append(
            f"Apenas {comparables_count} comparáveis (mínimo {_MIN_COMPARABLES})."
        )
    if retail_low and retail_high and retail_estimate > 0:
        width = (retail_high - retail_low) / retail_estimate
        if width > _MAX_INTERVAL_WIDTH:
            weak_evidence.append(
                f"Intervalo de estimativa muito largo ({width:.0%} do valor)."
            )
    if valuation_confidence and valuation_confidence < 0.35:
        weak_evidence.append(f"Confiança da avaliação baixa ({valuation_confidence:.0%}).")

    # ── 2. Receita realista ─────────────────────────────────────────────
    sale = realistic_sale_price(
        retail_estimate,
        seller_type="profissional" if professional_reseller else "particular",
        days_to_sell=audit.days_to_sell,
        has_damage=has_damage,
        damage_severity=damage_severity,
    )
    audit.realistic_sale_price = sale
    audit.realistic_buy_price = round(float(asking_price), 2)

    # ── 3. Custos de aquisição ──────────────────────────────────────────
    imported = (
        False if is_national is True
        else True if (is_national is False or str(country).upper() != "PT")
        else False
    )
    transport = (
        float(transport_cost)
        if transport_cost is not None
        else _TRANSPORT_BY_COUNTRY.get(str(country).upper(), 0.0)
    )
    recon = (
        float(repair_costs)
        if repair_costs is not None
        else estimate_reconditioning(condition_score, vehicle_type, asking_price)
    )
    if has_damage and repair_costs is None:
        # Um dano declarado tem custo próprio, acima do recondicionamento
        # normal de preparação para venda.
        recon += 3500.0 if damage_severity == "total" else 600.0

    reg_year = (
        int(year) if year
        else datetime.now().year - 8   # idade neutra quando o ano é desconhecido
    )
    costs = calculate_transaction_costs(
        asking_price=asking_price,
        engine_cc=int(engine_cc or 1500),
        co2_gkm=co2_gkm,
        fuel_type=fuel_type,
        year=reg_year,
        vehicle_type=vehicle_type,
        is_national=not imported,
        from_eu=from_eu,
        condition_score=condition_score,
        repair_costs=recon,
        transport_cost=transport,
        needs_ipo=True,
    )
    audit.cost_breakdown = _round_costs(costs)
    audit.total_acquisition_cost = round(costs.total_cost, 2)

    # ── 4. Custos de venda ──────────────────────────────────────────────
    selling = calculate_selling_costs(
        sale, days_to_sell=audit.days_to_sell, vehicle_type=vehicle_type
    )
    audit.selling_cost = round(selling["total"], 2)

    # ── 5. IVA do regime da margem ──────────────────────────────────────
    # Só o revendedor profissional o entrega, e apenas sobre a margem
    # positiva. Ignorá-lo sobrestimava o lucro em ~23% da margem bruta.
    margin_before_vat = sale - costs.total_cost
    audit.iva_margem = (
        round(max(0.0, margin_before_vat) * IVA_RATE / (1 + IVA_RATE), 2)
        if professional_reseller else 0.0
    )

    # ── 6. Resultado ────────────────────────────────────────────────────
    audit.gross_spread = round(retail_estimate - asking_price, 2)
    net = margin_before_vat - selling["total"] - audit.iva_margem
    audit.net_profit = round(net, 2)
    audit.net_margin_pct = round(net / sale * 100.0, 2) if sale > 0 else 0.0
    invested = costs.total_cost
    audit.roi_pct = round(net / invested * 100.0, 2) if invested > 0 else 0.0
    audit.roi_annualized_pct = round(
        audit.roi_pct * (365.0 / audit.days_to_sell), 2
    )
    # Preço máximo de compra para não perder dinheiro: útil para negociar.
    fixed_overhead = costs.acquisition_costs + selling["total"] + audit.iva_margem
    audit.break_even_price = round(max(0.0, sale - fixed_overhead), 2)

    # Cenário pessimista: e se o carro só valer o limite inferior do intervalo?
    if retail_low and retail_low > 0:
        worst_sale = realistic_sale_price(
            retail_low,
            seller_type="profissional" if professional_reseller else "particular",
            days_to_sell=audit.days_to_sell,
            has_damage=has_damage,
            damage_severity=damage_severity,
        )
        worst_selling = calculate_selling_costs(
            worst_sale, days_to_sell=audit.days_to_sell, vehicle_type=vehicle_type
        )
        worst_margin = worst_sale - costs.total_cost
        worst_vat = (
            max(0.0, worst_margin) * IVA_RATE / (1 + IVA_RATE)
            if professional_reseller else 0.0
        )
        audit.net_profit_worst_case = round(
            worst_margin - worst_selling["total"] - worst_vat, 2
        )
    else:
        audit.net_profit_worst_case = audit.net_profit

    # ── 7. Sinais de risco ──────────────────────────────────────────────
    discount_vs_retail = (retail_estimate - asking_price) / retail_estimate
    if discount_vs_retail > 0.55:
        audit.risk_flags.append(
            f"Preço {discount_vs_retail:.0%} abaixo do mercado: verificar salvado, "
            "penhora, quilometragem adulterada ou anúncio fraudulento."
        )
    if audit.roi_pct > _IMPLAUSIBLE_ROI:
        audit.risk_flags.append(
            f"ROI de {audit.roi_pct:.0f}% não é plausível num usado — "
            "assumir erro de dados até prova em contrário."
        )
    if imported and not co2_gkm:
        audit.risk_flags.append(
            "Importado sem CO2 conhecido: o ISV é uma estimativa e pode variar "
            "em centenas de euros."
        )
    if has_damage:
        audit.risk_flags.append(
            f"Dano declarado ({damage_severity or 'não especificado'}); "
            "custo de reparação é a maior incerteza do negócio."
        )
    if km and year:
        age = max(1, datetime.now().year - int(year))
        if km / age > 45000:
            audit.risk_flags.append(
                f"Média de {km / age:,.0f} km/ano — desgaste acima do normal."
            )
    audit.reasons.extend(weak_evidence)

    # ── 8. Veredito ─────────────────────────────────────────────────────
    if weak_evidence and len(weak_evidence) >= 2:
        audit.verdict = "indeterminado"
        audit.confidence = round(min(0.3, valuation_confidence), 3)
        audit.reasons.insert(0, "Evidência insuficiente para uma decisão fiável.")
        return audit

    if audit.roi_pct > _IMPLAUSIBLE_ROI or discount_vs_retail > 0.55:
        audit.verdict = "suspeito"
        audit.confidence = round(valuation_confidence * 0.5, 3)
        audit.reasons.insert(
            0, "Margem boa demais para ser verdadeira; exige verificação humana."
        )
        return audit

    if net < 0:
        audit.verdict = "sem_margem"
        audit.reasons.insert(
            0,
            f"Depois de custos reais ({audit.total_acquisition_cost:,.0f} € de "
            f"aquisição + {audit.selling_cost:,.0f} € de venda + "
            f"{audit.iva_margem:,.0f} € de IVA), o negócio dá prejuízo.",
        )
    elif net < _MIN_VIABLE_PROFIT:
        audit.verdict = "marginal"
        audit.reasons.insert(
            0,
            f"Lucro líquido de {net:,.0f} € não compensa o risco e o capital "
            f"imobilizado durante {audit.days_to_sell} dias.",
        )
    elif audit.net_profit_worst_case < 0:
        audit.verdict = "marginal"
        audit.reasons.insert(
            0,
            "Lucro positivo no cenário central mas negativo no limite inferior "
            "da estimativa: o negócio depende de vender acima da média.",
        )
    else:
        audit.verdict = "negocio"
        audit.reasons.insert(
            0,
            f"Lucro líquido de {net:,.0f} € ({audit.roi_pct:.1f}% ROI, "
            f"{audit.roi_annualized_pct:.0f}% anualizado) após todos os custos.",
        )

    # Confiança final: a da avaliação, penalizada por evidência fraca e por
    # risco. Um lucro certo sobre uma avaliação incerta continua incerto.
    confidence = float(valuation_confidence or 0.0)
    if weak_evidence:
        confidence *= 0.7
    if audit.risk_flags:
        confidence *= 0.8
    audit.confidence = round(max(0.0, min(1.0, confidence)), 3)
    return audit


def audit_from_valuation(
    vehicle: Dict[str, Any], valuation: Dict[str, Any]
) -> ProfitAudit:
    """Adapta a saída de :meth:`HybridValuator.estimate` para :func:`audit_deal`.

    Ponte entre o motor de avaliação existente e a auditoria de realismo,
    para que o chamador não tenha de conhecer os dois formatos.
    """
    year = vehicle.get("year")
    country = str(vehicle.get("country") or "PT").upper()
    days = int(vehicle.get("days_to_sell") or 60)

    return audit_deal(
        asking_price=float(vehicle.get("price") or 0.0),
        retail_estimate=float(valuation.get("estimated_value") or 0.0),
        retail_low=valuation.get("value_low"),
        retail_high=valuation.get("value_high"),
        valuation_confidence=float(valuation.get("confidence") or 0.0),
        comparables_count=int(valuation.get("comparables_count") or 0),
        year=int(year) if year else None,
        km=vehicle.get("km"),
        engine_cc=vehicle.get("engine_size"),
        co2_gkm=vehicle.get("co2_gkm"),
        fuel_type=str(vehicle.get("fuel_type") or "gasolina"),
        vehicle_type=str(vehicle.get("vehicle_type") or "carros"),
        is_national=vehicle.get("is_national"),
        country=country,
        seller_type=str(vehicle.get("seller_type") or "unknown"),
        condition_score=vehicle.get("condition_score"),
        has_damage=bool(vehicle.get("has_damage")),
        damage_severity=vehicle.get("damage_severity"),
        days_to_sell=days,
    )


__all__ = [
    "ProfitAudit",
    "REALISM_VERSION",
    "IVA_RATE",
    "audit_deal",
    "audit_from_valuation",
    "realistic_sale_price",
]
