"""Serviço de avaliação — o único ponto por onde os campos derivados nascem.

Antes desta correção existiam três grupos de escritores desligados entre si:

* **A** (noturno): ``estimated_value``, ``deal_score``, ``profit_potential``,
  ``profit_percentage``;
* **B** (só scripts manuais): ``credible_profit``, ``adjusted_estimated_value``,
  ``comparables_count``, ``valuation_confidence``, ``profit_is_publishable``,
  ``buyer_profit``, ``net_profit``…;
* **C** (API por anúncio): outro subconjunto ainda.

O dashboard ordenava por colunas do grupo B, que só eram atualizadas à mão,
enquanto o grupo A mexia no preço e na estimativa por baixo. Daí vinham as
"vantagens" de +25.553 € em carros pedidos acima do mercado.

Este módulo elimina o problema pela raiz: :func:`evaluate` produz **todos** os
campos derivados de uma vez, a partir dos valores atuais, e
:func:`revalue_database` escreve-os num único ``UPDATE`` por anúncio. Qualquer
escritor que não passe por aqui é um bug.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from valuation.canonical_vehicle import canonicalize
from valuation.comparables import ComparableIndex, MarketEstimate
from valuation.listing_guard import ListingFlags, dedupe, fingerprint, inspect_listing
from valuation.market_math import compute_delta, finite, json_safe
from valuation.opportunity import Opportunity, OpportunityLabel, classify

logger = logging.getLogger(__name__)

__all__ = [
    "VALUATION_VERSION",
    "DERIVED_FIELDS",
    "VehicleValuation",
    "ValuationService",
    "evaluate",
    "build_service",
]

#: Versão do algoritmo. Muda sempre que a semântica dos campos derivados muda,
#: para que a reavaliação incremental saiba o que está desatualizado.
VALUATION_VERSION = "v3.0"

#: Todos os campos derivados escritos em conjunto. Escrever um subconjunto
#: destes é exatamente o bug que este módulo elimina.
DERIVED_FIELDS: Tuple[str, ...] = (
    "estimated_value",
    "adjusted_estimated_value",
    "deal_score",
    "deal_grade",
    "profit_potential",
    "profit_percentage",
    "price_discount_percentage",
    "estimated_savings",
    "buyer_profit",
    "buyer_profit_margin",
    "buyer_roi",
    "net_profit",
    "credible_profit",
    "profit_is_publishable",
    "comparables_count",
    "valuation_confidence",
    "valuation_details",
)

#: Fontes de leilão: o preço é uma transação, não um ask de retalho. Não
#: servem de comparável e não são avaliadas com a lógica de retalho.
AUCTION_SOURCES = frozenset({
    "LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA",
    "AUTOLINE", "MARTELO", "PENHORADO",
})


@dataclass
class VehicleValuation:
    """Bloco derivado completo e internamente consistente de um anúncio."""

    vehicle_id: Any
    estimate: MarketEstimate
    opportunity: Opportunity
    flags: ListingFlags
    canonical: Dict[str, Any]
    fingerprint: str
    duplicate_of: Optional[Any] = None
    net_profit: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    # -- projeções ---------------------------------------------------------

    @property
    def deal_score(self) -> Optional[float]:
        """Score 0-10 ancorado no intervalo, limitado pela confiança.

        Sem estimativa não há score: ``None``, e não o antigo 5.0 neutro que
        aparecia como "meio bom" no ranking.
        """
        est = self.estimate
        opp = self.opportunity
        if est.value is None or opp.discount_pct is None:
            return None
        # 5 = exatamente no valor de mercado. ±1 ponto por cada 6 % de desvio.
        raw = 5.0 + max(-5.0, min(5.0, opp.discount_pct / 6.0))
        # A confiança limita a amplitude: dados fracos nunca produzem extremos.
        conf = est.confidence
        if conf >= 0.65:
            lo, hi = 0.0, 10.0
        elif conf >= 0.45:
            lo, hi = 2.0, 8.0
        elif conf >= 0.25:
            lo, hi = 3.5, 6.5
        else:
            lo, hi = 4.5, 5.5
        if opp.label in (OpportunityLabel.SUSPICIOUS, OpportunityLabel.NEEDS_REVIEW):
            hi = min(hi, 6.0)
        return round(max(lo, min(hi, raw)), 2)

    @property
    def deal_grade(self) -> str:
        return self.opportunity.label

    @property
    def is_publishable(self) -> bool:
        """Pode entrar na lista de melhores negócios sem validação humana."""
        return (
            self.opportunity.is_opportunity
            and self.flags.publishable
            and self.estimate.value is not None
            and self.estimate.comparables_used >= 3
            and self.estimate.confidence >= 0.45
        )

    def derived_fields(self) -> Dict[str, Any]:
        """Bloco pronto a escrever na base — todos os campos, de uma vez."""
        est = self.estimate
        opp = self.opportunity
        publishable = self.is_publishable
        # `credible_profit` é o desconto que sobrevive ao intervalo: a
        # distância ao limite INFERIOR, não ao valor central. É o número
        # defensável, e é `None` (não zero) quando não há evidência.
        credible = None
        if publishable and est.low is not None and opp.listing_price is not None:
            credible = round(max(0.0, est.low - opp.listing_price), 2)

        return {
            "estimated_value": est.value,
            "adjusted_estimated_value": est.low if publishable else est.value,
            "deal_score": self.deal_score,
            "deal_grade": self.deal_grade,
            "profit_potential": opp.discount_eur,
            "profit_percentage": opp.discount_pct,
            "price_discount_percentage": opp.discount_pct,
            "estimated_savings": opp.discount_eur if opp.is_opportunity else None,
            "buyer_profit": opp.discount_eur,
            "buyer_profit_margin": opp.discount_pct,
            "buyer_roi": opp.discount_pct,
            "net_profit": self.net_profit,
            "credible_profit": credible,
            "profit_is_publishable": bool(publishable),
            "comparables_count": est.comparables_used,
            "valuation_confidence": est.confidence_label,
            "valuation_details": self.details(),
        }

    def details(self) -> Dict[str, Any]:
        """Rasto completo da avaliação (guardado em ``valuation_details``)."""
        est = self.estimate
        return json_safe({
            "valuation_version": VALUATION_VERSION,
            "valued_at": datetime.now(timezone.utc).isoformat(),
            "status": est.status,
            "method": est.method,
            "reference_level": est.level,
            "estimated_value": est.value,
            "value_low": est.low,
            "value_high": est.high,
            "confidence": est.confidence,
            "confidence_label": est.confidence_label,
            "comparables_count": est.comparables_used,
            "comparables_rejected": est.comparables_rejected,
            "mean_similarity": est.mean_similarity,
            "dispersion_pct": est.dispersion_pct,
            "rejection_summary": est.rejection_summary,
            "comparables_used": [c.to_dict() for c in est.used[:15]],
            "valuation_explanation": est.explanation,
            "opportunity": self.opportunity.to_dict(),
            "canonical": self.canonical,
            "flags": self.flags.to_dict(),
            "fingerprint": self.fingerprint,
            "duplicate_of": self.duplicate_of,
            "notes": self.notes + est.notes,
        })

    def to_dict(self) -> Dict[str, Any]:
        out = dict(self.derived_fields())
        out["vehicle_id"] = self.vehicle_id
        return json_safe(out)


# ---------------------------------------------------------------------------
# Serviço
# ---------------------------------------------------------------------------


class ValuationService:
    """Avalia anúncios contra um índice de comparáveis coerente."""

    def __init__(
        self,
        index: ComparableIndex,
        *,
        duplicate_map: Optional[Dict[Any, Any]] = None,
        net_profit_fn: Optional[Callable[[Dict[str, Any], MarketEstimate], Optional[float]]] = None,
    ):
        self.index = index
        #: ``id do duplicado -> id do registo principal``
        self.duplicate_map: Dict[Any, Any] = duplicate_map or {}
        self._net_profit_fn = net_profit_fn or _default_net_profit

    # -- construção --------------------------------------------------------

    @classmethod
    def from_rows(
        cls, rows: Sequence[Dict[str, Any]], *, apply_dedupe: bool = True
    ) -> "ValuationService":
        """Constrói o serviço a partir de linhas brutas.

        Filtra o que não pode ser comparável (anúncios bloqueados, preços não
        totais, leilões) **antes** de indexar: um comparável mau contamina
        todos os outros anúncios do mesmo modelo.
        """
        eligible: List[Dict[str, Any]] = []
        duplicate_map: Dict[Any, Any] = {}
        prepared: List[Dict[str, Any]] = []

        for row in rows:
            data = dict(row)
            data["fingerprint"] = fingerprint(data)
            prepared.append(data)

        if apply_dedupe:
            for group in dedupe(prepared):
                for dup_id in group.duplicate_ids:
                    duplicate_map[dup_id] = group.primary_id

        for data in prepared:
            source = str(getattr(data.get("source"), "value", data.get("source")) or "").upper()
            if source in AUCTION_SOURCES:
                continue
            if data.get("id") in duplicate_map:
                continue  # duplicados não contam como comparáveis independentes
            if not inspect_listing(data).usable_as_comparable:
                continue
            eligible.append(data)

        logger.info(
            "Índice de comparáveis: %d elegíveis de %d anúncios (%d duplicados)",
            len(eligible), len(prepared), len(duplicate_map),
        )
        return cls(ComparableIndex.from_rows(eligible), duplicate_map=duplicate_map)

    # -- avaliação ---------------------------------------------------------

    def evaluate(self, vehicle: Dict[str, Any]) -> VehicleValuation:
        """Avalia um anúncio e devolve o bloco derivado completo."""
        data = dict(vehicle)
        fp = data.get("fingerprint") or fingerprint(data)
        data["fingerprint"] = fp
        vid = data.get("id")
        duplicate_of = self.duplicate_map.get(vid)
        canon = canonicalize(data)
        flags = inspect_listing(data)
        notes: List[str] = []

        source = str(getattr(data.get("source"), "value", data.get("source")) or "").upper()
        if source in AUCTION_SOURCES:
            notes.append(
                "Fonte de leilão: o preço é uma adjudicação, não um preço de "
                "retalho — não é comparável com anúncios de stand."
            )
        if duplicate_of is not None:
            notes.append(f"Duplicado do anúncio {duplicate_of}.")
        notes.extend(f"normalização: {n}" for n in canon.notes)

        # Anúncio bloqueado: não se avalia, não se compara, não se publica.
        if flags.blocking or not flags.price_is_total:
            estimate = MarketEstimate(
                value=None, low=None, high=None,
                status="anuncio_excluido",
                method="excluido_por_validacao",
                level=None, comparables_used=0, comparables_rejected=0,
                mean_similarity=None, dispersion_pct=None,
                confidence=0.0, confidence_label="sem_dados",
                explanation=(
                    "Anúncio excluído da avaliação: "
                    + ", ".join(flags.blocking or ("preço não é total",))
                    + "."
                ),
                notes=notes,
            )
        else:
            estimate = self.index.estimate(
                data,
                exclude_ids=[vid, duplicate_of] if duplicate_of is not None else [vid],
                exclude_fingerprints=[fp],
            )
            estimate.notes = list(estimate.notes) + notes

        opportunity = classify(
            listing_price=data.get("price"),
            market_value=estimate.value,
            market_low=estimate.low,
            market_high=estimate.high,
            confidence=estimate.confidence,
            confidence_label=estimate.confidence_label,
            comparables_count=estimate.comparables_used,
            risk_flags=list(flags.suspicious),
            blocking_flags=list(flags.blocking) + (
                [] if flags.price_is_total else ["preco_nao_total"]
            ),
        )

        return VehicleValuation(
            vehicle_id=vid,
            estimate=estimate,
            opportunity=opportunity,
            flags=flags,
            canonical=canon.to_dict(),
            fingerprint=fp,
            duplicate_of=duplicate_of,
            net_profit=self._net_profit_fn(data, estimate),
            notes=notes,
        )

    def evaluate_all(
        self, vehicles: Iterable[Dict[str, Any]]
    ) -> List[VehicleValuation]:
        return [self.evaluate(v) for v in vehicles]


def _default_net_profit(
    vehicle: Dict[str, Any], estimate: MarketEstimate
) -> Optional[float]:
    """Lucro líquido realista para revenda, ou ``None`` sem base para o dizer.

    Usa o limite **inferior** do intervalo como receita esperada (conservador)
    e o modelo fiscal português existente para os custos. Sem estimativa
    fiável não há lucro — nem zero, que sugeriria "sem margem".
    """
    price = finite(vehicle.get("price"))
    if price is None or price <= 0 or estimate.low is None:
        return None
    try:
        from valuation.pt_fiscal import (
            calculate_selling_costs,
            calculate_transaction_costs,
        )

        acquisition = calculate_transaction_costs(asking_price=price)
        selling = calculate_selling_costs(sale_price=estimate.low)
        total_cost = price + float(
            acquisition.get("total_cost", acquisition.get("total", 0.0)) or 0.0
        ) - price
        sell_cost = float(selling.get("total", 0.0) or 0.0)
        margin = estimate.low - price - total_cost - sell_cost
        # IVA do regime da margem (23 % sobre a margem positiva).
        if margin > 0:
            margin -= margin * 0.23 / 1.23
        return round(margin, 2)
    except Exception as exc:  # pragma: no cover - o modelo fiscal é aditivo
        logger.debug("Modelo fiscal indisponível: %s", exc)
        delta = compute_delta(price, estimate.low)
        return delta.discount_eur


# ---------------------------------------------------------------------------
# Conveniências
# ---------------------------------------------------------------------------


def build_service(
    rows: Optional[Sequence[Dict[str, Any]]] = None, *, limit: Optional[int] = None
) -> ValuationService:
    """Constrói o serviço a partir da base de dados (ou de linhas dadas)."""
    if rows is None:
        rows = load_market_rows(limit=limit)
    return ValuationService.from_rows(rows)


def load_market_rows(*, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Carrega da base os anúncios ativos que podem formar o mercado."""
    from database.db import get_db_context
    from database.models import Vehicle

    with get_db_context() as db:
        query = db.query(Vehicle).filter(
            Vehicle.is_active.is_(True),
            Vehicle.price.isnot(None),
            Vehicle.price > 0,
        )
        if limit:
            query = query.limit(limit)
        return [vehicle_to_dict(v) for v in query.all()]


def vehicle_to_dict(v: Any) -> Dict[str, Any]:
    """Projeta um ORM ``Vehicle`` para o dicionário que a avaliação consome."""

    def val(attr: str) -> Any:
        return getattr(getattr(v, attr, None), "value", getattr(v, attr, None))

    return {
        "id": v.id,
        "source": val("source"),
        "source_id": getattr(v, "source_id", None),
        "url": getattr(v, "url", None),
        "brand": v.brand,
        "normalized_brand": getattr(v, "normalized_brand", None),
        "model": v.model,
        "version": getattr(v, "version", None),
        "trim_level": getattr(v, "trim_level", None),
        "title": getattr(v, "title", None),
        "description": getattr(v, "description", None),
        "year": v.year,
        "km": v.km,
        "horsepower": getattr(v, "horsepower", None),
        "engine_size": getattr(v, "engine_size", None),
        "doors": getattr(v, "doors", None),
        "fuel_type": val("fuel_type"),
        "transmission": val("transmission"),
        "vehicle_type": val("vehicle_type"),
        "price": v.price,
        "price_kind": getattr(v, "price_kind", None),
        "currency": getattr(v, "currency", None),
        "price_rejection_reason": getattr(v, "price_rejection_reason", None),
        "location": getattr(v, "location", None),
        "district": getattr(v, "district", None),
        "seller_name": getattr(v, "seller_name", None),
        "seller_type": getattr(v, "seller_type", None),
        "condition_score": getattr(v, "condition_score", None),
        "has_accident": getattr(v, "has_accident", None),
        "has_damage": getattr(v, "has_damage", None),
        "is_national": getattr(v, "is_national", None),
        "quality_status": getattr(v, "quality_status", None),
        "first_seen": getattr(v, "first_seen", None),
        "last_seen": getattr(v, "last_seen", None),
    }


def evaluate(
    vehicle: Dict[str, Any], service: Optional[ValuationService] = None
) -> VehicleValuation:
    """Avalia um único anúncio (constrói o índice se não for fornecido)."""
    return (service or build_service()).evaluate(vehicle)


# ---------------------------------------------------------------------------
# Escrita atómica na base de dados
# ---------------------------------------------------------------------------

def revalue_database(*, batch_size: int = 500, force: bool = False) -> Dict[str, int]:
    """Reavalia a base inteira escrevendo **todos** os campos derivados.

    Substitui ``scripts/reprocess_db.py::step_revalue`` (que só escrevia 4
    campos e deixava o dashboard a ordernar por colunas congeladas). Cada
    anúncio recebe o seu bloco completo e consistente num único ``UPDATE``.

    Returns:
        Estatísticas da passagem (avaliados, insuficientes, excluídos, …).
    """
    from database.db import get_db_context
    from database.models import Vehicle

    rows = load_market_rows(limit=None)
    svc = ValuationService.from_rows(rows)
    by_id = {r["id"]: r for r in rows}

    stats = {
        "valued": 0, "insufficient": 0, "excluded": 0,
        "excellent": 0, "good": 0, "needs_review": 0,
        "errors": 0,
    }
    batch: List[VehicleValuation] = []

    def flush(rows_batch: Sequence[VehicleValuation]) -> None:
        ids = [b.vehicle_id for b in rows_batch]
        with get_db_context() as db:
            objs = db.query(Vehicle).filter(Vehicle.id.in_(ids)).all()
            objs_by_id = {o.id: o for o in objs}
            for b in rows_batch:
                o = objs_by_id.get(b.vehicle_id)
                if o is None:
                    continue
                fields = b.derived_fields()
                for k, val in fields.items():
                    setattr(o, k, val)
            db.commit()

    for r in rows:
        try:
            b = svc.evaluate(r)
        except Exception as exc:  # não deixar um erro afundar a passagem
            logger.warning("erro ao avaliar %s: %s", r.get("id"), exc)
            stats["errors"] += 1
            continue
        stats["valued" if b.estimate.value is not None else "insufficient"] += 1
        if b.opportunity.label == OpportunityLabel.EXCELLENT:
            stats["excellent"] += 1
        elif b.opportunity.label == OpportunityLabel.GOOD:
            stats["good"] += 1
        elif b.opportunity.label == OpportunityLabel.NEEDS_REVIEW:
            stats["needs_review"] += 1
        elif b.flags.blocking or not b.flags.price_is_total:
            stats["excluded"] += 1
        batch.append(b)
        if len(batch) >= batch_size:
            flush(batch)
            batch = []
    if batch:
        flush(batch)

    logger.info("Reavaliação coerente: %s", stats)
    return stats
