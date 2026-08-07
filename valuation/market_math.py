"""Aritmética central e defensiva do valor de mercado.

Este módulo é a **única** fonte de verdade para as três grandezas que o
sistema mostra ao utilizador:

* ``discount_eur = estimated_market_value - listing_price``
* ``discount_pct = discount_eur / listing_price * 100``
* o sinal/rótulo que daí decorre.

Perspetiva (fixa e não negociável)
----------------------------------
``discount_eur`` é sempre calculado do ponto de vista do **comprador**:

* **positivo** ⇒ o mercado vale mais do que o preço pedido (vantagem);
* **negativo** ⇒ o carro está pedido acima do mercado.

Exemplo do relatório de bugs (BMW Série 5 2021)::

    listing_price = 36_900 €
    market_value  = 34_728 €
    discount_eur  = -2_172 €
    discount_pct  = -5.885 %   → "5,9 % acima do mercado"

Nunca pode existir uma vantagem positiva com ``market_value < listing_price``.

Porquê um módulo próprio
------------------------
Antes desta correção existiam cinco convenções em simultâneo (percentagem
sobre o preço, sobre o valor estimado, lucro truncado em zero, percentil,
escala 0-100), cada uma numa camada diferente. O resultado eram diferenças
que não batiam certo com os preços mostrados e percentagens ``nan``.

Todo o valor derivado tem de nascer aqui, a partir dos valores **atuais**.
Nada é lido de campos derivados guardados na base de dados.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

__all__ = [
    "MIN_PLAUSIBLE_PRICE",
    "MAX_PLAUSIBLE_PRICE",
    "MAX_PLAUSIBLE_RATIO",
    "MIN_PLAUSIBLE_RATIO",
    "PriceDelta",
    "finite",
    "safe_ratio",
    "json_safe",
    "compute_delta",
    "round_estimate",
    "round_interval",
]

#: Abaixo disto um "preço" não é o preço total de um automóvel: é uma entrada,
#: uma mensalidade, um placeholder (1 €, 500 €) ou um erro de extração.
MIN_PLAUSIBLE_PRICE: float = 300.0

#: Acima disto é erro de extração (dígitos colados, cêntimos lidos como euros).
MAX_PLAUSIBLE_PRICE: float = 2_000_000.0

#: Um valor de mercado nunca pode ser um múltiplo absurdo do preço pedido.
#: Acima destes limites o par (preço, estimativa) é matematicamente possível
#: mas economicamente incoerente — o resultado é marcado como não fiável em
#: vez de ser mostrado como um negócio.
MAX_PLAUSIBLE_RATIO: float = 3.0
MIN_PLAUSIBLE_RATIO: float = 0.2


def finite(value: Any) -> Optional[float]:
    """Converte para ``float`` finito, ou devolve ``None``.

    Absorve ``None``, strings vazias, ``"nan"``, ``NaN``, ``±inf``, objetos
    numpy/pandas e qualquer coisa não convertível. É a porta de entrada de
    todos os números que circulam no pipeline de avaliação.

    >>> finite("1234.5"), finite(float("nan")), finite(float("inf")), finite(None)
    (1234.5, None, None, None)
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def safe_ratio(numerator: Any, denominator: Any) -> Optional[float]:
    """Divisão que nunca produz ``NaN``, ``inf`` nem ``ZeroDivisionError``."""
    num = finite(numerator)
    den = finite(denominator)
    if num is None or den is None or den == 0.0:
        return None
    out = num / den
    return out if math.isfinite(out) else None


def json_safe(payload: Any) -> Any:
    """Torna uma estrutura segura para JSON/API: ``NaN``/``inf`` viram ``None``.

    Percorre dicts, listas e tuplos recursivamente. Nenhuma resposta da API
    nem nenhum componente do frontend pode receber ``NaN`` ou ``Infinity``:
    é isso que produzia ``nan%`` no ecrã.
    """
    if isinstance(payload, dict):
        return {k: json_safe(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [json_safe(v) for v in payload]
    if isinstance(payload, bool) or payload is None:
        return payload
    if isinstance(payload, (int,)):
        return payload
    if isinstance(payload, float):
        return payload if math.isfinite(payload) else None
    # numpy / pandas escalares expõem .item()
    item = getattr(payload, "item", None)
    if callable(item):
        try:
            return json_safe(item())
        except Exception:  # pragma: no cover - escalar exótico
            return None
    return payload


@dataclass(frozen=True)
class PriceDelta:
    """Resultado da comparação entre preço pedido e valor de mercado.

    Quando ``ok`` é ``False`` todos os campos derivados são ``None`` — nunca
    zero e nunca ``NaN``. Zero significaria "está exatamente ao preço do
    mercado", que é uma afirmação bem diferente de "não sei".
    """

    listing_price: Optional[float]
    market_value: Optional[float]
    #: mercado − preço. Positivo ⇒ pedido abaixo do mercado (vantagem).
    discount_eur: Optional[float]
    #: desconto em % do preço pedido. Positivo ⇒ abaixo do mercado.
    discount_pct: Optional[float]
    #: quanto o pedido está acima do mercado, em % do mercado. Só quando > 0.
    above_market_pct: Optional[float]
    #: ``market_value / listing_price`` quando ambos são utilizáveis.
    ratio: Optional[float]
    ok: bool
    reason: Optional[str]

    @property
    def is_below_market(self) -> bool:
        return bool(self.ok and self.discount_eur is not None and self.discount_eur > 0)

    @property
    def is_above_market(self) -> bool:
        return bool(self.ok and self.discount_eur is not None and self.discount_eur < 0)

    def to_dict(self) -> Dict[str, Any]:
        return json_safe(asdict(self))


def _unusable(
    price: Optional[float], market: Optional[float], reason: str
) -> PriceDelta:
    return PriceDelta(
        listing_price=price,
        market_value=market,
        discount_eur=None,
        discount_pct=None,
        above_market_pct=None,
        ratio=None,
        ok=False,
        reason=reason,
    )


def compute_delta(
    listing_price: Any,
    market_value: Any,
    *,
    min_price: float = MIN_PLAUSIBLE_PRICE,
    max_price: float = MAX_PLAUSIBLE_PRICE,
    enforce_ratio_bounds: bool = True,
) -> PriceDelta:
    """Calcula a diferença e a percentagem, com todas as proteções.

    Args:
        listing_price: preço anunciado (qualquer coisa; é saneado).
        market_value: valor de mercado estimado. ``None`` é legítimo e
            significa "sem estimativa fiável".
        min_price: piso abaixo do qual o preço não é um preço total.
        max_price: teto acima do qual o preço é erro de extração.
        enforce_ratio_bounds: rejeita pares economicamente incoerentes
            (mercado > 3× o pedido, ou < 0,2×). Desligar apenas em testes
            que queiram observar o rácio bruto.

    Returns:
        :class:`PriceDelta`. ``ok=False`` sempre que a operação não é
        defensável — e nesse caso **nenhum** número derivado é produzido.

    >>> d = compute_delta(36_900, 34_728)
    >>> round(d.discount_eur, 2), round(d.discount_pct, 2)
    (-2172.0, -5.89)
    >>> compute_delta(36_900, None).ok
    False
    >>> compute_delta(0, 20_000).reason
    'preco_ausente_ou_implausivel'
    """
    price = finite(listing_price)
    market = finite(market_value)

    if price is None or price <= 0 or price < min_price or price > max_price:
        return _unusable(price, market, "preco_ausente_ou_implausivel")
    if market is None:
        return _unusable(price, None, "sem_estimativa")
    if market <= 0:
        return _unusable(price, market, "estimativa_nao_positiva")
    if market > max_price:
        return _unusable(price, market, "estimativa_implausivel")

    ratio = market / price
    if enforce_ratio_bounds and (
        ratio > MAX_PLAUSIBLE_RATIO or ratio < MIN_PLAUSIBLE_RATIO
    ):
        return _unusable(price, market, f"racio_incoerente({ratio:.2f}x)")

    discount_eur = market - price
    discount_pct = discount_eur / price * 100.0
    above_market_pct = (-discount_eur / market * 100.0) if discount_eur < 0 else None

    # Blindagem final: nenhuma destas grandezas pode sair não-finita.
    if not all(
        math.isfinite(v)
        for v in (discount_eur, discount_pct, ratio)
        if v is not None
    ):  # pragma: no cover - inalcançável com as guardas acima
        return _unusable(price, market, "resultado_nao_finito")

    return PriceDelta(
        listing_price=round(price, 2),
        market_value=round(market, 2),
        discount_eur=round(discount_eur, 2),
        discount_pct=round(discount_pct, 3),
        above_market_pct=round(above_market_pct, 3) if above_market_pct is not None else None,
        ratio=round(ratio, 4),
        ok=True,
        reason=None,
    )


def round_estimate(value: Any, *, uncertainty_pct: Optional[float] = None) -> Optional[float]:
    """Arredonda uma estimativa ao passo coerente com a sua incerteza.

    Mostrar «81.348 €» sugere uma precisão ao euro que nenhuma avaliação
    tem. A regra:

    * incerteza alta (> 25 % de largura relativa) **e** valor ≥ 50 000 € → 1 000 €
    * incerteza alta, ou valor ≥ 50 000 € → 500 €
    * caso contrário → 100 €

    >>> round_estimate(81_348.37, uncertainty_pct=60)
    81000.0
    >>> round_estimate(18_483.0)
    18500.0
    """
    val = finite(value)
    if val is None or val <= 0:
        return None
    unc = finite(uncertainty_pct) or 0.0
    if unc > 25.0 and val >= 50_000:
        step = 1000.0
    elif unc > 25.0 or val >= 50_000:
        step = 500.0
    else:
        step = 100.0
    return float(round(val / step) * step)


def round_interval(
    low: Any, high: Any, center: Any
) -> tuple[Optional[float], Optional[float]]:
    """Arredonda os limites de um intervalo mantendo ``low <= center <= high``.

    O limite inferior arredonda para baixo e o superior para cima: um
    intervalo apresentado nunca deve ser mais estreito do que o calculado.
    """
    c = finite(center)
    lo = finite(low)
    hi = finite(high)
    if c is None or c <= 0:
        return None, None
    width_pct = None
    if lo is not None and hi is not None and c > 0:
        width_pct = (hi - lo) / c * 100.0
    step = 1000.0 if (c >= 50_000 and (width_pct or 0) > 25) else (500.0 if c >= 50_000 else 100.0)
    out_lo = float(math.floor(lo / step) * step) if lo is not None and lo > 0 else None
    out_hi = float(math.ceil(hi / step) * step) if hi is not None and hi > 0 else None
    if out_lo is not None and out_hi is not None and out_lo >= out_hi:
        out_hi = out_lo + step
    return out_lo, out_hi
