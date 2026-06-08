"""
PiscaPisca.pt scraper for AutoDeal IA Hunter
PiscaPisca is a vehicle search engine aggregating stands across Portugal.
Uses modern React-based frontend with JSON data embedded in __NEXT_DATA__.
"""
from __future__ import annotations
import json
import logging
import asyncio
import re
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from urllib.parse import urljoin

from config import settings
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from database.db import get_db_context
from validation.scraped_models import ScrapedVehicle
from utils.data_validation import validate_scraped_data
from utils.observability import track_scrape
from utils.proxy_manager import get_proxy_pool

try:
    from scrapers.browser_pool import get_browser_pool
except ImportError:
    get_browser_pool = None

logger = logging.getLogger(__name__)


class PiscaPiscaScraper:
    """Scraper for PiscaPisca.pt - vehicle aggregator with structured data."""
    
    def __init__(self) -> None:
        self.base_url = "https://www.piscapisca.pt"
        self.timeout = getattr(settings, 'playwright_timeout', 30000)
        self.headless = getattr(settings, 'playwright_headless', True)
        self.proxy_pool = get_proxy_pool()
    
    @track_scrape(source='piscapisca')
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 100,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False
    ) -> List[Dict[str, object]]:
        """
        Scrape listings from PiscaPisca.pt
        
        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum listings to scrape
            filters: Optional filters
            scrape_details: Whether to scrape detail pages
        """
        logger.info(f"[PISCAPISCA] Starting scrape for {vehicle_type}, max {max_listings}")
        
        url = self._build_url(vehicle_type, filters)
        html = await self._fetch_html(url)
        
        if not html:
            logger.warning("[PISCAPISCA] No HTML fetched")
            return []
        
        # Try JSON extraction first (fastest)
        listings = self._extract_from_next_data(html, max_listings)
        if listings:
            logger.info(f"[PISCAPISCA] Extracted {len(listings)} from JSON")
        else:
            # Fallback to DOM parsing
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            listings = self._parse_soup(soup, max_listings)
            logger.info(f"[PISCAPISCA] Extracted {len(listings)} from DOM")
        
        if scrape_details and listings:
            listings = await self._enrich_with_details(listings)
        
        return listings
    
    def _build_url(self, vehicle_type: str, filters: Optional[Dict[str, object]] = None) -> str:
        """Build search URL for PiscaPisca."""
        path = "/carros" if vehicle_type == "carros" else "/motos"
        url = f"{self.base_url}{path}"
        
        params = []
        if filters:
            if filters.get("brand"):
                params.append(f"marca={filters['brand']}")
            if filters.get("max_price"):
                params.append(f"preco_max={filters['max_price']}")
            if filters.get("min_year"):
                params.append(f"ano_min={filters['min_year']}")
        
        if params:
            url += "?" + "&".join(params)
        
        return url
    
    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML using browser pool for speed."""
        if not get_browser_pool:
            logger.error("[PISCAPISCA] Browser pool not available")
            return None
        
        try:
            pool = get_browser_pool()
            page = await pool.new_page("piscapisca")
            
            await page.goto(url, timeout=self.timeout, wait_until='networkidle')
            
            # Wait for content
            try:
                await page.wait_for_selector('article, [data-testid], .vehicle-card', timeout=5000)
            except Exception:
                pass
            
            # Scroll for lazy loading
            for _ in range(3):
                await page.mouse.wheel(0, 800)
                await asyncio.sleep(0.2)
            
            html = await page.content()
            await page.close()
            return html
            
        except Exception as e:
            logger.error(f"[PISCAPISCA] Fetch failed: {e}")
            return None
    
    def _extract_from_next_data(self, html: str, max_listings: int) -> List[Dict[str, object]]:
        """Extract listings from __NEXT_DATA__ JSON."""
        try:
            match = re.search(
                r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
                html, re.DOTALL | re.IGNORECASE
            )
            if not match:
                return []
            
            data = json.loads(match.group(1))
            listings = []
            
            # Find vehicle nodes anywhere in the JSON
            vehicles = []
            self._find_vehicles_recursive(data, vehicles)
            
            for v in vehicles:
                listing = self._normalize_vehicle(v)
                if listing:
                    listings.append(listing)
                if len(listings) >= max_listings:
                    break
            
            return listings
            
        except Exception as e:
            logger.debug(f"[PISCAPISCA] JSON extraction failed: {e}")
            return []

    def _find_vehicles_recursive(self, data: Any, found: List[Dict[str, Any]]) -> None:
        if isinstance(data, dict):
            if self._is_vehicle_node(data):
                found.append(data)
            else:
                for v in data.values():
                    self._find_vehicles_recursive(v, found)
        elif isinstance(data, list):
            for item in data:
                self._find_vehicles_recursive(item, found)
    
    
    def _is_vehicle_node(self, node: Dict[str, Any]) -> bool:
        """Check if a dict node represents a vehicle listing."""
        has_price = any(k in node for k in ('price', 'preco', 'priceValue', 'amount'))
        has_title = any(k in node for k in ('title', 'titulo', 'name', 'modelo'))
        has_url = any(k in node for k in ('url', 'link', 'slug', 'href'))
        return has_price and has_title and has_url
    
    def _normalize_vehicle(self, data: Dict[str, Any]) -> Optional[Dict[str, object]]:
        """Normalize a vehicle dict to scraper schema."""
        try:
            url = (data.get('url') or data.get('link') or data.get('href') or '')
            if not url:
                return None
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
            
            title = (data.get('title') or data.get('titulo') or data.get('modelo') or '')
            if not title:
                return None
            
            price_raw = (data.get('price') or data.get('preco') or data.get('priceValue') or data.get('amount'))
            price = self._safe_float(price_raw)
            if not price:
                return None
            
            year = self._safe_int(data.get('year') or data.get('ano') or data.get('firstRegistrationYear'))
            km = self._safe_int(data.get('mileage') or data.get('km') or data.get('quilometragem'))
            
            location = data.get('location') or data.get('localizacao') or data.get('city') or ''
            if isinstance(location, dict):
                location = location.get('city') or location.get('name') or ''
            
            images = []
            imgs = data.get('images') or data.get('photos') or data.get('imageUrls') or []
            if isinstance(imgs, list):
                for img in imgs:
                    if isinstance(img, str) and img.startswith('http'):
                        images.append(img)
                    elif isinstance(img, dict):
                        url_img = img.get('url') or img.get('src') or img.get('large')
                        if isinstance(url_img, str) and url_img.startswith('http'):
                            images.append(url_img)
            
            brand, model = self._parse_brand_model(title)
            
            return {
                "source": "piscapisca",
                "source_id": str(data.get('id') or data.get('_id') or url),
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "location": str(location),
                "images": images,
                "fuel_type": (data.get('fuel') or data.get('combustivel') or ''),
                "transmission": (data.get('transmission') or data.get('caixa') or ''),
                "description": (data.get('description') or data.get('descricao') or ''),
                "raw_data": str(data),
            }
            
        except Exception as e:
            logger.debug(f"[PISCAPISCA] Normalization failed: {e}")
            return None
    
    def _parse_soup(self, soup: Any, max_listings: int) -> List[Dict[str, object]]:
        """Parse listings from BeautifulSoup."""
        listings = []
        
        # Try common selectors
        selectors = [
            'article.vehicle-card',
            'article[data-testid]',
            '.vehicle-card',
            '.listing-card',
            '[data-testid="vehicle-card"]',
        ]
        
        elements = []
        for sel in selectors:
            elements = soup.select(sel)
            if elements:
                break
        
        for elem in elements[:max_listings]:
            listing = self._parse_element(elem)
            if listing:
                listings.append(listing)
        
        return listings
    
    def _parse_element(self, elem: Any) -> Optional[Dict[str, object]]:
        """Parse a single listing element."""
        try:
            # URL
            link = elem.find('a', href=True)
            url = link['href'] if link else ''
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
            
            # Title
            title_elem = elem.find(['h2', 'h3', '.title', '[data-testid="title"]'])
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # Price
            price_elem = elem.find(class_=re.compile(r'price|preco'))
            price = self._safe_float(price_elem.get_text(strip=True)) if price_elem else None
            
            if not title or not price:
                return None
            
            brand, model = self._parse_brand_model(title)
            
            return {
                "source": "piscapisca",
                "source_id": url,
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "raw_data": str(elem),
            }
            
        except Exception as e:
            logger.debug(f"[PISCAPISCA] Element parse failed: {e}")
            return None
    
    async def _enrich_with_details(self, listings: List[Dict[str, object]], max_concurrent: int = 5) -> List[Dict[str, object]]:
        """Enrich listings with detail page data - concurrent."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_one(listing: Dict[str, object]) -> Dict[str, object]:
            url = listing.get("url")
            if not isinstance(url, str) or not url.startswith("http"):
                return listing
            
            async with semaphore:
                try:
                    html = await self._fetch_html(url)
                    if html:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, 'lxml')
                        details = self._extract_details(soup)
                        if details:
                            listing.update(details)
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.debug(f"[PISCAPISCA] Detail enrichment failed: {e}")
            
            return listing
        
        tasks = [enrich_one(lst.copy()) for lst in listings]
        return await asyncio.gather(*tasks)
    
    def _extract_details(self, soup: Any) -> Dict[str, object]:
        """Extract details from a listing page."""
        details: Dict[str, object] = {}
        
        # Description
        desc = soup.find(['.description', '[data-testid="description"]', '.vehicle-description'])
        if desc:
            details["description"] = desc.get_text(strip=True)
        
        # Specs
        specs = soup.find_all(['.spec', '.specification', '[data-testid="spec"]'])
        for spec in specs:
            text = spec.get_text(strip=True).lower()
            if 'ano' in text:
                details["year"] = self._safe_int(text)
            elif 'km' in text or 'quil' in text:
                details["km"] = self._safe_int(text)
            elif 'combust' in text:
                details["fuel_type"] = text
            elif 'caixa' in text:
                details["transmission"] = text
        
        return details
    
    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            digits = re.sub(r"\D", "", str(value))
            return int(digits) if digits else None
        except Exception:
            return None
    
    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            normalized = re.sub(r"[^\d.,]", "", str(value))
            normalized = normalized.replace(".", "").replace(",", ".")
            return float(normalized) if normalized else None
        except Exception:
            return None
    
    def _parse_brand_model(self, title: str) -> tuple[str, str]:
        """Parse brand and model from title."""
        brands = [
            "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz",
            "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
            "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
            "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo",
            "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini",
            "Ducati", "Yamaha", "Kawasaki", "Triumph", "KTM",
        ]
        
        title_lower = title.lower()
        for brand in brands:
            if brand.lower() in title_lower:
                idx = title_lower.index(brand.lower())
                model = title[idx + len(brand):].strip()
                return brand, model
        
        parts = title.split()
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        return title, ""
    
    def save_to_database(self, listings: List[Dict[str, object]], vehicle_type: str = "carros") -> None:
        """Save scraped listings to database."""
        logger.info(f"[PISCAPISCA] Saving {len(listings)} listings")
        saved = 0
        updated = 0
        
        with get_db_context() as db:
            for listing in listings:
                try:
                    url = listing.get("url")
                    if not url:
                        continue
                    
                    existing = db.query(Vehicle).filter(Vehicle.url == url).first()
                    
                    v_type = VehicleType.carros if vehicle_type == "carros" else VehicleType.motos
                    
                    if existing:
                        existing.price = listing.get("price")
                        existing.last_seen = datetime.now(timezone.utc)
                        updated += 1
                    else:
                        vehicle = Vehicle(
                            source=Source.PISCAPISCA,
                            source_id=listing.get("source_id", ""),
                            url=url,
                            vehicle_type=v_type,
                            brand=listing.get("brand", "Unknown"),
                            model=listing.get("model", ""),
                            title=listing.get("title", ""),
                            price=listing.get("price"),
                            location=listing.get("location"),
                            images=listing.get("images", []),
                            year=listing.get("year"),
                            km=listing.get("km"),
                            description=listing.get("description", ""),
                            is_active=True,
                        )
                        db.add(vehicle)
                        saved += 1
                except Exception as e:
                    logger.warning(f"[PISCAPISCA] Save error: {e}")
            
            db.commit()
            logger.info(f"[PISCAPISCA] Saved: {saved} new, {updated} updated")


if __name__ == "__main__":
    import asyncio
    scraper = PiscaPiscaScraper()
    results = asyncio.run(scraper.scrape_listings("carros", max_listings=10))
    print(f"Scraped {len(results)} listings")
    for r in results[:3]:
        print(f"  {r.get('title')} - €{r.get('price')}")
