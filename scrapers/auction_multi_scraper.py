"""
Multi-source auction scraper for Manheim, Autorola, and BCA.
Follows patterns from auction_scraper.py with circuit breaker and observability support.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config import settings
from database.models import AuctionTransaction, Source, VehicleType, FuelType
from database.db import get_db_context
from utils.retry import retry_network
from utils.production_safeguards import (
    with_circuit_breaker,
    _manheim_circuit_breaker,
    _autorola_circuit_breaker,
    _bca_circuit_breaker,
)
from utils.observability import track_scrape

logger = logging.getLogger(__name__)

_HTTP_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9,pt-PT;q=0.8,pt;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}


class AuctionScraper:
    """Base scraper with shared HTTP fetch, parsing, retry, circuit breaker and observability."""

    BASE_URL: str = ""
    SEARCH_PATH: str = "/search"
    REFERER: str = ""

    def __init__(self, source: Source, breaker) -> None:
        self.source = source
        self.breaker = breaker
        self.timeout = 30
        self.max_retries = 3
        self._session: Optional[Any] = None
        self.headers = dict(_HTTP_BROWSER_HEADERS)
        self.headers.setdefault("Referer", self.REFERER or self.BASE_URL)

    async def __aenter__(self) -> "AuctionScraper":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        await self.close()
        return None

    async def initialize(self) -> None:
        try:
            import httpx
            limits = httpx.Limits(max_connections=3, max_keepalive_connections=1)
            timeout = httpx.Timeout(self.timeout, connect=15.0)
            self._session = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                headers=self.headers,
                follow_redirects=True,
            )
            logger.info(f"[{self.source.value}] Session initialized")
        except ImportError:
            logger.warning("httpx not installed, falling back without HTTP client")

    async def close(self) -> None:
        if self._session:
            try:
                await self._session.aclose()
            except Exception:
                try:
                    await self._session.close()
                except Exception:
                    pass
            self._session = None
            logger.info(f"[{self.source.value}] Session closed")

    async def _get_session(self):
        if self._session is None:
            await self.initialize()
        return self._session

    async def _fetch_text(self, url: str, *, retries: int = 2) -> Optional[str]:
        try:
            session = await self._get_session()
            if session is None:
                raise RuntimeError("No HTTP session available")
            response = await session.get(url)
            text = response.text
            return text
        except Exception as exc:
            if retries > 0:
                wait = 2 ** (self.max_retries - retries)
                logger.warning(f"[{self.source.value}] Fetch error for {url}: {exc}. Retrying in {wait}s")
                await asyncio.sleep(wait)
                return await self._fetch_text(url, retries=retries - 1)
            logger.error(f"[{self.source.value}] Failed to fetch {url}: {exc}")
            return None

    async def _playwright_fetch(self, url: str, wait_for: str = "body", timeout: int = 15000) -> Optional[str]:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=timeout)
                try:
                    await page.wait_for_selector(wait_for, timeout=timeout // 2)
                except Exception:
                    pass
                html = await page.content()
                await browser.close()
                logger.info(f"[{self.source.value}] Playwright rendered {url}")
                return html
        except ImportError:
            logger.error("[PLAYWRIGHT] Package not installed; install with: pip install playwright")
            return None
        except Exception as exc:
            logger.error(f"[{self.source.value}] Playwright error for {url}: {exc}")
            return None

    def _parse_listings(self, html: str, base_url: str, max_items: int) -> List[Dict[str, Any]]:
        return []

    @with_circuit_breaker(_manheim_circuit_breaker, "manheim-scrape")
    async def _scrape_manheim(self, vehicle_type: str, max_listings: int) -> List[Dict[str, Any]]:
        return await self._safe_scrape("manheim", vehicle_type, max_listings, paths=[
            "/us/search",
            "/us/en/search",
        ])

    @with_circuit_breaker(_autorola_circuit_breaker, "autorola-scrape")
    async def _scrape_autorola(self, vehicle_type: str, max_listings: int) -> List[Dict[str, Any]]:
        return await self._safe_scrape("autorola", vehicle_type, max_listings, paths=[
            "/en/search/car",
            "/en/search",
        ])

    @with_circuit_breaker(_bca_circuit_breaker, "bca-scrape")
    async def _scrape_bca(self, vehicle_type: str, max_listings: int) -> List[Dict[str, Any]]:
        return await self._safe_scrape("bca", vehicle_type, max_listings, paths=[
            "/search",
            "/search/cars",
        ])

    async def _safe_scrape(
        self,
        source_key: str,
        vehicle_type: str,
        max_listings: int,
        *,
        paths: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        listings: List[Dict[str, Any]] = []
        for path in paths or [self.SEARCH_PATH]:
            if not listings:
                url = self.BASE_URL + path
                logger.info(f"[{self.source.value}] Fetching {url}")
                html = await self._playwright_fetch(url)
                if html:
                    listings = self._parse_listings(html, self.BASE_URL, max_listings)
                if not listings:
                    logger.info(f"[{self.source.value}] Playwright returned no cards; attempting plain HTTP")
                    html = await self._fetch_text(url)
                    if html:
                        listings = self._parse_listings(html, self.BASE_URL, max_listings)
                    logger.info(f"[{self.source.value}] Extracted {len(listings)} listings from {url}")
                await asyncio.sleep(random.uniform(1.5, 3.0))
        if listings:
            self._save_to_database(listings)
        return listings[:max_listings]

    def _save_to_database(self, listings: List[Dict[str, Any]]) -> int:
        saved = 0
        for item in listings:
            try:
                with get_db_context() as db:
                    existing = db.query(AuctionTransaction).filter(
                        AuctionTransaction.source == item["source"],
                        AuctionTransaction.source_id == item["source_id"],
                    ).first()
                    if existing:
                        if item.get("adjudication_price"):
                            existing.adjudication_price = item["adjudication_price"]
                            existing.scraped_at = item.get("scraped_at")
                        continue
                    price = item.get("adjudication_price") or item.get("price") or 0
                    if price <= 0:
                        continue
                    transaction = AuctionTransaction(
                        source=item["source"],
                        source_id=item["source_id"],
                        url=item.get("url", ""),
                        vehicle_type=item["vehicle_type"],
                        brand=item.get("brand", ""),
                        model=item.get("model", ""),
                        year=item.get("year"),
                        km=item.get("km"),
                        fuel_type=item.get("fuel_type"),
                        transmission=item.get("transmission"),
                        horsepower=item.get("horsepower"),
                        engine_size=item.get("engine_size"),
                        location=item.get("location"),
                        auction_type=item.get("auction_type"),
                        adjudication_price=price,
                        starting_price=item.get("starting_price"),
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        images=item.get("images"),
                        scraped_at=item.get("scraped_at"),
                        is_active=True,
                    )
                    db.add(transaction)
                    saved += 1
                db.commit()
            except Exception as exc:
                logger.error(f"[{self.source.value}] Database save error: {exc}")
        if saved:
            logger.info(f"[{self.source.value}] Saved {saved} transactions")
        return saved


class ManheimScraper(AuctionScraper):
    """Scraper for Manheim USA/Europe public search pages."""

    BASE_URL = "https://www.manheim.com"
    SEARCH_PATH = "/us/search"
    REFERER = "https://www.manheim.com/"

    def __init__(self) -> None:
        from utils.production_safeguards import _manheim_circuit_breaker
        super().__init__(Source.MANHEIM, _manheim_circuit_breaker)

    @retry_network(max_attempts=3)
    @track_scrape("manheim")
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False,
    ) -> List[Dict[str, object]]:
        logger.info(f"[MANHEIM] Starting scrape (type={vehicle_type}, max={max_listings})")
        return await self._scrape_manheim(vehicle_type, max_listings)

    def _parse_listings(self, html: str, base_url: str, max_items: int) -> List[Dict[str, Any]]:
        return self._extract_cards(html, base_url, max_items, source_prefix="manheim")

    def _extract_cards(self, html: str, base_url: str, max_items: int, *, source_prefix: str) -> List[Dict[str, Any]]:
        listings: List[Dict[str, Any]] = []
        try:
            soup = BeautifulSoup(html, "lxml")
            cards = soup.select("div[class*='result'], div[class*='card'], li[class*='result'], article[class*='result']")
            if not cards:
                generic = soup.find_all(["li", "div", "article"], class_=lambda x: x and any(k in str(x).lower() for k in ["result", "listing", "lot", "vehicle"]))
                cards = generic
            logger.info(f"[{source_prefix.upper()}] Found {len(cards)} candidate cards")
            for card in cards[:max_items]:
                try:
                    title = ""
                    title_candidates = card.select("h2, h3, h4, [class*='title'], [class*='name'], a[class*='title']")
                    if title_candidates:
                        title = title_candidates[0].get_text(strip=True)
                    link = card.select_one("a[href]")
                    href = link.get("href", "") if link else ""
                    url = urljoin(base_url, href) if href else ""
                    if not title or len(title) < 5 or not url:
                        continue
                    price_text = ""
                    price_elems = card.select("[class*='price'], [class*='cost'], [class*='bid'], span, p")
                    for price_elem in price_elems:
                        candidate = price_elem.get_text(strip=True)
                        if any(ch.isdigit() for ch in candidate):
                            price_text = candidate
                            break
                    adjudication_price = self._parse_price(price_text)
                    location = ""
                    loc_elems = card.select("[class*='location'], [class*='city'], [class*='state']")
                    if loc_elems:
                        location = loc_elems[0].get_text(strip=True)
                    listing = {
                        "source_id": f"{source_prefix}_{abs(hash(title + url)) % 10_000_000}",
                        "title": title,
                        "adjudication_price": adjudication_price,
                        "starting_price": None,
                        "url": url,
                        "source": self.source,
                        "auction_type": "dealer",
                        "vehicle_type": VehicleType.carros if vehicle_type == "carros" else VehicleType.motos,
                        "location": location,
                        "description": "",
                        "images": [],
                        "scraped_at": datetime.now(timezone.utc),
                    }
                    brand_model = self._extract_brand_model(title)
                    listing.update(brand_model)
                    listing["year"] = self._extract_year(card, title) or listing.get("year")
                    listing["km"] = self._extract_km(card)
                    if adjudication_price:
                        listings.append(listing)
                except Exception as exc:
                    logger.debug(f"[{source_prefix.upper()}] Failed to parse card: {exc}")
                    continue
        except Exception as exc:
            logger.error(f"[{source_prefix.upper()}] HTML parse error: {exc}")
        return listings

    def _extract_year(self, card, title: str) -> Optional[int]:
        year_candidates = card.select("[class*='year'], [class*='ano']")
        if year_candidates:
            return self._parse_int(year_candidates[0].get_text())
        import re
        match = re.search(r"\b(19|20)\d{2}\b", title)
        if match:
            return int(match.group())
        return None

    def _extract_km(self, card) -> Optional[int]:
        for elem in card.select("[class*='mileage'], [class*='km'], [class*='odometer']"):
            return self._parse_int(elem.get_text())
        return None

    def _extract_brand_model(self, title: str) -> Dict[str, Any]:
        return _shared_brand_model(title)

    @staticmethod
    def _parse_price(text: Optional[str]) -> Optional[float]:
        if not text:
            return None
        text = text.replace("€", "").replace("EUR", "").replace("&euro;", "").strip()
        import re
        match = re.search(r"[\d.,]+", text.replace(" ", ""))
        if match:
            price_str = match.group().replace(".", "").replace(",", ".")
            try:
                return float(price_str)
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_int(text: str) -> Optional[int]:
        if not text:
            return None
        import re
        match = re.search(r"[\d.,]+", text)
        if match:
            num_str = match.group().replace(".", "").replace(",", "")
            try:
                return int(num_str)
            except ValueError:
                return None
        return None


class AutorolaScraper(AuctionScraper):
    """Scraper for Autorola public auction listings."""

    BASE_URL = "https://www.autorola.com"
    SEARCH_PATH = "/en/search/car"
    REFERER = "https://www.autorola.com/"

    def __init__(self) -> None:
        from utils.production_safeguards import _autorola_circuit_breaker
        super().__init__(Source.AUTOROLA, _autorola_circuit_breaker)

    @retry_network(max_attempts=3)
    @track_scrape("autorola")
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False,
    ) -> List[Dict[str, object]]:
        logger.info(f"[AUTOROLA] Starting scrape (type={vehicle_type}, max={max_listings})")
        return await self._scrape_autorola(vehicle_type, max_listings)

    def _parse_listings(self, html: str, base_url: str, max_items: int) -> List[Dict[str, Any]]:
        return self._extract_cards(html, base_url, max_items, source_prefix="autorola")


class BCAScraper(AuctionScraper):
    """Scraper for BCA public search pages."""

    BASE_URL = "https://www.bca.co.uk"
    SEARCH_PATH = "/search"
    REFERER = "https://www.bca.co.uk/"

    def __init__(self) -> None:
        from utils.production_safeguards import _bca_circuit_breaker
        super().__init__(Source.BCA, _bca_circuit_breaker)

    @retry_network(max_attempts=3)
    @track_scrape("bca")
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False,
    ) -> List[Dict[str, object]]:
        logger.info(f"[BCA] Starting scrape (type={vehicle_type}, max={max_listings})")
        return await self._scrape_bca(vehicle_type, max_listings)

    def _parse_listings(self, html: str, base_url: str, max_items: int) -> List[Dict[str, Any]]:
        return self._extract_cards(html, base_url, max_items, source_prefix="bca")


class AuctionMultiScraperFacade:
    """Facade to expose the three multi-auction scrapers as a single service."""
    
    def __init__(self) -> None:
        self.manheim = ManheimScraper()
        self.autorola = AutorolaScraper()
        self.bca = BCAScraper()
    
    async def close(self) -> None:
        await self.manheim.close()
        await self.autorola.close()
        await self.bca.close()
    
    async def __aenter__(self) -> "AuctionMultiScraperFacade":
        await self.manheim.initialize()
        await self.autorola.initialize()
        await self.bca.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        await self.close()
        return None


async def scrape_all_auctions(max_per_source: int = 50) -> Dict[str, int]:
    results: Dict[str, int] = {}
    async with ManheimScraper() as manheim:
        listings = await manheim.scrape_listings(max_listings=max_per_source)
        results["manheim"] = len(listings)
    async with AutorolaScraper() as autorola:
        listings = await autorola.scrape_listings(max_listings=max_per_source)
        results["autorola"] = len(listings)
    async with BCAScraper() as bca:
        listings = await bca.scrape_listings(max_listings=max_per_source)
        results["bca"] = len(listings)
    return results


_multi_scraper_singleton: Optional[AuctionMultiScraperFacade] = None


async def get_auction_multi_scraper() -> AuctionMultiScraperFacade:
    global _multi_scraper_singleton
    if _multi_scraper_singleton is None:
        _multi_scraper_singleton = AuctionMultiScraperFacade()
        await _multi_scraper_singleton.__aenter__()
    return _multi_scraper_singleton


def _shared_brand_model(title: str) -> Dict[str, Any]:
    result = {"brand": "", "model": ""}
    common_brands = [
        "Volkswagen", "VW", "Toyota", "Renault", "Peugeot", "Citroën", "BMW", "Mercedes",
        "Audi", "Ford", "Opel", "Fiat", "Honda", "Nissan", "Hyundai", "Kia", "Seat",
        "Skoda", "Volvo", "Mazda", "Suzuki", "Mitsubishi", "Porsche", "Tesla",
    ]
    title_lower = title.lower()
    for brand in common_brands:
        if brand.lower() in title_lower:
            result["brand"] = brand
            break
    if result["brand"]:
        brand_lower = result["brand"].lower()
        remaining = title_lower.split(brand_lower)[-1] if brand_lower in title_lower else title_lower
        remaining = remaining.strip(" -_.,/")
        words = remaining.split()[:4]
        result["model"] = " ".join(w for w in words if w and len(w) > 1 and not w.isdigit())
    return result


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    results = asyncio.run(scrape_all_auctions(10))
    print(results)
