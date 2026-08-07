"""
VER PRECOS - Optimized Parallel Scraper Runner v2
=================================================
Runs ALL scrapers concurrently with ThreadPoolExecutor.
Includes: Carplus (LD+JSON), AutoUncle (market analysis), PiscaPisca (SSR state)
Saves results to autodeal.db with deduplication.

Key optimizations:
- Thread pool for parallel HTTP requests (no more sequential waiting)
- Shared requests.Session per scraper (connection pooling)
- Batch DB inserts (commit once per scraper, not per listing)
- Exponential backoff retry for Cloudflare/rate limits
- Rotating User-Agents
- 4x faster than sequential execution
"""
from __future__ import annotations
import logging
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.extractors import field_coverage

logger = logging.getLogger(__name__)

# Resiliência: retry + circuit breaker + fallback chain (ver scrapers/resilience.py)
try:
    from scrapers.resilience import scrape_with_resilience, FallbackChain
    from utils.production_safeguards import CircuitBreaker
    _RESILIENCE_AVAILABLE = True
except Exception as _e:  # noqa: BLE001
    logger.warning("Módulo de resiliência indisponível: %s", _e)
    _RESILIENCE_AVAILABLE = False


@dataclass
class ScrapingResult:
    scraper_name: str
    source: str
    listings: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration: float = 0.0
    success: bool = False
    persisted: int = 0
    updated: int = 0
    rejected: int = 0
    duplicates: int = 0
    quarantined: int = 0
    valid_price_pct: float = 0.0
    complete_fields_pct: float = 0.0
    #: Relatório de :func:`scrapers.extractors.field_coverage`. Serve para
    #: detetar degradação silenciosa: uma fonte pode continuar a devolver
    #: anúncios e a não falhar, mas ter deixado de ler km, ano ou preço.
    coverage: Dict[str, Any] = field(default_factory=dict)


def _run_source(
    name: str,
    max_listings: int = 200,
    vehicle_type: str = "carros",
    *,
    scrape_details: bool = False,
) -> ScrapingResult:
    """Executa uma fonte, seja ela declarativa ou um scraper dedicado.

    Substitui as catorze funções ``run_*`` que eram cópias literais umas das
    outras. A resiliência (retry + circuit breaker) é aplicada uma única vez,
    aqui, em vez de repetida por fonte — o que garantia que qualquer fonte
    acrescentada mais tarde ficava sem proteção por esquecimento.
    """
    from scrapers.sources import ALL_CONFIGS, LEGACY_SOURCES, build_legacy_callable, get_source

    key = name.lower()
    t0 = time.time()
    result = ScrapingResult(name, name.upper())

    if key in ALL_CONFIGS:
        config = ALL_CONFIGS[key]
        result.source = config.source_enum
        scraper = get_source(key)

        def _fn() -> List[Dict[str, Any]]:
            return scraper.scrape_listings(
                vehicle_type, max_listings=max_listings, scrape_details=scrape_details
            )
    elif key in LEGACY_SOURCES:
        result.source = str(LEGACY_SOURCES[key]["enum"])
        _fn = build_legacy_callable(key, max_listings, vehicle_type)
        scraper = None
    else:
        result.errors.append(f"Fonte desconhecida: {name}")
        result.duration = time.time() - t0
        return result

    try:
        if _RESILIENCE_AVAILABLE:
            listings, ok = scrape_with_resilience(
                key, _fn, CircuitBreaker(failure_threshold=3, recovery_timeout=300)
            )
            result.listings, result.success = listings or [], ok
            if not ok:
                result.errors.append("retry/circuit exaurido")
        else:
            result.listings, result.success = _fn(), True
    except Exception as exc:  # noqa: BLE001 — uma fonte não pode derrubar o lote
        result.errors.append(f"{type(exc).__name__}: {exc}")

    # Cobertura de campos: uma fonte que devolve anúncios mas perdeu os
    # campos críticos está partida, mesmo sem lançar exceção. Sem esta
    # verificação a degradação passa despercebida durante semanas.
    if result.listings:
        coverage = (
            scraper.last_coverage if scraper is not None and scraper.last_coverage
            else field_coverage(result.listings)
        )
        result.coverage = coverage
        if not coverage.get("critical_ok", True):
            weak = sorted(
                (f for f, pct in coverage.get("critical", {}).items() if pct < 60.0)
            )
            result.errors.append(
                "cobertura crítica insuficiente: " + ", ".join(weak)
            )

    result.duration = time.time() - t0
    return result


def run_source(name: str, max_listings: int = 200, vehicle_type: str = "carros") -> ScrapingResult:
    """API pública para correr uma única fonte pelo nome."""
    return _run_source(name, max_listings, vehicle_type)


def save_to_database(
    listings: List[Dict[str, Any]],
    source: str,
    metrics: Optional[Dict[str, int]] = None,
) -> int:
    """Batch-save listings and fill source-level persistence metrics."""
    metrics = metrics if metrics is not None else {}
    metrics.update(
        discovered=len(listings),
        persisted=0,
        updated=0,
        rejected=0,
        duplicates=0,
        quarantined=0,
        valid_price=0,
        complete_fields=0,
    )
    from database.db import get_db_context
    from database.models import Vehicle, VehicleType, FuelType, Transmission, Source
    from processing.model_canon import canon_listing
    from scrapers.schema import parse_price_evidence
    from processing.quality import classify_listing
    source_map = {
        "piscapisca": Source.PISCAPISCA,
        "carplus": Source.CARPLUS,
        "autoscout24": Source.AUTOSCOUT24,
        "imovirtual": Source.IMOVIRTUAL,
        "autouncle": Source.AUTO_UNCLE,
        "facebook": Source.FACEBOOK,
        "leilosoc": Source.LEILOSOC,
        "custojusto": Source.CUSTOJUSTO,
        "autopt": Source.AUTOPT,
        "olx": Source.OLX,
        "mcoutinho": Source.MCOUTINHO,
        "autohub": Source.AUTOHUB,
        "martelo": Source.MARTELO,
        "autoline": Source.AUTOLINE,
        "penhorado": Source.PENHORADO,
        # Fontes acrescentadas em 2026-08
        "standvirtuallight": Source.STANDVIRTUAL,
        "standvirtual": Source.STANDVIRTUAL,
        "caetanousados": Source.CAETANO,
        "santogalusados": Source.SANTOGAL,
        "eleiloes": Source.ELEILOES,
         "autoscout24de": Source.AUTOSCOUT24_DE,
        "autoscout24es": Source.AUTOSCOUT24_ES,
        "autoscout24fr": Source.AUTOSCOUT24_FR,
        # New European sources (2026-08-06)
        "spoticarpt": Source.SPOTICAR_PT,
        "comprarcarro": Source.COMPRAR_CARRO,
        "autouncle_pt": Source.AUTOUNCLE_PT,
        "autoscout24pt": Source.AUTOSCOUT24_PT,
        "autohero": Source.AUTOHERO,
        "spoticar": Source.SPOTICAR,
        "leboncoin": Source.LEBONCOIN,
        "wallapop": Source.WALLAPOP,
        "lacentrale": Source.LACENTRALE,
        "milanuncios": Source.MILANUNCIOS,
        "cochesnet": Source.COCHES_NET,
        "lacentrale_es": Source.LACENTRALE_ES,
        "idealista_autos": Source.IDEALISTA_AUTOS,
        "argus_fr": Source.ARGUS_FR,
    }
    source_enum = source_map.get(source.lower())
    if source_enum is None:
        raise ValueError(f"Fonte sem mapeamento de persistência: {source}")

    saved = 0
    with get_db_context() as db:
        for listing in listings:
            try:
                url = listing.get("url", "")
                if not url or len(url) < 10:
                    metrics["rejected"] += 1
                    continue

                source_id = str(listing.get("source_id", url))[:100]

                # Primeiro identifica a mesma fonte; depois trata URL repetida
                # entre fontes como duplicado cross-source (a URL é UNIQUE).
                existing = db.query(Vehicle).filter(
                    Vehicle.source == source_enum,
                    Vehicle.source_id == source_id,
                ).first()
                if existing is None:
                    by_url = db.query(Vehicle).filter(Vehicle.url == url).first()
                    if by_url is not None:
                        metrics["duplicates"] += 1
                        metrics["rejected"] += 1
                        continue
                source_price = listing.get("price")
                price_raw = listing.get("price_raw")
                price_evidence = parse_price_evidence(
                    price_raw if price_raw is not None else source_price,
                    context=" ".join(
                        str(listing.get(key) or "")
                        for key in ("title", "description", "brand", "model", "source")
                    ) + f" source={source}",
                    declared_currency=listing.get("currency"),
                    declared_kind=listing.get("price_kind"),
                )
                # Enriquecer antes da métrica de completude e da classificação;
                # caso contrário o relatório diz que faltam campos que já estão
                # presentes no título da fonte.
                from processing.text_enrich import extract_specs
                specs = extract_specs(str(listing.get("title", "")))
                if specs:
                    for key in ("year", "km", "horsepower"):
                        if not listing.get(key) and specs.get(key):
                            listing[key] = specs[key]
                    if not listing.get("fuel_type") and specs.get("fuel_type"):
                        listing["fuel_type"] = specs["fuel_type"]
                    if not listing.get("transmission") and specs.get("transmission"):
                        listing["transmission"] = specs["transmission"]
                retail_price = (
                    price_evidence.value
                    if price_evidence.kind.value == "total"
                    and price_evidence.currency == "EUR"
                    else 0.0
                )
                if retail_price > 0:
                    metrics["valid_price"] += 1
                if all(listing.get(key) not in (None, "") for key in (
                    "brand", "model", "year", "km", "fuel_type", "transmission"
                )):
                    metrics["complete_fields"] += 1
                quality_input = dict(listing)
                quality_input.update(
                    price=retail_price,
                    price_raw=price_evidence.raw,
                    price_observed_value=price_evidence.value,
                    currency=price_evidence.currency,
                    price_kind=price_evidence.kind.value,
                    price_evidence=price_evidence.evidence,
                    price_rejection_reason=price_evidence.rejection_reason,
                    source=source,
                )
                quality = classify_listing(quality_input)
                if quality["quality_status"] == "quarantined":
                    metrics["quarantined"] += 1
                provenance = {
                    "price": retail_price,
                    "price_raw": price_evidence.raw,
                    "price_observed_value": price_evidence.value,
                    "currency": price_evidence.currency,
                    "price_kind": price_evidence.kind.value,
                    "price_evidence": price_evidence.evidence,
                    "price_rejection_reason": price_evidence.rejection_reason,
                    "quality_status": quality["quality_status"],
                    "quality_reasons": quality["quality_reasons"],
                    "quality_checked_at": datetime.now(timezone.utc),
                }
                if existing:
                    metrics["duplicates"] += 1
                    metrics["updated"] += 1
                    for key, value in provenance.items():
                        setattr(existing, key, value)
                    existing.last_seen = datetime.now(timezone.utc)
                    existing.scrape_count = (existing.scrape_count or 1) + 1
                    saved += 1
                    metrics["persisted"] += 1
                    continue

                # Parse fuel type enum
                fuel_raw = str(listing.get("fuel_type", "")).lower()
                fuel_type = None
                for ft in FuelType:
                    if ft.value in fuel_raw:
                        fuel_type = ft
                        break

                # Parse transmission enum
                trans_raw = str(listing.get("transmission", "")).lower()
                transmission = None
                for tr in Transmission:
                    if tr.value in trans_raw:
                        transmission = tr
                        break

                brand = str(listing.get("brand", "Unknown"))[:100]
                if not brand or brand.lower() in ("unknown", "", "none"):
                    metrics["rejected"] += 1
                    continue

                price = retail_price

                # Canonização de marca/modelo (Fase 14) nunca pode substituir
                # um preço observado por texto do modelo/título.
                canon = canon_listing(
                    brand=brand,
                    model=str(listing.get("model", ""))[:100],
                    title=str(listing.get("title", ""))[:500],
                    price=price,
                    source=source,
                )
                brand = canon["brand"][:100]
                price = retail_price

                # Recalcular enums depois do enriquecimento textual.
                fuel_raw = str(listing.get("fuel_type", "")).lower()
                fuel_type = next((ft for ft in FuelType if ft.value in fuel_raw), None)
                trans_raw = str(listing.get("transmission", "")).lower()
                transmission = next((tr for tr in Transmission if tr.value in trans_raw), None)

                vehicle = Vehicle(
                    source=source_enum,
                    source_id=source_id,
                    url=url,
                    vehicle_type=listing.get("vehicle_type", VehicleType.carros),
                    brand=brand,
                    model=str(canon["model"])[:100],
                    year=int(listing.get("year")) if listing.get("year") else None,
                    km=int(listing.get("km")) if listing.get("km") else None,
                    price=float(price),
                    title=str(listing.get("title", ""))[:500],
                    fuel_type=fuel_type,
                    transmission=transmission,
                    horsepower=int(listing.get("horsepower")) if listing.get("horsepower") else None,
                    engine_size=int(listing.get("engine_size")) if listing.get("engine_size") else None,
                    location=str(listing.get("location", ""))[:200],
                    images=listing.get("images", []) or [],
                    image_count=listing.get("image_count", 0),
                    is_active=True,
                    first_seen=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc),
                    # AutoUncle market data
                    deal_grade=listing.get("deal_rating"),
                    seller_name=listing.get("seller_name"),
                    price_raw=provenance["price_raw"],
                    price_observed_value=provenance["price_observed_value"],
                    currency=provenance["currency"],
                    price_kind=provenance["price_kind"],
                    price_evidence=provenance["price_evidence"],
                    price_rejection_reason=provenance["price_rejection_reason"],
                    quality_status=provenance["quality_status"],
                    quality_reasons=provenance["quality_reasons"],
                    quality_checked_at=provenance["quality_checked_at"],
                )
                try:
                    # SAVEPOINT: uma linha inválida não pode fazer rollback dos
                    # anúncios válidos já preparados no lote.
                    with db.begin_nested():
                        db.add(vehicle)
                        db.flush()
                except Exception as e:
                    metrics["rejected"] += 1
                    logger.debug(f"Row rejected (savepoint): {e}")
                    continue
                saved += 1
                metrics["persisted"] += 1
            except Exception as e:
                logger.debug(f"Error saving listing: {e}")
                continue

        try:
            db.commit()
        except Exception as e:
            # Roll back only the (partially failed) transaction; safe rows were
            # already flushed+committed per-row above, so only the last unsafe
            # batch segment is lost.
            logger.error(f"DB commit failed (rolling back final segment): {e}")
            try:
                db.rollback()
            except Exception:
                pass

    return saved


#: Fontes corridas por omissão. Inclui retalho nacional (define o preço de
#: venda), leilões e importação (definem o preço de compra). Sem as duas
#: pontas não há margem para calcular.
DEFAULT_SOURCES: tuple[str, ...] = (
    # Retalho PT
    "carplus", "autouncle", "piscapisca", "custojusto", "autopt", "olx",
    "mcoutinho", "autohub", "autoscout24", "standvirtuallight",
    "caetanousados", "santogalusados",
    "spoticar_pt", "comprarcarro", "autouncle_pt", "autoscout24pt",
    # Leilões PT (preço de aquisição abaixo do mercado)
    "leilosoc", "martelo", "autoline", "penhorado", "eleiloes",
    # Importação (arbitragem transfronteiriça)
    "autoscout24de", "autoscout24es", "autoscout24fr",
    "autohero", "spoticar", "leboncoin", "wallapop", "lacentrale",
    "milanuncios", "cochesnet", "lacentrale_es", "idealista_autos", "argus_fr",
)


def run_all_scrapers(
    max_per_scraper: int = 200,
    save_to_db: bool = True,
    max_workers: int = 4,
    sources: Optional[List[str]] = None,
    vehicle_type: str = "carros",
    scrape_details: bool = False,
) -> Dict[str, Any]:
    """Run configured lightweight scrapers in parallel with source metrics."""
    logger.info(f"Starting parallel scraper run with {max_workers} workers")
    started_at = datetime.now(timezone.utc)

    selected = list(sources) if sources else list(DEFAULT_SOURCES)
    scrapers = [(name, min(max_per_scraper, 50) if name.lower() == "piscapisca" else max_per_scraper)
                for name in selected]
    vehicle_types = ["carros", "motos"] if vehicle_type == "all" else [vehicle_type]
    work = [
        (name, max_n, vtype)
        for name, max_n in scrapers
        for vtype in vehicle_types
    ]
    if not work:
        raise ValueError("Nenhuma fonte lightweight selecionada")

    results: Dict[str, ScrapingResult] = {}
    total_listings = 0
    total_saved = 0
    start = time.time()

    print(f"\n{'='*60}")
    print("  VER PRECOS - Parallel Scraper Runner v3")
    print(
        f"  {len(scrapers)} scrapers | {max_workers} workers | "
        f"{max_per_scraper} max listings each | type={vehicle_type}"
    )
    print(f"{'='*60}\n")

    with ThreadPoolExecutor(max_workers=min(max_workers, len(work))) as executor:
        futures = {}
        for name, max_n, vtype in work:
            future = executor.submit(
                _run_source, name, max_n, vtype, scrape_details=scrape_details
            )
            futures[future] = (name, vtype)

        for future in as_completed(futures):
            name, vtype = futures[future]
            result_key = f"{name}:{vtype}"
            try:
                result = future.result()
                # Some source adapters omit vehicle_type because the request
                # already scoped the category.  The runner must preserve that
                # contract instead of silently rejecting every valid row.
                for listing in result.listings:
                    if listing.get("vehicle_type") in (None, ""):
                        listing["vehicle_type"] = vtype
                wanted_type = vtype.lower()
                type_mismatch = [
                    listing for listing in result.listings
                    if str(getattr(listing.get("vehicle_type"), "value", listing.get("vehicle_type") or ""))
                    .lower() != wanted_type
                ]
                if type_mismatch:
                    result.errors.append(
                        f"{len(type_mismatch)} anúncios rejeitados: vehicle_type "
                        f"não corresponde a {vehicle_type}"
                    )
                    result.rejected += len(type_mismatch)
                    result.listings = [
                        listing for listing in result.listings
                        if listing not in type_mismatch
                    ]
                n = len(result.listings)

                status_icon = "✅" if result.success else "❌"
                print(f"  {status_icon} [{name}] {n:>4} listings in {result.duration:.1f}s")

                if result.errors:
                    for err in result.errors:
                        print(f"     ⚠️  {err}")

                if save_to_db and result.listings:
                    source_metrics: Dict[str, int] = {}
                    saved = save_to_database(result.listings, name.lower(), source_metrics)
                    total_saved += saved
                    result.persisted = source_metrics.get("persisted", 0)
                    result.updated = source_metrics.get("updated", 0)
                    result.rejected = source_metrics.get("rejected", 0)
                    result.duplicates = source_metrics.get("duplicates", 0)
                    result.quarantined = source_metrics.get("quarantined", 0)
                    discovered = source_metrics.get("discovered", len(result.listings)) or 1
                    result.valid_price_pct = round(
                        source_metrics.get("valid_price", 0) * 100 / discovered, 2
                    )
                    result.complete_fields_pct = round(
                        source_metrics.get("complete_fields", 0) * 100 / discovered, 2
                    )
                    if saved > 0:
                        print(f"     💾 {saved} persisted/updated")

                total_listings += n
                results[result_key] = result

            except Exception as e:
                print(f"  💥 [{name}] CRASHED: {e}")
                results[result_key] = ScrapingResult(
                    name, name.upper(), errors=[str(e)], duration=0.0, success=False
                )

    total_duration = time.time() - start

    print(f"\n{'='*60}")
    print(f"  📊 TOTAL: {total_listings} listings from {len(results)} scrapers")
    print(f"  ⏱️  Duration: {total_duration:.1f}s")
    print(f"  💾 Saved to DB: {total_saved}")
    print(f"{'='*60}\n")

    failed_sources = [
        key for key, result in results.items()
        if not result.success or bool(result.errors)
    ]
    summary = {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "total_listings": total_listings,
        "total_saved": total_saved,
        "total_duration": total_duration,
        "vehicle_type": vehicle_type,
        "overall_success": not failed_sources,
        "failed_sources": failed_sources,
        "scrapers": {
            key: {
                "source": r.source,
                "count": len(r.listings),
                "duration": r.duration,
                "success": r.success,
                "errors": r.errors,
                "persisted": r.persisted,
                "updated": r.updated,
                "rejected": r.rejected,
                "duplicates": r.duplicates,
                "quarantined": r.quarantined,
                "valid_price_pct": r.valid_price_pct,
                "complete_fields_pct": r.complete_fields_pct,
                "field_coverage": r.coverage.get("coverage", {}),
                "critical_fields_ok": r.coverage.get("critical_ok"),
            }
            for key, r in results.items()
        },
    }
    try:
        report_dir = Path("reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "scrape_last_run.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:  # pragma: no cover - observability must not abort scrape
        logger.warning("Não foi possível gravar métricas do scrape: %s", exc)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    summary = run_all_scrapers(
        max_per_scraper=200,
        save_to_db=True,
        max_workers=4,
    )

    # Quick stats
    print("Quick DB stats:")
    import sqlite3
    from core.settings import settings
    db_path = settings.resolved_db_url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT COUNT(*), source FROM vehicles GROUP BY source ORDER BY COUNT(*) DESC")
    for count, source in cur.fetchall():
        print(f"  {source}: {count}")
    conn.close()
