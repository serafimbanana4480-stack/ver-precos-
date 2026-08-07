#!/usr/bin/env python3
"""
Verifica a saúde de cada fonte de scraping.

O modo de falha que isto apanha
-------------------------------
Um scraper raramente morre com estrondo. O que acontece é o site mudar uma
classe CSS e o parser passar a devolver anúncios sem km, sem ano ou sem
preço. O scraper "funciona": não lança exceção, devolve linhas, e o pipeline
guarda-as. Semanas depois descobre-se que metade da base é inútil, porque
uma avaliação sem km e sem ano não vale nada.

Este script corre cada fonte com um lote pequeno e mede a **cobertura de
campos**. Uma fonte que devolve 50 anúncios com 4% de km preenchido está
partida, mesmo que o relatório de execução diga "sucesso".

Uso:
    python scripts/check_sources.py
    python scripts/check_sources.py --fonte eleiloes --fonte autoscout24de
    python scripts/check_sources.py --amostra 30 --json reports/saude_fontes.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.extractors import CRITICAL_FIELDS, field_coverage  # noqa: E402
from scrapers.parallel_runner import DEFAULT_SOURCES, _run_source  # noqa: E402

logger = logging.getLogger("check_sources")

#: Abaixo desta cobertura, o campo conta como perdido.
FIELD_THRESHOLD = 60.0
#: Abaixo deste nº de anúncios, assume-se bloqueio ou fonte esgotada.
MIN_LISTINGS = 3


def check_source(name: str, sample: int = 20, vehicle_type: str = "carros") -> Dict[str, Any]:
    """Corre uma fonte com um lote pequeno e devolve o diagnóstico."""
    result = _run_source(name, sample, vehicle_type)
    listings = result.listings
    coverage = result.coverage or field_coverage(listings)

    if not listings:
        status = "morta"
        diagnosis = (
            "Nenhum anúncio devolvido. Causas prováveis: bloqueio anti-bot, "
            "URL de pesquisa alterada, ou site em baixo."
        )
    elif len(listings) < MIN_LISTINGS:
        status = "degradada"
        diagnosis = f"Só {len(listings)} anúncios: paginação ou filtro partido."
    elif not coverage.get("critical_ok", False):
        status = "degradada"
        weak = [
            f"{f} ({coverage['critical'].get(f, 0):.0f}%)"
            for f in CRITICAL_FIELDS
            if coverage.get("critical", {}).get(f, 0) < FIELD_THRESHOLD
        ]
        diagnosis = (
            "Anúncios chegam mas faltam campos críticos: " + ", ".join(weak) +
            ". O parser precisa de ser reajustado ao HTML atual."
        )
    else:
        status = "saudavel"
        diagnosis = "Volume e cobertura de campos dentro do esperado."

    return {
        "fonte": name,
        "estado": status,
        "diagnostico": diagnosis,
        "anuncios": len(listings),
        "duracao_s": round(result.duration, 1),
        "erros": result.errors,
        "cobertura_critica": coverage.get("critical", {}),
        "cobertura": coverage.get("coverage", {}),
        "exemplo": listings[0] if listings else None,
    }


def check_all(
    sources: Optional[List[str]] = None,
    sample: int = 20,
    vehicle_type: str = "carros",
) -> Dict[str, Any]:
    names = list(sources) if sources else list(DEFAULT_SOURCES)
    reports = []
    for name in names:
        logger.info("A verificar %s…", name)
        try:
            reports.append(check_source(name, sample, vehicle_type))
        except Exception as exc:  # noqa: BLE001
            reports.append({
                "fonte": name, "estado": "erro", "anuncios": 0,
                "diagnostico": f"{type(exc).__name__}: {exc}",
                "erros": [str(exc)], "cobertura_critica": {}, "cobertura": {},
            })

    tally: Dict[str, int] = {}
    for report in reports:
        tally[report["estado"]] = tally.get(report["estado"], 0) + 1

    return {
        "verificado_em": datetime.now(timezone.utc).isoformat(),
        "amostra_por_fonte": sample,
        "resumo": tally,
        "fontes": reports,
    }


def _print(report: Dict[str, Any]) -> None:
    icon = {"saudavel": "OK  ", "degradada": "AVIS", "morta": "FALH", "erro": "ERRO"}
    print()
    print("=" * 78)
    print("  SAÚDE DAS FONTES DE SCRAPING")
    print("=" * 78)
    print(f"  Resumo: {report['resumo']}")
    print(f"  Amostra por fonte: {report['amostra_por_fonte']} anúncios")
    print("-" * 78)
    for source in sorted(report["fontes"], key=lambda r: (r["estado"], r["fonte"])):
        print(f"  [{icon.get(source['estado'], '????')}] {source['fonte']:<20} "
              f"{source['anuncios']:>4} anúncios  {source['duracao_s']:>6.1f}s")
        if source["estado"] != "saudavel":
            print(f"         {source['diagnostico']}")
        for err in source.get("erros", [])[:2]:
            print(f"         erro: {err[:100]}")
    print("=" * 78)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostica cada fonte de scraping.")
    parser.add_argument("--fonte", action="append", default=None, help="Fonte a testar (repetível)")
    parser.add_argument("--amostra", type=int, default=20, help="Anúncios por fonte")
    parser.add_argument("--tipo", default="carros", choices=["carros", "motos"])
    parser.add_argument("--json", type=str, default=None, help="Gravar relatório JSON")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    report = check_all(args.fonte, args.amostra, args.tipo)
    _print(report)

    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8")
        print(f"  Relatório em {path}")

    # Código de saída não-zero quando há fontes mortas: serve para CI/cron.
    return 1 if report["resumo"].get("morta") or report["resumo"].get("erro") else 0


if __name__ == "__main__":
    raise SystemExit(main())
