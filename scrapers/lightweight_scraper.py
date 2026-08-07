"""
Lightweight scraper using httpx only (no Playwright).
Fast data collection without browser overhead.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, BRANDS
from scrapers.extractors import enrich_listing, from_jsonld_vehicle, iter_jsonld
from core.settings import settings
from processing.model_canon import parse_price_evidence

logger = logging.getLogger(__name__)


class LightweightOLXScraper(BaseScraper):
    """Fast OLX scraper using httpx + BS4 only."""

    BASE_URL = "https://www.olx.pt"

    def __init__(self):
        super().__init__("OLX")

    async def scrape_listings(
        self, vehicle_type: str, max_listings: int = 50, scrape_details: bool = True
    ) -> List[Dict[str, Any]]:
        listings = []
        page = 1
        headers = self._headers()

        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
            while len(listings) < max_listings:
                url = self._search_url(vehicle_type, page)
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning(f"OLX page {page}: HTTP {resp.status_code}")
                        break
                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = self._parse_cards(soup)
                    if not cards:
                        break
                    for card in cards[:max_listings - len(listings)]:
                        listing = self._normalize(card, vehicle_type)
                        if listing:
                            listings.append(listing)
                    if len(cards) < 30:
                        break
                    page += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"OLX page {page} error: {e}")
                    break

        if scrape_details and listings:
            await self._enrich_details(listings)

        logger.info(f"[LIGHT_OLX] {len(listings)} listings")
        return listings

    def _headers(self) -> Dict[str, str]:
        import random
        return {
            "User-Agent": random.choice(settings.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        }

    def _search_url(self, vehicle_type: str, page: int = 1) -> str:
        return f"{self.BASE_URL}/carros/?page={page}"

    def _parse_cards(self, soup: BeautifulSoup) -> List[Any]:
        cards = soup.select("div[data-cy='l-card']")
        if not cards:
            cards = soup.select("li.css-1du9zl4, div.css-1sw7q4x, article")
        return cards

    #: Seletores de preço por ordem de fiabilidade. O primeiro que exista
    #: ganha; nunca se procura o preço no texto solto do cartão, porque aí
    #: aparecem também mensalidades de financiamento ("desde 149 €/mês").
    PRICE_SELECTORS = (
        "[data-testid='ad-price']",
        "p[data-testid='ad-price']",
        "[data-cy='ad-price']",
        ".price, .css-10b0gli, .css-13afqrm",
    )

    def _normalize(self, card: Any, vehicle_type: str) -> Optional[Dict[str, Any]]:
        try:
            link = card.select_one("a[href]")
            if not link:
                return None
            url = link.get("href", "")
            if url.startswith("/"):
                url = self.BASE_URL + url
            title_el = link.select_one("h6, h4, h3, [data-cy='ad_title']")
            title = title_el.get_text(strip=True) if title_el else ""

            price_el = None
            for selector in self.PRICE_SELECTORS:
                price_el = card.select_one(selector)
                if price_el is not None:
                    break
            price_text = price_el.get_text(strip=True) if price_el is not None else ""
            if not price_text:
                # Sem elemento de preço identificável não se inventa um valor:
                # o anúncio segue com preço 0 e é rejeitado a jusante pela
                # camada de qualidade, com motivo auditável.
                logger.debug("Cartão OLX sem elemento de preço: %s", url)
            price_evidence = parse_price_evidence(price_text, context=title)
            price = (
                price_evidence.value
                if price_evidence.kind.value == "total" and price_evidence.currency == "EUR"
                else 0.0
            )

            details = card.get_text(" ", strip=True)
            listing = self.build_vehicle_dict(
                url=url, title=title, price=price, vehicle_type=vehicle_type,
                price_raw=price_evidence.raw,
                price_observed_value=price_evidence.value,
                currency=price_evidence.currency,
                price_kind=price_evidence.kind.value,
                price_evidence=price_evidence.evidence,
                price_rejection_reason=price_evidence.rejection_reason,
            )
            # O texto do cartão traz ano/km/combustível/caixa; a extração
            # partilhada garante o mesmo resultado que nas restantes fontes.
            enrich_listing(listing, extra_text=details)
            return listing
        except Exception as e:
            logger.debug(f"Card parse error: {e}")
            return None

    def _parse_price(self, text: str) -> float:
        """Compatibility wrapper returning only a total EUR value."""
        evidence = parse_price_evidence(text)
        return evidence.value if evidence.kind.value == "total" and evidence.value else 0.0

    async def _enrich_details(self, listings: List[Dict]) -> None:
        """Scrape detail pages for HP, cc, fuel_type, transmission."""
        headers = self._headers()
        async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
            for listing in listings:
                url = listing.get("url", "")
                if not url:
                    continue
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        self._extract_detail_features(resp.text, listing)
                except Exception:
                    pass
                await asyncio.sleep(1)

    def _extract_detail_features(self, html: str, listing: Dict) -> None:
        """Completa o anúncio com o que só existe na página de detalhe.

        Prefere dados estruturados (JSON-LD) e só depois cai para a extração
        textual, para não depender de classes CSS que o site muda sem aviso.
        """
        for node in iter_jsonld(html):
            structured = from_jsonld_vehicle(node)
            for key, value in structured.items():
                # O preço da listagem já foi validado com proveniência; não
                # pode ser substituído silenciosamente pelo JSON-LD.
                if key in ("price", "price_raw", "currency", "url", "title"):
                    continue
                if listing.get(key) in (None, "", [], 0):
                    listing[key] = value

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        enrich_listing(listing, extra_text=text)


async def fast_scrape_all(vehicle_type: str = "carros", max_listings: int = 50) -> List[Dict]:
    """Run lightweight scrapers for all available sources."""
    all_listings = []
    scrapers = [LightweightOLXScraper()]
    
    for scraper in scrapers:
        try:
            listings = await scraper.scrape_listings(vehicle_type, max_listings)
            all_listings.extend(listings)
        except Exception as e:
            logger.error(f"Scraper error: {e}")
    
    return all_listings


def save_listings_to_db(listings: List[Dict]) -> int:
    """Save listings with deduplication and auditable quality state."""
    from database.db import get_db_context
    from database.models import Vehicle, Source, FuelType, Transmission
    from processing.quality import classify_listing
    from sqlalchemy import select

    saved = 0
    with get_db_context() as db:
        for l in listings:
            sid = str(l.get("source_id") or hashlib.md5(str(l.get("url", "")).encode()).hexdigest())
            src_name = l.get("source", "OLX")
            try:
                src = Source(src_name)
            except ValueError:
                logger.warning("Skipping listing with unknown source=%s source_id=%s", src_name, sid)
                continue

            quality = classify_listing(l)
            price = float(l.get("price") or l.get("price_observed_value") or 0.0)
            values = {
                "price": price,
                "price_raw": l.get("price_raw"),
                "price_observed_value": l.get("price_observed_value"),
                "currency": l.get("currency"),
                "price_kind": l.get("price_kind"),
                "price_evidence": l.get("price_evidence"),
                "price_rejection_reason": l.get("price_rejection_reason"),
                "quality_status": quality["quality_status"],
                "quality_reasons": quality["quality_reasons"],
                "quality_checked_at": datetime.now(timezone.utc),
            }

            existing = db.execute(
                select(Vehicle).where(Vehicle.source == src, Vehicle.source_id == sid)
            ).scalar_one_or_none()

            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
                existing.last_seen = datetime.now(timezone.utc)
                existing.scrape_count = (existing.scrape_count or 1) + 1
                continue

            fuel = l.get("fuel_type")
            if fuel and isinstance(fuel, str):
                try:
                    fuel = FuelType(fuel.lower())
                except ValueError:
                    fuel = None
            trans = l.get("transmission")
            if trans and isinstance(trans, str):
                try:
                    trans = Transmission(trans.lower())
                except ValueError:
                    trans = None

            v = Vehicle(
                source=src, source_id=sid,
                url=str(l.get("url", "")),
                vehicle_type=l.get("vehicle_type", "carros"),
                brand=str(l.get("brand", "Unknown")),
                model=str(l.get("model", "Unknown")),
                year=l.get("year"), km=l.get("km"),
                title=str(l.get("title", "")),
                location=str(l.get("location", "")),
                fuel_type=fuel, transmission=trans,
                horsepower=l.get("horsepower"), engine_size=l.get("engine_size"),
                **values,
            )
            db.add(v)
            saved += 1
        db.commit()
    return saved


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    listings = asyncio.run(fast_scrape_all("carros", 30))
    saved = save_listings_to_db(listings)
    print(f"Saved {saved} new vehicles")
