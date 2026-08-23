"""
VER PRECOS — Backfill de buyer_profit / net_profit (lucro líquido REAL)
=====================================================================

Corrige o enviesamento do lucro dos veículos. O cálculo anterior usava
spread bruto (estimated_value - price) como "buyer_profit", o que ignora
impostos, reparos, comissão de venda e despesas — subestimando o custo
real e inflacionando o lucro apresentado.

Este script calcula a MARGEM LÍQUIDA real:

    net_profit = preco_revenda
                - impostos (IMT 5% + Selo 0.5%  [ISV aplicado só a importação])
                - reparos (estimados por condition_score)
                - comissao 7%  (sobre o preco de revenda)
                - despesas fixas 250€
                - preco de compra

Regras:
  * Leilões (LEILOSOC / VPAUTO / MANHEIM / AUTOROLA / BCA) usam a lógica
    própria do HybridValuator (múltiplo leilão->retail + reparos) e NÃO o
    segment median inflacionado. O preço de revenda já vem ajustado; aqui
    aplica-se apenas a comissão/despesas normais + IMT/Selo (não ISV, pois
    leilão nacional já traz impostos incorporados no martelo).
  * O preço de revenda vem do valuation.hybrid_valuator (produção canónica),
    igual ao usado para preencher `estimated_value`.

Popula também a coluna `net_profit` (criada via ALTER TABLE se não existir)
para o dashboard não ter de refazer o cálculo por página.

Uso:
    python scripts/backfill_profit.py --batch 50     # teste pequeno (seguro)
    python scripts/backfill_profit.py --all           # corre TODA a BD (confirma!)
    python scripts/backfill_profit.py --dry-run      # só reporta, não escreve
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_profit")

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "autodeal.db"

# --- Parâmetros de custo (Portugal, revenda a particular/stand) ---
IMT_RATE = 0.05          # IMT sobre transmissão onerosa
SELO_RATE = 0.005        # Imposto de Selo
COMMISSION_RATE = 0.07   # comissão de venda (stand/portal) sobre revenda
FIXED_EXPENSES = 250.0  # despesas fixas (transporte, registo, publicidade)

AUCTION_SOURCES = {"LEILOSOC", "VPAUTO", "MANHEIM", "AUTOROLA", "BCA", "AUTOLINE", "MARTELO", "PENHORADO"}

REPAIR_BY_CONDITION = [
    (8.0, 0), (6.0, 500), (4.0, 1500), (2.0, 3000), (0.0, 5000),
]

# Lógica de múltiplo leilão->retail (espelha HybridValuator)
def _auction_multiple(age: int, km: int) -> float:
    if age > 15 or km > 250000:
        return 3.5
    if age > 10 or km > 150000:
        return 2.5
    if age > 5:
        return 2.0
    return 1.6

def estimate_repair(condition_score: Optional[float]) -> float:
    cs = float(condition_score) if condition_score is not None else 6.0
    for threshold, cost in REPAIR_BY_CONDITION:
        if cs >= threshold:
            return float(cost)
    return 5000.0


def compute_net_profit(price: float, resale: float, source: str,
                       condition_score: Optional[float], km: Optional[int],
                       year: Optional[int]) -> dict:
    """Margem líquida real. `resale` = preço de revenda já estimado."""
    price = float(price or 0)
    resale = float(resale or 0)
    is_auction = str(source).upper() in AUCTION_SOURCES
    age = max(0, datetime.now().year - int(year)) if year else 0
    km = int(km or 0)

    repair = estimate_repair(condition_score)

    if is_auction:
        # Leilão nacional: martelo já inclui ISV/IMT; só Selo + comissão + despesas.
        taxes = price * SELO_RATE
    else:
        taxes = price * (IMT_RATE + SELO_RATE)

    commission = resale * COMMISSION_RATE
    costs = taxes + repair + commission + FIXED_EXPENSES
    net = resale - price - costs
    net_pct = (net / price * 100.0) if price > 0 else 0.0

    return {
        "buyer_profit": round(net, 2),
        "buyer_profit_margin": round(net_pct, 2),
        "net_profit": round(net, 2),
        "taxes": round(taxes, 2),
        "repair_costs": round(repair, 2),
        "commission": round(commission, 2),
        "total_additional_costs": round(costs, 2),
        "is_auction": is_auction,
    }


def ensure_net_profit_column(conn: sqlite3.Connection) -> bool:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(vehicles)")
    cols = {r[1] for r in cur.fetchall()}
    if "net_profit" not in cols:
        cur.execute("ALTER TABLE vehicles ADD COLUMN net_profit FLOAT")
        conn.commit()
        logger.info("Coluna net_profit criada.")
        return True
    return False


def get_resale_valuator():
    """Carrega o HybridValuator (produção) — respeita a regra de não mexer em valuation/."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from valuation.hybrid_valuator import get_valuator
    return get_valuator()


def fetch_targets(conn: sqlite3.Connection, limit: Optional[int]) -> list:
    cur = conn.cursor()
    q = """
        SELECT id, price, estimated_value, source, condition_score, km, year,
               brand, model, fuel_type
        FROM vehicles
        WHERE is_active = 1 AND price > 0 AND buyer_profit IS NULL
    """
    if limit:
        q += f" LIMIT {int(limit)}"
    cur.execute(q)
    return cur.fetchall()


def run(limit: Optional[int], dry_run: bool, verbose: bool = True) -> dict:
    """Recompute profit through the same canonical valuation writer.

    The former implementation updated only a subset of profit columns with a
    second fiscal formula. That made the dashboard depend on which script ran
    last. Dry-run still evaluates the exact canonical block, but never writes.
    """
    from valuation.service import ValuationService, load_market_rows, revalue_database

    rows = load_market_rows(limit=None, include_ineligible=True)
    targets = rows if limit is None else rows[:limit]
    if not targets:
        logger.info("Nenhum veículo elegível para reavaliação.")
        return {"processed": 0, "avg_before": 0, "avg_after": 0}

    service = ValuationService.from_rows(rows)
    if dry_run:
        values = [service.evaluate(row) for row in targets]
        before = [
            float(row.get("valuation_details", {}).get("estimated_value") or 0.0)
            - float(row.get("price") or 0.0)
            for row in targets
        ]
        after = [float(value.net_profit) for value in values if value.net_profit is not None]
        stats = {
            "processed": len(values),
            "avg_before": sum(before) / len(before) if before else 0.0,
            "avg_after": sum(after) / len(after) if after else 0.0,
            "dry_run": True,
        }
    else:
        stats = revalue_database(
            force=True,
            limit=limit,
            batch_size=min(max(limit or 500, 1), 1000),
        )
        stats = {**stats, "dry_run": False}

    if verbose:
        logger.info("Reavaliação canónica: %s", stats)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=False)

    grp.add_argument("--batch", type=int, default=50, help="Nº de veículos (teste, seguro)")
    grp.add_argument("--all", action="store_true", help="Corre TODA a BD sem limite")
    ap.add_argument("--dry-run", action="store_true", help="Não escreve na BD")
    args = ap.parse_args()

    limit = None if args.all else args.batch
    run(limit=limit, dry_run=args.dry_run)
