"""Max Buy Price — o inverso acionável do motor de lucro.

O resto do sistema responde "quanto lucro tenho se comprar por X?".
Um comprador real precisa da pergunta invertida: "qual é o X máximo que
ainda me deixa lucro-alvo e ROI mínimo depois de TODOS os custos?".

Este módulo reutiliza *exatamente* o modelo de custos de
``deal_scorer_unified.calculate_profit_potential`` (impostos PT 2026,
recondicionamento, transporte, garantia estatutária, custo de capital)
em vez de duplicar matemática: uma bisseção monotónica sobre o preço de
compra encontra o ponto exato em que as duas restrições se cruzam.

Filosofia fail-closed herdada do serviço de valuation:
  * sem estimativa de saída -> sem max buy (None, nunca um número inventado);
  * o valor de saída usado é conservador (abaixo do valor de mercado de
    referência) porque ``estimated_value`` é um preço *de anúncio*, não uma
    venda realizada.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "calculate_max_buy_price",
    "buy_verdict",
]

#: Lucro líquido mínimo após venda para valer a operação (EUR).
DEFAULT_TARGET_PROFIT_EUR = 1000.0
#: Retorno mínimo sobre capital investido (lucro / investido).
DEFAULT_MIN_ROI = 0.12
#: Margem de segurança aplicada ao valor de saída antes de calcular.
DEFAULT_SAFETY_MARGIN_PCT = 0.03
#: Desconto conservador entre valor de mercado (ask) e saída esperada.
DEFAULT_EXIT_DISCOUNT_PCT = 0.05
#: Limiar de desconto face ao pedido acima do qual negociar primeiro.
NEGOTIATION_WINDOW_PCT = 0.10

_MAX_ITERATIONS = 48


def _profit_at_price(
    price: float,
    *,
    exit_value: float,
    cost_kwargs: Dict[str, Any],
) -> Dict[str, float]:
    """Lucro líquido pós-venda e ROI simulando compra a ``price``."""
    from valuation.deal_scorer_unified import calculate_profit_potential

    result = calculate_profit_potential(
        estimated_value=exit_value,
        asking_price=price,
        include_selling_costs=True,
        **cost_kwargs,
    )
    return {
        "net": float(result.get("net_profit_after_sale") or 0.0),
        "invested": float(result.get("total_cost") or 0.0),
    }


def _feasible(
    price: float,
    *,
    exit_value: float,
    target_profit: float,
    min_roi: float,
    cost_kwargs: Dict[str, Any],
) -> bool:
    """Compra a ``price`` cumpre lucro-alvo E ROI mínimo simultaneamente."""
    sim = _profit_at_price(price, exit_value=exit_value, cost_kwargs=cost_kwargs)
    if sim["net"] < target_profit:
        return False
    if sim["invested"] <= 0:
        return False
    return (sim["net"] / sim["invested"]) >= min_roi


def calculate_max_buy_price(
    estimated_value: Optional[float],
    *,
    vehicle_type: str = "carros",
    engine_cc: int = 1500,
    co2_gkm: float = 120.0,
    fuel_type: str = "gasolina",
    age_years: int = 5,
    is_national: bool = True,
    repair_costs: float = 0.0,
    condition_score: Optional[float] = None,
    transport_cost: float = 0.0,
    days_to_sell: int = 45,
    target_profit_eur: Optional[float] = None,
    min_roi: Optional[float] = None,
    safety_margin_pct: Optional[float] = None,
    exit_discount_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """Preço máximo de compra que ainda garante o alvo económico.

    Args:
        estimated_value: valor de mercado de referência (preço de anúncio
            típico). ``None`` => resultado fail-closed sem máximo.
        target_profit_eur: lucro líquido mínimo desejado (default 1000 €).
        min_roi: retorno mínimo sobre capital investido (default 12 %).
        safety_margin_pct: folga extra subtraída à saída (default 3 %).
        exit_discount_pct: desconto conservador ask->saída (default 5 %).

    Returns:
        dict com ``max_buy_price`` (None quando não há dados suficientes ou
        nem compra a 0 € cumpre o alvo), ``exit_value``, ``breakdown`` com a
        decomposição de custos no ponto ótimo, e ``constraints``.
    """
    est = float(estimated_value) if estimated_value else 0.0
    if est <= 0:
        return _empty_result(reason="no_estimate")

    target_profit = (
        float(target_profit_eur)
        if target_profit_eur is not None
        else DEFAULT_TARGET_PROFIT_EUR
    )
    roi_floor = float(min_roi) if min_roi is not None else DEFAULT_MIN_ROI
    margin = (
        float(safety_margin_pct)
        if safety_margin_pct is not None
        else DEFAULT_SAFETY_MARGIN_PCT
    )
    exit_disc = (
        float(exit_discount_pct)
        if exit_discount_pct is not None
        else DEFAULT_EXIT_DISCOUNT_PCT
    )

    exit_value = round(est * (1.0 - exit_disc) * (1.0 - margin), 2)

    cost_kwargs: Dict[str, Any] = dict(
        engine_cc=int(engine_cc or 1500),
        co2_gkm=float(co2_gkm or 120.0),
        fuel_type=fuel_type or "gasolina",
        age_years=int(age_years or 0),
        is_national=bool(is_national),
        repair_costs=float(repair_costs or 0.0),
        vehicle_type=vehicle_type or "carros",
        condition_score=condition_score,
        transport_cost=float(transport_cost or 0.0),
        days_to_sell=int(days_to_sell or 45),
    )

    # Nem comprando de graça o negócio fecha: falha explícita, não um número.
    if not _feasible(
        0.01,
        exit_value=exit_value,
        target_profit=target_profit,
        min_roi=roi_floor,
        cost_kwargs=cost_kwargs,
    ):
        return _empty_result(
            reason="infeasible_even_free",
            exit_value=exit_value,
            target_profit=target_profit,
            min_roi=roi_floor,
        )

    lo, hi = 0.01, exit_value
    # O limite superior teórico é a própria saída: comprar ao preço de saída
    # nunca dá lucro. A bisseção explora a monotonia decrescente do lucro.
    for _ in range(_MAX_ITERATIONS):
        mid = (lo + hi) / 2.0
        if _feasible(
            mid,
            exit_value=exit_value,
            target_profit=target_profit,
            min_roi=roi_floor,
            cost_kwargs=cost_kwargs,
        ):
            lo = mid
        else:
            hi = mid
        if hi - lo < 0.5:  # precisão de 50 cêntimos chega para negociar
            break

    max_price = round(lo, 2)
    sim = _profit_at_price(max_price, exit_value=exit_value, cost_kwargs=cost_kwargs)
    detail = _price_detail(
        max_price,
        exit_value=exit_value,
        cost_kwargs=cost_kwargs,
    )
    return {
        "max_buy_price": max_price,
        "exit_value": exit_value,
        "target_profit_eur": target_profit,
        "min_roi": roi_floor,
        "roi_at_max": round(sim["net"] / sim["invested"] * 100.0, 2) if sim["invested"] else None,
        "net_profit_at_max": round(sim["net"], 2),
        "breakdown": detail,
        "constraints": {
            "safety_margin_pct": margin,
            "exit_discount_pct": exit_disc,
            "days_to_sell": int(days_to_sell or 45),
        },
        "reason": None,
    }


def buy_verdict(
    asking_price: Optional[float],
    max_buy: Optional[Dict[str, Any]],
) -> str:
    """Classifica o pedido face ao máximo de compra.

    BUY ZONE   pedido <= max_buy
    NEGOTIATE  pedido dentro da janela de negociação acima do max_buy
    PASS       pedido claramente acima do max_buy (ou sem max_buy fiável)
    """
    if not max_buy or not max_buy.get("max_buy_price"):
        return "PASS"
    if not asking_price or asking_price <= 0:
        return "PASS"
    cap = float(max_buy["max_buy_price"])
    if asking_price <= cap:
        return "BUY_ZONE"
    if asking_price <= cap * (1.0 + NEGOTIATION_WINDOW_PCT):
        return "NEGOTIATE"
    return "PASS"


def _price_detail(
    price: float,
    *,
    exit_value: float,
    cost_kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    from valuation.deal_scorer_unified import calculate_transaction_costs, calculate_selling_costs

    costs = calculate_transaction_costs(
        asking_price=price,
        engine_cc=cost_kwargs["engine_cc"],
        co2_gkm=cost_kwargs["co2_gkm"],
        fuel_type=cost_kwargs["fuel_type"],
        year=__import__("datetime").datetime.now().year - cost_kwargs["age_years"],
        vehicle_type=cost_kwargs["vehicle_type"],
        is_national=cost_kwargs["is_national"],
        repair_costs=cost_kwargs["repair_costs"],
        needs_ipo=True,
        transport_cost=cost_kwargs["transport_cost"],
    )
    selling = calculate_selling_costs(
        exit_value, days_to_sell=cost_kwargs["days_to_sell"],
        vehicle_type=cost_kwargs["vehicle_type"],
    )
    return {
        "purchase": round(price, 2),
        "taxes_fees": round(costs.isv + costs.registo_propriedade + costs.legalization + costs.ipo, 2),
        "repairs": round(costs.reconditioning, 2),
        "transport": round(costs.transport, 2),
        "total_invested": round(costs.total_cost, 2),
        "selling_costs": {
            "warranty_provision": selling.get("warranty_provision"),
            "holding_cost": selling.get("holding_cost"),
            "listing_fees": selling.get("listing_fees"),
            "total": selling.get("total"),
        },
        "expected_exit": round(exit_value, 2),
    }


def _empty_result(
    reason: str,
    *,
    exit_value: Optional[float] = None,
    target_profit: Optional[float] = None,
    min_roi: Optional[float] = None,
) -> Dict[str, Any]:
    return {
        "max_buy_price": None,
        "exit_value": exit_value,
        "target_profit_eur": target_profit,
        "min_roi": min_roi,
        "roi_at_max": None,
        "net_profit_at_max": None,
        "breakdown": None,
        "constraints": None,
        "reason": reason,
    }
