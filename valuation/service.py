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
from valuation.comparables import (
    CURRENT_SNAPSHOT,
    FUTURE,
    FRESH,
    HISTORICAL,
    HISTORICAL_SNAPSHOT,
    NOT_MEASURED,
    STALE,
    ComparableIndex,
    MarketEstimate,
    _insufficient,
    normalize_cutoff,
    resolve_freshness_config,
    row_freshness,
)
from valuation.ensemble import blend_estimate, reference_for
from valuation.listing_guard import ListingFlags, dedupe, fingerprint, inspect_listing
from valuation.market_math import compute_delta, finite, json_safe
from valuation.opportunity import Opportunity, OpportunityLabel, classify
from valuation.reliability import ReliabilityAssessment, assess as assess_reliability

logger = logging.getLogger(__name__)

__all__ = [
    "VALUATION_VERSION",
    "VALUATION_TARGET",
    "DERIVED_FIELDS",
    "VehicleValuation",
    "ValuationService",
    "evaluate",
    "build_service",
    "load_market_rows",
    "revalue_database",
]

#: Versão do algoritmo. Muda sempre que a semântica dos campos derivados muda,
#: para que a reavaliação incremental saiba o que está desatualizado.
VALUATION_VERSION = "v3.2"
VALUATION_TARGET = "asking_price"

# Sale/realized fields are accepted only when the input explicitly carries a
# ground-truth transaction.  The operational Vehicle schema has no such
# column; its ``price`` and ``PriceHistory`` are asking-price observations.
_GROUND_TRUTH_PRICE_KEYS = (
    "ground_truth_sale_price",
    "realized_sale_price",
    "sold_price",
    "transaction_price",
)
_GROUND_TRUTH_PROFIT_KEYS = ("ground_truth_realized_profit", "realized_profit")

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
    reliability: Optional[ReliabilityAssessment] = None
    notes: List[str] = field(default_factory=list)
    # Explicit provenance attached to every result.  ``ground_truth`` is
    # intentionally separate from the asking-price snapshot: a listing price
    # history is not a sold-price label.
    freshness: Dict[str, Any] = field(default_factory=dict)
    snapshot: str = CURRENT_SNAPSHOT
    target: str = VALUATION_TARGET
    ground_truth_available: Optional[bool] = None
    ground_truth: Dict[str, Any] = field(default_factory=dict)

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
            and self._freshness_allows_publish
            and self._profit_semantics_available
            and self.net_profit is not None
            and self.net_profit > 0
            and (self.reliability is None or self.reliability.is_publishable)
        )

    @property
    def _profit_semantics_available(self) -> bool:
        """Legacy manual objects remain readable; service results fail closed."""
        return self.ground_truth_available is not False

    @property
    def _freshness_allows_publish(self) -> bool:
        if not self.freshness:
            return True
        status = self.freshness.get("freshness", NOT_MEASURED)
        # Historical analysis is useful evidence, but it is never a current
        # opportunity.  A current publish requires a measured fresh snapshot.
        return status == FRESH

    def derived_fields(self) -> Dict[str, Any]:
        """Bloco pronto a escrever na base — todos os campos, de uma vez."""
        est = self.estimate
        opp = self.opportunity
        publishable = self.is_publishable
        # Profit não é a diferença entre dois preços pedidos. O único valor
        # publicável é o lucro líquido calculado depois dos custos fiscais e
        # operacionais; sem isso o campo tem de ficar desconhecido.
        # ``net_profit`` is a measured/ground-truth-dependent output.  A
        # current asking-price snapshot can support an asking-price delta, not
        # a realized resale profit.
        net_profit = (
            finite(self.net_profit)
            if self._profit_semantics_available
            else None
        )
        asking_price = finite(opp.listing_price)
        net_margin = (
            net_profit / asking_price * 100.0
            if net_profit is not None and asking_price and asking_price > 0
            else None
        )
        credible = round(net_profit, 2) if publishable and net_profit > 0 else None
        gross_discount = opp.discount_eur if opp.is_opportunity else None

        return {
            "estimated_value": est.value,
            "adjusted_estimated_value": est.low if publishable else est.value,
            "deal_score": self.deal_score,
            "deal_grade": self.deal_grade,
            "profit_potential": net_profit,
            "profit_percentage": net_margin,
            "price_discount_percentage": opp.discount_pct,
            "estimated_savings": gross_discount,
            "buyer_profit": net_profit,
            "buyer_profit_margin": net_margin,
            "buyer_roi": net_margin,
            "net_profit": net_profit,
            "credible_profit": credible,
            "profit_is_publishable": bool(publishable and net_profit is not None),
            "comparables_count": est.comparables_used,
            "valuation_confidence": est.confidence_label,
            "valuation_details": self.details(),
        }

    def _decision_block(self) -> Dict[str, Any]:
        """Max Buy Price + hard gates sobre os dados já disponíveis.

        Bloco de *decisão* (não é campo derivado da BD): vive dentro de
        ``valuation_details``. Fail-closed — qualquer peça em falta devolve
        um bloco vazio em vez de números inventados.
        """
        est = self.estimate
        opp = self.opportunity
        if est.value is None or not self.canonical:
            return {}
        try:
            from valuation.economics import buy_verdict, calculate_max_buy_price
            from valuation.gates import apply_hard_gates

            canon = self.canonical
            year = canon.get("year")
            age_years = (
                datetime.now(timezone.utc).year - int(year)
                if year
                else 5
            )
            # Lucro esperado: ground truth quando existe; senão a projecção
            # bruta ask vs mercado (claramente identificada como tal).
            expected_profit = self.net_profit
            profit_basis = "ground_truth"
            if expected_profit is None and opp.listing_price and opp.discount_eur:
                expected_profit = float(opp.discount_eur)
                profit_basis = "gross_projection"

            max_buy = calculate_max_buy_price(
                est.value,
                vehicle_type=canon.get("vehicle_type") or "carros",
                engine_cc=int(canon.get("engine_cc") or 0) or 1500,
                fuel_type=canon.get("fuel") or "gasolina",
                age_years=max(0, age_years),
                is_national=bool(canon.get("is_national", True)),
                days_to_sell=45,
            )
            verdict = buy_verdict(opp.listing_price, max_buy)
            gates = apply_hard_gates(
                confidence=est.confidence,
                expected_profit=expected_profit,
                discount_pct=opp.discount_pct,
                asking_price=opp.listing_price,
                max_buy_price=max_buy.get("max_buy_price"),
            )
            return {
                "profit_basis": profit_basis,
                "max_buy": max_buy,
                "price_verdict": verdict,
                "hard_gates": gates,
                "verdict": gates["verdict"] if gates["verdict"] != "BUY" else verdict,
            }
        except Exception as exc:  # noqa: BLE001 — decisão nunca quebra valuation
            logger.debug("decision block unavailable: %s", exc)
            return {}

    def details(self) -> Dict[str, Any]:
        """Rasto completo da avaliação (guardado em ``valuation_details``)."""
        est = self.estimate
        gt_available = bool(
            self.ground_truth_available
            if self.ground_truth_available is not None
            else self.ground_truth.get("available", False)
        )
        profit_status = (
            "MEASURED" if gt_available and self.net_profit is not None
            else "INCONCLUSIVE" if gt_available
            else NOT_MEASURED
        )
        ground_truth_sale = (
            finite(self.ground_truth.get("sale_price")) if gt_available else None
        )
        ground_truth_profit = (
            finite(self.ground_truth.get("realized_profit")) if gt_available else None
        )
        freshness = dict(self.freshness or {})
        # The estimate may have come through the ensemble, which constructs a
        # fresh MarketEstimate.  Service-level metadata is authoritative.
        freshness.setdefault("freshness", est.freshness)
        freshness.setdefault("age_hours", est.age_hours)
        freshness.setdefault("observed_at", est.observed_at)
        freshness.setdefault("cutoff", est.cutoff)
        freshness.setdefault("max_age_hours", est.max_age_hours)
        freshness.setdefault("snapshot", self.snapshot)
        return json_safe({
            "valuation_version": VALUATION_VERSION,
            "valued_at": datetime.now(timezone.utc).isoformat(),
            "status": est.status,
            "method": est.method,
            "reference_level": est.level,
            "estimated_value": est.value,
            "value_low": est.low,
            "value_high": est.high,
            "target": self.target,
            "target_field": self.target,
            "target_value": est.value,
            "asking_price": finite(self.opportunity.listing_price),
            "snapshot": self.snapshot,
            "cutoff": freshness.get("cutoff"),
            "max_age_hours": freshness.get("max_age_hours"),
            "freshness": freshness.get("freshness", NOT_MEASURED),
            "freshness_status": freshness.get("freshness", NOT_MEASURED),
            "age_hours": freshness.get("age_hours"),
            "observed_at": freshness.get("observed_at"),
            "observed_at_field": freshness.get("observed_at_field"),
            "snapshot_size": est.snapshot_size,
            "confidence": est.confidence,
            "confidence_label": est.confidence_label,
            "comparables_count": est.comparables_used,
            "comparables_rejected": est.comparables_rejected,
            "mean_similarity": est.mean_similarity,
            "dispersion_pct": est.dispersion_pct,
            "rejection_summary": est.rejection_summary,
            # Sinais adicionais do ensemble (transparência ML/referência).
            "ml_estimate": est.ml_estimate,
            "reference_estimate": est.reference_estimate,
            "comparables_used": [c.to_dict() for c in est.used[:15]],
            "valuation_explanation": est.explanation,
            "opportunity": self.opportunity.to_dict(),
            "canonical": self.canonical,
            "flags": self.flags.to_dict(),
            "fingerprint": self.fingerprint,
            "duplicate_of": self.duplicate_of,
            "reliability": self.reliability.to_dict() if self.reliability else None,
            # Bloco de decisão (max buy + gates) — projeção, não campo derivado.
            "decision": self._decision_block(),
            "semantics": {
                "target": self.target,
                "target_field": self.target,
                "ground_truth_available": gt_available,
                "profit_status": profit_status,
                # These fields are null unless the input explicitly contains
                # transaction ground truth.  They are never inferred from
                # ``asking_price`` or the listing-price history.
                "sale_price": ground_truth_sale,
                "realized_profit": ground_truth_profit,
            },
            "ground_truth": {
                "available": gt_available,
                "sale_price": ground_truth_sale,
                "realized_profit": ground_truth_profit,
                "observed_at": self.ground_truth.get("observed_at") if gt_available else None,
                "source": self.ground_truth.get("source") if gt_available else None,
            },
            "notes": self.notes + est.notes,
        })

    def to_dict(self) -> Dict[str, Any]:
        out = dict(self.derived_fields())
        out["vehicle_id"] = self.vehicle_id
        out["target"] = self.target
        out["target_field"] = self.target
        out["freshness"] = (self.freshness or {}).get("freshness", NOT_MEASURED)
        out["age_hours"] = (self.freshness or {}).get("age_hours")
        out["snapshot"] = self.snapshot
        out["ground_truth_available"] = bool(self.ground_truth_available)
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
        cutoff: Any = None,
        max_age_hours: Optional[float] = None,
        snapshot: str = CURRENT_SNAPSHOT,
        snapshot_type: Optional[str] = None,
    ):
        self.index = index
        #: ``id do duplicado -> id do registo principal``
        self.duplicate_map: Dict[Any, Any] = duplicate_map or {}
        if snapshot_type is not None:
            snapshot = snapshot_type
        inherited_cutoff = cutoff if cutoff is not None else getattr(index, "cutoff", None)
        configured_age = (
            max_age_hours
            if max_age_hours is not None
            else getattr(index, "max_age_hours", None)
        )
        self.cutoff, self.max_age_hours = resolve_freshness_config(
            inherited_cutoff, configured_age
        )
        self.snapshot = snapshot or getattr(index, "snapshot", CURRENT_SNAPSHOT)
        if self.snapshot not in (CURRENT_SNAPSHOT, HISTORICAL_SNAPSHOT):
            raise ValueError("snapshot deve ser 'current' ou 'historical'")
        self._freshness_enforced = (
            self.cutoff is not None or self.max_age_hours is not None
        )
        # A legacy custom callable remains supported, but its result is still
        # suppressed when the row has no explicit transaction ground truth.
        self._net_profit_fn = net_profit_fn or _ground_truth_net_profit

    # -- construção --------------------------------------------------------

    @classmethod
    def from_rows(
        cls,
        rows: Sequence[Dict[str, Any]],
        *,
        apply_dedupe: bool = True,
        cutoff: Any = None,
        max_age_hours: Optional[float] = None,
        snapshot: str = CURRENT_SNAPSHOT,
        snapshot_type: Optional[str] = None,
    ) -> "ValuationService":
        """Constrói o serviço a partir de linhas brutas.

        Filtra o que não pode ser comparável (anúncios bloqueados, preços não
        totais, leilões) **antes** de indexar: um comparável mau contamina
        todos os outros anúncios do mesmo modelo.
        """
        if snapshot_type is not None:
            snapshot = snapshot_type
        effective_cutoff, effective_age = resolve_freshness_config(
            cutoff, max_age_hours
        )
        if snapshot not in (CURRENT_SNAPSHOT, HISTORICAL_SNAPSHOT):
            raise ValueError("snapshot deve ser 'current' ou 'historical'")
        freshness_enforced = effective_cutoff is not None or effective_age is not None
        eligible: List[Dict[str, Any]] = []
        duplicate_map: Dict[Any, Any] = {}
        prepared: List[Dict[str, Any]] = []

        for row in rows:
            data = dict(row)
            data["fingerprint"] = fingerprint(data)
            prepared.append(data)

        if freshness_enforced:
            # Dedupe only inside the requested snapshot.  Otherwise an old
            # primary listing could hide a fresh duplicate and contaminate the
            # current index with stale identity decisions.
            snapshot_rows = []
            for data in prepared:
                temporal = row_freshness(
                    data,
                    cutoff=effective_cutoff,
                    max_age_hours=effective_age,
                    snapshot=snapshot,
                )
                allowed = (
                    temporal.get("freshness") == FRESH
                    if snapshot == CURRENT_SNAPSHOT
                    else temporal.get("freshness") == HISTORICAL
                )
                if allowed:
                    snapshot_rows.append(data)
            dedupe_rows = snapshot_rows
        else:
            dedupe_rows = prepared

        if apply_dedupe:
            for group in dedupe(dedupe_rows):
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
        index = ComparableIndex.from_rows(
            eligible,
            cutoff=effective_cutoff,
            max_age_hours=effective_age,
            snapshot=snapshot,
        )
        return cls(
            index,
            duplicate_map=duplicate_map,
            cutoff=effective_cutoff,
            max_age_hours=effective_age,
            snapshot=snapshot,
        )

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
        temporal = row_freshness(
            data,
            cutoff=self.cutoff,
            max_age_hours=self.max_age_hours,
            snapshot=self.snapshot,
        )
        ground_truth = _extract_ground_truth(data)

        source = str(getattr(data.get("source"), "value", data.get("source")) or "").upper()
        if source in AUCTION_SOURCES:
            notes.append(
                "Fonte de leilão: o preço é uma adjudicação, não um preço de "
                "retalho — não é comparável com anúncios de stand."
            )
        if duplicate_of is not None:
            notes.append(f"Duplicado do anúncio {duplicate_of}.")
        notes.extend(f"normalização: {n}" for n in canon.notes)
        if temporal.get("freshness") == NOT_MEASURED:
            notes.append(
                "Freshness NOT_MEASURED: não foi fornecido cutoff/max_age_hours "
                "ou timestamp observável."
            )
        elif temporal.get("freshness") in (STALE, FUTURE):
            notes.append(
                "Snapshot recusado por freshness "
                f"{temporal.get('freshness')} (age_hours={temporal.get('age_hours')})."
            )

        # Anúncio bloqueado: não se avalia, não se compara, não se publica.
        freshness_blocked = self._freshness_enforced and not _freshness_allows_target(
            temporal, self.snapshot
        )
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
                cutoff=temporal.get("cutoff"),
                max_age_hours=temporal.get("max_age_hours"),
                snapshot=self.snapshot,
                freshness=temporal.get("freshness", NOT_MEASURED),
                age_hours=temporal.get("age_hours"),
                observed_at=temporal.get("observed_at"),
                target=VALUATION_TARGET,
                snapshot_size=self.index.snapshot_metadata.get("indexed_rows"),
            )
        elif freshness_blocked:
            estimate = _insufficient(
                "Freshness insuficiente para o snapshot corrente: "
                f"{temporal.get('freshness', NOT_MEASURED)}.",
                [],
                {f"freshness_{str(temporal.get('freshness', NOT_MEASURED)).lower()}": 1},
                notes,
                freshness=temporal,
                snapshot=self.snapshot,
                snapshot_size=self.index.snapshot_metadata.get("indexed_rows"),
            )
        else:
            estimate = self.index.estimate(
                data,
                exclude_ids=[vid, duplicate_of] if duplicate_of is not None else [vid],
                exclude_fingerprints=[fp],
            )
            estimate.notes = list(estimate.notes) + notes
            # Ensemble: triangula comparáveis + ML + referência PVP.
            estimate = blend_estimate(
                data, estimate, ref=reference_for(data, canon), canon=canon
            )

            # ``valuation.ensemble`` intentionally constructs a fresh
            # MarketEstimate for compatibility.  Reapply the authoritative
            # temporal/semantic envelope after blending.
            _stamp_estimate(
                estimate,
                temporal,
                snapshot=self.snapshot,
                snapshot_size=self.index.snapshot_metadata.get("indexed_rows"),
            )

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
        reliability = assess_reliability(
            data.get("price"),
            estimate.value,
            estimate.comparables_used,
            price_is_retail=(flags.price_is_total and source not in AUCTION_SOURCES),
        )

        return VehicleValuation(
            vehicle_id=vid,
            estimate=estimate,
            opportunity=opportunity,
            flags=flags,
            canonical=canon.to_dict(),
            fingerprint=fp,
            duplicate_of=duplicate_of,
            net_profit=(
                self._net_profit_fn(data, estimate)
                if ground_truth.get("available") and estimate.value is not None
                else None
            ),
            reliability=reliability,
            notes=notes,
            freshness=temporal,
            snapshot=self.snapshot,
            target=VALUATION_TARGET,
            ground_truth_available=bool(ground_truth.get("available")),
            ground_truth=ground_truth,
        )

    def evaluate_all(
        self, vehicles: Iterable[Dict[str, Any]]
    ) -> List[VehicleValuation]:
        return [self.evaluate(v) for v in vehicles]


def _freshness_allows_target(meta: Dict[str, Any], snapshot: str) -> bool:
    """Target gate kept separate from legacy no-contract behaviour."""
    status = meta.get("freshness", NOT_MEASURED)
    if snapshot == HISTORICAL_SNAPSHOT:
        return status == HISTORICAL
    return status == FRESH


def _stamp_estimate(
    estimate: MarketEstimate,
    temporal: Dict[str, Any],
    *,
    snapshot: str,
    snapshot_size: Optional[int],
) -> MarketEstimate:
    """Restores freshness metadata after an ensemble creates a new estimate."""
    estimate.cutoff = temporal.get("cutoff")
    estimate.max_age_hours = temporal.get("max_age_hours")
    estimate.snapshot = snapshot
    estimate.freshness = temporal.get("freshness", NOT_MEASURED)
    estimate.age_hours = temporal.get("age_hours")
    estimate.observed_at = temporal.get("observed_at")
    estimate.target = VALUATION_TARGET
    estimate.snapshot_size = snapshot_size
    return estimate


def _extract_ground_truth(vehicle: Dict[str, Any]) -> Dict[str, Any]:
    """Read explicit sold-transaction evidence, never listing history.

    ``price``/``last_seen``/``PriceHistory`` are asking-price observations and
    are intentionally ignored.  A generic ``sale_price`` is accepted only
    with an explicit ground-truth flag or a transaction marker; dedicated
    names such as ``ground_truth_sale_price`` are self-describing.
    """
    nested_values = []
    for key in ("ground_truth", "sale", "transaction"):
        value = vehicle.get(key)
        if isinstance(value, dict):
            nested_values.append(value)
    sources = [vehicle, *nested_values]

    explicit = any(
        source.get("ground_truth_available") is True
        or source.get("is_ground_truth") is True
        or source.get("sale_price_is_ground_truth") is True
        for source in sources
    )
    sale_price = None
    sale_source = None
    for source in sources:
        for key in _GROUND_TRUTH_PRICE_KEYS:
            candidate = finite(source.get(key))
            if candidate is not None and candidate > 0:
                sale_price = candidate
                sale_source = key
                explicit = True
                break
        if sale_price is not None:
            break

    if sale_price is None:
        for source in sources:
            candidate = finite(source.get("sale_price"))
            transaction_marker = any(
                source.get(key) is not None
                for key in (
                    "sale_date",
                    "sold_at",
                    "realized_at",
                    "transaction_id",
                    "sale_status",
                )
            )
            if candidate is not None and candidate > 0 and (explicit or transaction_marker):
                sale_price = candidate
                sale_source = "sale_price"
                explicit = True
                break

    realized_profit = None
    for source in sources:
        for key in _GROUND_TRUTH_PROFIT_KEYS:
            candidate = finite(source.get(key))
            if candidate is not None:
                realized_profit = candidate
                explicit = True
                break
        if realized_profit is not None:
            break

    observed_at = None
    source_name = None
    for source in sources:
        observed_at = source.get("sale_date") or source.get("sold_at") or source.get("realized_at")
        source_name = source.get("sale_source") or source.get("transaction_source")
        if observed_at is not None or source_name is not None:
            break

    available = bool(explicit and (sale_price is not None or realized_profit is not None))
    return {
        "available": available,
        "sale_price": sale_price if available else None,
        "realized_profit": realized_profit if available else None,
        "observed_at": observed_at if available else None,
        "source": source_name or sale_source if available else None,
    }


def _ground_truth_net_profit(
    vehicle: Dict[str, Any], estimate: MarketEstimate
) -> Optional[float]:
    """Calcula lucro somente a partir de uma venda explicitamente observada."""
    ground_truth = _extract_ground_truth(vehicle)
    if not ground_truth.get("available"):
        return None
    if ground_truth.get("realized_profit") is not None:
        return round(float(ground_truth["realized_profit"]), 2)
    sale_price = finite(ground_truth.get("sale_price"))
    if sale_price is None or sale_price <= 0:
        return None
    return _net_profit_for_sale_price(vehicle, sale_price)


def _default_net_profit(
    vehicle: Dict[str, Any], estimate: MarketEstimate
) -> Optional[float]:
    """Lucro líquido realista para revenda, ou ``None`` sem base para o dizer.

    Usa o limite **inferior** do intervalo como receita esperada (conservador)
    e o modelo fiscal português existente para os custos. Sem estimativa
    fiável não há lucro — nem zero, que sugeriria "sem margem".
    """
    sale_price = finite(estimate.low)
    if sale_price is None or sale_price <= 0:
        return None
    return _net_profit_for_sale_price(vehicle, sale_price)


def _net_profit_for_sale_price(
    vehicle: Dict[str, Any], sale_price: float
) -> Optional[float]:
    """Compatibilidade interna para o cálculo fiscal, com preço explícito."""
    price = finite(vehicle.get("price"))
    if price is None or price <= 0 or sale_price <= 0:
        return None
    try:
        from valuation.pt_fiscal import (
            calculate_selling_costs,
            calculate_transaction_costs,
        )

        source = str(
            getattr(vehicle.get("source"), "value", vehicle.get("source")) or ""
        ).upper()
        foreign_sources = {
            "AUTOSCOUT24_DE", "AUTOSCOUT24_ES", "AUTOSCOUT24_FR", "AUTOHERO",
            "SPOTICAR", "LEBONCOIN", "LACENTRALE", "ARGUS_FR", "MILANUNCIOS",
            "WALLAPOP", "COCHES_NET", "IDEALISTA_AUTOS", "LACENTRALE_ES",
        }
        is_national = vehicle.get("is_national")
        if is_national is None:
            is_national = source not in foreign_sources
        vehicle_type = str(
            getattr(vehicle.get("vehicle_type"), "value", vehicle.get("vehicle_type"))
            or "carros"
        )
        acquisition = calculate_transaction_costs(
            asking_price=price,
            engine_cc=int(vehicle.get("engine_size") or 0),
            fuel_type=str(
                getattr(vehicle.get("fuel_type"), "value", vehicle.get("fuel_type"))
                or "gasolina"
            ),
            year=vehicle.get("year"),
            vehicle_type=vehicle_type,
            is_national=bool(is_national),
            condition_score=vehicle.get("condition_score"),
            repair_costs=vehicle.get("repair_costs"),
            seats=vehicle.get("seats"),
        )
        selling = calculate_selling_costs(
            sale_price=sale_price,
            vehicle_type=vehicle_type,
        )
        # ``total_cost`` já inclui o preço pedido. Subtraí-lo uma segunda vez
        # produzia lucros líquidos artificialmente negativos.
        total_cost = float(acquisition.total_cost)
        sell_cost = float(selling.get("total", 0.0) or 0.0)
        margin = sale_price - total_cost - sell_cost
        # IVA do regime da margem (23 % sobre a margem positiva).
        if margin > 0:
            margin -= margin * 0.23 / 1.23
        return round(margin, 2)
    except Exception as exc:  # fail closed: não converter erro de custos em lucro
        logger.warning("Modelo fiscal indisponível; lucro líquido não calculado: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Conveniências
# ---------------------------------------------------------------------------


def build_service(
    rows: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    limit: Optional[int] = None,
    cutoff: Any = None,
    max_age_hours: Optional[float] = None,
    snapshot: str = CURRENT_SNAPSHOT,
    snapshot_type: Optional[str] = None,
) -> ValuationService:
    """Constrói o serviço a partir da base de dados (ou de linhas dadas)."""
    if snapshot_type is not None:
        snapshot = snapshot_type
    if rows is None:
        rows = load_market_rows(
            limit=limit,
            cutoff=cutoff,
            max_age_hours=max_age_hours,
            snapshot=snapshot,
        )
    return ValuationService.from_rows(
        rows,
        cutoff=cutoff,
        max_age_hours=max_age_hours,
        snapshot=snapshot,
        snapshot_type=snapshot_type,
    )


def load_market_rows(
    *,
    limit: Optional[int] = None,
    include_ineligible: bool = False,
    cutoff: Any = None,
    max_age_hours: Optional[float] = None,
    snapshot: str = CURRENT_SNAPSHOT,
    include_history: Optional[bool] = None,
    snapshot_type: Optional[str] = None,
    include_historical: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Carrega anúncios ativos para o índice ou para reavaliação.

    Por omissão devolve apenas o snapshot corrente elegível para comparáveis.
    ``snapshot='historical'`` separa o inventário histórico do stock ativo e
    aceita linhas anteriores ao cutoff (mas nunca linhas futuras). Com
    ``include_ineligible=True`` inclui também anúncios bloqueados, permitindo
    que uma reavaliação limpe derivados antigos em vez de os deixar visíveis.

    O filtro temporal é aplicado também em Python depois da consulta, para
    que timestamps ausentes sejam excluídos fail-closed quando há contrato
    explícito, em vez de depender do comportamento de NULL do SQL.
    """
    from database.db import get_db_context
    from database.models import Vehicle

    if snapshot_type is not None:
        snapshot = snapshot_type
    if include_history is True or include_historical is True:
        snapshot = HISTORICAL_SNAPSHOT
    if snapshot not in (CURRENT_SNAPSHOT, HISTORICAL_SNAPSHOT):
        raise ValueError("snapshot deve ser 'current' ou 'historical'")
    normalized_cutoff, max_age_hours = resolve_freshness_config(
        cutoff, max_age_hours
    )

    with get_db_context() as db:
        query = db.query(Vehicle)
        if snapshot == CURRENT_SNAPSHOT:
            query = query.filter(Vehicle.is_active.is_(True))
        if not include_ineligible:
            query = query.filter(
                Vehicle.price_kind == "total",
                Vehicle.currency == "EUR",
                Vehicle.price > 0,
                Vehicle.quality_status.in_(("valid", "valid_with_warning")),
            )
        query = query.order_by(Vehicle.id.asc())
        rows = [vehicle_to_dict(v) for v in query.all()]

    if normalized_cutoff is not None or max_age_hours is not None:
        rows = [
            row for row in rows
            if _row_is_in_snapshot(
                row,
                cutoff=normalized_cutoff,
                max_age_hours=max_age_hours,
                snapshot=snapshot,
            )
        ]
    if limit:
        rows = rows[:limit]
    return rows


def _row_is_in_snapshot(
    row: Dict[str, Any],
    *,
    cutoff: Any = None,
    max_age_hours: Optional[float] = None,
    snapshot: str = CURRENT_SNAPSHOT,
) -> bool:
    """Filtro comum para load/service; sem timestamp + contrato => rejeitado."""
    temporal = row_freshness(
        row,
            cutoff=effective_cutoff,
            max_age_hours=effective_age,
            snapshot=snapshot,
            snapshot_type=snapshot_type,
        )
    if cutoff is None and max_age_hours is None:
        return True
    return _freshness_allows_target(temporal, snapshot)


def vehicle_to_dict(v: Any) -> Dict[str, Any]:
    """Projeta um ORM ``Vehicle`` para o dicionário que a avaliação consome."""

    def val(attr: str) -> Any:
        return getattr(getattr(v, attr, None), "value", getattr(v, attr, None))

    result: Dict[str, Any] = {
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
        "repair_costs": getattr(v, "repair_costs", None),
        "seats": getattr(v, "seats", None),
        "has_accident": getattr(v, "has_accident", None),
        "has_damage": getattr(v, "has_damage", None),
        "is_national": getattr(v, "is_national", None),
        "quality_status": getattr(v, "quality_status", None),
        "first_seen": getattr(v, "first_seen", None),
        "last_seen": getattr(v, "last_seen", None),
        "valuation_details": getattr(v, "valuation_details", None),
    }
    # Future/experimental stores may carry transaction labels without the
    # current operational schema having to be migrated.  Only explicit fields
    # are copied; the normal Vehicle.price and PriceHistory are not treated as
    # sold ground truth.
    for attr in (
        "ground_truth_available",
        "ground_truth_sale_price",
        "realized_sale_price",
        "sold_price",
        "transaction_price",
        "sale_price",
        "sale_price_is_ground_truth",
        "realized_profit",
        "ground_truth_realized_profit",
        "sale_date",
        "sold_at",
        "realized_at",
        "transaction_id",
        "sale_status",
        "sale_source",
        "transaction_source",
        "ground_truth",
    ):
        if hasattr(v, attr):
            result[attr] = getattr(v, attr)
    return result


def evaluate(
    vehicle: Dict[str, Any], service: Optional[ValuationService] = None
) -> VehicleValuation:
    """Avalia um único anúncio (constrói o índice se não for fornecido)."""
    return (service or build_service()).evaluate(vehicle)


# ---------------------------------------------------------------------------
# Escrita atómica na base de dados
# ---------------------------------------------------------------------------

def revalue_database(
    *,
    batch_size: int = 500,
    force: bool = False,
    limit: Optional[int] = None,
    cutoff: Any = None,
    max_age_hours: Optional[float] = None,
    snapshot: str = CURRENT_SNAPSHOT,
) -> Dict[str, int]:
    """Reavalia anúncios com um índice global e escrita em lotes.

    Substitui ``scripts/reprocess_db.py::step_revalue`` (que só escrevia 4
    campos e deixava o dashboard a ordernar por colunas congeladas). Cada
    anúncio recebe o seu bloco completo e consistente num único ``UPDATE``.

    Returns:
        Estatísticas da passagem (avaliados, insuficientes, excluídos, …).
    """
    if batch_size <= 0:
        raise ValueError("batch_size tem de ser positivo")
    if limit is not None and limit <= 0:
        raise ValueError("limit tem de ser positivo quando fornecido")

    from database.db import get_db_context
    from database.models import Vehicle

    # O índice é construído com o inventário inteiro elegível, não apenas com
    # o lote que vai ser escrito. O lote limita trabalho/escrita, não a
    # evidência disponível para comparar um veículo.
    # Load the full current inventory first; the temporal gate belongs to the
    # read-only service so stale rows can still be rewritten to an explicit
    # insufficient/NOT_MEASURED state rather than being silently skipped.
    all_rows = load_market_rows(
        limit=None,
        include_ineligible=True,
        snapshot=snapshot,
    )

    def has_current_version(row: Dict[str, Any]) -> bool:
        details = row.get("valuation_details")
        return isinstance(details, dict) and details.get("valuation_version") == VALUATION_VERSION

    target_rows = [r for r in all_rows if force or not has_current_version(r)]
    if limit is not None:
        target_rows = target_rows[:limit]

    stats = {
        "processed": 0, "valued": 0, "insufficient": 0, "excluded": 0,
        "excellent": 0, "good": 0, "needs_review": 0,
        "errors": 0, "stale": 0, "not_measured": 0,
    }
    if not target_rows:
        return stats

    svc = ValuationService.from_rows(
        all_rows,
        cutoff=cutoff,
        max_age_hours=max_age_hours,
        snapshot=snapshot,
    )

    batch: List[VehicleValuation] = []

    def flush(rows_batch: Sequence[VehicleValuation]) -> None:
        with get_db_context() as db:
            mappings = []
            for b in rows_batch:
                fields = b.derived_fields()
                fields["id"] = b.vehicle_id
                mappings.append(fields)
            # Core executemany: não dispara a validação de preço porque só
            # escrevemos campos derivados, e reduz round-trips por lote.
            db.bulk_update_mappings(Vehicle, mappings)
            db.commit()

    for r in target_rows:
        stats["processed"] += 1
        try:
            b = svc.evaluate(r)
        except Exception as exc:  # não deixar um erro afundar a passagem
            logger.warning("erro ao avaliar %s: %s", r.get("id"), exc)
            stats["errors"] += 1
            continue
        stats["valued" if b.estimate.value is not None else "insufficient"] += 1
        if b.freshness.get("freshness") == STALE:
            stats["stale"] += 1
        elif b.freshness.get("freshness") == NOT_MEASURED:
            stats["not_measured"] += 1
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

    logger.info(
        "Reavaliação coerente: %s (force=%s, limit=%s, inventário=%d)",
        stats, force, limit, len(all_rows),
    )
    return stats
