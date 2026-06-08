#!/usr/bin/env python3
"""
Script de execução para coleta de Ground Truth (preços reais de adjudicação)
================================================================================
Executa o scraper de leilões para todas as fontes configuradas, coleta
mínimo 500 transações, mostra estatísticas ao final e salva backup CSV.

Uso:
    python scripts/collect_ground_truth.py
    python scripts/collect_ground_truth.py --max-per-source 300 --min-total 1000
    python scripts/collect_ground_truth.py --csv data/backups/ground_truth_$(date +%Y%m%d).csv
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from scrapers.ground_truth_scraper import scrape_all_ground_truth

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(log_dir: Path, log_level: str = "INFO") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"ground_truth_{timestamp}.log"

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=settings.log_format,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger("collect_ground_truth")
    logger.info(f"Logging to {log_file}")
    return logger


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coleta preços reais de adjudicação de leilões de veículos em Portugal"
    )
    parser.add_argument(
        "--max-per-source",
        type=int,
        default=200,
        help="Máximo de listagens por fonte (default: 200)",
    )
    parser.add_argument(
        "--min-total",
        type=int,
        default=500,
        help="Mínimo total de transações a coletar (default: 500)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Caminho para backup CSV (default: auto-gerado em data/backups/)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nível de logging",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Não salvar no banco de dados (apenas CSV)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Statistics display
# ---------------------------------------------------------------------------

def print_statistics(stats: Dict[str, Any]) -> None:
    print("\n" + "=" * 70)
    print("  ESTATÍSTICAS DE COLETA — GROUND TRUTH")
    print("=" * 70)

    started = stats.get("started_at", "N/A")
    finished = stats.get("finished_at", "N/A")
    print(f"  Início:     {started}")
    print(f"  Término:    {finished}")
    print(f"  Total listagens coletadas: {stats.get('total_listings', 0)}")
    print(f"  Total salvas na BD:        {stats.get('total_saved', 0)}")
    print()

    print("  Por fonte:")
    print("  " + "-" * 66)
    print(f"  {'Fonte':<15} {'Coletadas':>10} {'Válidas':>10} {'Salvas':>10} {'Erros':>10}")
    print("  " + "-" * 66)
    for source, data in stats.get("by_source", {}).items():
        scraped = data.get("scraped", 0)
        valid = data.get("valid", 0)
        saved = data.get("saved", 0)
        errors = data.get("errors", 0)
        exc = data.get("exception", "")
        status = "✅" if saved > 0 else "⚠️" if scraped > 0 else "❌"
        print(f"  {status} {source:<12} {scraped:>10} {valid:>10} {saved:>10} {errors:>10}")
        if exc:
            print(f"      └─ Erro: {exc[:60]}")
    print("  " + "-" * 66)

    errors = stats.get("errors", [])
    if errors:
        print(f"\n  ⚠️  Erros globais ({len(errors)}):")
        for err in errors[:5]:
            print(f"      • {err}")
        if len(errors) > 5:
            print(f"      ... e mais {len(errors) - 5} erros (ver log)")

    print("=" * 70)

    # Target check
    total = stats.get("total_listings", 0)
    target = stats.get("min_total", 500)
    if total >= target:
        print(f"\n  ✅ META ATINGIDA: {total} >= {target} transações")
    else:
        print(f"\n  ⚠️  META NÃO ATINGIDA: {total} < {target} transações")
        print("      Recomendação: aumentar max-per-source ou verificar fontes B2B (BCA, Manheim)")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main_async(args: argparse.Namespace) -> int:
    logger = setup_logging(PROJECT_ROOT / "logs", args.log_level)
    logger.info("=" * 60)
    logger.info("COLLECT GROUND TRUTH — Iniciando coleta de preços reais de leilão")
    logger.info("=" * 60)

    # Determine CSV path
    if args.csv:
        csv_path = args.csv
    else:
        backup_dir = PROJECT_ROOT / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_path = str(backup_dir / f"ground_truth_{timestamp}.csv")

    logger.info(f"Config: max_per_source={args.max_per_source}, min_total={args.min_total}")
    logger.info(f"CSV backup: {csv_path}")

    try:
        stats = await scrape_all_ground_truth(
            max_per_source=args.max_per_source,
            min_total=args.min_total,
            save_csv_path=csv_path,
        )
        stats["min_total"] = args.min_total
    except Exception as e:
        logger.exception("Falha fatal na coleta de ground truth")
        print(f"\n❌ ERRO FATAL: {e}\n")
        return 1

    print_statistics(stats)
    logger.info("Coleta finalizada com sucesso")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo utilizador")
        return 130


if __name__ == "__main__":
    sys.exit(main())
