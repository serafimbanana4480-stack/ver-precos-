"""
Backtest rigoroso do motor de avaliacao v3.0 contra precos reais da BD.

Metodologia (sem vazamento):
  * Carrega todos os anuncios retalhistas elegiveis (fonte nao-leilao, preco
    total, EUR, qualidade valid/valid_with_warning, preco plausivel).
  * Constroi UM ComparableIndex a partir de TODO o stock.
  * Para cada anuncio: esconde o preco, avalia com ValuationService excluindo
    o proprio anuncio (e o seu duplicado). Leave-one-out dentro do pool.
Uso:
  PYTHONPATH=. python scripts/backtest_valuation.py
  PYTHONPATH=. python scripts/backtest_valuation.py --sample 400 --ml
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valuation.comparables import (
    FUTURE,
    HISTORICAL,
    HISTORICAL_SNAPSHOT,
    NOT_MEASURED,
    STALE,
    normalize_cutoff,
    row_freshness,
)
from valuation.service import VALUATION_TARGET, VALUATION_VERSION, ValuationService, load_market_rows

logger = logging.getLogger("backtest")

PRICE_BANDS = [
    (0, 5_000), (5_000, 10_000), (10_000, 15_000), (15_000, 20_000),
    (20_000, 30_000), (30_000, 50_000), (50_000, 200_000),
]
AGE_BANDS = [0, 2, 5, 8, 12, 16, 25, 60]

_AUCTION = frozenset({
    "LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA",
    "AUTOLINE", "MARTELO", "PENHORADO", "ELEILOES",
})


def _band(value: float, bands) -> str:
    for lo, hi in bands:
        if lo <= value < hi:
            return f"{lo//1000}k-{hi//1000}k" if lo >= 1000 else f"<{hi//1000}k"
    return ">=200k"


def _age_band(age: int) -> str:
    for i in range(len(AGE_BANDS) - 1):
        if AGE_BANDS[i] <= age < AGE_BANDS[i + 1]:
            return f"{AGE_BANDS[i]}-{AGE_BANDS[i+1]}y"
    return f">{AGE_BANDS[-1]}y"


def _comp_bucket(n: int) -> str:
    if n < 3:
        return "<3"
    if n <= 5:
        return "3-5"
    if n <= 10:
        return "6-10"
    return ">10"


def _metrics(errors: List[float], actuals: List[float]) -> Dict[str, Any]:
    if not errors:
        return {"n": 0, "status": NOT_MEASURED}
    abs_err = np.abs(np.array(errors, dtype=float))
    pct = abs_err / np.maximum(np.array(actuals, dtype=float), 1.0) * 100.0
    return {
        "n": len(errors),
        "mae": round(float(np.mean(abs_err)), 2),
        "median_ae": round(float(np.median(abs_err)), 2),
        "rmse": round(float(np.sqrt(np.mean(np.array(errors, dtype=float) ** 2))), 2),
        "mape_pct": round(float(np.nanmedian(pct)), 2),
        "rmspe_pct": round(float(np.sqrt(np.nanmean(pct ** 2))), 2),
    }


def _eligible(row: Dict[str, Any]) -> bool:
    price = row.get("price")
    if not price:
        return False
    try:
        price = float(price)
    except (TypeError, ValueError):
        return False
    if not (300 <= price <= 500_000):
        return False
    if str(row.get("price_kind") or "").lower() != "total":
        return False
    if str(row.get("currency") or "").upper() != "EUR":
        return False
    if str(row.get("quality_status") or "").lower() not in {
        "valid", "valid_with_warning"
    }:
        return False
    if str(row.get("source", "")).upper() in _AUCTION:
        return False
    return True


def _resolve_historical_cutoff(
    rows: List[Dict[str, Any]], cutoff: Any = None
) -> Any:
    if cutoff is not None:
        return normalize_cutoff(cutoff)
    observed = []
    for row in rows:
        for field in ("last_seen", "observed_at", "first_seen"):
            value = normalize_cutoff(row.get(field))
            if value is not None:
                observed.append(value)
                break
    # A historical backtest is explicitly as-of the last observed listing,
    # not as-of an implicit future ``now``.  With no timestamps the service
    # remains compatible but reports NOT_MEASURED.
    return max(observed) if observed else None


def run_backtest(
    rows: List[Dict[str, Any]],
    *,
    tag: str = "baseline",
    use_ml: bool = False,
    cutoff: Any = None,
    max_age_hours: Any = None,
    snapshot: str = HISTORICAL_SNAPSHOT,
) -> Dict[str, Any]:
    """Leave-one-out contra o target observado de ``asking_price``.

    Isto mede erro contra outro preço anunciado no mesmo snapshot. Não é uma
    métrica de preço vendido, lucro realizado ou retorno financeiro: a BD
    operacional só contém observações de asking e histórico de asking.
    """
    effective_cutoff = (
        _resolve_historical_cutoff(rows, cutoff)
        if snapshot == HISTORICAL_SNAPSHOT
        else normalize_cutoff(cutoff)
    )
    svc = ValuationService.from_rows(
        rows,
        cutoff=effective_cutoff,
        max_age_hours=max_age_hours,
        snapshot=snapshot,
    )

    ml = None
    if use_ml:
        try:
            from valuation.predict import PricePredictor
            ml = PricePredictor("carros")
            if not ml.model_loaded_ok:
                ml = None
        except Exception as exc:  # pragma: no cover
            logging.warning("ML indisponivel: %s", exc)
            ml = None

    results: List[Dict[str, Any]] = []
    for r in rows:
        res = svc.evaluate(r)
        est = res.estimate
        price = float(r.get("price") or 0)
        temporal = row_freshness(
            r,
            cutoff=effective_cutoff,
            max_age_hours=max_age_hours,
            snapshot=snapshot,
        )
        ml_pred = None
        if ml is not None:
            try:
                ml_pred = ml.predict(r)
            except Exception:
                ml_pred = None
        results.append({
            "id": r["id"], "brand": r.get("brand"), "model": r.get("model"),
            "year": r.get("year"), "km": r.get("km"),
            # ``price`` is retained as a compatibility alias; the semantic
            # target is explicit and never called sale_price.
            "price": price, "asking_price": price,
            "target": VALUATION_TARGET, "target_field": VALUATION_TARGET,
            "est": est.value, "low": est.low, "high": est.high,
            "confidence": est.confidence, "conf_label": est.confidence_label,
            "n_comp": est.comparables_used, "method": est.method, "status": est.status,
            "opportunity": res.opportunity.label, "deal_score": res.deal_score,
            "mean_similarity": est.mean_similarity, "ml_pred": ml_pred,
            "freshness": temporal.get("freshness", NOT_MEASURED),
            "freshness_status": temporal.get("freshness", NOT_MEASURED),
            "age_hours": temporal.get("age_hours"),
            "observed_at": temporal.get("observed_at"),
            "cutoff": temporal.get("cutoff"),
            "max_age_hours": temporal.get("max_age_hours"),
            "snapshot": snapshot,
            "ground_truth_available": bool(res.ground_truth_available),
        })

    valued = [r for r in results if r["est"] is not None and r["price"] > 0]
    errors = [r["est"] - r["price"] for r in valued]
    actuals = [r["price"] for r in valued]
    global_m = _metrics(errors, actuals)
    coverage = len(valued) / len(results) if results else 0.0
    in_interval = [
        r["low"] <= r["price"] <= r["high"]
        for r in valued if r["low"] is not None and r["high"] is not None
    ]
    interval_hit = float(np.mean(in_interval)) if in_interval else None

    def bucketed(key_fn):
        groups: Dict[str, List[float]] = defaultdict(list)
        acts: Dict[str, List[float]] = defaultdict(list)
        for r in valued:
            k = key_fn(r)
            groups[k].append(r["est"] - r["price"])
            acts[k].append(r["price"])
        return {k: _metrics(groups[k], acts[k]) for k in sorted(groups)}

    ml_metrics = None
    if ml is not None and any(r["ml_pred"] for r in results):
        ml_v = [r for r in results if r["ml_pred"] and r["price"] > 0]
        ml_metrics = _metrics(
            [r["ml_pred"] - r["price"] for r in ml_v],
            [r["price"] for r in ml_v],
        )

    confs = [r["confidence"] for r in valued if r["confidence"] is not None]
    comps = [r["n_comp"] for r in valued]
    freshness_counts = Counter(r["freshness"] for r in results)
    gt_count = sum(1 for r in results if r["ground_truth_available"])
    effective_cutoff_iso = (
        normalize_cutoff(effective_cutoff).isoformat()
        if effective_cutoff is not None else None
    )
    report = {
        "tag": tag,
        "valuation_version": VALUATION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": VALUATION_TARGET,
        "target_field": VALUATION_TARGET,
        "snapshot": {
            "kind": snapshot,
            "cutoff": effective_cutoff_iso,
            "max_age_hours": float(max_age_hours) if max_age_hours is not None else None,
            "freshness_counts": dict(freshness_counts),
        },
        "ground_truth": {
            "available_count": gt_count,
            "status": "MEASURED" if gt_count else NOT_MEASURED,
            "note": (
                "Backtest compara asking_price; não mede sale_price ou "
                "realized_profit sem labels de transação."
            ),
        },
        "population": {
            "total": len(results), "valued": len(valued),
            "insufficient": len(results) - len(valued),
            "coverage_pct": round(coverage * 100, 1) if results else None,
            "not_measured": freshness_counts.get(NOT_MEASURED, 0),
            "stale": freshness_counts.get(STALE, 0),
            "future": freshness_counts.get(FUTURE, 0),
        },
        "global": global_m,
        "interval_coverage_pct": round(interval_hit * 100, 1) if interval_hit is not None else None,
        "ml_isolated": ml_metrics,
        "by_price_band": bucketed(lambda r: _band(r["price"], PRICE_BANDS)),
        "by_age_band": bucketed(lambda r: _age_band(2026 - (r["year"] or 2000))),
        "by_num_comps": bucketed(lambda r: _comp_bucket(r["n_comp"])),
        "by_conf_label": bucketed(lambda r: r["conf_label"] or "unknown"),
        "by_brand": bucketed(lambda r: str(r["brand"])[:20]),
        "confidence_mean": round(float(np.mean(confs)), 3) if confs else None,
        "mean_comps": round(float(np.mean(comps)), 1) if comps else None,
        "methods": dict(Counter(r["method"] for r in valued).most_common(15)),
        "opportunities": dict(Counter(r["opportunity"] for r in valued).most_common()),
        "worst_errors": sorted(
            valued,
            key=lambda r: abs((r["est"] - r["price"]) / max(r["price"], 1)),
            reverse=True,
        )[:25],
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=0, help="0 = usar toda a base")
    parser.add_argument("--out", default="reports/backtest_baseline.json")
    parser.add_argument("--tag", default="v3.0")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ml", action="store_true", help="tambem mede o ML isolado")
    parser.add_argument(
        "--cutoff",
        default=None,
        help="cutoff ISO-8601; por omissão usa o último last_seen no snapshot histórico",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        help="janela temporal explícita; ausente no histórico não inventa freshness",
    )
    parser.add_argument(
        "--snapshot",
        choices=("current", "historical"),
        default=HISTORICAL_SNAPSHOT,
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rows = load_market_rows(
        limit=None,
        cutoff=args.cutoff,
        max_age_hours=args.max_age_hours,
        snapshot=args.snapshot,
    )
    rows = [r for r in rows if _eligible(r)]
    if args.sample and args.sample > 0:
        rng = np.random.default_rng(args.seed)
        idx = rng.choice(len(rows), size=min(args.sample, len(rows)), replace=False)
        rows = [rows[i] for i in idx]

    logging.info("Backtest %s: %d veiculos elegiveis", args.tag, len(rows))
    report = run_backtest(
        rows,
        tag=args.tag,
        use_ml=args.ml,
        cutoff=args.cutoff,
        max_age_hours=args.max_age_hours,
        snapshot=args.snapshot,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    summary = {k: v for k, v in report.items() if k != "worst_errors"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    logging.info("Gravado em %s", out)


if __name__ == "__main__":
    main()
