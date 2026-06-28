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
from core.settings import settings

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

            price_el = card.select_one("[data-testid='ad-price'], h3, p.css-13v1nwv, p[class*='price']")
            price_text = price_el.get_text(strip=True) if price_el else "0"
            price = self._parse_price(price_text)

            details = card.get_text(" ", strip=True).lower()
            year = None
            km = None
            year_match = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", details)
            if year_match:
                year = int(year_match.group(1))
            km_match = re.search(r"(\d[\d\s]*(?:\.?\d{3})*)\s*km", details)
            if km_match:
                km = int(km_match.group(1).replace(" ", "").replace(".", ""))

            fuel = None
            for f in ["gasolina", "diesel", "elétrico", "eletrico", "hibrido", "híbrido", "gpl"]:
                if f in details:
                    fuel = f
                    break

            trans = None
            for t in ["manual", "automático", "automatico", "automático"]:
                if t in details:
                    trans = "manual" if t == "manual" else "automatico"
                    break

            return self.build_vehicle_dict(
                url=url, title=title, price=price, vehicle_type=vehicle_type,
                year=year, km=km, fuel_type=fuel, transmission=trans,
            )
        except Exception as e:
            logger.debug(f"Card parse error: {e}")
            return None

    def _parse_price(self, text: str) -> float:
        nums = re.findall(r"[\d.]+", text.replace(",", "."))
        if nums:
            return float(nums[0])
        return 0.0

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
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True).lower()

        hp_match = re.search(r"(\d{2,3})\s*(cv|cavalo|hp)", text)
        if hp_match:
            listing["horsepower"] = int(hp_match.group(1))

        cc_match = re.search(r"(\d{3,4})\s*cm3|(\d{1,2}\.\d)\s*l(?:itros)", text)
        if cc_match:
            val = cc_match.group(1) or cc_match.group(2)
            if "." in str(val):
                listing["engine_size"] = int(float(val) * 1000)
            else:
                listing["engine_size"] = int(val)

        if not listing.get("fuel_type"):
            for f in ["gasolina", "diesel", "elétrico", "eletrico", "hibrido", "híbrido", "gpl"]:
                if f in text:
                    listing["fuel_type"] = f
                    break

        if not listing.get("transmission"):
            for t in ["manual", "automático", "automatico"]:
                if t in text:
                    listing["transmission"] = "manual" if t == "manual" else "automatico"
                    break


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
    """Save listings with dedup check."""
    from database.db import get_db_context
    from database.models import Vehicle, Source, FuelType, Transmission
    from sqlalchemy import select

    saved = 0
    with get_db_context() as db:
        for l in listings:
            sid = str(l.get("source_id") or hashlib.md5(str(l.get("url", "")).encode()).hexdigest())
            src_name = l.get("source", "OLX")
            try:
                src = Source(src_name)
            except ValueError:
                continue

            existing = db.execute(
                select(Vehicle).where(Vehicle.source == src, Vehicle.source_id == sid)
            ).scalar_one_or_none()

            if existing:
                existing.price = float(l.get("price", existing.price))
                existing.last_seen = datetime.now(timezone.utc)
                existing.scrape_count = (existing.scrape_count or 1) + 1
            else:
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
                    price=float(l.get("price", 0)),
                    title=str(l.get("title", "")),
                    location=str(l.get("location", "")),
                    fuel_type=fuel, transmission=trans,
                    horsepower=l.get("horsepower"), engine_size=l.get("engine_size"),
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
