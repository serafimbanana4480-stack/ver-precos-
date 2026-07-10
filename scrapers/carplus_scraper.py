"""
Carplus.pt scraper for AutoDeal IA Hunter
Carplus is a stand-online platform with verified vehicle listings.
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


class CarplusScraper:
    """Scraper for Carplus.pt - online stand with structured listings."""
    
    def __init__(self) -> None:
        self.base_url = "https://www.carplus.pt"
        self.timeout = getattr(settings, 'playwright_timeout', 60000)
        self.headless = getattr(settings, 'playwright_headless', True)
        self.proxy_pool = get_proxy_pool()
    
    @track_scrape(source='carplus')
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 100,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False
    ) -> List[Dict[str, object]]:
        """
        Scrape listings from Carplus.pt
        
        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum listings
            filters: Optional filters
            scrape_details: Whether to scrape details
        """
        logger.info(f"[CARPLUS] Starting scrape, max {max_listings}")
        
        url = self._build_url(filters)
        html = await self._fetch_html(url)
        
        if not html:
            return []
        
        # Try JSON first
        listings = self._extract_from_json(html, max_listings)
        if listings:
            logger.info(f"[CARPLUS] Extracted {len(listings)} from JSON")
        else:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            listings = self._parse_soup(soup, max_listings)
            logger.info(f"[CARPLUS] Extracted {len(listings)} from DOM")
        
        if scrape_details and listings:
            listings = await self._enrich_with_details(listings)
        
        return listings
    
    def _build_url(self, filters: Optional[Dict[str, object]] = None) -> str:
        """Build search URL."""
        url = f"{self.base_url}/carros-usados"
        
        params = []
        if filters:
            if filters.get("brand"):
                params.append(f"marca={filters['brand']}")
            if filters.get("max_price"):
                params.append(f"preco_ate={filters['max_price']}")
        
        if params:
            url += "?" + "&".join(params)
        
        async def _fetch_html(self, url: str, retry_count: int = 0) -> Optional[str]:
            """Fetch HTML using browser pool with retry logic."""
            if not get_browser_pool:
                logger.error("[CARPLUS] Browser pool not available")
                return None
        
            try:
                pool = get_browser_pool()
                page = await pool.new_page("carplus")
            
                # Use 60s timeout as requested
                timeout_ms = 60000
            
                try:
                    await page.goto(url, timeout=timeout_ms, wait_until='networkidle')
                except Exception as e:
                    logger.warning(f"[CARPLUS] Navigation timeout on attempt {retry_count + 1}: {e}")
                    if retry_count < 2:
                        await page.close()
                        backoff_time = (2 ** retry_count) * 2 + random.uniform(1, 2)
                        logger.info(f"[CARPLUS] Retrying after {backoff_time:.1f}s...")
                        await asyncio.sleep(backoff_time)
                        return await self._fetch_html(url, retry_count + 1)
                    await page.close()
                    return None
            
                # Wait for content with retry
                try:
                    await page.wait_for_selector('article, .vehicle-card, .car-card', timeout=10000)
                except Exception:
                    logger.debug("[CARPLUS] Timeout waiting for selector, continuing anyway")
            
                # Scroll for lazy loading
                for _ in range(3):
                    await page.mouse.wheel(0, 800)
                    await asyncio.sleep(0.2)
            
                html = await page.content()
                await page.close()
            
                if html and len(html) > 1000:
                    return html
                else:
                    logger.warning(f"[CARPLUS] HTML too short ({len(html) if html else 0} chars)")
                    if retry_count < 2:
                        backoff_time = (2 ** retry_count) * 2 + random.uniform(1, 2)
                        logger.info(f"[CARPLUS] Retrying after {backoff_time:.1f}s...")
                        await asyncio.sleep(backoff_time)
                        return await self._fetch_html(url, retry_count + 1)
                    return None
            
            except Exception as e:
                logger.error(f"[CARPLUS] Fetch failed: {e}")
                if retry_count < 2:
                    backoff_time = (2 ** retry_count) * 2 + random.uniform(1, 2)
                    logger.info(f"[CARPLUS] Retrying after error in {backoff_time:.1f}s...")
                    await asyncio.sleep(backoff_time)
                    return await self._fetch_html(url, retry_count + 1)
                return None
    
    def _extract_from_json(self, html: str, max_listings: int) -> List[Dict[str, object]]:
        """Extract from embedded JSON or window.__DATA__."""
        try:
            # Try __NEXT_DATA__
            match = re.search(
                r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
                html, re.DOTALL | re.IGNORECASE
            )
            if match:
                data = json.loads(match.group(1))
                vehicles = self._find_vehicles_in_json(data)
                return [self._normalize_vehicle(v) for v in vehicles[:max_listings] if self._normalize_vehicle(v)]
            
            # Try window.__INITIAL_STATE__ or similar
            match = re.search(
                r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
                html, re.DOTALL
            )
            if match:
                data = json.loads(match.group(1))
                vehicles = self._find_vehicles_in_json(data)
                return [self._normalize_vehicle(v) for v in vehicles[:max_listings] if self._normalize_vehicle(v)]
            
            return []
            
        except Exception as e:
            logger.debug(f"[CARPLUS] JSON extraction failed: {e}")
            return []
    
    def _find_vehicles_in_json(self, node: Any) -> List[Dict[str, Any]]:
        """Recursively find vehicle objects."""
        vehicles = []
        
        if isinstance(node, dict):
            if self._is_vehicle_node(node):
                vehicles.append(node)
            else:
                for v in node.values():
                    vehicles.extend(self._find_vehicles_in_json(v))
        elif isinstance(node, list):
            for item in node:
                vehicles.extend(self._find_vehicles_in_json(item))
        
        return vehicles
    
    def _is_vehicle_node(self, node: Dict[str, Any]) -> bool:
        """Check if node is a vehicle."""
        has_price = any(k in node for k in ('price', 'preco', 'priceValue'))
        has_title = any(k in node for k in ('title', 'modelo', 'name'))
        return has_price and has_title
    
    def _normalize_vehicle(self, data: Dict[str, Any]) -> Optional[Dict[str, object]]:
        """Normalize to scraper schema."""
        try:
            url = data.get('url') or data.get('link') or ''
            if not url:
                return None
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
            
            title = data.get('title') or data.get('modelo') or data.get('name') or ''
            if not title:
                return None
            
            price = self._safe_float(data.get('price') or data.get('preco'))
            if not price:
                return None
            
            year = self._safe_int(data.get('year') or data.get('ano'))
            km = self._safe_int(data.get('mileage') or data.get('km') or data.get('quilometragem'))
            
            location = str(data.get('location') or data.get('localizacao') or '')
            
            images = []
            imgs = data.get('images') or data.get('photos') or []
            if isinstance(imgs, list):
                for img in imgs:
                    if isinstance(img, str) and img.startswith('http'):
                        images.append(img)
                    elif isinstance(img, dict):
                        url_img = img.get('url') or img.get('src')
                        if isinstance(url_img, str) and url_img.startswith('http'):
                            images.append(url_img)
            
            brand, model = self._parse_brand_model(title)
            
            return {
                "source": "CARPLUS",
                "source_id": str(data.get('id') or url),
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "location": location,
                "images": images,
                "fuel_type": str(data.get('fuel') or data.get('combustivel') or ''),
                "transmission": str(data.get('transmission') or data.get('caixa') or ''),
                "description": str(data.get('description') or data.get('descricao') or ''),
                "raw_data": str(data),
            }
            
        except Exception as e:
            logger.debug(f"[CARPLUS] Normalization failed: {e}")
            return None
    
    def _parse_soup(self, soup: Any, max_listings: int) -> List[Dict[str, object]]:
        """Parse from DOM."""
        listings = []
        
        selectors = [
            'article.vehicle-card',
            '.car-card',
            '.listing-item',
            'article[data-testid]',
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
        """Parse single element."""
        try:
            link = elem.find('a', href=True)
            url = link['href'] if link else ''
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
            
            title_elem = elem.find(['h2', 'h3', '.title'])
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            price_elem = elem.find(class_=re.compile(r'price|preco'))
            price = self._safe_float(price_elem.get_text(strip=True)) if price_elem else None
            
            if not title or not price:
                return None
            
            brand, model = self._parse_brand_model(title)
            
            return {
                "source": "CARPLUS",
                "source_id": url,
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "raw_data": str(elem),
            }
            
        except Exception as e:
            logger.debug(f"[CARPLUS] Element parse failed: {e}")
            return None
    
    async def _enrich_with_details(self, listings: List[Dict[str, object]], max_concurrent: int = 5) -> List[Dict[str, object]]:
        """Enrich with details concurrently."""
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
                    logger.debug(f"[CARPLUS] Detail error: {e}")
            
            return listing
        
        tasks = [enrich_one(lst.copy()) for lst in listings]
        return await asyncio.gather(*tasks)
    
    def _extract_details(self, soup: Any) -> Dict[str, object]:
        """Extract details from page."""
        details: Dict[str, object] = {}
        
        desc = soup.select_one('.description, .vehicle-description')
        if desc:
            details["description"] = desc.get_text(strip=True)
        
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
        brands = [
            "Alfa Romeo", "Mercedes-Benz", "Land Rover",
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
        """Save to database."""
        logger.info(f"[CARPLUS] Saving {len(listings)} listings")
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
                            source=Source.CARPLUS,
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
                    logger.warning(f"[CARPLUS] Save error: {e}")
            
            db.commit()
            logger.info(f"[CARPLUS] Saved: {saved} new, {updated} updated")


if __name__ == "__main__":
    import asyncio
    scraper = CarplusScraper()
    results = asyncio.run(scraper.scrape_listings("carros", max_listings=10))
    print(f"Scraped {len(results)} listings")
    for r in results[:3]:
        print(f"  {r.get('title')} - €{r.get('price')}")
