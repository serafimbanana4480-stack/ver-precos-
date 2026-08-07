"""Live audit of every vehicle scraper registered in this repository.

The audit deliberately does not equate ``HTTP 200`` or ``[]`` with a healthy
scraper.  It records source identity, timeout/block/auth state, field coverage,
duplicate adverts, and price-provenance problems for each adapter.

Examples (from the repository root)::

    .venv\\Scripts\\python.exe scripts\\audit_scrapers.py --max-listings 3
    .venv\\Scripts\\python.exe scripts\\audit_scrapers.py --source OLX:lightweight

This module is also used by ``scripts/soak_scrapers.py`` for bounded long runs.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import logging
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional
from urllib.parse import urlparse

try:  # Use Windows' trusted root CAs for live HTTP audits.
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scrapers.schema import parse_price_evidence  # noqa: E402

logger = logging.getLogger("scraper_audit")


Adapter = Callable[[str, int], Awaitable[List[Any]]]


@dataclass(frozen=True)
class ScraperSpec:
    name: str
    expected_source: str
    website: str
    adapter: Adapter
    category: str = "marketplace"
    credential: Optional[str] = None


def _as_dict(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    if dataclasses.is_dataclass(item):
        return dataclasses.asdict(item)
    if hasattr(item, "model_dump"):
        return dict(item.model_dump())
    if hasattr(item, "dict"):
        return dict(item.dict())
    return dict(vars(item))


async def _sync(fn: Callable[[], List[Any]]) -> List[Any]:
    return await asyncio.to_thread(fn)


async def _light(cls: Any, vehicle_type: str, max_listings: int) -> List[Any]:
    return cls().scrape_listings(vehicle_type, max_listings=max_listings)


async def _leilosoc_light(vehicle_type: str, max_listings: int) -> List[Any]:
    # Leilosoc's lightweight adapter is auction-category scoped and therefore
    # has no vehicle_type parameter.
    from scrapers.leilosoc_lightweight import LeilosocLightweight

    return LeilosocLightweight().scrape_listings(max_listings=max_listings)


async def _browser(cls: Any, vehicle_type: str, max_listings: int) -> List[Any]:
    return await cls().scrape_listings(
        vehicle_type, max_listings=max_listings, scrape_details=False
    )


async def _olx_playwright(vehicle_type: str, max_listings: int) -> List[Any]:
    from scrapers.olx_scraper import OlxScraper

    return await OlxScraper().scrape_listings(
        vehicle_type, max_listings=max_listings, scrape_details=False
    )


async def _olx_generic(vehicle_type: str, max_listings: int) -> List[Any]:
    from scrapers.lightweight_scraper import LightweightOLXScraper

    return await LightweightOLXScraper().scrape_listings(vehicle_type, max_listings)


async def _imovirtual(vehicle_type: str, max_listings: int) -> List[Any]:
    from scrapers.imovirtual_scraper import ImoVirtualScraper

    return await _sync(
        lambda: ImoVirtualScraper().scrape_listings(
            max_listings=max_listings, vehicle_type=vehicle_type
        )
    )


async def _old_auction(source: str, _vehicle_type: str, max_listings: int) -> List[Any]:
    from scrapers.auction_scraper import AuctionScraper

    async with AuctionScraper() as scraper:
        if source == "VPAUTO":
            return await scraper.scrape_vpauto(max_listings)
        return await scraper.scrape_leilosoc(max_listings)


async def _multi_auction(cls: Any, vehicle_type: str, max_listings: int) -> List[Any]:
    async with cls() as scraper:
        return await scraper.scrape_listings(
            vehicle_type=vehicle_type, max_listings=max_listings
        )


async def _ground_truth(cls: Any, _vehicle_type: str, max_listings: int) -> List[Any]:
    from scrapers.ground_truth_scraper import (
        HTTPFallback,
        PlaywrightHelper,
        RateLimiter,
    )
    from core.settings import settings

    limiter = RateLimiter(
        base_delay=settings.request_delay_seconds,
        jitter=settings.request_delay_jitter,
        max_rpm=settings.max_requests_per_minute,
    )
    browser = PlaywrightHelper(
        headless=settings.playwright_headless, timeout=settings.playwright_timeout
    )
    http = HTTPFallback(timeout=settings.scraper_timeout)
    scraper = cls(limiter, browser, http)
    try:
        async with scraper:
            return await scraper.scrape(max_listings=max_listings)
    finally:
        await http.close()


async def _ebay(vehicle_type: str, max_listings: int) -> List[Any]:
    if not os.getenv("EBAY_API_KEY"):
        raise RuntimeError("credential_missing: EBAY_API_KEY")
    from scrapers.ebay_motors import eBayMotorsAPI

    return await eBayMotorsAPI().scrape_listings(vehicle_type, max_listings=max_listings)


def build_specs() -> List[ScraperSpec]:
    """Return one entry for every callable scraper implementation in scope."""
    from scrapers.autohub_lightweight import AutohubLightweight
    from scrapers.autoline_lightweight import AutolineLightweight
    from scrapers.autopt_lightweight import AutoPtLightweightScraper
    from scrapers.autopt_scraper import AutoPtScraper
    from scrapers.autosapo_scraper import AutoSapoScraper
    from scrapers.autoscout24_lightweight import AutoScout24Lightweight
    from scrapers.autoscout24_scraper import AutoScout24Scraper
    from scrapers.autouncle_lightweight import AutoUncleLightweight
    from scrapers.carplus_lightweight import CarplusLightweightScraper
    from scrapers.carplus_scraper import CarplusScraper
    from scrapers.custojusto_scraper import CustoJustoScraper
    from scrapers.facebook_marketplace_scraper import FacebookMarketplaceScraper
    from scrapers.facebook_scraper import FacebookScraper
    from scrapers.leilosoc_lightweight import LeilosocLightweight
    from scrapers.martelo_lightweight import MarteloLightweight
    from scrapers.mcoutinho_lightweight import McoutinhoLightweight
    from scrapers.olx_lightweight import OLXLightweight
    from scrapers.piscapisca_lightweight import PiscaPiscaLightweight
    from scrapers.piscapisca_scraper import PiscaPiscaScraper
    from scrapers.penhorado_lightweight import PenhoradoLightweight
    from scrapers.standvirtual_scraper import StandvirtualScraper
    from scrapers.lightweight_scraper import LightweightOLXScraper
    from scrapers.auction_multi_scraper import AutorolaScraper, BCAScraper, ManheimScraper
    from scrapers.ground_truth_scraper import (
        AutorolaScraper as GroundAutorola,
        BCAScraper as GroundBCA,
        LeilosocScraper as GroundLeilosoc,
        ManheimScraper as GroundManheim,
        VPAutoScraper as GroundVPAuto,
    )

    def light(name: str, source: str, website: str, cls: Any, category: str = "marketplace") -> ScraperSpec:
        return ScraperSpec(
            name, source, website,
            lambda vt, n, c=cls: _light(c, vt, n), category=category,
        )

    def browser(name: str, source: str, website: str, cls: Any) -> ScraperSpec:
        return ScraperSpec(
            name, source, website,
            lambda vt, n, c=cls: _browser(c, vt, n),
        )

    specs = [
        light("OLX:lightweight", "OLX", "https://www.olx.pt", OLXLightweight),
        ScraperSpec("OLX:generic-lightweight", "OLX", "https://www.olx.pt", _olx_generic),
        ScraperSpec("OLX:playwright", "OLX", "https://www.olx.pt", _olx_playwright),
        browser("Standvirtual:playwright", "STANDVIRTUAL", "https://www.standvirtual.com", StandvirtualScraper),
        browser("AutoSapo:playwright", "AUTOSAPO", "https://www.autosapo.pt", AutoSapoScraper),
        browser("CustoJusto:playwright", "CUSTOJUSTO", "https://www.custojusto.pt", CustoJustoScraper),
        light("PiscaPisca:lightweight", "PISCAPISCA", "https://www.piscapisca.pt", PiscaPiscaLightweight),
        browser("PiscaPisca:playwright", "PISCAPISCA", "https://www.piscapisca.pt", PiscaPiscaScraper),
        light("Carplus:lightweight", "CARPLUS", "https://www.carplus.pt", CarplusLightweightScraper),
        browser("Carplus:playwright", "CARPLUS", "https://www.carplus.pt", CarplusScraper),
        light("AutoPT:lightweight", "AUTOPT", "https://www.auto.pt", AutoPtLightweightScraper),
        browser("AutoPT:playwright", "AUTOPT", "https://www.auto.pt", AutoPtScraper),
        light("AutoScout24:lightweight", "AUTOSCOUT24", "https://www.autoscout24.pt", AutoScout24Lightweight),
        browser("AutoScout24:playwright", "AUTOSCOUT24", "https://www.autoscout24.pt", AutoScout24Scraper),
        light("AutoUncle:lightweight", "AUTOUNCLE", "https://www.autouncle.pt", AutoUncleLightweight),
        ScraperSpec("Leilosoc:lightweight", "LEILOSOC", "https://www.leilosoc.com", _leilosoc_light, category="auction"),
        light("MCoutinho:lightweight", "MCOUTINHO", "https://usados.mcoutinho.pt", McoutinhoLightweight),
        light("AutoHub:lightweight", "AUTOHUB", "https://www.autohub.pt", AutohubLightweight),
        light("Martelo:lightweight", "MARTELO", "https://martelo.pt", MarteloLightweight, "auction"),
        light("Autoline:lightweight", "AUTOLINE", "https://www.autoline.pt", AutolineLightweight, "auction"),
        light("Penhorado:lightweight", "PENHORADO", "https://penhorado.pt", PenhoradoLightweight, "auction"),
        ScraperSpec("Imovirtual:requests", "IMOVIRTUAL", "https://www.imovirtual.com", _imovirtual),
        browser("FacebookMarketplace:direct", "FACEBOOK", "https://www.facebook.com/marketplace", FacebookMarketplaceScraper),
        browser("Facebook:legacy", "FACEBOOK", "https://www.facebook.com/marketplace", FacebookScraper),
        ScraperSpec("eBayMotors:api", "EBAY_MOTORS", "https://api.ebay.com", _ebay, credential="EBAY_API_KEY"),
        ScraperSpec("Auction:VPAUTO:legacy", "VPAUTO", "https://www.vpauto.pt", lambda vt, n: _old_auction("VPAUTO", vt, n), category="auction"),
        ScraperSpec("Auction:Leilosoc:legacy", "LEILOSOC", "https://www.leilosoc.pt", lambda vt, n: _old_auction("LEILOSOC", vt, n), category="auction"),
        ScraperSpec("AuctionMulti:Manheim", "MANHEIM", "https://www.manheim.com", lambda vt, n: _multi_auction(ManheimScraper, vt, n), category="auction"),
        ScraperSpec("AuctionMulti:Autorola", "AUTOROLA", "https://www.autorola.com", lambda vt, n: _multi_auction(AutorolaScraper, vt, n), category="auction"),
        ScraperSpec("AuctionMulti:BCA", "BCA", "https://www.bca.co.uk", lambda vt, n: _multi_auction(BCAScraper, vt, n), category="auction"),
        ScraperSpec("GroundTruth:VPAuto", "VPAUTO", "https://www.vpauto.pt", lambda vt, n: _ground_truth(GroundVPAuto, vt, n), category="auction"),
        ScraperSpec("GroundTruth:Leilosoc", "LEILOSOC", "https://www.leilosoc.com", lambda vt, n: _ground_truth(GroundLeilosoc, vt, n), category="auction"),
        ScraperSpec("GroundTruth:BCA", "BCA", "https://www.bcamarketplace.pt", lambda vt, n: _ground_truth(GroundBCA, vt, n), category="auction"),
        ScraperSpec("GroundTruth:Manheim", "MANHEIM", "https://www.manheim.pt", lambda vt, n: _ground_truth(GroundManheim, vt, n), category="auction"),
        ScraperSpec("GroundTruth:Autorola", "AUTOROLA", "https://www.autorola.pt", lambda vt, n: _ground_truth(GroundAutorola, vt, n), category="auction"),
    ]
    return specs


def _price_check(row: Dict[str, Any], source: str) -> Dict[str, Any]:
    title = str(row.get("title") or "")
    raw = row.get("price_raw")
    if raw in (None, ""):
        for key in ("price", "adjudication_price", "current_bid", "starting_price"):
            if row.get(key) not in (None, ""):
                raw = row[key]
                break
    declared_kind = row.get("price_kind")
    if not declared_kind:
        declared_kind = {
            "adjudicado": "auction_adjudicated",
            "licitacao_aberta": "auction_current",
            "valor_base": "auction_start",
        }.get(str(row.get("price_type") or "").lower())
    evidence = parse_price_evidence(
        raw,
        context=f"{title} {row.get('description') or ''} source={source}",
        declared_currency=row.get("currency"),
        declared_kind=declared_kind,
    )
    stored = row.get("price")
    if stored in (None, ""):
        stored = row.get("adjudication_price") or row.get("current_bid") or row.get("starting_price")
    try:
        stored_f = float(stored) if stored not in (None, "") else None
    except (TypeError, ValueError):
        stored_f = None
    result = {
        "valid_total_eur": bool(evidence.value and evidence.kind.value == "total" and evidence.currency == "EUR"),
        "missing": stored_f is None or stored_f <= 0,
        "non_total": evidence.kind.value not in ("total", "unknown"),
        "currency": evidence.currency,
        "kind": evidence.kind.value,
        "raw": str(raw)[:160] if raw is not None else None,
        "evidence_value": evidence.value,
        "stored_value": stored_f,
        "rejection_reason": evidence.rejection_reason,
        "provenance_missing": not bool(row.get("price_raw") or row.get("currency") or row.get("price_kind")),
        "mismatch": bool(stored_f and evidence.value and abs(stored_f - evidence.value) > 0.01),
        "suspicious_range": bool(stored_f is not None and (stored_f < 50 or stored_f > 500_000)),
    }
    return result


def validate_rows(rows: Iterable[Any], spec: ScraperSpec, vehicle_type: str) -> Dict[str, Any]:
    records = [_as_dict(row) for row in rows]
    issues: Counter[str] = Counter()
    prices: List[Dict[str, Any]] = []
    urls: Counter[str] = Counter()
    source_ids: Counter[str] = Counter()
    field_missing: Counter[str] = Counter()

    for row in records:
        url = str(row.get("url") or "")
        sid = str(row.get("source_id") or "")
        urls[url] += 1
        source_ids[sid] += 1
        if not url or urlparse(url).scheme not in {"http", "https"}:
            issues["invalid_url"] += 1
        if not str(row.get("title") or "").strip():
            issues["missing_title"] += 1
        for field in (
            "brand", "model", "year", "km", "fuel_type", "transmission",
            "vehicle_type",
        ):
            if row.get(field) in (None, "", 0):
                field_missing[field] += 1
        row_source = str(row.get("source") or "").upper()
        if row_source and row_source != spec.expected_source.upper():
            issues["source_mismatch"] += 1
        expected_host = (urlparse(spec.website).hostname or "").lower().removeprefix("www.")
        actual_host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        if expected_host and actual_host and not (
            actual_host == expected_host or actual_host.endswith("." + expected_host)
        ):
            issues["cross_source_url"] += 1
        row_type = str(getattr(row.get("vehicle_type"), "value", row.get("vehicle_type") or "")).lower()
        if row_type and row_type != vehicle_type:
            issues["vehicle_type_mismatch"] += 1
        price = _price_check(row, spec.expected_source)
        prices.append(price)
        for key in ("missing", "non_total", "mismatch", "suspicious_range", "provenance_missing"):
            if price[key]:
                issues[f"price_{key}"] += 1

    duplicate_urls = sum(n - 1 for n in urls.values() if n > 1 and n > 1)
    duplicate_source_ids = sum(n - 1 for n in source_ids.values() if n > 1 and n > 1)
    if duplicate_urls:
        issues["duplicate_url"] = duplicate_urls
    if duplicate_source_ids:
        issues["duplicate_source_id"] = duplicate_source_ids
    return {
        "count": len(records),
        "issues": dict(issues),
        "field_missing": dict(field_missing),
        "price": {
            "valid_total_eur": sum(1 for p in prices if p["valid_total_eur"]),
            "missing": sum(1 for p in prices if p["missing"]),
            "non_total": sum(1 for p in prices if p["non_total"]),
            "mismatch": sum(1 for p in prices if p["mismatch"]),
            "suspicious_range": sum(1 for p in prices if p["suspicious_range"]),
            "provenance_missing": sum(1 for p in prices if p["provenance_missing"]),
            "samples": [p for p in prices if p["mismatch"] or p["suspicious_range"]][:10],
        },
        "samples": [
            {
                "title": str(row.get("title") or "")[:120],
                "price": row.get("price") or row.get("adjudication_price") or row.get("current_bid"),
                "url": row.get("url"),
                "source": str(row.get("source") or ""),
            }
            for row in records[:5]
        ],
    }


def _classify_error(message: str) -> str:
    text = message.lower()
    if "source_unavailable" in text:
        return "unsupported"
    if "credential_missing" in text or "api_key" in text or "authentication" in text:
        return "blocked_credentials"
    if any(token in text for token in ("captcha", "cloudflare", "blocked", "forbidden", "429", "challenge")):
        return "blocked"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    return "failed"


async def run_spec(spec: ScraperSpec, vehicle_type: str, max_listings: int, timeout: float) -> Dict[str, Any]:
    started = time.monotonic()
    result: Dict[str, Any] = {
        "name": spec.name,
        "source": spec.expected_source,
        "website": spec.website,
        "category": spec.category,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "errors": [],
    }
    try:
        rows = await asyncio.wait_for(spec.adapter(vehicle_type, max_listings), timeout=timeout)
        audit = validate_rows(rows, spec, vehicle_type)
        result.update(audit)
        result["status"] = "ok" if audit["count"] > 0 and not any(
            key in audit["issues"] for key in ("invalid_url", "source_mismatch", "price_mismatch")
        ) else ("empty" if audit["count"] == 0 else "degraded")
    except Exception as exc:  # noqa: BLE001 - audit must isolate each source
        message = f"{type(exc).__name__}: {exc}"
        result["errors"] = [message]
        result["status"] = _classify_error(message)
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result


async def audit_once(
    *,
    max_listings: int = 3,
    timeout: float = 90.0,
    vehicle_type: str = "carros",
    sources: Optional[Iterable[str]] = None,
    concurrency: int = 3,
) -> Dict[str, Any]:
    specs = build_specs()
    wanted = {str(source).lower() for source in sources or []}
    if wanted:
        specs = [s for s in specs if s.name.lower() in wanted or s.expected_source.lower() in wanted]
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def guarded(spec: ScraperSpec) -> Dict[str, Any]:
        async with semaphore:
            return await run_spec(spec, vehicle_type, max_listings, timeout)

    started = datetime.now(timezone.utc)
    results = await asyncio.gather(*(guarded(spec) for spec in specs))
    status_counts = Counter(r["status"] for r in results)
    return {
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "vehicle_type": vehicle_type,
        "max_listings": max_listings,
        "scraper_count": len(results),
        "status_counts": dict(status_counts),
        "overall_success": not any(r["status"] in {"failed", "timeout"} for r in results),
        "scrapers": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-listings", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--vehicle-type", choices=("carros", "motos"), default="carros")
    parser.add_argument("--source", action="append", help="Name or source code; repeatable")
    parser.add_argument("--output", default="reports/scraper_audit_latest.json")
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.WARNING), format="%(asctime)s %(levelname)s %(message)s")
    report = asyncio.run(audit_once(
        max_listings=max(1, args.max_listings), timeout=max(5.0, args.timeout),
        vehicle_type=args.vehicle_type, sources=args.source, concurrency=max(1, args.concurrency),
    ))
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("scraper_count", "status_counts", "overall_success", "vehicle_type")}, ensure_ascii=False))
    for row in report["scrapers"]:
        print(f"{row['status']:>20} {row['name']:<32} {row.get('count', 0):>4} {row['duration_seconds']:>7.1f}s")
    return 0 if report["overall_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
