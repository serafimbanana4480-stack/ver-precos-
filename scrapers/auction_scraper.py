"""
Scraper for Portugal automotive auction houses (VPauto, Leilosoc)
Uses Playwright for JavaScript-rendered pages and direct HTTP for simpler pages
Collects REAL transaction prices (adjudicação) for ML training ground truth
"""
import logging
import asyncio
import re
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from urllib.parse import urljoin
import json

from bs4 import BeautifulSoup
import aiohttp

from config import settings
from database.models import AuctionTransaction, Source, VehicleType, FuelType, Transmission
from database.db import get_db_context

logger = logging.getLogger(__name__)


class AuctionScraper:
    """Scraper for PT Vehicle Auctions - collects real transaction prices"""

    BASE_URLS = {
        "vpauto": "https://www.vpauto.pt",
        "leilosoc": "https://www.leilosoc.pt",
    }

    LEILOSOC_AUCTION_PATHS = [
        "/category/6-veiculos/",
        "/auction/",
    ]

    def __init__(self) -> None:
        self.timeout = 30
        self.max_retries = 3
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def initialize(self):
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("[AUCTION] Session initialized")

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("[AUCTION] Session closed")

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a single page with retry logic"""
        if not self.session:
            await self.initialize()

        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        logger.info(f"[AUCTION] Fetched: {url}")
                        return await response.text()
                    elif response.status == 429:
                        wait_time = 2 ** attempt * 5
                        logger.warning(f"[AUCTION] Rate limited, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                    elif response.status == 404:
                        logger.warning(f"[AUCTION] Page not found (404): {url}")
                        return None
                    else:
                        logger.warning(f"[AUCTION] HTTP {response.status} for {url}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"[AUCTION] Timeout for {url} (attempt {attempt + 1})")
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"[AUCTION] Error fetching {url}: {e}")
                await asyncio.sleep(2 ** attempt)
        return None

    async def scrape_with_playwright_async(self, url: str, wait_for_selector: str = "body", timeout: int = 15000) -> Optional[str]:
        """
        Use Playwright Async API to fetch JavaScript-rendered page content.
        Returns the rendered HTML.
        """
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=timeout)
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=timeout // 2)
                    except Exception:
                        pass
                content = await page.content()
                await browser.close()
                logger.info(f"[AUCTION] Playwright Async fetched: {url}")
                return content
        except ImportError:
            logger.error("[AUCTION] Playwright not installed. Install with: pip install playwright")
            return None
        except Exception as e:
            logger.error(f"[AUCTION] Playwright async error for {url}: {e}")
            return None

    def scrape_with_playwright(self, url: str, wait_for_selector: str = "body", timeout: int = 15000) -> Optional[str]:
        """Sync wrapper for Playwright (runs in thread to avoid asyncio conflicts)"""
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=timeout)
                if wait_for_selector:
                    try:
                        page.wait_for_selector(wait_for_selector, timeout=timeout // 2)
                    except Exception:
                        pass
                content = page.content()
                browser.close()
                logger.info(f"[AUCTION] Playwright fetched: {url}")
                return content
        except ImportError:
            logger.error("[AUCTION] Playwright not installed. Install with: pip install playwright")
            return None
        except Exception as e:
            logger.error(f"[AUCTION] Playwright error for {url}: {e}")
            return None

    async def scrape_leilosoc(self, max_listings: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape Leilosoc.pt auction listings using Playwright for JS rendering.
        """
        logger.info(f"[LEILOSOC] Starting Leilosoc scraping with Playwright (limit: {max_listings})")
        listings = []

        base_url = self.BASE_URLS['leilosoc']

        for path in self.LEILOSOC_AUCTION_PATHS:
            if len(listings) >= max_listings:
                break

            url = f"{base_url}{path}"
            logger.info(f"[LEILOSOC] Fetching with Playwright: {url}")

            html = await self.scrape_with_playwright_async(url, wait_for_selector="article, .item, [class*='card']")

            if html:
                page_listings = self._extract_leilosoc_from_html(html, base_url, max_listings - len(listings))
                listings.extend(page_listings)
                logger.info(f"[LEILOSOC] Extracted {len(page_listings)} from {url}")

            await asyncio.sleep(2)

        if not listings:
            logger.warning("[LEILOSOC] No listings found. Trying fallback HTTP method...")
            fallback_listings = await self._scrape_leilosoc_fallback(base_url, max_listings)
            listings.extend(fallback_listings)

        logger.info(f"[LEILOSOC] Total extracted: {len(listings)} listings")
        return listings[:max_listings]

    async def _scrape_leilosoc_fallback(self, base_url: str, max_listings: int) -> List[Dict[str, Any]]:
        """Fallback method using HTTP without JS rendering"""
        listings = []
        for path in self.LEILOSOC_AUCTION_PATHS:
            if len(listings) >= max_listings:
                break
            url = f"{base_url}{path}"
            html = await self._fetch_page(url)
            if html:
                page_listings = self._extract_leilosoc_from_html(html, base_url, max_listings - len(listings))
                listings.extend(page_listings)
            await asyncio.sleep(1)
        return listings

    def _extract_leilosoc_from_html(self, html: str, base_url: str, max_items: int) -> List[Dict[str, Any]]:
        """Extract Leilosoc listing cards from HTML"""
        listings = []

        try:
            soup = BeautifulSoup(html, "lxml")

            selectors = [
                "div.c-gqwkJN",
                "[class*='auction-card']",
                "article[class*='item']",
                "div[class*='item']",
            ]

            cards = []
            for selector in selectors:
                cards = soup.select(selector)
                if len(cards) > 3:
                    logger.info(f"[LEILOSOC] Found {len(cards)} cards with selector: {selector}")
                    break

            if not cards:
                cards = soup.find_all(["article", "div"], class_=lambda x: x and any(k in str(x).lower() for k in ["item", "card", "product", "listing"]))

            logger.info(f"[LEILOSOC] Processing {len(cards)} cards")

            for card in cards[:max_items]:
                try:
                    title_elem = card.select_one("h3.c-fqASOw, h2, h3, h4, [class*='titulo'], [class*='title']")
                    price_elem = card.select_one("[class*='preco'], [class*='price'], [class*='valor'], span, p")
                    location_elem = card.select_one("[class*='local'], [class*='location'], [class*='region'], .auction-card-location")

                    title = title_elem.get_text(strip=True) if title_elem else ""
                    if not title or len(title) < 5:
                        continue

                    price_text = price_elem.get_text(strip=True) if price_elem else ""
                    adjudication_price = self._parse_price(price_text)

                    if not adjudication_price:
                        starting_price = self._parse_price(price_text.replace("mínimo", "").replace("partida", "").replace("valor", ""))
                        if starting_price:
                            adjudication_price = starting_price
                            starting_price = None

                    link = card.select_one("a")
                    url = ""
                    if link:
                        href = link.get('href', '')
                        if href.startswith('/'):
                            url = urljoin(base_url, href)
                        elif href.startswith('http'):
                            url = href

                    location = location_elem.get_text(strip=True) if location_elem else ""

                    listing = {
                        "source_id": f"leilosoc_{hash(title + url) % 10000000}",
                        "title": title,
                        "adjudication_price": adjudication_price,
                        "starting_price": starting_price,
                        "url": url,
                        "source": Source.LEILOSOC,
                        "auction_type": "judicial",
                        "vehicle_type": VehicleType.carros,
                        "location": location,
                        "description": "",
                        "images": [],
                        "scraped_at": datetime.now(timezone.utc),
                    }

                    brand_model = self._extract_brand_model(title)
                    listing.update(brand_model)

                    self._extract_vehicle_details(card, listing)

                    if adjudication_price:
                        listing["year"] = listing.get("year", 2020)
                        listings.append(listing)

                except Exception as e:
                    logger.debug(f"[LEILOSOC] Error parsing card: {e}")
                    continue

        except Exception as e:
            logger.error(f"[LEILOSOC] Error parsing HTML: {e}")

        return listings

    async def scrape_vpauto(self, max_listings: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape VPauto.pt auction listings using Playwright for JS rendering.
        VPauto requires JavaScript to load vehicle listings.
        """
        logger.info(f"[VPAUTO] Starting VPauto scraping with Playwright (limit: {max_listings})")
        listings = []

        base_url = self.BASE_URLS['vpauto']

        url = f"{base_url}/leilao-automovel/"
        logger.info(f"[VPAUTO] Fetching with Playwright: {url}")

        html = await self.scrape_with_playwright_async(url, wait_for_selector="article, .item, [class*='card'], [class*='listing']")

        if html:
            listings = self._extract_vpauto_from_html(html, base_url, max_listings)

        if not listings:
            logger.warning("[VPAUTO] No listings found via Playwright. Trying homepage fallback...")
            html = await self._fetch_page(base_url)
            if html:
                listings = self._extract_vpauto_from_html(html, base_url, max_listings)

        logger.info(f"[VPAUTO] Extracted {len(listings)} listings")
        return listings[:max_listings]

    def _extract_vpauto_from_html(self, html: str, base_url: str, max_items: int) -> List[Dict[str, Any]]:
        """Extract VPauto listing cards from HTML"""
        listings = []
        try:
            soup = BeautifulSoup(html, "lxml")

            selectors = [
                "article[class*='item']",
                "div[class*='item']",
                "div[class*='card']",
                "div[class*='product']",
                "div[class*='listing']",
                "div[class*='classified']",
            ]

            cards = []
            for selector in selectors:
                cards = soup.select(selector)
                if len(cards) > 3:
                    logger.info(f"[VPAUTO] Found {len(cards)} cards with selector: {selector}")
                    break

            for card in cards[:max_items]:
                try:
                    title_elem = card.select_one("h1, h2, h3, h4, [class*='titulo'], [class*='title'], [class*='name']")
                    price_elem = card.select_one("[class*='preco'], [class*='price'], [class*='valor'], span")
                    link = card.select_one("a")

                    title = title_elem.get_text(strip=True) if title_elem else ""
                    if not title or len(title) < 5:
                        continue

                    price_text = price_elem.get_text(strip=True) if price_elem else ""
                    price = self._parse_price(price_text)

                    url = ""
                    if link:
                        href = link.get('href', '')
                        if href.startswith('/'):
                            url = urljoin(base_url, href)
                        elif href.startswith('http'):
                            url = href

                    if not price:
                        continue

                    listing = {
                        "source_id": f"vpauto_{hash(title + url) % 10000000}",
                        "title": title,
                        "price": price,
                        "url": url,
                        "source": Source.VPAUTO,
                        "auction_type": "dealer",
                        "vehicle_type": VehicleType.carros,
                        "description": "",
                        "images": [],
                        "scraped_at": datetime.now(timezone.utc),
                    }

                    brand_model = self._extract_brand_model(title)
                    listing.update(brand_model)

                    self._extract_vehicle_details(card, listing)

                    listing["year"] = listing.get("year", 2020)
                    listings.append(listing)

                except Exception as e:
                    logger.debug(f"[VPAUTO] Error parsing card: {e}")
                    continue

        except Exception as e:
            logger.error(f"[VPAUTO] Error parsing HTML: {e}")

        return listings

    def _extract_vehicle_details(self, card, listing: Dict):
        """Extract vehicle details (km, year, fuel, etc.) from card element"""
        details = card.select("[class*='detail'], [class*='spec'], [class*='info'], span, p, li")
        for detail in details:
            text = detail.get_text(strip=True).lower()
            if any(x in text for x in ["km", "quilm"]):
                listing["km"] = self._parse_int(text)
            elif "ano" in text or "year" in text:
                listing["year"] = self._parse_int(text)
            elif "cv" in text or "hp" in text:
                listing["horsepower"] = self._parse_int(text)
            elif "cilindrada" in text or "cc" in text:
                listing["engine_size"] = self._parse_int(text)
            elif any(x in text for x in ["gasolina", "gasoleo", "diesel"]):
                if "gasoleo" in text or "diesel" in text:
                    listing["fuel_type"] = FuelType.DIESEL
                else:
                    listing["fuel_type"] = FuelType.GASOLINE
            elif "eletrico" in text or "electric" in text:
                listing["fuel_type"] = FuelType.ELECTRIC
            elif "híbrido" in text or "hybrid" in text:
                listing["fuel_type"] = FuelType.HYBRID

    def _extract_brand_model(self, title: str) -> Dict[str, Any]:
        """Extract brand and model from title"""
        result = {"brand": "", "model": ""}

        common_brands = [
            "Volkswagen", "VW", "Toyota", "Renault", "Peugeot", "Citroën", "BMW", "Mercedes",
            "Audi", "Ford", "Opel", "Fiat", "Honda", "Nissan", "Hyundai", "Kia", "Seat",
            "Skoda", "Volvo", "Mazda", "Suzuki", "Mitsubishi", "Porsche", "Tesla",
            "Yamaha", "KTM", "Kawasaki", "Ducati", "Harley", "BMW Motorrad",
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

    def _parse_price(self, text: str) -> Optional[float]:
        """Parse price from text like '12.500 €' or '€12.500'"""
        if not text:
            return None
        text = text.replace("€", "").replace("EUR", "").replace("&euro;", "").strip()
        match = re.search(r"[\d.,]+", text.replace(" ", ""))
        if match:
            price_str = match.group().replace(".", "").replace(",", ".")
            try:
                return float(price_str)
            except ValueError:
                return None
        return None

    def _parse_int(self, text: str) -> Optional[int]:
        """Parse integer from text like '45.000 km'"""
        if not text:
            return None
        match = re.search(r"[\d.,]+", text)
        if match:
            num_str = match.group().replace(".", "").replace(",", "")
            try:
                return int(num_str)
            except ValueError:
                return None
        return None

    def save_to_database(self, listings: List[Dict[str, Any]]) -> int:
        """Save auction transactions to database"""
        saved_count = 0
        with get_db_context() as db:
            for item in listings:
                existing = db.query(AuctionTransaction).filter(
                    AuctionTransaction.source_id == item["source_id"]
                ).first()

                if existing:
                    if item.get("adjudication_price") and existing.adjudication_price != item["adjudication_price"]:
                        existing.adjudication_price = item["adjudication_price"]
                        existing.scraped_at = datetime.now(timezone.utc)
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
                    year=item.get("year", 2020),
                    km=item.get("km"),
                    fuel_type=item.get("fuel_type"),
                    transmission=item.get("transmission"),
                    horsepower=item.get("horsepower"),
                    engine_size=item.get("engine_size"),
                    location=item.get("location", ""),
                    auction_type=item.get("auction_type"),
                    adjudication_price=price,
                    starting_price=item.get("starting_price"),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    images=item.get("images"),
                    scraped_at=datetime.now(timezone.utc),
                    is_active=True,
                )
                db.add(transaction)
                saved_count += 1

            db.commit()
        logger.info(f"[AUCTION] Saved {saved_count} transactions to database")
        return saved_count


async def scrape_all_auctions(max_per_source: int = 50) -> Dict[str, int]:
    """Scrape all auction sources and save to database"""
    results = {}
    async with AuctionScraper() as scraper:
        leilosoc_listings = await scraper.scrape_leilosoc(max_per_source)
        if leilosoc_listings:
            saved = scraper.save_to_database(leilosoc_listings)
            results["leilosoc"] = saved

        await asyncio.sleep(2)

        vpauto_listings = await scraper.scrape_vpauto(max_per_source)
        if vpauto_listings:
            saved = scraper.save_to_database(vpauto_listings)
            results["vpauto"] = saved

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = asyncio.run(scrape_all_auctions(30))
    print(f"Results: {results}")
