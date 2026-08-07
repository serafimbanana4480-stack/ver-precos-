#!/usr/bin/env python3
"""
Encontra e ordena os melhores negócios por LUCRO LÍQUIDO REALISTA.

Diferença face ao ranking anterior
----------------------------------
O ``deal_score`` ordena por *desconto relativo ao mercado*. É uma boa medida
de "está barato", mas não de "quanto dinheiro é que isto me dá". Um Fiat
Panda 20% abaixo do mercado tem um score excelente e €300 de margem; um BMW
Série 5 10% abaixo tem score medíocre e €2.400. Quem compra para revender
quer o segundo.

Este script ordena pelo que sobra depois de:
  * conversão do preço pedido em preço realista de venda;
  * ISV, registo, IPO e legalização (:mod:`valuation.pt_fiscal`);
  * recondicionamento e transporte;
  * IVA do regime da margem;
  * custo de venda e de capital imobilizado.

E descarta activamente o que parece bom demais: um desconto de 60% quase
nunca é uma oportunidade, é um salvado, uma penhora ou uma burla.

Uso:
    python scripts/find_best_deals.py
    python scripts/find_best_deals.py --min-profit 1500 --top 30
    python scripts/find_best_deals.py --incluir-suspeitos --json relatorio.json
    python scripts/find_best_deals.py --fonte ELEILOES --fonte AUTOSCOUT24_DE
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valuation.realism import ProfitAudit, audit_deal  # noqa: E402

logger = logging.getLogger("find_best_deals")

#: Vereditos que representam dinheiro real. ``suspeito`` fica de fora por
#: omissão: é uma lista de coisas a investigar, não de coisas a comprar.
ACTIONABLE = {"negocio"}


@dataclass
class DealRow:
    vehicle_id: int
    source: str
    url: str
    title: str
    brand: str
    model: str
    year: Optional[int]
    km: Optional[int]
    asking_price: float
    audit: ProfitAudit

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.vehicle_id,
            "fonte": self.source,
            "url": self.url,
            "titulo": self.title,
            "marca": self.brand,
            "modelo": self.model,
            "ano": self.year,
            "km": self.km,
            "preco_pedido": self.asking_price,
            "veredito": self.audit.verdict,
            "lucro_liquido": self.audit.net_profit,
            "lucro_pior_caso": self.audit.net_profit_worst_case,
            "roi_pct": self.audit.roi_pct,
            "roi_anualizado_pct": self.audit.roi_annualized_pct,
            "venda_realista": self.audit.realistic_sale_price,
            "preco_maximo_compra": self.audit.break_even_price,
            "custo_aquisicao": self.audit.total_acquisition_cost,
            "custos": self.audit.cost_breakdown,
            "iva_margem": self.audit.iva_margem,
            "custo_venda": self.audit.selling_cost,
            "dias_para_vender": self.audit.days_to_sell,
            "confianca": self.audit.confidence,
            "razoes": self.audit.reasons,
            "riscos": self.audit.risk_flags,
        }


def _country_for(source: str) -> str:
    return {
        "AUTOSCOUT24_DE": "DE",
        "AUTOSCOUT24_ES": "ES",
        "AUTOSCOUT24_FR": "FR",
    }.get(str(source).upper(), "PT")


def _enum_value(value: Any) -> Optional[str]:
    return getattr(value, "value", value)


def load_candidates(
    *,
    limit: int = 5000,
    sources: Optional[List[str]] = None,
    vehicle_type: str = "carros",
) -> List[Any]:
    """Carrega veículos elegíveis da base.

    Só entram anúncios com preço total válido e qualidade aceite: um preço
    em quarentena ou uma mensalidade classificada como preço produziriam um
    "negócio" que não existe.
    """
    from database.db import get_db_context
    from database.models import Source, Vehicle

    with get_db_context() as db:
        query = db.query(Vehicle).filter(
            Vehicle.price > 300,
            Vehicle.is_active.is_(True),
        )
        # Preço tem de ser retalho total em euros.
        query = query.filter(
            (Vehicle.price_kind.is_(None)) | (Vehicle.price_kind == "total")
        )
        query = query.filter(
            (Vehicle.quality_status.is_(None))
            | (Vehicle.quality_status.in_(["valid", "valid_with_warning"]))
        )
        if vehicle_type and vehicle_type != "all":
            query = query.filter(Vehicle.vehicle_type == vehicle_type)
        if sources:
            wanted = []
            for name in sources:
                try:
                    wanted.append(Source(name.upper()))
                except ValueError:
                    logger.warning("Fonte desconhecida ignorada: %s", name)
            if wanted:
                query = query.filter(Vehicle.source.in_(wanted))

        rows = query.order_by(Vehicle.last_seen.desc()).limit(limit).all()
        # Desligar os objetos da sessão para poderem ser usados depois.
        return [
            {
                "id": v.id,
                "source": _enum_value(v.source),
                "url": v.url,
                "title": v.title,
                "brand": v.brand,
                "model": v.model,
                "year": v.year,
                "km": v.km,
                "price": float(v.price or 0.0),
                "engine_size": v.engine_size,
                "fuel_type": _enum_value(v.fuel_type),
                "transmission": _enum_value(v.transmission),
                "vehicle_type": _enum_value(v.vehicle_type),
                "condition_score": v.condition_score,
                "has_accident": bool(v.has_accident),
                "seller_name": getattr(v, "seller_name", None),
                "comparables_count": v.comparables_count,
                "estimated_value": v.estimated_value,
            }
            for v in rows
        ]


def evaluate(vehicle: Dict[str, Any]) -> Optional[DealRow]:
    """Avalia um veículo e devolve a linha auditada, ou ``None``.

    A estimativa de mercado vem do motor coerente (valuation/service), que
    trata a exclusão do próprio anúncio, a hierarquia de comparáveis e a
    confiança medida. O ``audit_deal`` (custos de liquidez/condição) continua
    a correr por cima dessa estimativa.
    """
    from valuation.service import ValuationService, load_market_rows

    price = float(vehicle.get("price") or 0.0)
    if price <= 0:
        return None

    # Estimativa defensável: constrói o índice uma vez por chamada de lote se
    # necessário (find_best_deals passa os candidatos já carregados).
    svc = getattr(evaluate, "_svc", None)
    if svc is None:
        svc = ValuationService.from_rows(load_market_rows())
        evaluate._svc = svc
    valuation_row = dict(vehicle)
    v = svc.evaluate(valuation_row)
    estimate = v.estimate.value
    if estimate is None:
        return None

    source = str(vehicle.get("source") or "")
    country = _country_for(source)
    try:
        from valuation.price_drivers import liquidity_driver

        days = int(liquidity_driver(vehicle.get("brand")).get("days_to_sell", 60))
    except Exception:  # noqa: BLE001 — liquidez é um refinamento, não um requisito
        days = 60

    audit = audit_deal(
        asking_price=price,
        retail_estimate=float(estimate),
        retail_low=v.estimate.low,
        retail_high=v.estimate.high,
        valuation_confidence=float(v.estimate.confidence or 0.0),
        comparables_count=int(v.estimate.comparables_used or 0),
        year=vehicle.get("year"),
        km=vehicle.get("km"),
        engine_cc=vehicle.get("engine_size"),
        co2_gkm=vehicle.get("co2_gkm"),
        fuel_type=str(vehicle.get("fuel_type") or "gasolina"),
        vehicle_type=str(vehicle.get("vehicle_type") or "carros"),
        is_national=vehicle.get("is_national") if country == "PT" else False,
        country=country,
        condition_score=vehicle.get("condition_score"),
        has_damage=bool(vehicle.get("has_accident")),
        damage_severity="total" if vehicle.get("has_accident") else None,
        days_to_sell=days,
    )
    return DealRow(
        vehicle_id=int(vehicle["id"]),
        source=source,
        url=str(vehicle.get("url") or ""),
        title=str(vehicle.get("title") or ""),
        brand=str(vehicle.get("brand") or ""),
        model=str(vehicle.get("model") or ""),
        year=vehicle.get("year"),
        km=vehicle.get("km"),
        asking_price=price,
        audit=audit,
    )


def find_best_deals(
    *,
    top: int = 25,
    min_profit: float = 750.0,
    min_confidence: float = 0.35,
    limit: int = 5000,
    sources: Optional[List[str]] = None,
    vehicle_type: str = "carros",
    include_suspect: bool = False,
) -> Dict[str, Any]:
    """Devolve os melhores negócios ordenados por lucro líquido realista."""
    candidates = load_candidates(limit=limit, sources=sources, vehicle_type=vehicle_type)
    logger.info("Candidatos carregados: %d", len(candidates))

    rows: List[DealRow] = []
    tally: Dict[str, int] = {}
    for vehicle in candidates:
        try:
            row = evaluate(vehicle)
        except Exception as exc:  # noqa: BLE001 — um anúncio mau não pára a análise
            logger.debug("Falha ao avaliar %s: %s", vehicle.get("id"), exc)
            continue
        if row is None:
            tally["sem_estimativa"] = tally.get("sem_estimativa", 0) + 1
            continue
        tally[row.audit.verdict] = tally.get(row.audit.verdict, 0) + 1
        rows.append(row)

    accepted = ACTIONABLE | ({"suspeito"} if include_suspect else set())
    shortlist = [
        row for row in rows
        if row.audit.verdict in accepted
        and row.audit.net_profit >= min_profit
        and row.audit.confidence >= min_confidence
    ]
    # Ordenar por ROI anualizado: €1.000 em 30 dias vale mais do que €1.500
    # em 180 dias, porque o capital roda. O lucro absoluto desempata.
    shortlist.sort(
        key=lambda r: (r.audit.roi_annualized_pct, r.audit.net_profit), reverse=True
    )

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "analisados": len(rows),
        "distribuicao_veredito": dict(sorted(tally.items())),
        "criterios": {
            "lucro_minimo": min_profit,
            "confianca_minima": min_confidence,
            "inclui_suspeitos": include_suspect,
            "tipo": vehicle_type,
        },
        "negocios": [row.to_dict() for row in shortlist[:top]],
    }


def _print_report(report: Dict[str, Any]) -> None:
    deals = report["negocios"]
    print()
    print("=" * 78)
    print("  MELHORES NEGÓCIOS — por lucro líquido realista")
    print("=" * 78)
    print(f"  Analisados: {report['analisados']}")
    print(f"  Vereditos : {report['distribuicao_veredito']}")
    print(f"  Critérios : {report['criterios']}")
    print("=" * 78)

    if not deals:
        print()
        print("  Nenhum negócio passou os critérios.")
        print()
        print("  Isto não é uma falha: significa que, depois de ISV, registo,")
        print("  recondicionamento, IVA da margem e custo de capital, nada no")
        print("  stock analisado deixa margem suficiente. Baixar --min-profit")
        print("  mostra mais candidatos, mas não torna nenhum deles rentável.")
        print()
        return

    for i, deal in enumerate(deals, 1):
        print()
        print(f"  {i:>2}. {deal['titulo'][:66]}")
        print(f"      {deal['marca']} {deal['modelo']} · {deal['ano']} · "
              f"{(deal['km'] or 0):,} km · {deal['fonte']}")
        print(f"      Pedido {deal['preco_pedido']:>10,.0f} €   →   "
              f"venda realista {deal['venda_realista']:>10,.0f} €")
        print(f"      LUCRO LÍQUIDO {deal['lucro_liquido']:>9,.0f} €   "
              f"(pior caso {deal['lucro_pior_caso']:,.0f} €)")
        print(f"      ROI {deal['roi_pct']:.1f}%  ·  anualizado "
              f"{deal['roi_anualizado_pct']:.0f}%  ·  "
              f"{deal['dias_para_vender']} dias em stock")
        custos = deal["custos"]
        print(f"      Custos: ISV {custos['isv']:,.0f} € · "
              f"recond. {custos['recondicionamento']:,.0f} € · "
              f"transp. {custos['transporte']:,.0f} € · "
              f"IVA margem {deal['iva_margem']:,.0f} €")
        print(f"      Pagar no máximo: {deal['preco_maximo_compra']:,.0f} €  "
              f"(confiança {deal['confianca']:.0%})")
        for risk in deal["riscos"]:
            print(f"      ⚠  {risk}")
        print(f"      {deal['url']}")
    print()
    print("=" * 78)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ordena anúncios por lucro líquido realista.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--top", type=int, default=25, help="Nº de negócios a mostrar")
    parser.add_argument("--min-profit", type=float, default=750.0,
                        help="Lucro líquido mínimo em euros")
    parser.add_argument("--min-confianca", type=float, default=0.35,
                        help="Confiança mínima da avaliação (0-1)")
    parser.add_argument("--limite", type=int, default=5000,
                        help="Máximo de anúncios a analisar")
    parser.add_argument("--fonte", action="append", default=None,
                        help="Restringir a estas fontes (repetível)")
    parser.add_argument("--tipo", default="carros", choices=["carros", "motos", "all"])
    parser.add_argument("--incluir-suspeitos", action="store_true",
                        help="Incluir anúncios marcados como suspeitos (para investigar)")
    parser.add_argument("--json", type=str, default=None, help="Gravar relatório JSON")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    report = find_best_deals(
        top=args.top,
        min_profit=args.min_profit,
        min_confidence=args.min_confianca,
        limit=args.limite,
        sources=args.fonte,
        vehicle_type=args.tipo,
        include_suspect=args.incluir_suspeitos,
    )
    _print_report(report)

    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  Relatório gravado em {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
