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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.extractors import enrich_listing, field_coverage

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
    started_at: Optional[datetime] = None
    log_recorded: bool = False


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
    result = ScrapingResult(name, name.upper(), started_at=datetime.now(timezone.utc))

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

    # Apply the shared, evidence-only text enrichment before deciding whether
    # the source lost critical fields. This avoids marking a parser broken
    # when the card contains "2019 · 80.000 km" in its title/description, and
    # it never supplies defaults for fields without textual evidence.
    for listing in result.listings:
        if listing.get("vehicle_type") in (None, ""):
            listing["vehicle_type"] = vehicle_type
        enrich_listing(listing)

    # Uma lista vazia não prova que uma fonte está saudável: em produção é
    # indistinguível de parser partido, bloqueio ou endpoint alterado. Falhar
    # fechado deixa a degradação visível no run report.
    if result.success and not result.listings:
        result.success = False
        result.errors.append(
            "POSSIBLE_PARSER_BREAKAGE: fonte devolveu zero anúncios"
        )

    # Cobertura de campos: uma fonte que devolve anúncios mas perdeu os
    # campos críticos está partida, mesmo sem lançar exceção. Sem esta
    # verificação a degradação passa despercebida durante semanas.
    if result.listings:
        coverage = field_coverage(result.listings)
        result.coverage = coverage
        if not coverage.get("critical_ok", True):
            weak = sorted(
                (f for f, pct in coverage.get("critical", {}).items() if pct < 60.0)
            )
            result.errors.append(
                "cobertura crítica insuficiente: " + ", ".join(weak)
            )
            result.success = False

    close = getattr(scraper, "close", None)
    if callable(close):
        try:
            close()
        except Exception as exc:  # noqa: BLE001 — cleanup não deve ocultar o resultado
            logger.debug("Falha ao fechar sessão de %s: %s", name, exc)

    result.duration = time.time() - t0
    return result


def run_source(name: str, max_listings: int = 200, vehicle_type: str = "carros") -> ScrapingResult:
    """API pública para correr uma única fonte pelo nome."""
    return _run_source(name, max_listings, vehicle_type)


def _record_scraping_log(result: ScrapingResult, fallback_source: Optional[str] = None) -> bool:
    """Write one durable source-run record without sharing the scrape session.

    The log is intentionally written after listing persistence in an
    independent session.  A failed/rolled-back listing transaction therefore
    cannot leave a false ``persisted`` count, and the log does not hold a lock
    while worker threads are scraping or writing vehicles.
    """
    try:
        from database.db import get_db_context
        from database.models import ScrapingLog, Source
        from utils.source_normalize import UNKNOWN_SOURCE, normalize_source

        canonical = normalize_source(result.source)
        if canonical == UNKNOWN_SOURCE and fallback_source:
            canonical = normalize_source(fallback_source)
        try:
            source_enum = Source(canonical)
        except ValueError:
            logger.warning("Run log skipped: source sem fonte canónica (%s)", canonical)
            return False

        finished_at = datetime.now(timezone.utc)
        started_at = result.started_at or (
            finished_at - timedelta(seconds=max(float(result.duration), 0.0))
        )
        status = "completed" if result.success and not result.errors else "failed"
        error_message = "; ".join(str(error) for error in result.errors) or None
        with get_db_context() as db:
            db.add(ScrapingLog(
                source=source_enum,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                listings_found=len(result.listings),
                listings_added=result.persisted,
                listings_updated=result.updated,
                error_message=error_message,
            ))
        result.log_recorded = True
        return True
    except Exception as exc:  # observability must not abort an ingestion run
        logger.warning("Não foi possível persistir o run log de %s: %s", result.source, exc)
        return False


def save_to_database(
    listings: List[Dict[str, Any]],
    source: str,
    metrics: Optional[Dict[str, int]] = None,
    *,
    batch_size: int = 250,
) -> int:
    """Persist only evidence-backed observations and retain their history.

    A parser can return a row with an URL while having lost the price or its
    semantics.  Such a row is counted and rejected for persistence: it must
    not refresh ``last_seen``, replace a known price with zero, or create a
    misleading ``PriceHistory`` entry.  Valid rows keep the bounded batch
    insert/savepoint path so concurrent writers are isolated by the existing
    database constraints.
    """
    if batch_size <= 0:
        raise ValueError("batch_size tem de ser positivo")
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
        invalid_observations=0,
        unknown_sources=0,
    )
    from urllib.parse import urlparse

    from database.db import get_db_context
    from database.models import (
        FuelType,
        PriceHistory,
        Source,
        Transmission,
        Vehicle,
        VehicleType,
    )
    from processing.model_canon import canon_listing
    from processing.quality import classify_listing
    from scrapers.schema import parse_price_evidence
    from utils.source_normalize import normalize_source

    source_map = {
        "piscapisca": Source.PISCAPISCA,
        "carplus": Source.CARPLUS,
        "autoscout24": Source.AUTOSCOUT24,
        "imovirtual": Source.IMOVIRTUAL,
        "autouncle": Source.AUTO_UNCLE,
        "facebook": Source.FACEBOOK,
        "leilosoc": Source.LEILOSOC,
        "vpauto": Source.VPAUTO,
        "custojusto": Source.CUSTOJUSTO,
        "autopt": Source.AUTOPT,
        "olx": Source.OLX,
        "mcoutinho": Source.MCOUTINHO,
        "autohub": Source.AUTOHUB,
        "martelo": Source.MARTELO,
        "autoline": Source.AUTOLINE,
        "penhorado": Source.PENHORADO,
        "standvirtuallight": Source.STANDVIRTUAL,
        "standvirtual": Source.STANDVIRTUAL,
        "caetanousados": Source.CAETANO,
        "santogalusados": Source.SANTOGAL,
        "eleiloes": Source.ELEILOES,
        "autoscout24de": Source.AUTOSCOUT24_DE,
        "autoscout24es": Source.AUTOSCOUT24_ES,
        "autoscout24fr": Source.AUTOSCOUT24_FR,
        "spoticarpt": Source.SPOTICAR_PT,
        "spoticar_pt": Source.SPOTICAR_PT,
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
    source_enum = source_map.get(str(source).lower())
    if source_enum is None:
        try:
            source_enum = Source(normalize_source(source))
        except ValueError:
            source_enum = None
    if source_enum is None:
        raise ValueError(f"Fonte sem mapeamento de persistência: {source}")

    def _chunks(values: List[str], size: int = 500):
        for start in range(0, len(values), size):
            yield values[start:start + size]

    def _valid_url(value: Any) -> bool:
        raw = str(value or "").strip()
        if len(raw) < 10:
            return False
        try:
            parsed = urlparse(raw if "://" in raw else f"//{raw}")
        except ValueError:
            return False
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)

    def _enum_value(value: Any) -> str:
        return str(getattr(value, "value", value) or "").strip().lower()

    def _enum_or_none(enum_type, value: Any):
        raw = _enum_value(value)
        return next((member for member in enum_type if member.value in raw), None)

    def _advance_last_seen(vehicle: Vehicle, observed_at: datetime) -> None:
        current = vehicle.last_seen
        if current is None:
            vehicle.last_seen = observed_at
            return
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        if current < observed_at:
            vehicle.last_seen = observed_at

    # Resolve the source once per listing.  URL authority may correct a stale
    # adapter label (including an AUTOPT/AutoUncle mix-up), so the preload key
    # is (canonical source, source_id), not source_id alone.
    resolved_sources: Dict[int, Optional[Source]] = {}
    candidate_ids: Dict[Source, List[str]] = {}
    candidate_urls = sorted({
        str(item.get("url", "")).strip()
        for item in listings
        if item.get("url")
    })
    for index, item in enumerate(listings):
        raw_label = item.get("source")
        label = source if raw_label in (None, "") else raw_label
        canonical = normalize_source(label, item.get("url"))
        try:
            row_source = Source(canonical)
        except ValueError:
            row_source = None
        if row_source is None and raw_label in (None, ""):
            # A source argument is an explicit dispatch contract even when a
            # legacy adapter emitted a host outside this authority table.
            row_source = source_enum
        resolved_sources[index] = row_source
        if row_source is not None and item.get("url"):
            source_id = str(item.get("source_id") or item.get("url"))[:100]
            candidate_ids.setdefault(row_source, []).append(source_id)

    saved = 0
    with get_db_context() as db:
        pending_new = []
        pending_keys = set()
        pending_urls = set()

        existing_by_identity = {}
        existing_by_url = {}
        for row_source, source_ids in candidate_ids.items():
            for batch_ids in _chunks(sorted(set(source_ids))):
                if not batch_ids:
                    continue
                for row in db.query(Vehicle).filter(
                    Vehicle.source == row_source,
                    Vehicle.source_id.in_(batch_ids),
                ).all():
                    existing_by_identity[(row_source, row.source_id)] = row
        for batch_urls in _chunks(candidate_urls):
            if batch_urls:
                for row in db.query(Vehicle).filter(Vehicle.url.in_(batch_urls)).all():
                    existing_by_url[row.url] = row

        def _history(vehicle: Vehicle, price: float, recorded_at: datetime) -> None:
            db.add(PriceHistory(
                vehicle_id=vehicle.id,
                price=float(price),
                recorded_at=recorded_at,
            ))

        def flush_new_batch() -> None:
            nonlocal saved
            if not pending_new:
                return
            batch = list(pending_new)
            pending_new.clear()
            vehicles = [item[0] for item in batch]
            try:
                with db.begin_nested():
                    db.add_all(vehicles)
                    db.flush()
                    for vehicle, observed_price, observed_at in batch:
                        _history(vehicle, observed_price, observed_at)
                    db.flush()
                saved += len(batch)
                metrics["persisted"] += len(batch)
            except Exception as batch_error:
                logger.warning(
                    "Batch insert rejected (%d rows); isolating rows: %s",
                    len(batch), batch_error,
                )
                for vehicle, observed_price, observed_at in batch:
                    try:
                        with db.begin_nested():
                            db.add(vehicle)
                            db.flush()
                            _history(vehicle, observed_price, observed_at)
                            db.flush()
                        saved += 1
                        metrics["persisted"] += 1
                    except Exception as row_error:
                        metrics["rejected"] += 1
                        logger.debug("Row rejected after batch fallback: %s", row_error)
                    finally:
                        try:
                            if vehicle in db:
                                db.expunge(vehicle)
                        except Exception:
                            pass

        for index, listing in enumerate(listings):
            try:
                row_source = resolved_sources.get(index)
                if row_source is None:
                    metrics["unknown_sources"] += 1
                    metrics["invalid_observations"] += 1
                    metrics["rejected"] += 1
                    continue

                url = str(listing.get("url") or "").strip()
                if not _valid_url(url):
                    metrics["invalid_observations"] += 1
                    metrics["rejected"] += 1
                    continue

                source_id = str(listing.get("source_id") or url)[:100]
                identity = (row_source, source_id)

                # First identify the same source; then reject URL reuse across
                # sources because vehicles.url remains the existing unique key.
                existing = existing_by_identity.get(identity)
                if existing is None:
                    by_url = existing_by_url.get(url)
                    if by_url is not None:
                        metrics["duplicates"] += 1
                        metrics["rejected"] += 1
                        continue
                    if identity in pending_keys or url in pending_urls:
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
                    ) + f" source={row_source.value}",
                    declared_currency=listing.get("currency"),
                    declared_kind=listing.get("price_kind"),
                )

                # Enrich before completeness/quality, without supplying
                # defaults where the card contains no textual evidence.
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

                observed_price = price_evidence.value
                valid_observation = (
                    observed_price is not None
                    and observed_price > 0
                    and price_evidence.kind.value == "total"
                    and price_evidence.currency == "EUR"
                    and not any(
                        token.startswith("proveniencia_")
                        for token in str(price_evidence.rejection_reason or "").split(";")
                    )
                )
                if valid_observation:
                    metrics["valid_price"] += 1
                if all(listing.get(key) not in (None, "") for key in (
                    "brand", "model", "year", "km", "fuel_type", "transmission"
                )):
                    metrics["complete_fields"] += 1

                quality_input = dict(listing)
                quality_input.update(
                    price=observed_price,
                    price_raw=price_evidence.raw,
                    price_observed_value=price_evidence.value,
                    currency=price_evidence.currency,
                    price_kind=price_evidence.kind.value,
                    price_evidence=price_evidence.evidence,
                    price_rejection_reason=price_evidence.rejection_reason,
                    source=row_source.value,
                )
                quality = classify_listing(quality_input)
                if quality["quality_status"] == "quarantined":
                    metrics["quarantined"] += 1

                # A syntactically present URL is not enough: unknown prices,
                # non-retail prices and quality-invalid cards must not refresh
                # an existing record or create a synthetic zero-price row.
                if not valid_observation or quality["quality_status"] == "invalid":
                    metrics["invalid_observations"] += 1
                    metrics["rejected"] += 1
                    continue

                observed_at = datetime.now(timezone.utc)
                provenance = {
                    "price": float(observed_price),
                    "price_raw": price_evidence.raw,
                    "price_observed_value": price_evidence.value,
                    "currency": price_evidence.currency,
                    "price_kind": price_evidence.kind.value,
                    "price_evidence": price_evidence.evidence,
                    "price_rejection_reason": price_evidence.rejection_reason,
                    "quality_status": quality["quality_status"],
                    "quality_reasons": quality["quality_reasons"],
                    "quality_checked_at": observed_at,
                }

                fuel_type = _enum_or_none(FuelType, listing.get("fuel_type"))
                transmission = _enum_or_none(Transmission, listing.get("transmission"))
                brand = str(listing.get("brand") or "").strip()[:100]
                if not brand or brand.lower() in ("unknown", "none"):
                    metrics["invalid_observations"] += 1
                    metrics["rejected"] += 1
                    continue
                canon = canon_listing(
                    brand=brand,
                    model=str(listing.get("model") or "")[:100],
                    title=str(listing.get("title") or "")[:500],
                    price=float(observed_price),
                    source=row_source.value,
                )
                normalized_vehicle_type = listing.get("vehicle_type", VehicleType.carros)
                if not isinstance(normalized_vehicle_type, VehicleType):
                    try:
                        normalized_vehicle_type = VehicleType(str(normalized_vehicle_type))
                    except ValueError:
                        normalized_vehicle_type = VehicleType.carros

                if existing:
                    old_price = existing.price
                    metrics["duplicates"] += 1
                    metrics["updated"] += 1
                    for key, value in provenance.items():
                        setattr(existing, key, value)
                    core_values = {
                        "vehicle_type": normalized_vehicle_type,
                        "brand": canon["brand"][:100],
                        "model": str(canon["model"])[:100],
                        "year": int(listing["year"]) if listing.get("year") else None,
                        "km": int(listing["km"]) if listing.get("km") else None,
                        "title": str(listing["title"])[:500] if listing.get("title") else None,
                        "description": str(listing["description"]) if listing.get("description") else None,
                        "location": str(listing["location"])[:200] if listing.get("location") else None,
                        "district": str(listing["district"])[:100] if listing.get("district") else None,
                        "fuel_type": fuel_type,
                        "transmission": transmission,
                        "horsepower": int(listing["horsepower"]) if listing.get("horsepower") else None,
                        "engine_size": int(listing["engine_size"]) if listing.get("engine_size") else None,
                        "images": listing.get("images") or None,
                        "image_count": listing.get("image_count") or None,
                        "seller_name": str(listing["seller_name"])[:200] if listing.get("seller_name") else None,
                        "seller_type": listing.get("seller_type"),
                    }
                    # A partial later card does not erase stronger evidence.
                    for key, value in core_values.items():
                        if value not in (None, "", [], 0):
                            setattr(existing, key, value)
                    existing.is_active = True
                    _advance_last_seen(existing, observed_at)
                    existing.scrape_count = (existing.scrape_count or 1) + 1
                    try:
                        price_changed = old_price is None or float(old_price) != float(observed_price)
                    except (TypeError, ValueError):
                        price_changed = True
                    if price_changed:
                        _history(existing, float(observed_price), observed_at)
                    saved += 1
                    metrics["persisted"] += 1
                    continue

                vehicle = Vehicle(
                    source=row_source,
                    source_id=source_id,
                    url=url,
                    vehicle_type=normalized_vehicle_type,
                    brand=canon["brand"][:100],
                    model=str(canon["model"])[:100],
                    year=int(listing.get("year")) if listing.get("year") else None,
                    km=int(listing.get("km")) if listing.get("km") else None,
                    price=float(observed_price),
                    title=str(listing.get("title") or "")[:500],
                    description=str(listing.get("description")) if listing.get("description") else None,
                    fuel_type=fuel_type,
                    transmission=transmission,
                    horsepower=int(listing.get("horsepower")) if listing.get("horsepower") else None,
                    engine_size=int(listing.get("engine_size")) if listing.get("engine_size") else None,
                    location=str(listing.get("location"))[:200] if listing.get("location") else None,
                    district=str(listing.get("district"))[:100] if listing.get("district") else None,
                    images=listing.get("images") or [],
                    image_count=listing.get("image_count") or 0,
                    is_active=True,
                    first_seen=observed_at,
                    last_seen=observed_at,
                    deal_grade=listing.get("deal_rating"),
                    seller_name=listing.get("seller_name"),
                    seller_type=listing.get("seller_type"),
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
                pending_new.append((vehicle, float(observed_price), observed_at))
                pending_keys.add(identity)
                pending_urls.add(url)
                if len(pending_new) >= batch_size:
                    flush_new_batch()
            except Exception as exc:  # one malformed listing cannot abort a batch
                logger.debug("Error saving listing: %s", exc)
                metrics["rejected"] += 1
                continue

        flush_new_batch()
        try:
            db.commit()
        except Exception as exc:
            # All writes share the outer transaction; do not report rows that
            # were rolled back when a concurrent writer/constraint aborts it.
            logger.error("DB commit failed (rolling back batch transaction): %s", exc)
            saved = 0
            metrics["persisted"] = 0
            metrics["updated"] = 0
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
    "leilosoc", "vpauto", "martelo", "autoline", "penhorado", "eleiloes",
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
    if max_per_scraper <= 0:
        raise ValueError("max_per_scraper tem de ser positivo")
    if max_workers <= 0:
        raise ValueError("max_workers tem de ser positivo")
    if vehicle_type not in {"carros", "motos", "all"}:
        raise ValueError("vehicle_type tem de ser carros, motos ou all")
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
                    name,
                    name.upper(),
                    errors=[str(e)],
                    duration=0.0,
                    success=False,
                    started_at=datetime.now(timezone.utc),
                )

            _record_scraping_log(results[result_key], fallback_source=name)

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
                "run_log_recorded": r.log_recorded,
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
