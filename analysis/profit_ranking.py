"""
Profit ranking — which vehicles actually make money in Portugal (2026).

Two complementary views:

``rank_models``
    Structural view. For every model in the market reference, simulate the
    classic arbitrage — buy from a private seller, recondition, resell at
    professional price — and rank by profit and by annualised return on
    capital. Needs no database, so it works on day one.

``rank_listings``
    Operational view. Rank the listings actually in the database by realistic
    net profit, using the same cost model.

Why annualised ROI matters
--------------------------
A Jaguar with 3.000 € of margin that sits 95 days in stock returns less per
euro-year than a Clio with 1.100 € of margin that sells in 42 days. Ranking by
raw margin is how resellers end up with dead capital, so both figures are
always reported.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from valuation.market_reference import (
    estimate_reference_value,
    load_reference,
    residual_factor,
)
from valuation.price_drivers import BRAND_LIQUIDITY, DEFAULT_LIQUIDITY
from valuation.pt_fiscal import (
    calculate_selling_costs,
    calculate_transaction_costs,
    estimate_reconditioning,
)

logger = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now().year

# Observed structure of the Portuguese market.
#
# The particular→stand spread is NOT constant in percentage terms: it is wide
# at the bottom of the market and thin at the top. A 3.000 € Clio bought from a
# private seller retails around 4.300 € at a stand (+40%); a 45.000 € Classe E
# retails at maybe +10%, because buyers at that level are informed, the stock is
# financed and stands compete directly. Using a flat markup makes every ranking
# collapse into "the most expensive car wins", which is false.
#
# (upper price bound, private discount, professional markup)
_SPREAD_BY_PRICE_BAND: List[tuple] = [
    (3000, 0.18, 0.42),
    (6000, 0.16, 0.34),
    (10000, 0.14, 0.26),
    (15000, 0.12, 0.21),
    (25000, 0.10, 0.16),
    (40000, 0.08, 0.12),
    (float("inf"), 0.07, 0.10),
]

# What can still be negotiated off a private seller's asking price.
NEGOTIATION_MARGIN = 0.04

# Backwards-compatible defaults (mid-market band).
PRIVATE_DISCOUNT = 0.12
PROFESSIONAL_MARKUP = 0.21

# Minimum thresholds to consider an operation worth doing.
MIN_ABSOLUTE_PROFIT = 700.0
MIN_ROI_PCT = 8.0

# Risk of the operation going wrong (hidden damage, no buyer, price drop while
# in stock). Grows with ticket size — a 40.000 € mistake is unrecoverable.
_RISK_DISCOUNT_BY_VALUE: List[tuple] = [
    (5000, 0.02),
    (15000, 0.03),
    (30000, 0.05),
    (float("inf"), 0.07),
]


def _spread_for(value: float) -> tuple:
    for ceiling, discount, markup in _SPREAD_BY_PRICE_BAND:
        if value <= ceiling:
            return discount, markup
    return PRIVATE_DISCOUNT, PROFESSIONAL_MARKUP


def _risk_discount(value: float) -> float:
    for ceiling, pct in _RISK_DISCOUNT_BY_VALUE:
        if value <= ceiling:
            return pct
    return 0.07


@dataclass
class ProfitOpportunity:
    """A single ranked buy/recondition/resell opportunity."""

    label: str
    brand: str
    model: str
    year: int
    age: int
    segment: str
    vehicle_type: str
    market_value: float
    buy_price: float
    sell_price: float
    acquisition_costs: float
    reconditioning: float
    selling_costs: float
    total_invested: float
    net_profit: float
    margin_pct: float
    roi_pct: float
    days_to_sell: int
    roi_annualized_pct: float
    liquidity_factor: float
    confidence: float
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _liquidity(brand: str) -> Dict[str, float]:
    """Brand liquidity, tolerant to casing and accents ("bmw" → "BMW")."""
    raw = (brand or "").strip()
    if raw in BRAND_LIQUIDITY:
        return BRAND_LIQUIDITY[raw]
    try:
        from valuation.deal_scorer_unified import canonicalize_brand

        canonical = canonicalize_brand(raw)
        if canonical in BRAND_LIQUIDITY:
            return BRAND_LIQUIDITY[canonical]
    except Exception:  # pragma: no cover
        pass
    lowered = raw.lower()
    for key, value in BRAND_LIQUIDITY.items():
        if key.lower() == lowered:
            return value
    return DEFAULT_LIQUIDITY


def _title(text: str) -> str:
    return " ".join(w.capitalize() for w in str(text or "").split())


def evaluate_opportunity(
    brand: str,
    model: str,
    year: int,
    *,
    km: Optional[int] = None,
    fuel_type: str = "gasolina",
    vehicle_type: str = "carros",
    engine_cc: Optional[int] = None,
    condition_score: float = 6.0,
    is_national: bool = True,
    buy_price: Optional[float] = None,
    market_value: Optional[float] = None,
) -> Optional[ProfitOpportunity]:
    """
    Simulate one buy/recondition/resell cycle with the full real cost stack.

    ``buy_price`` overrides the simulated private-seller price, which is what
    makes this reusable for real listings.
    """
    ref = estimate_reference_value(
        brand=brand,
        model=model,
        year=year,
        km=km,
        fuel_type=fuel_type,
        vehicle_type=vehicle_type,
        engine_cc=engine_cc,
    )
    value = market_value if market_value else ref["value"]
    if not value or value <= 0:
        return None

    age = max(0, CURRENT_YEAR - int(year))
    is_moto = str(vehicle_type).lower().startswith("moto")

    # Buy side: private seller, after negotiation. Spread depends on the price
    # band — the bottom of the market is where the percentage margin lives.
    private_discount, professional_markup = _spread_for(value)
    if buy_price is None:
        buy_price = value * (1 - private_discount) * (1 - NEGOTIATION_MARGIN)
    buy_price = float(buy_price)

    # Sell side: professional retail price, net of the risk of the operation
    # not going as planned (hidden damage, no buyer, price drift in stock).
    sell_price = value * (1 + professional_markup) * (1 - _risk_discount(value))

    recon = estimate_reconditioning(condition_score, vehicle_type, buy_price)

    liq = _liquidity(brand)
    days = int(liq["days"])

    costs = calculate_transaction_costs(
        asking_price=buy_price,
        engine_cc=engine_cc or (650 if is_moto else 1600),
        co2_gkm=None,
        fuel_type=fuel_type,
        year=int(year),
        vehicle_type=vehicle_type,
        is_national=is_national,
        condition_score=condition_score,
        repair_costs=recon,
    )
    selling = calculate_selling_costs(
        sell_price, days_to_sell=days, vehicle_type=vehicle_type
    )

    invested = costs.total_cost
    net = sell_price - invested - selling["total"]
    roi = (net / invested * 100.0) if invested > 0 else 0.0
    roi_annual = roi * (365.0 / max(1, days))

    notes: List[str] = list(costs.notes)
    if ref.get("confidence", 0) < 0.5:
        notes.append("Referência de baixa confiança: validar com anúncios reais.")
    if costs.iuc_year > 300:
        notes.append(
            f"IUC de {costs.iuc_year:.0f} €/ano trava a procura na revenda."
        )
    if days > 75:
        notes.append(f"Rotação lenta ({days} dias): capital preso.")

    return ProfitOpportunity(
        label=f"{_title(brand)} {_title(model)} {year}",
        brand=_title(brand),
        model=_title(model),
        year=int(year),
        age=age,
        segment=ref.get("segment", "media"),
        vehicle_type=vehicle_type,
        market_value=round(value, 2),
        buy_price=round(buy_price, 2),
        sell_price=round(sell_price, 2),
        acquisition_costs=costs.acquisition_costs,
        reconditioning=recon,
        selling_costs=selling["total"],
        total_invested=invested,
        net_profit=round(net, 2),
        margin_pct=round((net / sell_price * 100.0) if sell_price else 0.0, 2),
        roi_pct=round(roi, 2),
        days_to_sell=days,
        roi_annualized_pct=round(roi_annual, 2),
        liquidity_factor=float(liq["factor"]),
        confidence=float(ref.get("confidence", 0.0)),
        notes=notes,
    )


def rank_models(
    *,
    ages: Iterable[int] = (3, 5, 8, 12),
    vehicle_type: Optional[str] = None,
    min_profit: float = MIN_ABSOLUTE_PROFIT,
    min_roi: float = MIN_ROI_PCT,
    sort_by: str = "roi_annualized_pct",
    limit: int = 40,
    min_confidence: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Structural ranking across the whole reference catalogue.

    Args:
        ages: vehicle ages to simulate for every model.
        vehicle_type: "carros" | "motos" | None for both.
        sort_by: "roi_annualized_pct", "net_profit" or "roi_pct".
    """
    ref = load_reference()
    models: Dict[str, Any] = ref.get("models", {})
    results: List[ProfitOpportunity] = []

    moto_segments = {"moto", "scooter"}

    for key, entry in models.items():
        segment = entry.get("segment", "media")
        is_moto = segment in moto_segments
        vt = "motos" if is_moto else "carros"
        if vehicle_type and vt != vehicle_type:
            continue
        if entry.get("confidence") == "low" and min_confidence > 0.5:
            continue

        parts = key.split()
        brand = parts[0]
        model = " ".join(parts[1:]) or parts[0]
        # Brands whose name has two words in the reference keys.
        for two_word in ("mercedes-benz", "land rover", "alfa romeo", "harley-davidson"):
            if key.startswith(two_word):
                brand = two_word
                model = key[len(two_word):].strip()
                break

        fuel = "gasolina"
        if segment == "eletrico":
            fuel = "eletrico"

        for age in ages:
            year = CURRENT_YEAR - age
            if year < 1995:
                continue
            engine = 125 if segment == "scooter" else (650 if segment == "moto" else 1600)
            expected_km = (age * 5000) if is_moto else (age * 14000)
            opp = evaluate_opportunity(
                brand,
                model,
                year,
                km=expected_km,
                fuel_type=fuel,
                vehicle_type=vt,
                engine_cc=engine,
                condition_score=6.5,
            )
            if not opp:
                continue
            if opp.confidence < min_confidence:
                continue
            if opp.net_profit < min_profit or opp.roi_pct < min_roi:
                continue
            results.append(opp)

    key_fn = {
        "roi_annualized_pct": lambda o: o.roi_annualized_pct,
        "net_profit": lambda o: o.net_profit,
        "roi_pct": lambda o: o.roi_pct,
        "margin_pct": lambda o: o.margin_pct,
    }.get(sort_by, lambda o: o.roi_annualized_pct)

    results.sort(key=key_fn, reverse=True)
    return [o.to_dict() for o in results[:limit]]


def rank_listings(
    listings: Iterable[Dict[str, Any]],
    *,
    min_profit: float = MIN_ABSOLUTE_PROFIT,
    min_roi: float = MIN_ROI_PCT,
    sort_by: str = "roi_annualized_pct",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Rank real listings by realistic net profit.

    Each listing needs at least ``brand``, ``model``, ``year`` and ``price``.
    ``estimated_value`` is used when present, otherwise the market reference.
    """
    out: List[Dict[str, Any]] = []
    for item in listings:
        try:
            price = float(item.get("price") or 0)
            if price <= 0:
                continue
            opp = evaluate_opportunity(
                brand=item.get("brand") or "",
                model=item.get("model") or "",
                year=int(item.get("year") or CURRENT_YEAR - 8),
                km=item.get("km"),
                fuel_type=str(item.get("fuel_type") or "gasolina"),
                vehicle_type=str(item.get("vehicle_type") or "carros"),
                engine_cc=item.get("engine_size"),
                condition_score=float(item.get("condition_score") or 6.0),
                is_national=bool(item.get("is_national", True)),
                buy_price=price,
                market_value=item.get("estimated_value"),
            )
            if not opp:
                continue
            if opp.net_profit < min_profit or opp.roi_pct < min_roi:
                continue
            row = opp.to_dict()
            row["url"] = item.get("url")
            row["source"] = item.get("source")
            row["listing_id"] = item.get("id")
            row["title"] = item.get("title")
            out.append(row)
        except Exception as exc:  # pragma: no cover - never break the batch
            logger.debug("Listagem ignorada no ranking: %s", exc)

    out.sort(key=lambda r: r.get(sort_by, 0), reverse=True)
    return out[:limit]


def rank_listings_from_db(limit: int = 50, **kwargs) -> List[Dict[str, Any]]:
    """Convenience wrapper that pulls active listings from the database."""
    from database.db import get_db_context
    from database.models import Vehicle

    with get_db_context() as db:
        vehicles = (
            db.query(Vehicle)
            .filter(Vehicle.is_active.is_(True), Vehicle.price.isnot(None))
            .all()
        )
        rows = [
            {
                "id": v.id,
                "brand": v.brand,
                "model": v.model,
                "year": v.year,
                "km": v.km,
                "price": v.price,
                "estimated_value": v.estimated_value,
                "fuel_type": v.fuel_type.value if v.fuel_type else None,
                "vehicle_type": v.vehicle_type.value if v.vehicle_type else "carros",
                "engine_size": v.engine_size,
                "condition_score": v.condition_score,
                "url": v.url,
                "title": v.title,
                "source": v.source.value if v.source else None,
            }
            for v in vehicles
        ]
    return rank_listings(rows, limit=limit, **kwargs)


def summary_by_segment(ranked: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Aggregate a ranking by segment — where the money structurally is."""
    agg: Dict[str, Dict[str, float]] = {}
    for row in ranked:
        seg = row.get("segment", "desconhecido")
        bucket = agg.setdefault(
            seg, {"n": 0, "avg_profit": 0.0, "avg_roi": 0.0, "avg_days": 0.0}
        )
        bucket["n"] += 1
        bucket["avg_profit"] += row.get("net_profit", 0.0)
        bucket["avg_roi"] += row.get("roi_annualized_pct", 0.0)
        bucket["avg_days"] += row.get("days_to_sell", 0)
    for bucket in agg.values():
        n = max(1, bucket["n"])
        bucket["avg_profit"] = round(bucket["avg_profit"] / n, 2)
        bucket["avg_roi"] = round(bucket["avg_roi"] / n, 2)
        bucket["avg_days"] = round(bucket["avg_days"] / n, 1)
    return dict(sorted(agg.items(), key=lambda kv: kv[1]["avg_roi"], reverse=True))


__all__ = [
    "ProfitOpportunity",
    "evaluate_opportunity",
    "rank_models",
    "rank_listings",
    "rank_listings_from_db",
    "summary_by_segment",
]
