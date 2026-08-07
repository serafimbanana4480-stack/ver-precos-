#!/usr/bin/env python3
"""
Correcção das fugas de preço + recalibração do ranking
======================================================

Script idempotente que repara a base de dados existente e deixa as colunas de
fiabilidade prontas para o dashboard. Executa quatro fases:

1. **Purga do lucro fantasma** — viaturas sem preço retail (``price <= 0`` ou
   ``price_kind`` de leilão/mensalidade/entrada) perdem todos os campos de
   profit. Eram 990 registos a somar 5,4 M€ de lucro inexistente.

2. **Contagem de comparáveis** — para cada viatura, quantos anúncios existem
   da mesma marca+modelo com ano ±2. É o preditor dominante do erro do
   modelo (MAPE 24,6 % com <3 comparáveis vs 6,9 % com 20+).

3. **Shrinkage empírico-Bayesiano** — encolhe o gap ``estimated_value/price``
   proporcionalmente à fiabilidade do tier. Ver ``valuation/reliability.py``.

4. **Recalibração do deal_score + deal_grade** — substitui a escala colapsada
   (91 % das viaturas em 5,x) por percentis do profit credível, e preenche o
   ``deal_grade`` que estava 99,8 % NULL.

Uso::

    python scripts/fix_price_leaks.py                 # aplica
    python scripts/fix_price_leaks.py --dry-run       # só relata
    python scripts/fix_price_leaks.py --db outro.db
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# Carrega valuation.reliability directamente do ficheiro: o __init__ do pacote
# valuation puxa sklearn/lightgbm, e este script tem de correr numa instalação
# mínima (só stdlib) para poder ser usado em CI e em contentores de manutenção.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_reliability", os.path.join(_ROOT, "valuation", "reliability.py")
)
_reliability = importlib.util.module_from_spec(_spec)
# Tem de estar em sys.modules antes de exec_module: o @dataclass resolve
# type hints via sys.modules[cls.__module__].
sys.modules["_reliability"] = _reliability
_spec.loader.exec_module(_reliability)

DEFAULT_LAMBDAS = _reliability.DEFAULT_LAMBDAS
MAX_CREDIBLE_GAP_PCT = _reliability.MAX_CREDIBLE_GAP_PCT
ConfidenceTier = _reliability.ConfidenceTier
assess = _reliability.assess
comparable_tier = _reliability.comparable_tier
fit_shrinkage_lambdas = _reliability.fit_shrinkage_lambdas

DEFAULT_DB = os.path.join("data", "autodeal.db")

# Colunas de fiabilidade acrescentadas por este script.
NEW_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("comparables_count", "INTEGER"),
    ("valuation_confidence", "TEXT"),
    ("adjusted_estimated_value", "REAL"),
    ("credible_profit", "REAL"),
    ("profit_is_publishable", "INTEGER"),
)

# Campos zerados quando não há preço retail.
PROFIT_FIELDS: Tuple[str, ...] = (
    "profit_potential",
    "profit_percentage",
    "net_profit",
    "buyer_profit",
    "buyer_profit_margin",
    "buyer_roi",
    "estimated_savings",
    "price_discount_percentage",
    "repair_costs",
    "taxes",
    "total_additional_costs",
)

RETAIL_KINDS = {"total", "retail", None, ""}

# Fontes de leilão: o preço é transação, não ask de retalho — não servem de
# comparáveis (mesma lista do HybridValuator; mantida aqui porque este script
# corre sem o stack de ML).
AUCTION_SOURCES = (
    "LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA",
    "AUTOLINE", "MARTELO", "PENHORADO",
)

# Grades por percentil do profit credível entre viaturas publicáveis.
# Substitui os thresholds absolutos, que colapsavam tudo em 'fair'.
GRADE_PERCENTILES: Tuple[Tuple[float, str], ...] = (
    (99.0, "exceptional"),
    (95.0, "excellent"),
    (85.0, "good"),
    (60.0, "fair"),
    (0.0, "poor"),
)


def _model_key(brand: Optional[str], model: Optional[str]) -> Tuple[str, str]:
    """Chave de agrupamento de comparáveis, tolerante a ruído de scraping.

    Os sites de leilão injectam números de lote no campo ``model``
    ("206 18", "GTC 4 47"), por isso trunca-se aos primeiros 12 caracteres
    normalizados — suficiente para agrupar o modelo, curto o bastante para
    ignorar o sufixo do lote.
    """
    return ((brand or "").strip().lower(), (model or "").strip().lower()[:12])


def ensure_columns(conn: sqlite3.Connection, dry_run: bool = False) -> List[str]:
    """Acrescenta as colunas de fiabilidade se ainda não existirem."""
    existing = {r[1] for r in conn.execute("PRAGMA table_info(vehicles)")}
    added = []
    for name, sql_type in NEW_COLUMNS:
        if name not in existing:
            added.append(name)
            if not dry_run:
                conn.execute(f"ALTER TABLE vehicles ADD COLUMN {name} {sql_type}")
    return added


def purge_phantom_profit(conn: sqlite3.Connection, dry_run: bool = False) -> Dict:
    """Fase 1 — apaga profit em viaturas sem preço retail."""
    kinds = ",".join("?" for _ in RETAIL_KINDS if _)
    where = (
        "(price IS NULL OR price <= 0) "
        f"OR (price_kind IS NOT NULL AND price_kind NOT IN ({kinds})) "
        "OR (price_rejection_reason IS NOT NULL AND price_rejection_reason != '')"
    )
    params = [k for k in RETAIL_KINDS if k]

    affected = conn.execute(
        f"SELECT COUNT(*) FROM vehicles WHERE {where}", params
    ).fetchone()[0]
    phantom = conn.execute(
        f"SELECT COALESCE(SUM(profit_potential),0) FROM vehicles "
        f"WHERE ({where}) AND profit_potential > 0",
        params,
    ).fetchone()[0]

    if not dry_run:
        sets = ", ".join(f"{f} = NULL" for f in PROFIT_FIELDS)
        conn.execute(
            f"UPDATE vehicles SET {sets}, deal_grade = 'N/A', "
            f"valuation_confidence = ?, profit_is_publishable = 0, "
            f"credible_profit = NULL, adjusted_estimated_value = NULL "
            f"WHERE {where}",
            [ConfidenceTier.NONE] + params,
        )

    return {
        "vehicles_without_retail_price": affected,
        "phantom_profit_eur": round(phantom, 2),
    }


def count_comparables(conn: sqlite3.Connection) -> Dict[int, int]:
    """Fase 2 — nº de comparáveis (marca+modelo, ano ±2) por viatura.

    Só anúncios retail ativos e válidos contam como comparáveis — leilões,
    preços de entrada/mensalidade, inativos e inválidos são excluídos,
    alinhado com o ``HybridValuator``. Contá-los a mais empurrava veículos
    para tiers mais densos (menos shrinkage) e re-inflava o lucro credível.
    O(N): contagens por chave num Counter, sem varrimentos repetidos.
    """
    kinds = ",".join("?" for _ in RETAIL_KINDS if _)
    auctions = ",".join("?" for _ in AUCTION_SOURCES)
    rows = conn.execute(
        f"SELECT id, brand, model, year FROM vehicles "
        f"WHERE is_active = 1 AND price > 0 "
        f"AND (price_kind IS NULL OR price_kind IN ({kinds})) "
        f"AND (price_rejection_reason IS NULL OR price_rejection_reason = '') "
        f"AND quality_status IN ('valid', 'valid_with_warning') "
        f"AND (source IS NULL OR source NOT IN ({auctions}))",
        [k for k in RETAIL_KINDS if k] + list(AUCTION_SOURCES),
    ).fetchall()

    by_year: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    for _id, brand, model, year in rows:
        by_year[_model_key(brand, model)][year or 0] += 1

    counts: Dict[int, int] = {}
    for _id, brand, model, year in rows:
        y = year or 0
        window = sum(
            by_year[_model_key(brand, model)][yy]
            for yy in range(y - 2, y + 3)
        )
        # -1 para não contar a própria viatura
        counts[_id] = max(0, window - 1)
    return counts


def apply_reliability(
    conn: sqlite3.Connection,
    counts: Dict[int, int],
    dry_run: bool = False,
) -> Dict:
    """Fase 3 — ajusta estimated_value e profit por fiabilidade."""
    rows = conn.execute(
        "SELECT id, price, estimated_value, price_kind, price_rejection_reason, "
        "quality_status FROM vehicles"
    ).fetchall()

    # Ajusta os lambdas aos dados reais desta base.
    observations = [
        (r[1], r[2], counts.get(r[0], 0))
        for r in rows
        if r[1] and r[2] and r[1] > 1000 and r[2] > 500
        and r[5] in ("valid", "valid_with_warning")
    ]
    lambdas = fit_shrinkage_lambdas(observations)

    updates = []
    tier_hist: Dict[str, int] = defaultdict(int)
    capped = 0
    publishable = 0

    for _id, price, ev, kind, rejection, _q in rows:
        n_comp = counts.get(_id, 0)
        is_retail = (kind in RETAIL_KINDS) and not rejection
        a = assess(
            price, ev, n_comp,
            lambdas=lambdas,
            price_is_retail=is_retail,
            max_gap_pct=MAX_CREDIBLE_GAP_PCT,
        )
        tier_hist[a.confidence] += 1
        capped += int(a.capped)
        publishable += int(a.is_publishable)
        updates.append((
            n_comp,
            a.confidence,
            a.adjusted_estimated_value,
            a.credible_profit,
            1 if a.is_publishable else 0,
            _id,
        ))

    if not dry_run:
        conn.executemany(
            "UPDATE vehicles SET comparables_count=?, valuation_confidence=?, "
            "adjusted_estimated_value=?, credible_profit=?, "
            "profit_is_publishable=? WHERE id=?",
            updates,
        )

    return {
        "lambdas": lambdas,
        "confidence_distribution": dict(tier_hist),
        "gaps_capped": capped,
        "publishable_deals": publishable,
    }


def recalibrate_scores(conn: sqlite3.Connection, dry_run: bool = False) -> Dict:
    """Fase 4 — deal_score por percentil + deal_grade preenchido."""
    # Em --dry-run as colunas de fiabilidade ainda não existem: nada a pontuar.
    columns = {r[1] for r in conn.execute("PRAGMA table_info(vehicles)")}
    if not {"credible_profit", "profit_is_publishable"} <= columns:
        return {"scored": 0, "grades": {}, "skipped": "colunas ainda não criadas"}

    rows = conn.execute(
        "SELECT id, credible_profit, price FROM vehicles "
        "WHERE profit_is_publishable = 1 AND credible_profit IS NOT NULL"
    ).fetchall()

    if not rows:
        return {"scored": 0, "grades": {}}

    # Ordena por margem relativa: um lucro de 2 000 € num carro de 8 000 € é
    # melhor negócio do que 2 000 € num de 80 000 €.
    ranked = sorted(
        rows,
        key=lambda r: (r[1] / r[2]) if r[2] else 0.0,
    )
    total = len(ranked)

    updates = []
    grades: Dict[str, int] = defaultdict(int)
    for idx, (_id, profit, price) in enumerate(ranked):
        pct = (idx + 1) / total * 100.0
        # Escala 0-10 espalhada pelos percentis reais em vez de colapsada em 5.
        score = round(pct / 10.0, 2)
        grade = next(g for threshold, g in GRADE_PERCENTILES if pct >= threshold)
        grades[grade] += 1
        updates.append((score, grade, _id))

    if not dry_run:
        conn.executemany(
            "UPDATE vehicles SET deal_score=?, deal_grade=? WHERE id=?", updates
        )
        # Viaturas não publicáveis mantêm o deal_score honesto da reavaliação
        # (posição do preço face ao valor estimado). O filtro de publicação
        # vive em profit_is_publishable — zero em massa enganaria o utilizador
        # e escondia carros simplesmente caros.

    return {"scored": total, "grades": dict(grades)}


def build_report(conn: sqlite3.Connection) -> Dict:
    """Métricas de verificação pós-correcção."""
    q = lambda sql: conn.execute(sql).fetchone()

    total = q("SELECT COUNT(*) FROM vehicles")[0]
    leaks = q(
        "SELECT COUNT(*) FROM vehicles "
        "WHERE (price IS NULL OR price <= 0) AND profit_potential > 0"
    )[0]
    grade_null = q("SELECT COUNT(*) FROM vehicles WHERE deal_grade IS NULL")[0]
    score_5 = q(
        "SELECT COUNT(*) FROM vehicles WHERE deal_score >= 4.5 AND deal_score < 5.5"
    )[0]
    scored = q("SELECT COUNT(*) FROM vehicles WHERE deal_score IS NOT NULL")[0]

    return {
        "total_vehicles": total,
        "remaining_phantom_profit_rows": leaks,
        "deal_grade_null": grade_null,
        "deal_score_bunched_at_5": score_5,
        "deal_score_bunched_pct": round(score_5 / scored * 100, 2) if scored else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DEFAULT_DB, help="caminho da base SQLite")
    parser.add_argument("--dry-run", action="store_true", help="não escreve nada")
    parser.add_argument("--json", help="grava o relatório neste ficheiro")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERRO: base de dados não encontrada: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    report: Dict = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "db": args.db,
        "dry_run": args.dry_run,
    }

    try:
        report["columns_added"] = ensure_columns(conn, args.dry_run)
        print(f"[1/4] colunas de fiabilidade: {report['columns_added'] or 'já existiam'}")

        report["phase1_purge"] = purge_phantom_profit(conn, args.dry_run)
        p = report["phase1_purge"]
        print(
            f"[2/4] lucro fantasma purgado: {p['vehicles_without_retail_price']} viaturas, "
            f"{p['phantom_profit_eur']:,.0f} €"
        )

        counts = count_comparables(conn)
        report["phase3_reliability"] = apply_reliability(conn, counts, args.dry_run)
        r = report["phase3_reliability"]
        print(f"[3/4] shrinkage aplicado — lambdas={r['lambdas']}")
        print(f"      confiança={r['confidence_distribution']}")
        print(f"      gaps truncados={r['gaps_capped']}  publicáveis={r['publishable_deals']}")

        report["phase4_scores"] = recalibrate_scores(conn, args.dry_run)
        s = report["phase4_scores"]
        print(f"[4/4] scores recalibrados: {s['scored']} — grades={s['grades']}")

        if not args.dry_run:
            conn.commit()

        report["verification"] = build_report(conn)
        v = report["verification"]
        print()
        print("VERIFICAÇÃO")
        print(f"  lucro fantasma restante ... {v['remaining_phantom_profit_rows']} (alvo: 0)")
        print(f"  deal_grade NULL ........... {v['deal_grade_null']} (alvo: 0)")
        print(f"  scores amontoados em 5.x .. {v['deal_score_bunched_pct']} % (antes: 91 %)")
    finally:
        conn.close()

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f"\nRelatório: {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
