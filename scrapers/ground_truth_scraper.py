"""
Ground Truth Scraper for AutoDeal IA Hunter
=============================================
Production-ready scraper for collecting REAL transaction prices (adjudicação)
from Portuguese vehicle auction houses. Uses Playwright with stealth for
JavaScript-rendered pages, with aiohttp fallback.

Sources:
  - VPAuto.pt      (renting, fleet, judicial auctions)
  - Leilosoc.pt    (judicial and notarial auctions)
  - BCA Marketplace (dealer auctions — requires auth)
  - Manheim Portugal (dealer auctions — requires auth)

Schema target: auction_transactions (see database/models.py)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from config import settings
from database.db import get_db_context
from database.models import (
    AuctionTransaction,
    FuelType,
    Source,
    Transmission,
    VehicleType,
)
from utils.parsers import parse_km, parse_price
from utils.playwright_stealth import apply_stealth_async
from utils.retry import retry_network

logger = logging.getLogger("ground_truth")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMON_BRANDS: List[str] = [
    "Volkswagen", "VW", "Toyota", "Renault", "Peugeot", "Citroën", "Citroen",
    "BMW", "Mercedes", "Mercedes-Benz", "Audi", "Ford", "Opel", "Fiat",
    "Honda", "Nissan", "Hyundai", "Kia", "Seat", "Skoda", "Volvo", "Mazda",
    "Suzuki", "Mitsubishi", "Porsche", "Tesla", "Dacia", "Jeep", "Mini",
    "Land Rover", "Jaguar", "Lexus", "Alfa Romeo", "Smart", "Chevrolet",
    "Yamaha", "KTM", "Kawasaki", "Ducati", "Harley-Davidson", "Harley",
    "Triumph", "BMW Motorrad", "Piaggio", "Vespa",
]

FUEL_KEYWORDS: Dict[str, FuelType] = {
    "gasoleo": FuelType.DIESEL,
    "diesel": FuelType.DIESEL,
    "gasolina": FuelType.GASOLINE,
    "gpl": FuelType.GPL,
    "gas natural": FuelType.GAS,
    "eletrico": FuelType.ELECTRIC,
    "elétrico": FuelType.ELECTRIC,
    "electric": FuelType.ELECTRIC,
    "hibrido": FuelType.HYBRID,
    "híbrido": FuelType.HYBRID,
    "hybrid": FuelType.HYBRID,
    "plug-in": FuelType.HYBRID,
    "plug in": FuelType.HYBRID,
}

TRANSMISSION_KEYWORDS: Dict[str, Transmission] = {
    "manual": Transmission.MANUAL,
    "automatico": Transmission.AUTOMATIC,
    "automático": Transmission.AUTOMATIC,
    "automatic": Transmission.AUTOMATIC,
    "auto": Transmission.AUTOMATIC,
    "cvt": Transmission.AUTOMATIC,
    "dsg": Transmission.AUTOMATIC,
    "semi": Transmission.SEMI_AUTOMATIC,
    "semi-automatico": Transmission.SEMI_AUTOMATIC,
    "semi-automático": Transmission.SEMI_AUTOMATIC,
    "semi automatic": Transmission.SEMI_AUTOMATIC,
}

COLOR_KEYWORDS: List[str] = [
    "preto", "branco", "cinzento", "cinza", "prateado", "prata", "azul",
    "vermelho", "verde", "amarelo", "laranja", "castanho", "marrom", "bege",
    "dourado", "roxo", "rosa", "grafite", "preto metalizado", "branco perolizado",
    "black", "white", "grey", "gray", "silver", "blue", "red", "green",
    "yellow", "orange", "brown", "beige", "gold", "purple", "pink",
]

PT_DISTRICTS: List[str] = [
    "Lisboa", "Porto", "Braga", "Aveiro", "Faro", "Coimbra", "Leiria",
    "Setúbal", "Viana do Castelo", "Vila Real", "Évora", "Beja", "Bragança",
    "Castelo Branco", "Guarda", "Portalegre", "Santarém", "Viseu", "Madeira",
    "Açores", "Acores",
]

# ---------------------------------------------------------------------------
# Data Transfer Object
# ---------------------------------------------------------------------------

@dataclass
class AuctionListing:
    """Normalized auction listing ready for database insertion."""
    source: Source
    source_id: str
    url: str
    vehicle_type: VehicleType = VehicleType.carros
    brand: str = ""
    model: str = ""
    version: Optional[str] = None
    year: int = 0
    km: Optional[int] = None
    horsepower: Optional[int] = None
    engine_size: Optional[int] = None
    fuel_type: Optional[FuelType] = None
    transmission: Optional[Transmission] = None
    color: Optional[str] = None
    location: Optional[str] = None
    district: Optional[str] = None
    auction_type: str = ""
    auction_date: Optional[datetime] = None
    lot_number: Optional[str] = None
    adjudication_price: float = 0.0
    reserve_price: Optional[float] = None
    starting_price: Optional[float] = None
    retail_price: Optional[float] = None
    condition_grade: Optional[str] = None
    has_damage: bool = False
    damage_notes: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    images: List[str] = field(default_factory=list)
    seller_type: Optional[str] = None
    seller_name: Optional[str] = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dict compatible with AuctionTransaction model."""
        return {
            "source": self.source,
            "source_id": self.source_id,
            "url": self.url,
            "vehicle_type": self.vehicle_type,
            "brand": self.brand,
            "model": self.model,
            "version": self.version,
            "year": self.year,
            "km": self.km,
            "horsepower": self.horsepower,
            "engine_size": self.engine_size,
            "fuel_type": self.fuel_type,
            "transmission": self.transmission,
            "color": self.color,
            "location": self.location,
            "district": self.district,
            "auction_type": self.auction_type,
            "auction_date": self.auction_date,
            "lot_number": self.lot_number,
            "adjudication_price": self.adjudication_price,
            "reserve_price": self.reserve_price,
            "starting_price": self.starting_price,
            "retail_price": self.retail_price,
            "condition_grade": self.condition_grade,
            "has_damage": self.has_damage,
            "damage_notes": self.damage_notes,
            "title": self.title,
            "description": self.description,
            "images": self.images if self.images else None,
            "seller_type": self.seller_type,
            "seller_name": self.seller_name,
            "scraped_at": self.scraped_at,
            "is_active": self.is_active,
        }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ListingValidator:
    """Validate auction listings before DB insertion."""

    MIN_PRICE: float = 100.0
    MAX_PRICE: float = 500_000.0
    MIN_YEAR: int = 1980
    MAX_YEAR: int = datetime.now().year + 1
    MAX_KM: int = 1_000_000

    @classmethod
    def validate(cls, listing: AuctionListing) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not listing.source_id or len(listing.source_id) < 3:
            errors.append("source_id missing or too short")
        if not listing.url or not listing.url.startswith("http"):
            errors.append(f"invalid url: {listing.url}")
        if not listing.title or len(listing.title) < 3:
            errors.append("title missing or too short")
        if listing.adjudication_price < cls.MIN_PRICE or listing.adjudication_price > cls.MAX_PRICE:
            errors.append(
                f"adjudication_price out of range ({cls.MIN_PRICE}-{cls.MAX_PRICE}): "
                f"{listing.adjudication_price}"
            )
        if listing.year < cls.MIN_YEAR or listing.year > cls.MAX_YEAR:
            errors.append(f"year out of range: {listing.year}")
        if listing.km is not None and (listing.km < 0 or listing.km > cls.MAX_KM):
            errors.append(f"km out of range: {listing.km}")
        if not listing.brand:
            errors.append("brand missing")
        return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Async rate limiter with jitter to avoid detection."""

    def __init__(self, base_delay: float = 2.0, jitter: float = 1.0, max_rpm: int = 30):
        self.base_delay = base_delay
        self.jitter = jitter
        self.min_interval = 60.0 / max_rpm if max_rpm > 0 else 0.0
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self.base_delay + random.uniform(0, self.jitter)
            wait = max(delay, self.min_interval, self._last_request + self.min_interval - now)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()


# ---------------------------------------------------------------------------
# Playwright Helper
# ---------------------------------------------------------------------------

class PlaywrightHelper:
    """Reusable Playwright browser manager with stealth."""

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self._playwright_available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._playwright_available is not None:
            return self._playwright_available
        try:
            import playwright  # noqa: F401
            self._playwright_available = True
            return True
        except ImportError:
            self._playwright_available = False
            logger.warning("Playwright not installed. Fallback to aiohttp/requests.")
            return False

    async def fetch(
        self,
        url: str,
        wait_for_selector: str = "body",
        extra_wait: int = 2000,
    ) -> Optional[str]:
        if not self.is_available():
            return None
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    locale="pt-PT",
                    timezone_id="Europe/Lisbon",
                    viewport={"width": 1920, "height": 1080},
                    user_agent=random.choice(settings.user_agents),
                )
                page = await context.new_page()
                await apply_stealth_async(page)
                await page.goto(url, wait_until="networkidle", timeout=self.timeout)
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=self.timeout // 2)
                    except Exception:
                        pass
                if extra_wait > 0:
                    await asyncio.sleep(extra_wait / 1000)
                content = await page.content()
                await browser.close()
                logger.info(f"[PLAYWRIGHT] Fetched: {url}")
                return content
        except Exception as e:
            logger.error(f"[PLAYWRIGHT] Error fetching {url}: {e}")
            return None


# ---------------------------------------------------------------------------
# HTTP Fallback
# ---------------------------------------------------------------------------

class HTTPFallback:
    """aiohttp-based fallback fetcher."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._session: Optional[Any] = None

    async def _get_session(self) -> Any:
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    "User-Agent": random.choice(settings.user_agents),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                },
            )
        return self._session

    @retry_network(max_attempts=3, min_wait=2, max_wait=10)
    async def fetch(self, url: str) -> Optional[str]:
        session = await self._get_session()
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    text = await response.text()
                    logger.info(f"[HTTP] Fetched: {url}")
                    return text
                elif response.status == 429:
                    logger.warning(f"[HTTP] Rate limited (429): {url}")
                    await asyncio.sleep(5)
                    return None
                elif response.status == 404:
                    logger.warning(f"[HTTP] Not found (404): {url}")
                    return None
                else:
                    logger.warning(f"[HTTP] Status {response.status}: {url}")
                    return None
        except Exception as e:
            logger.error(f"[HTTP] Error fetching {url}: {e}")
            return None

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None


# ---------------------------------------------------------------------------
# Base Scraper
# ---------------------------------------------------------------------------

class BaseAuctionScraper(ABC):
    """Abstract base for all auction scrapers."""

    SOURCE: Source = Source.VPAUTO  # overridden by subclasses
    BASE_URL: str = ""
    AUCTION_TYPE: str = "dealer"

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        playwright: Optional[PlaywrightHelper] = None,
        http: Optional[HTTPFallback] = None,
    ):
        self.rate_limiter = rate_limiter or RateLimiter()
        self.playwright = playwright or PlaywrightHelper()
        self.http = http or HTTPFallback()
        self.stats = {
            "fetched": 0,
            "parsed": 0,
            "validated": 0,
            "saved": 0,
            "errors": 0,
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http.close()

    async def fetch_html(self, url: str, wait_for: str = "body", use_pw: bool = True) -> Optional[str]:
        await self.rate_limiter.acquire()
        self.stats["fetched"] += 1
        if use_pw and self.playwright.is_available():
            html = await self.playwright.fetch(url, wait_for_selector=wait_for)
            if html:
                return html
            logger.warning(f"[FETCH] Playwright failed for {url}, trying HTTP fallback")
        return await self.http.fetch(url)

    @abstractmethod
    async def scrape(self, max_listings: int = 50) -> List[AuctionListing]:
        """Scrape listings and return normalized AuctionListing objects."""
        ...

    # ------------------------------------------------------------------
    # Shared extraction utilities
    # ------------------------------------------------------------------

    @staticmethod
    def make_source_id(source: Source, raw_id: str) -> str:
        """Create a deterministic, unique source_id."""
        key = f"{source.value}_{raw_id}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    @staticmethod
    def extract_brand_model(title: str) -> Tuple[str, str]:
        """Extract brand and model from a vehicle title."""
        title_lower = title.lower()
        brand = ""
        for b in COMMON_BRANDS:
            if b.lower() in title_lower:
                brand = b
                break
        model = ""
        if brand:
            parts = title_lower.split(brand.lower())
            remainder = parts[-1] if len(parts) > 1 else title_lower
            remainder = remainder.strip(" -_.,/|")
            words = remainder.split()[:4]
            model = " ".join(
                w for w in words
                if w and len(w) > 1 and not w.isdigit() and w not in {"de", "do", "da", "em", "com", "para"}
            )
            model = model.title()
        return brand, model

    @staticmethod
    def extract_fuel_type(text: str) -> Optional[FuelType]:
        text_lower = text.lower()
        for keyword, fuel in FUEL_KEYWORDS.items():
            if keyword in text_lower:
                return fuel
        return None

    @staticmethod
    def extract_transmission(text: str) -> Optional[Transmission]:
        text_lower = text.lower()
        for keyword, trans in TRANSMISSION_KEYWORDS.items():
            if keyword in text_lower:
                return trans
        return None

    @staticmethod
    def extract_color(text: str) -> Optional[str]:
        text_lower = text.lower()
        for c in COLOR_KEYWORDS:
            if c.lower() in text_lower:
                return c.title()
        return None

    @staticmethod
    def extract_district(text: str) -> Optional[str]:
        text_lower = text.lower()
        for d in PT_DISTRICTS:
            if d.lower() in text_lower:
                return d
        return None

    @staticmethod
    def parse_int_from_text(text: str) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"[\d\s\.\,]+", text)
        if match:
            num_str = match.group().replace(" ", "").replace(".", "").replace(",", "")
            try:
                return int(num_str)
            except ValueError:
                return None
        return None

    @staticmethod
    def parse_year_from_text(text: str) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"\b(19|20)\d{2}\b", text)
        if match:
            year = int(match.group(0))
            if 1980 <= year <= datetime.now().year + 1:
                return year
        return None

    @staticmethod
    def parse_condition_grade(text: str) -> Optional[str]:
        text_upper = text.upper()
        for grade in ["A", "B", "C", "D", "E"]:
            if f"GRADE {grade}" in text_upper or f"CONDICAO {grade}" in text_upper or f"CONDIÇÃO {grade}" in text_upper:
                return grade
        return None

    @staticmethod
    def has_damage_indicators(text: str) -> Tuple[bool, Optional[str]]:
        damage_keywords = [
            "danos", "dano", "avaria", "avarias", "sinistrado", "acidente",
            "colisão", "colisao", "batido", "estrutural", "chassis", "airbag",
            "flood", "inundação", "inundacao", "queimado", "incêndio", "incendio",
        ]
        text_lower = text.lower()
        found = [k for k in damage_keywords if k in text_lower]
        if found:
            return True, ", ".join(found)
        return False, None

    @staticmethod
    def extract_lot_number(text: str) -> Optional[str]:
        match = re.search(r"lote\s*[#]?\s*(\d+)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r"#\s*(\d{3,})", text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def extract_images(soup: BeautifulSoup) -> List[str]:
        images = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if src and src.startswith("http"):
                images.append(src)
        return images[:10]  # limit to 10 images

    def save_listings(self, listings: List[AuctionListing]) -> int:
        """Save validated listings to SQLite, skipping duplicates."""
        saved = 0
        skipped = 0
        invalid = 0
        with get_db_context() as db:
            for listing in listings:
                is_valid, errors = ListingValidator.validate(listing)
                if not is_valid:
                    logger.debug(f"[VALIDATE] Skipping invalid listing: {errors}")
                    invalid += 1
                    continue

                existing = (
                    db.query(AuctionTransaction)
                    .filter(AuctionTransaction.source_id == listing.source_id)
                    .first()
                )
                if existing:
                    # Update price if changed
                    if existing.adjudication_price != listing.adjudication_price:
                        existing.adjudication_price = listing.adjudication_price
                        existing.scraped_at = datetime.now(timezone.utc)
                        logger.info(f"[UPDATE] Price changed for {listing.source_id}")
                    skipped += 1
                    continue

                db.add(AuctionTransaction(**listing.to_db_dict()))
                saved += 1
                self.stats["saved"] += 1

            db.commit()

        logger.info(
            f"[DB] Saved {saved} new, skipped {skipped} existing, rejected {invalid} invalid"
        )
        return saved


# ---------------------------------------------------------------------------
# VPAuto Scraper
# ---------------------------------------------------------------------------

class VPAutoScraper(BaseAuctionScraper):
    """Scraper for VPAuto.pt — renting, fleet, and judicial vehicle auctions."""

    SOURCE = Source.VPAUTO
    BASE_URL = "https://www.vpauto.pt"
    AUCTION_TYPE = "renting"

    LISTING_PATHS = [
        "/leilao-automovel/",
        "/leilao-automovel/page/2/",
        "/leilao-automovel/page/3/",
    ]

    async def scrape(self, max_listings: int = 50) -> List[AuctionListing]:
        logger.info(f"[VPAUTO] Starting scrape (limit={max_listings})")
        listings: List[AuctionListing] = []

        for path in self.LISTING_PATHS:
            if len(listings) >= max_listings:
                break
            url = f"{self.BASE_URL}{path}"
            html = await self.fetch_html(url, wait_for="article, .product, [class*='item']", use_pw=True)
            if not html:
                continue
            page_listings = self._parse_listing_page(html, max_listings - len(listings))
            listings.extend(page_listings)
            logger.info(f"[VPAUTO] Extracted {len(page_listings)} from {url}")
            await asyncio.sleep(random.uniform(1.5, 3.0))

        # Try to fetch detail pages for richer data
        enriched = await self._enrich_from_detail_pages(listings[:max_listings])
        logger.info(f"[VPAUTO] Total listings: {len(enriched)}")
        return enriched

    def _parse_listing_page(self, html: str, max_items: int) -> List[AuctionListing]:
        soup = BeautifulSoup(html, "lxml")
        listings: List[AuctionListing] = []

        # VPAuto uses various card layouts — try multiple selectors
        selectors = [
            "article.product",
            "div.product",
            "[class*='auction-item']",
            "[class*='vehicle-card']",
            "[class*='listing-item']",
            ".item",
        ]
        cards: List[Any] = []
        for sel in selectors:
            cards = soup.select(sel)
            if len(cards) >= 2:
                break
        if not cards:
            # Fallback: any div/article with image + price-like text
            cards = [
                tag for tag in soup.find_all(["article", "div"])
                if tag.find(["img"]) and tag.get_text().count("€") > 0
            ][:max_items * 2]

        for card in cards[:max_items]:
            try:
                listing = self._parse_card(card)
                if listing and listing.adjudication_price > 0:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[VPAUTO] Card parse error: {e}")
                self.stats["errors"] += 1

        return listings

    def _parse_card(self, card: Any) -> Optional[AuctionListing]:
        title_elem = (
            card.select_one("h2, h3, h4, [class*='title'], [class*='titulo'], [class*='name']")
            or card.find(["h2", "h3", "h4"])
        )
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        if len(title) < 5:
            return None

        price_elem = card.select_one(
            "[class*='price'], [class*='preco'], [class*='valor'], .amount, .price, span"
        )
        price_text = price_elem.get_text(strip=True) if price_elem else ""
        price = parse_price(price_text)
        if not price:
            return None

        link = card.select_one("a")
        url = ""
        if link:
            href = link.get("href", "")
            if href.startswith("/"):
                url = urljoin(self.BASE_URL, href)
            elif href.startswith("http"):
                url = href
            else:
                url = f"{self.BASE_URL}/{href}"

        brand, model = self.extract_brand_model(title)
        year = self.parse_year_from_text(title) or 2020
        km = parse_km(
            card.get_text(separator=" ", strip=True)
        )

        location_elem = card.select_one(
            "[class*='location'], [class*='local'], [class*='region']"
        )
        location = location_elem.get_text(strip=True) if location_elem else None
        district = self.extract_district(location or "")

        fuel = self.extract_fuel_type(title)
        transmission = self.extract_transmission(title)
        color = self.extract_color(title)

        has_damage, damage_notes = self.has_damage_indicators(title)
        lot = self.extract_lot_number(title)

        images = self.extract_images(card)

        source_id = self.make_source_id(self.SOURCE, f"{title}_{url}")

        return AuctionListing(
            source=self.SOURCE,
            source_id=source_id,
            url=url or f"{self.BASE_URL}/leilao-automovel/",
            vehicle_type=VehicleType.carros,
            brand=brand,
            model=model,
            year=year,
            km=km,
            fuel_type=fuel,
            transmission=transmission,
            color=color,
            location=location,
            district=district,
            auction_type=self.AUCTION_TYPE,
            lot_number=lot,
            adjudication_price=price,
            title=title,
            images=images,
            has_damage=has_damage,
            damage_notes=damage_notes,
            seller_type="renting_company",
            seller_name="VPAuto",
        )

    async def _enrich_from_detail_pages(self, listings: List[AuctionListing]) -> List[AuctionListing]:
        """Fetch detail pages to extract richer data (km, condition, etc.)."""
        enriched: List[AuctionListing] = []
        for listing in listings:
            if not listing.url or not listing.url.startswith("http"):
                enriched.append(listing)
                continue
            try:
                html = await self.fetch_html(listing.url, wait_for="body", use_pw=False)
                if html:
                    soup = BeautifulSoup(html, "lxml")
                    text = soup.get_text(separator=" ", strip=True)

                    # Extract KM if missing
                    if listing.km is None:
                        listing.km = parse_km(text)

                    # Extract year if default
                    if listing.year == 2020:
                        yr = self.parse_year_from_text(text)
                        if yr:
                            listing.year = yr

                    # Extract fuel if missing
                    if listing.fuel_type is None:
                        listing.fuel_type = self.extract_fuel_type(text)

                    # Extract transmission if missing
                    if listing.transmission is None:
                        listing.transmission = self.extract_transmission(text)

                    # Extract color if missing
                    if listing.color is None:
                        listing.color = self.extract_color(text)

                    # Extract condition grade
                    if listing.condition_grade is None:
                        listing.condition_grade = self.parse_condition_grade(text)

                    # Check for damage
                    has_dmg, dmg_notes = self.has_damage_indicators(text)
                    if has_dmg:
                        listing.has_damage = True
                        listing.damage_notes = dmg_notes

                    # Extract description
                    desc_elem = soup.select_one(
                        "[class*='description'], [class*='descricao'], .product-description, #tab-description"
                    )
                    if desc_elem:
                        listing.description = desc_elem.get_text(strip=True)[:2000]

                    # Extract more images
                    detail_images = self.extract_images(soup)
                    if detail_images:
                        listing.images = list(dict.fromkeys(listing.images + detail_images))[:10]

                    # Try to find reserve/starting price
                    for price_match in re.finditer(
                        r"(preço mínimo|preço de reserva|valor mínimo|starting price|reserve).*?([\d\s\.\,]+",
                        text.lower(),
                    ):
                        reserve = parse_price(price_match.group(2))
                        if reserve:
                            listing.reserve_price = reserve
                            break

                enriched.append(listing)
                await asyncio.sleep(random.uniform(1.0, 2.0))
            except Exception as e:
                logger.warning(f"[VPAUTO] Detail enrichment error for {listing.url}: {e}")
                enriched.append(listing)
        return enriched


# ---------------------------------------------------------------------------
# Leilosoc Scraper
# ---------------------------------------------------------------------------

class LeilosocScraper(BaseAuctionScraper):
    """Scraper for Leilosoc.pt — judicial and notarial vehicle auctions."""

    SOURCE = Source.LEILOSOC
    BASE_URL = "https://www.leilosoc.com"
    AUCTION_TYPE = "judicial"

    LISTING_PATHS = [
        "/pt/auctions/?category=vehicles",
        "/pt/auctions/?category=vehicles&page=2",
        "/pt/auctions/?category=vehicles&page=3",
    ]

    async def scrape(self, max_listings: int = 50) -> List[AuctionListing]:
        logger.info(f"[LEILOSOC] Starting scrape (limit={max_listings})")
        listings: List[AuctionListing] = []

        for path in self.LISTING_PATHS:
            if len(listings) >= max_listings:
                break
            url = f"{self.BASE_URL}{path}"
            html = await self.fetch_html(url, wait_for="[class*='auction'], [class*='lot'], article", use_pw=True)
            if not html:
                continue
            page_listings = self._parse_listing_page(html, max_listings - len(listings))
            listings.extend(page_listings)
            logger.info(f"[LEILOSOC] Extracted {len(page_listings)} from {url}")
            await asyncio.sleep(random.uniform(1.5, 3.0))

        enriched = await self._enrich_from_detail_pages(listings[:max_listings])
        logger.info(f"[LEILOSOC] Total listings: {len(enriched)}")
        return enriched

    def _parse_listing_page(self, html: str, max_items: int) -> List[AuctionListing]:
        soup = BeautifulSoup(html, "lxml")
        listings: List[AuctionListing] = []

        selectors = [
            "[class*='auction-card']",
            "[class*='lot-card']",
            "[class*='item']",
            "article",
            ".auction",
            ".lot",
        ]
        cards: List[Any] = []
        for sel in selectors:
            cards = soup.select(sel)
            if len(cards) >= 2:
                break
        if not cards:
            cards = [
                tag for tag in soup.find_all(["article", "div"])
                if tag.find(["img"]) and ("€" in tag.get_text() or "EUR" in tag.get_text())
            ][:max_items * 2]

        for card in cards[:max_items]:
            try:
                listing = self._parse_card(card)
                if listing and listing.adjudication_price > 0:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[LEILOSOC] Card parse error: {e}")
                self.stats["errors"] += 1

        return listings

    def _parse_card(self, card: Any) -> Optional[AuctionListing]:
        title_elem = (
            card.select_one("h2, h3, h4, [class*='title'], [class*='titulo']")
            or card.find(["h2", "h3", "h4"])
        )
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)
        if len(title) < 5:
            return None

        # Leilosoc often shows current bid / adjudication price
        price_elem = card.select_one(
            "[class*='price'], [class*='preco'], [class*='valor'], [class*='bid'], [class*='current'], span, p"
        )
        price_text = price_elem.get_text(strip=True) if price_elem else ""
        price = parse_price(price_text)
        if not price:
            return None

        link = card.select_one("a")
        url = ""
        if link:
            href = link.get("href", "")
            if href.startswith("/"):
                url = urljoin(self.BASE_URL, href)
            elif href.startswith("http"):
                url = href
            else:
                url = f"{self.BASE_URL}/{href}"

        brand, model = self.extract_brand_model(title)
        year = self.parse_year_from_text(title) or 2020
        km = parse_km(card.get_text(separator=" ", strip=True))

        location_elem = card.select_one(
            "[class*='location'], [class*='local'], [class*='region'], [class*='district']"
        )
        location = location_elem.get_text(strip=True) if location_elem else None
        district = self.extract_district(location or "")

        fuel = self.extract_fuel_type(title)
        transmission = self.extract_transmission(title)
        color = self.extract_color(title)

        has_damage, damage_notes = self.has_damage_indicators(title)
        lot = self.extract_lot_number(title)

        images = self.extract_images(card)

        # Determine auction type from context
        auction_type = self.AUCTION_TYPE
        text_lower = card.get_text(separator=" ", strip=True).lower()
        if "notarial" in text_lower or "notari" in text_lower:
            auction_type = "notarial"
        elif "fiscal" in text_lower or "insolvência" in text_lower:
            auction_type = "judicial"
        elif "empresa" in text_lower or "fleet" in text_lower:
            auction_type = "fleets"

        source_id = self.make_source_id(self.SOURCE, f"{title}_{url}")

        return AuctionListing(
            source=self.SOURCE,
            source_id=source_id,
            url=url or f"{self.BASE_URL}/pt/auctions/",
            vehicle_type=VehicleType.carros,
            brand=brand,
            model=model,
            year=year,
            km=km,
            fuel_type=fuel,
            transmission=transmission,
            color=color,
            location=location,
            district=district,
            auction_type=auction_type,
            lot_number=lot,
            adjudication_price=price,
            title=title,
            images=images,
            has_damage=has_damage,
            damage_notes=damage_notes,
            seller_type="judicial",
            seller_name="Leilosoc",
        )

    async def _enrich_from_detail_pages(self, listings: List[AuctionListing]) -> List[AuctionListing]:
        enriched: List[AuctionListing] = []
        for listing in listings:
            if not listing.url or not listing.url.startswith("http"):
                enriched.append(listing)
                continue
            try:
                html = await self.fetch_html(listing.url, wait_for="body", use_pw=False)
                if html:
                    soup = BeautifulSoup(html, "lxml")
                    text = soup.get_text(separator=" ", strip=True)

                    if listing.km is None:
                        listing.km = parse_km(text)
                    if listing.year == 2020:
                        yr = self.parse_year_from_text(text)
                        if yr:
                            listing.year = yr
                    if listing.fuel_type is None:
                        listing.fuel_type = self.extract_fuel_type(text)
                    if listing.transmission is None:
                        listing.transmission = self.extract_transmission(text)
                    if listing.color is None:
                        listing.color = self.extract_color(text)
                    if listing.condition_grade is None:
                        listing.condition_grade = self.parse_condition_grade(text)

                    has_dmg, dmg_notes = self.has_damage_indicators(text)
                    if has_dmg:
                        listing.has_damage = True
                        listing.damage_notes = dmg_notes

                    desc_elem = soup.select_one(
                        "[class*='description'], [class*='descricao'], [class*='details'], [class*='detalhes']"
                    )
                    if desc_elem:
                        listing.description = desc_elem.get_text(strip=True)[:2000]

                    detail_images = self.extract_images(soup)
                    if detail_images:
                        listing.images = list(dict.fromkeys(listing.images + detail_images))[:10]

                    # Try to find auction date
                    date_match = re.search(
                        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})|(\d{4}-\d{2}-\d{2})",
                        text,
                    )
                    if date_match and not listing.auction_date:
                        try:
                            date_str = date_match.group(0)
                            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
                                try:
                                    listing.auction_date = datetime.strptime(date_str, fmt)
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass

                enriched.append(listing)
                await asyncio.sleep(random.uniform(1.0, 2.0))
            except Exception as e:
                logger.warning(f"[LEILOSOC] Detail enrichment error for {listing.url}: {e}")
                enriched.append(listing)
        return enriched


# ---------------------------------------------------------------------------
# BCA Scraper (Stub — requires authentication)
# ---------------------------------------------------------------------------

class BCAScraper(BaseAuctionScraper):
    """
    Scraper for BCA Marketplace (bca.pt / bcamarketplace.pt).

    NOTE: BCA is a B2B dealer-only auction platform. Access requires:
      - Dealer license / VAT number
      - Registered account with BCA
      - API key or authenticated session

    This stub documents the expected structure. To activate:
      1. Obtain BCA dealer credentials
      2. Implement OAuth2 or session-based login
      3. Use their API or authenticated scraping
    """

    SOURCE = Source.BCA
    BASE_URL = "https://www.bcamarketplace.pt"
    AUCTION_TYPE = "dealer"

    async def scrape(self, max_listings: int = 50) -> List[AuctionListing]:
        logger.warning(
            "[BCA] BCA Marketplace requires dealer authentication. "
            "Returning empty list. Implement auth to enable."
        )
        return []


# ---------------------------------------------------------------------------
# Manheim Scraper (Stub — requires authentication)
# ---------------------------------------------------------------------------

class ManheimScraper(BaseAuctionScraper):
    """
    Scraper for Manheim Portugal.

    NOTE: Manheim is a B2B wholesale auction platform. Access requires:
      - Dealer account with Manheim Europe
      - API credentials or authenticated portal access

    This stub documents the expected structure. To activate:
      1. Obtain Manheim dealer account
      2. Implement their API client or portal scraping
    """

    SOURCE = Source.MANHEIM
    BASE_URL = "https://www.manheim.pt"
    AUCTION_TYPE = "dealer"

    async def scrape(self, max_listings: int = 50) -> List[AuctionListing]:
        logger.warning(
            "[MANHEIM] Manheim requires dealer authentication. "
            "Returning empty list. Implement auth to enable."
        )
        return []


# ---------------------------------------------------------------------------
# Autorola Scraper (Bonus — public fleet auctions)
# ---------------------------------------------------------------------------

class AutorolaScraper(BaseAuctionScraper):
    """
    Scraper for Autorola.pt / Autorola.eu — online fleet and lease auctions.

    NOTE: Autorola requires registration to view adjudication prices.
    Public listings show vehicle details but not final hammer prices.
    """

    SOURCE = Source.AUTOROLA
    BASE_URL = "https://www.autorola.pt"
    AUCTION_TYPE = "fleets"

    async def scrape(self, max_listings: int = 50) -> List[AuctionListing]:
        logger.warning(
            "[AUTOROLA] Autorola requires registration to view adjudication prices. "
            "Returning empty list. Implement auth to enable."
        )
        return []


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class GroundTruthOrchestrator:
    """Coordinates scraping from all auction sources and persists results."""

    def __init__(self):
        self.rate_limiter = RateLimiter(
            base_delay=settings.request_delay_seconds,
            jitter=settings.request_delay_jitter,
            max_rpm=settings.max_requests_per_minute,
        )
        self.playwright = PlaywrightHelper(
            headless=settings.playwright_headless,
            timeout=settings.playwright_timeout,
        )
        self.http = HTTPFallback(timeout=settings.scraper_timeout)
        self.scrapers: List[BaseAuctionScraper] = [
            VPAutoScraper(self.rate_limiter, self.playwright, self.http),
            LeilosocScraper(self.rate_limiter, self.playwright, self.http),
            BCAScraper(self.rate_limiter, self.playwright, self.http),
            ManheimScraper(self.rate_limiter, self.playwright, self.http),
            AutorolaScraper(self.rate_limiter, self.playwright, self.http),
        ]
        self.stats: Dict[str, Any] = {
            "started_at": None,
            "finished_at": None,
            "total_listings": 0,
            "total_saved": 0,
            "by_source": {},
            "errors": [],
        }

    async def run(
        self,
        max_per_source: int = 200,
        min_total: int = 500,
        save_to_db: bool = True,
        save_csv_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run all scrapers, collect listings, validate, save to DB and optionally CSV.

        Args:
            max_per_source: Maximum listings to scrape per source.
            min_total: Target minimum total listings (best effort).
            save_to_db: Whether to persist to SQLite.
            save_csv_path: Optional path to write CSV backup.

        Returns:
            Statistics dictionary.
        """
        self.stats["started_at"] = datetime.now(timezone.utc).isoformat()
        all_listings: List[AuctionListing] = []

        logger.info("=" * 60)
        logger.info("GROUND TRUTH SCRAPER STARTED")
        logger.info(f"Target: min {min_total} transactions | Max per source: {max_per_source}")
        logger.info("=" * 60)

        for scraper in self.scrapers:
            source_name = scraper.SOURCE.value
            try:
                async with scraper:
                    listings = await scraper.scrape(max_listings=max_per_source)
                    valid_listings = []
                    for lst in listings:
                        is_valid, errors = ListingValidator.validate(lst)
                        if is_valid:
                            valid_listings.append(lst)
                        else:
                            logger.debug(f"[VALIDATE] {source_name} invalid: {errors}")

                    all_listings.extend(valid_listings)
                    saved = scraper.save_listings(valid_listings) if save_to_db else 0

                    self.stats["by_source"][source_name] = {
                        "scraped": len(listings),
                        "valid": len(valid_listings),
                        "saved": saved,
                        "errors": scraper.stats["errors"],
                    }
                    logger.info(
                        f"[ORCHESTRATOR] {source_name}: {len(listings)} scraped, "
                        f"{len(valid_listings)} valid, {saved} saved"
                    )
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] {source_name} failed: {e}")
                self.stats["errors"].append(f"{source_name}: {str(e)}")
                self.stats["by_source"][source_name] = {
                    "scraped": 0,
                    "valid": 0,
                    "saved": 0,
                    "errors": 1,
                    "exception": str(e),
                }

            # Rate limit between sources
            await asyncio.sleep(random.uniform(3.0, 6.0))

        self.stats["total_listings"] = len(all_listings)
        self.stats["total_saved"] = sum(
            s.get("saved", 0) for s in self.stats["by_source"].values()
        )
        self.stats["finished_at"] = datetime.now(timezone.utc).isoformat()

        # CSV backup
        if save_csv_path and all_listings:
            self._write_csv_backup(all_listings, save_csv_path)

        self._log_summary()
        return self.stats

    def _write_csv_backup(self, listings: List[AuctionListing], path: str) -> None:
        import csv
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                if not listings:
                    return
                sample = listings[0].to_db_dict()
                fieldnames = list(sample.keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for lst in listings:
                    row = lst.to_db_dict()
                    # Convert enums and datetime to strings for CSV
                    for k, v in row.items():
                        if hasattr(v, "value"):
                            row[k] = v.value
                        elif isinstance(v, datetime):
                            row[k] = v.isoformat()
                        elif isinstance(v, list):
                            row[k] = json.dumps(v, ensure_ascii=False)
                    writer.writerow(row)
            logger.info(f"[CSV] Backup written to {path} ({len(listings)} rows)")
        except Exception as e:
            logger.error(f"[CSV] Failed to write backup: {e}")

    def _log_summary(self) -> None:
        logger.info("=" * 60)
        logger.info("GROUND TRUTH SCRAPER SUMMARY")
        logger.info("=" * 60)
        for source, data in self.stats["by_source"].items():
            logger.info(f"  {source:12s}: scraped={data.get('scraped', 0):4d}  "
                        f"valid={data.get('valid', 0):4d}  saved={data.get('saved', 0):4d}")
        logger.info(f"  TOTAL: {self.stats['total_listings']} listings | "
                    f"{self.stats['total_saved']} saved to DB")
        if self.stats["errors"]:
            logger.warning(f"  ERRORS: {len(self.stats['errors'])}")
        logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

async def scrape_all_ground_truth(
    max_per_source: int = 200,
    min_total: int = 500,
    save_csv_path: Optional[str] = None,
) -> Dict[str, Any]:
    """High-level entry point: scrape all sources and save."""
    orchestrator = GroundTruthOrchestrator()
    return await orchestrator.run(
        max_per_source=max_per_source,
        min_total=min_total,
        save_to_db=True,
        save_csv_path=save_csv_path,
    )
