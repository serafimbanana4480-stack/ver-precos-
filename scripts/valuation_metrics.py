"""
Métricas de observabilidade das avaliações (Fase 13).

Produz um snapshot JSON com:
* distribuição de estimated_value e deal_score;
* confiança média e contagem por etiqueta de confiança;
* avaliações inconclusivas;
* comparáveis médios por previsão;
* utilização por nível de referência / método;
* qualidade dos anúncios (valid/quarantined/invalid) e razões mais comuns;
* campos em falta mais frequentes;
* estado da componente ML (carregada, R², erro).

Uso: PYTHONPATH=. python scripts/valuation_metrics.py [--out reports/valuation_metrics.json]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_db_context
from database.models import Vehicle
from valuation.comparables import (
    FUTURE,
    FRESH,
    HISTORICAL_SNAPSHOT,
    NOT_MEASURED,
    STALE,
    normalize_cutoff,
    row_freshness,
)
from valuation.service import VALUATION_TARGET

logger = logging.getLogger("valuation_metrics")


def _value(obj, attr):
    value = getattr(obj, attr, None)
    return getattr(value, "value", value)


def _row_temporal(obj) -> dict:
    return {
        "last_seen": getattr(obj, "last_seen", None),
        "first_seen": getattr(obj, "first_seen", None),
    }


def _retail_eligible(obj) -> bool:
    try:
        price = float(getattr(obj, "price", 0) or 0)
    except (TypeError, ValueError):
        return False
    return (
        price > 0
        and str(getattr(obj, "price_kind", "") or "").lower() == "total"
        and str(getattr(obj, "currency", "") or "").upper() == "EUR"
        and str(getattr(obj, "quality_status", "") or "").lower()
        in {"valid", "valid_with_warning"}
    )


def collect_metrics(
    *,
    cutoff=None,
    max_age_hours: float | None = 48,
    snapshot: str = "current",
) -> dict:
    """Recolhe métricas read-only do snapshot corrente e contexto histórico.

    A avaliação só é contada no snapshot corrente fresco. Linhas antigas ou
    sem timestamp permanecem visíveis como cobertura/falha de freshness, mas
    não são convertidas em uma pontuação atual.
    """
    explicit_cutoff = normalize_cutoff(cutoff)
    if max_age_hours is not None:
        max_age_hours = float(max_age_hours)
        if max_age_hours <= 0:
            raise ValueError("max_age_hours deve ser positivo")
    effective_cutoff = explicit_cutoff or (
        datetime.now(timezone.utc) if max_age_hours is not None else None
    )
    metrics: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": VALUATION_TARGET,
        "target_field": VALUATION_TARGET,
        "snapshot": {
            "kind": snapshot,
            "cutoff": effective_cutoff.isoformat() if effective_cutoff else None,
            "cutoff_source": "explicit" if explicit_cutoff else "runtime_now" if max_age_hours is not None else None,
            "max_age_hours": float(max_age_hours) if max_age_hours is not None else None,
        },
    }

    with get_db_context() as db:
        all_rows = db.query(Vehicle).all()
        active_all = [v for v in all_rows if bool(getattr(v, "is_active", False))]
        eligible_all = [v for v in all_rows if _retail_eligible(v)]
        active = [v for v in eligible_all if bool(getattr(v, "is_active", False))]
        current_temporal = {
            getattr(v, "id", id(v)): row_freshness(
                _row_temporal(v),
                cutoff=effective_cutoff,
                max_age_hours=max_age_hours,
                snapshot=snapshot,
            )
            for v in active
        }
        current_rows = []
        if snapshot == "current":
            current_rows = [
                v for v in active
                if current_temporal[getattr(v, "id", id(v))].get("freshness") == FRESH
            ]
        else:
            # This script is a current observability snapshot.  A historical
            # request is represented separately and never silently joins it.
            current_rows = []

        freshness_counts = Counter(
            current_temporal[getattr(v, "id", id(v))].get("freshness", NOT_MEASURED)
            for v in active
        )
        metrics["active_listings"] = len(active)
        metrics["active_listings_total"] = len(active_all)
        metrics["current_snapshot_listings"] = len(current_rows)
        metrics["snapshot"].update({
            "eligible_active": len(active),
            "included_current": len(current_rows),
            "freshness_counts": dict(freshness_counts),
        })
        metrics["historical"] = {
            "eligible_rows": len(eligible_all),
            "inactive_rows": sum(1 for v in eligible_all if not bool(getattr(v, "is_active", False))),
            "active_rows_outside_current": len(active) - len(current_rows),
            "status": "SEPARATE_FROM_CURRENT_SNAPSHOT",
        }

        ests, scores, confs = [], [], []
        conf_labels = Counter()
        methods = Counter()
        ref_levels = Counter()
        deal_statuses = Counter()
        missing_fields = Counter()
        quality = Counter()
        quality_reasons = Counter()
        comparables = []
        inconclusive = 0
        skipped_quality = len(active_all) - len(active)
        measured_profit_count = 0

        for v in current_rows:
            quality[str(v.quality_status or "unknown")] += 1
            for r in (v.quality_reasons or []):
                quality_reasons[str(r).split("(")[0] + "()"] += 1
            if v.estimated_value is not None:
                ests.append(v.estimated_value)
            if v.deal_score is not None:
                scores.append(v.deal_score)
            vd = v.valuation_details or {}
            if isinstance(vd, str):
                vd = {}
            if vd.get("method"):
                methods[vd["method"]] += 1
            if vd.get("method") == "skipped_quality":
                skipped_quality += 1
                inconclusive += 1
            elif v.estimated_value is None:
                inconclusive += 1
            if vd.get("reference_level") is not None:
                ref_levels[str(vd["reference_level"])] += 1
            if vd.get("confidence_label"):
                conf_labels[vd["confidence_label"]] += 1
            if vd.get("confidence") is not None:
                confs.append(vd["confidence"])
            if vd.get("comparables_count") is not None:
                comparables.append(vd["comparables_count"])
            if vd.get("deal_status"):
                deal_statuses[vd["deal_status"]] += 1
                if vd["deal_status"] == "dados_insuficientes":
                    inconclusive += 1
            for f in (vd.get("features_missing") or []):
                missing_fields[f] += 1
            gt = vd.get("ground_truth") or {}
            if isinstance(gt, dict) and gt.get("available"):
                measured_profit_count += 1

    ests.sort()
    scores.sort()

    def pct(vals, p):
        if not vals:
            return None
        return round(vals[max(0, min(len(vals) - 1, int(p * (len(vals) - 1))))], 2)

    metrics["estimated_value"] = {
        "count": len(ests),
        "median": pct(ests, 0.5), "p10": pct(ests, 0.1), "p90": pct(ests, 0.9),
        "mean": round(sum(ests) / len(ests), 0) if ests else None,
        "exact_500": sum(1 for e in ests if e == 500.0),
        "exact_10000": sum(1 for e in ests if e == 10000.0),
    }
    metrics["deal_score"] = {
        "count": len(scores),
        "mean": round(sum(scores) / len(scores), 2) if scores else None,
        "median": pct(scores, 0.5),
        "lt3": sum(1 for s in scores if s < 3),
        "gte7": sum(1 for s in scores if s >= 7),
    }
    metrics["confidence"] = {
        "mean": round(sum(confs) / len(confs), 3) if confs else None,
        "by_label": dict(conf_labels),
    }
    metrics["inconclusive_valuations"] = inconclusive
    metrics["quality_excluded_from_valuation"] = skipped_quality
    metrics["freshness"] = {
        "status": "MEASURED" if max_age_hours is not None or effective_cutoff else NOT_MEASURED,
        "counts": dict(freshness_counts),
        "stale": freshness_counts.get(STALE, 0),
        "not_measured": freshness_counts.get(NOT_MEASURED, 0),
        "future": freshness_counts.get(FUTURE, 0),
    }
    metrics["valuation_semantics"] = {
        "target": VALUATION_TARGET,
        "target_field": VALUATION_TARGET,
        "ground_truth_sale_count": measured_profit_count,
        "profit_status": "MEASURED" if measured_profit_count else NOT_MEASURED,
        "note": "Preço pedido não é preço vendido; sem ground truth não há realized_profit.",
    }
    metrics["comparables_per_valuation"] = {
        "mean": round(sum(comparables) / len(comparables), 1) if comparables else None,
        "median": pct(sorted(comparables), 0.5),
    }
    metrics["methods_used"] = dict(methods.most_common())
    metrics["reference_levels"] = dict(ref_levels)
    metrics["deal_statuses"] = dict(deal_statuses.most_common())
    metrics["quality"] = {
        "counts": dict(quality),
        "top_reasons": dict(quality_reasons.most_common(15)),
    }
    metrics["missing_fields"] = dict(missing_fields.most_common())

    # Estado da componente ML
    try:
        from valuation.predict import PricePredictor
        p = PricePredictor("carros")
        metrics["ml"] = {
            "loaded": p.model_loaded_ok,
            "model_type": p.model_name,
            "r2": p.metrics.get("r2"),
            "mae": p.metrics.get("mae"),
            "mape_pct": p.metrics.get("mape_pct"),
            "load_error": p.load_error,
        }
    except Exception as e:
        metrics["ml"] = {"loaded": False, "load_error": f"{type(e).__name__}: {e}"}

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/valuation_metrics.json")
    parser.add_argument("--cutoff", default=None, help="cutoff ISO-8601 explícito")
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=48,
        help="idade máxima do snapshot corrente (default: 48)",
    )
    parser.add_argument(
        "--snapshot",
        choices=("current", "historical"),
        default="current",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    metrics = collect_metrics(
        cutoff=args.cutoff,
        max_age_hours=args.max_age_hours,
        snapshot=args.snapshot,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    logger.info("Métricas gravadas em %s", out)


if __name__ == "__main__":
    main()
