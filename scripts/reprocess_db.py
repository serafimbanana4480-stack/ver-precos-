"""
Reprocessamento integral da base de dados (2026-08-01).

Pipeline:
  1. Snapshot "antes" (distribuições, contagens de fallbacks).
  2. Normalização de marcas (raw preservado).
  3. Classificação de qualidade (valid/quarantined/invalid) com razões.
  4. Deduplicação conservadora (duplicados exatos → quarentena).
  5. Reavaliação completa com HybridValuator v2 (estatística + ML + referência).
  6. Snapshot "depois" + relatório de comparação.

Propriedades: lotes transacionais, retomável (salta anúncios já na versão
atual), idempotente, sem eliminações físicas (quarentena = soft).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_

from database.db import get_db_context
from database.models import Vehicle
from processing.model_canon import canon_listing
from processing.quality import classify_listing, normalize_brand
from scrapers.schema import parse_price_evidence
from valuation.hybrid_valuator import VALUATION_VERSION, get_valuator, reset_valuator

logger = logging.getLogger("reprocess")

BATCH = 250


def _backfill_price_evidence(vehicle: Vehicle):
    """Recover source-bound money evidence for legacy rows.

    Older rows only retained a numeric ``price``. When the title contains a
    currency-bound amount, that is stronger evidence and also repairs historic
    parser errors such as ``135,60 €`` being stored as ``60``. If no monetary
    token exists, the numeric value is retained but marked as an unverified
    numeric observation.
    """
    source = vehicle.source.value if hasattr(vehicle.source, "value") else str(vehicle.source or "")
    context = f"{source} {vehicle.title or ''} {vehicle.description or ''}"
    for text, label in ((vehicle.title or "", "title"), (vehicle.description or "", "description")):
        evidence = parse_price_evidence(text, context=context)
        if evidence.value is not None and evidence.evidence == "currency_bound":
            evidence.evidence = f"{label}_currency_bound"
            return evidence, True
    return parse_price_evidence(vehicle.price, context=context), False


def snapshot(tag: str) -> dict:
    from sqlalchemy import func
    with get_db_context() as db:
        total = db.query(func.count(Vehicle.id)).filter(Vehicle.is_active == True).scalar()  # noqa: E712
        est500 = db.query(func.count(Vehicle.id)).filter(
            Vehicle.is_active == True, Vehicle.estimated_value == 500).scalar()  # noqa: E712
        est10000 = db.query(func.count(Vehicle.id)).filter(
            Vehicle.is_active == True, Vehicle.estimated_value == 10000).scalar()  # noqa: E712
        no_est = db.query(func.count(Vehicle.id)).filter(
            Vehicle.is_active == True, Vehicle.estimated_value.is_(None)).scalar()  # noqa: E712
        rows = db.query(Vehicle.estimated_value, Vehicle.deal_score).filter(
            Vehicle.is_active == True, Vehicle.estimated_value.isnot(None)).all()  # noqa: E712
        scores = [r[1] for r in rows if r[1] is not None]
        ests = sorted(r[0] for r in rows)
        quals = db.query(Vehicle.quality_status, func.count()).filter(
            Vehicle.is_active == True).group_by(Vehicle.quality_status).all()  # noqa: E712

    def pct(vals, p):
        if not vals:
            return None
        k = max(0, min(len(vals) - 1, int(p * (len(vals) - 1))))
        return round(vals[k], 0)

    return {
        "tag": tag,
        "at": datetime.now(timezone.utc).isoformat(),
        "active_total": total,
        "estimated_500_exact": est500,
        "estimated_10000_exact": est10000,
        "without_estimate": no_est,
        "with_estimate": total - no_est,
        "publishable": db.query(func.count(Vehicle.id)).filter(
            Vehicle.is_active == True,  # noqa: E712
            Vehicle.profit_is_publishable == True,  # noqa: E712
        ).scalar() if "profit_is_publishable" in {c.name for c in Vehicle.__table__.columns} else None,
        "estimated_median": pct(ests, 0.5),
        "estimated_p10": pct(ests, 0.1),
        "estimated_p90": pct(ests, 0.9),
        "deal_score_mean": round(sum(scores) / len(scores), 2) if scores else None,
        "deal_score_lt3": sum(1 for s in scores if s < 3),
        "deal_score_3_7": sum(1 for s in scores if 3 <= s < 7),
        "deal_score_gte7": sum(1 for s in scores if s >= 7),
        "quality_counts": {str(k or "null"): v for k, v in quals},
    }


def step_normalize_quality(*, force: bool = False) -> dict:
    """Passa 1: normalização de marca + qualidade. Retomável via quality_checked_at."""
    from valuation.market_reference import estimate_reference_value

    stats = {
        "normalized": 0, "valid": 0, "valid_with_warning": 0,
        "quarantined": 0, "invalid": 0,
        "price_evidence_backfilled": 0, "price_recovered_from_text": 0,
        "stored_price_reconciled": 0, "models_cleaned": 0,
        "models_canonicalized": 0,
    }
    last_id = 0
    while True:
        with get_db_context() as db:
            query = db.query(Vehicle).filter(Vehicle.is_active == True)  # noqa: E712
            if force:
                query = query.filter(Vehicle.id > last_id).order_by(Vehicle.id.asc())
            else:
                query = query.filter(or_(
                    Vehicle.quality_checked_at.is_(None),
                    Vehicle.price_raw.is_(None),
                    Vehicle.price_kind.is_(None),
                    Vehicle.currency.is_(None),
                ))
            batch = query.limit(BATCH).all()
            if not batch:
                break
            for v in batch:
                old_price = float(v.price or 0)
                evidence, from_text = _backfill_price_evidence(v)
                if evidence.value is not None:
                    stats["price_evidence_backfilled"] += 1
                if from_text:
                    stats["price_recovered_from_text"] += 1
                    if abs(old_price - float(evidence.value or 0)) > 0.01:
                        stats["stored_price_reconciled"] += 1
                v.price_raw = evidence.raw
                v.price_observed_value = evidence.value
                v.currency = evidence.currency
                v.price_kind = evidence.kind.value
                v.price_evidence = evidence.evidence
                v.price_rejection_reason = evidence.rejection_reason
                v.price = (
                    float(evidence.value)
                    if evidence.value is not None
                    and evidence.kind.value == "total"
                    and evidence.currency == "EUR"
                    else 0.0
                )
                source = v.source.value if hasattr(v.source, "value") else str(v.source or "")
                canon = canon_listing(
                    v.brand, v.model, v.title, price=v.price, source=source
                )
                if canon.get("model_cleaned"):
                    stats["models_cleaned"] += 1
                if canon.get("model_canonicalized"):
                    stats["models_canonicalized"] += 1
                v.brand = (canon.get("brand") or v.brand or "Unknown")[:100]
                v.model = (canon.get("model") or v.model or "Unknown")[:100]
                nb = normalize_brand(v.brand)
                v.normalized_brand = nb["normalized_brand"]
                v.normalization_confidence = nb["normalization_confidence"]
                if nb["normalized_brand"] != nb["raw_brand"]:
                    stats["normalized"] += 1

                ref = estimate_reference_value(
                    brand=v.brand, model=v.model, year=v.year, km=v.km,
                    fuel_type=v.fuel_type.value if v.fuel_type else None,
                    vehicle_type=v.vehicle_type.value if v.vehicle_type else "carros",
                    engine_cc=v.engine_size,
                )
                q = classify_listing(
                    {
                        "price": v.price, "year": v.year, "km": v.km,
                        "price_raw": v.price_raw,
                        "price_observed_value": v.price_observed_value,
                        "currency": v.currency,
                        "price_kind": v.price_kind,
                        "price_evidence": v.price_evidence,
                        "price_rejection_reason": v.price_rejection_reason,
                        "brand": v.brand, "model": v.model, "title": v.title,
                        "description": v.description,
                        "source": source,
                        "vehicle_type": v.vehicle_type.value if v.vehicle_type else "carros",
                    },
                    reference_value=ref.get("value"),
                )
                v.quality_status = q["quality_status"]
                v.quality_reasons = q["quality_reasons"]
                v.quality_checked_at = datetime.now(timezone.utc)
                stats[q["quality_status"]] += 1
            db.commit()
            if force:
                last_id = batch[-1].id
    return stats


def step_dedupe() -> dict:
    """Duplicados exatos (marca/modelo/ano/km/preço) → quarentena (exceto o mais antigo)."""
    from collections import defaultdict
    stats = {"duplicates_quarantined": 0, "groups": 0}
    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(
            Vehicle.is_active == True,  # noqa: E712
            Vehicle.year.isnot(None), Vehicle.km.isnot(None),
            or_(Vehicle.quality_status.is_(None), Vehicle.quality_status == "valid"),
        ).order_by(Vehicle.first_seen.asc()).all()
        groups = defaultdict(list)
        for v in vehicles:
            key = ((v.normalized_brand or v.brand or "").lower(), (v.model or "").lower(),
                   v.year, v.km, round(v.price, 0))
            groups[key].append(v)
        for key, members in groups.items():
            if len(members) < 2:
                continue
            # Mesma fonte e source_id únicos por índice; aqui são anúncios
            # distintos com dados idênticos → provável republicação.
            stats["groups"] += 1
            for dup in members[1:]:
                dup.quality_status = "quarantined"
                reasons = list(dup.quality_reasons or [])
                reasons.append(f"duplicado_provavel(de id={members[0].id})")
                dup.quality_reasons = reasons
                stats["duplicates_quarantined"] += 1
        db.commit()
    return stats


def step_revalue(batch_size: int = BATCH, *, force: bool = False) -> dict:
    """Passa 3: reavaliação v2 de todos os ativos (exceto inválidos)."""
    reset_valuator()
    valuator = get_valuator()
    stats = {"valued": 0, "insufficient": 0, "skipped_quality": 0,
             "by_method": {}, "by_confidence": {}}
    last_id = 0
    while True:
        with get_db_context() as db:
            query = db.query(Vehicle).filter(Vehicle.is_active == True)  # noqa: E712
            if force:
                query = query.filter(Vehicle.id > last_id).order_by(Vehicle.id.asc())
            else:
                query = query.filter(or_(
                    Vehicle.valuation_details.is_(None),
                    Vehicle.valuation_details["valuation_version"].as_string() != VALUATION_VERSION,
                ))
            batch = query.limit(batch_size).all()
            if not batch:
                break
            for v in batch:
                if v.quality_status in ("invalid", "quarantined"):
                    # Inválidos não recebem avaliação; marcados como processados.
                    v.estimated_value = None
                    v.deal_score = None
                    v.valuation_details = {
                        "valuation_version": VALUATION_VERSION,
                        "method": "skipped_quality",
                        "quality_status": v.quality_status,
                        "quality_reasons": v.quality_reasons,
                        "valued_at": datetime.now(timezone.utc).isoformat(),
                    }
                    stats["skipped_quality"] += 1
                    continue

                data = {
                    "id": v.id, "year": v.year, "km": v.km,
                    "horsepower": v.horsepower, "engine_size": v.engine_size,
                    "doors": v.doors,
                    "fuel_type": v.fuel_type.value if v.fuel_type else "unknown",
                    "transmission": v.transmission.value if v.transmission else "unknown",
                    "brand": v.normalized_brand or v.brand or "Unknown",
                    "model": v.model or "", "version": v.version or "",
                    "location": v.location or "", "district": v.district or "",
                    "source": v.source.value if v.source else "",
                    "vehicle_type": v.vehicle_type.value if v.vehicle_type else "carros",
                    "title": v.title or "", "price": v.price or 0,
                    "condition_score": v.condition_score or 3.0,
                    "is_national": v.is_national,
                }
                res = valuator.calculate_deal_score(data)
                val = res.get("valuation", {})
                v.estimated_value = res.get("estimated_value")
                v.deal_score = res.get("deal_score")
                v.profit_potential = res.get("profit_potential")
                v.profit_percentage = res.get("profit_percentage")
                v.valuation_details = {
                    "estimated_value": val.get("estimated_value"),
                    "value_low": val.get("value_low"),
                    "value_high": val.get("value_high"),
                    "confidence": val.get("confidence"),
                    "confidence_label": val.get("confidence_label"),
                    "method": val.get("method"),
                    "comparables_count": val.get("comparables_count"),
                    "reference_level": val.get("reference_level"),
                    "methods_used": val.get("methods_used"),
                    "warnings": val.get("warnings"),
                    "features_missing": val.get("features_missing"),
                    "deal_status": res.get("deal_status"),
                    "risk_flags": res.get("risk_flags"),
                    "valuation_explanation": val.get("valuation_explanation"),
                    "valuation_version": val.get("valuation_version", VALUATION_VERSION),
                    "valued_at": datetime.now(timezone.utc).isoformat(),
                }
                stats["valued"] += 1
                m = val.get("method", "?")
                stats["by_method"][m] = stats["by_method"].get(m, 0) + 1
                c = val.get("confidence_label", "?")
                stats["by_confidence"][c] = stats["by_confidence"].get(c, 0) + 1
                if val.get("estimated_value") is None:
                    stats["insufficient"] += 1
            db.commit()
            if force:
                last_id = batch[-1].id
            logger.info("lote reavaliado: valued=%d insufficient=%d",
                        stats["valued"], stats["insufficient"])
    return stats


def step_revalue_coherent() -> dict:
    """Reavaliação coerente (valuation/service.revalue_database).

    Escreve **todos** os campos derivados num único UPDATE por anúncio —
    substitui ``step_revalue`` (que só escrevia 4 campos e deixava o dashboard
    a ordernar por colunas congeladas). Devolve as estatísticas da passagem.
    """
    from valuation.service import revalue_database
    return revalue_database(force=True)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="reports/reprocess_report.json")
    parser.add_argument("--legacy", action="store_true",
                        help="Usa o HybridValuator legado em vez do motor coerente (apenas para comparação)")
    parser.add_argument("--skip-quality", action="store_true")
    parser.add_argument("--force-quality", action="store_true", help="Reprocessa também linhas já auditadas")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    report = {"started_at": datetime.now(timezone.utc).isoformat(),
              "valuation_version": VALUATION_VERSION}
    report["before"] = snapshot("before")
    logger.info("ANTES: %s", json.dumps(report["before"], default=str))

    if not args.skip_quality:
        t0 = datetime.now()
        report["normalize_quality"] = step_normalize_quality(force=args.force_quality)
        logger.info("qualidade: %s (%.0fs)", report["normalize_quality"],
                    (datetime.now() - t0).total_seconds())
        report["dedupe"] = step_dedupe()
        logger.info("dedupe: %s", report["dedupe"])

    if not args.legacy:
        t0 = datetime.now()
        report["revalue"] = step_revalue_coherent()
        logger.info("reavaliação coerente: %s (%.0fs)", report["revalue"],
                    (datetime.now() - t0).total_seconds())
    else:
        t0 = datetime.now()
        report["revalue"] = step_revalue(force=True)
        logger.info("reavaliação (legado): %s (%.0fs)", report["revalue"],
                    (datetime.now() - t0).total_seconds())
    report["after"] = snapshot("after")
    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str),
                   encoding="utf-8")
    logger.info("DEPOIS: %s", json.dumps(report["after"], default=str))
    logger.info("Relatório: %s", out)


if __name__ == "__main__":
    main()
