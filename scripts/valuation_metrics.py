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

from sqlalchemy import func

from database.db import get_db_context
from database.models import Vehicle

logger = logging.getLogger("valuation_metrics")


def collect_metrics() -> dict:
    metrics: dict = {"generated_at": datetime.now(timezone.utc).isoformat()}

    with get_db_context() as db:
        active = db.query(Vehicle).filter(Vehicle.is_active == True).all()  # noqa: E712
        metrics["active_listings"] = len(active)

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
        skipped_quality = 0

        for v in active:
            quality[str(v.quality_status or "unknown")] += 1
            for r in (v.quality_reasons or []):
                quality_reasons[str(r).split("(")[0] + "()"] += 1
            if v.estimated_value is not None:
                ests.append(v.estimated_value)
            if v.deal_score is not None:
                scores.append(v.deal_score)
            vd = v.valuation_details or {}
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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    metrics = collect_metrics()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    logger.info("Métricas gravadas em %s", out)


if __name__ == "__main__":
    main()
