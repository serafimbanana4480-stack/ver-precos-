"""
Standvirtual.com scraper using Playwright with stealth
"""
from __future__ import annotations
import logging
import random
import time
import asyncio
import re
import json
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from urllib.parse import urljoin, quote

from config import settings
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from database.db import get_db_context
from utils.retry import retry_network
from utils.deduplication import is_url_processed, mark_url_processed
from validation.scraped_models import ScrapedVehicle
from utils.data_validation import DataValidator, validate_scraped_data
from utils.production_safeguards import with_circuit_breaker, _standvirtual_circuit_breaker
from utils.captcha_solver import CaptchaDetector, get_captcha_solver
from utils.proxy_manager import get_proxy_pool
from utils.selector_manager import get_selector_manager
from utils.observability import track_scrape

# Optional imports
try:
    from scrapers.managed_client import get_managed_client
except ImportError:
    get_managed_client = None

try:
    from scrapers.ai_scraper import get_ai_scraper
except ImportError:
    get_ai_scraper = None

try:
    from scrapers.ai_extractor import get_ai_extractor
except ImportError:
    get_ai_extractor = None

logger = logging.getLogger(__name__)


class StandvirtualScraper:
    """Scraper for Standvirtual.com using Playwright"""
    
    def __init__(self) -> None:
        self.base_url = settings.standvirtual_base_url
        self.headless = settings.playwright_headless
        self.timeout = settings.playwright_timeout
        self.managed_client = get_managed_client() if get_managed_client else None
        self.selector_manager = get_selector_manager()
        self.proxy_pool = get_proxy_pool()
        
    async def scrape_with_managed_service(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, object]] = None
    ) -> List[Dict[str, object]]:
        """
        Scrape using managed service (Apify) as fallback
        
        Args:
            vehicle_type: Vehicle type to scrape
            max_listings: Maximum listings to scrape
            filters: Additional filters
            
        Returns:
            List of scraped listings
        """
        logger.info(f"[MANAGED] Attempting to scrape Standvirtual via Apify")
        
        try:
            result = await self.managed_client.scrape_standvirtual_with_apify(
                vehicle_type=vehicle_type,
                max_listings=max_listings,
                filters=filters
            )
            
            if result:
                logger.info(f"[MANAGED] Successfully scraped {len(result)} listings via Apify")
                return result
            else:
                logger.warning("[MANAGED] Apify returned no results")
                return []
        except Exception as e:
            logger.error(f"[MANAGED] Apify scrape failed: {e}")
            return []
    
    @track_scrape(source='standvirtual')
    @with_circuit_breaker(_standvirtual_circuit_breaker, "Standvirtual scraping")
    @retry_network(max_attempts=3, min_wait=2, max_wait=10)  # type: ignore[misc]
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 100,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False
    ) -> List[Dict[str, object]]:
        """
        Scrape listings from Standvirtual.com using AI-first or Playwright-first approach based on priority
        
        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum number of listings to scrape
            filters: Optional filters (brand, model, min_price, max_price, etc.)
        
        Returns:
            List of vehicle dictionaries
        """
        logger.info(f"[PROGRESS] Starting Standvirtual scrape for {vehicle_type}, max {max_listings} listings")
        logger.info(f"[PROGRESS] AI scraping priority: {settings.ai_scraper_priority}")
        
        url = self._build_url(vehicle_type, page=1, filters=filters)
        
        # AI-First Approach (if configured as primary)
        if settings.ai_scraping_enabled and settings.ai_scraper_priority == "primary" and get_ai_scraper:
            logger.info("[AI_PRIMARY] Using AI scraper as primary method")
            try:
                ai_scraper = get_ai_scraper()
                listings = await ai_scraper.scrape_listings("standvirtual", url, max_listings)
                if listings:
                    logger.info(f"[AI_PRIMARY] AI scraper successfully retrieved {len(listings)} listings")
                    return listings
                else:
                    logger.warning("[AI_PRIMARY] AI scraper returned no results, falling back to Playwright")
            except Exception as e:
                logger.error(f"[AI_PRIMARY] AI scraper failed: {e}, falling back to Playwright")
        
        # Playwright-First Approach (fallback or if AI disabled)
        logger.info(f"[PROGRESS] Phase 1/5: Building URL with filters")
        listings = await self._scrape_with_resilient_flow(vehicle_type, max_listings, filters, scrape_details)
        
        # If still no results, try original Apify fallback if enabled
        if not listings and settings.apify_enabled:
             listings = await self.scrape_with_managed_service(vehicle_type, max_listings, filters)
        
        return listings


    async def _scrape_with_resilient_flow(
        self,
        vehicle_type: str,
        max_listings: int,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False
    ) -> List[Dict[str, object]]:
        all_listings = []
        page = 1
        
        while len(all_listings) < max_listings:
            url = self._build_url(vehicle_type, page, filters)
            logger.info(f"[STANDVIRTUAL] Scraping page {page}: {url}")
            
            # Use simple Playwright first (fast and reliable)
            page_listings = await self._scrape_page_with_playwright(url, vehicle_type, max_listings - len(all_listings))
            
            if not page_listings and self.managed_client:
                # Fallback to managed_client
                html = await self.managed_client.get_html(url, source="standvirtual")
                if html:
                    page_listings = self._extract_listings_from_next_data(html, max_listings - len(all_listings))
                    if not page_listings and get_ai_extractor:
                        ai_extractor = get_ai_extractor()
                        page_listings = await ai_extractor.extract_from_html(html, "standvirtual", max_listings - len(all_listings))
            
            if not page_listings:
                logger.info(f"[STANDVIRTUAL] No more listings found at page {page}")
                break
                
            all_listings.extend(page_listings)
            logger.info(f"[STANDVIRTUAL] Total listings so far: {len(all_listings)}")
            
            if len(page_listings) < 10: # Likely last page
                break
                
            page += 1
            if page > 10: # Safety break
                break

        if scrape_details and all_listings:
            # (Enrichment logic here if needed, but simple_playwright already tries to get some details)
            pass

        return all_listings[:max_listings]

    async def _scrape_page_with_playwright(self, url: str, vehicle_type: str, limit: int) -> List[Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
            from utils.playwright_stealth import apply_stealth_async
            from scrapers.browser_pool import get_browser_pool
            
            pool = get_browser_pool()
            page = await pool.new_page("standvirtual")
            
            try:
                await apply_stealth_async(page)
            except Exception:
                pass
            
            await page.goto(url, timeout=self.timeout, wait_until='networkidle')
            try:
                await page.wait_for_selector('article, [data-testid]', timeout=5000)
            except Exception:
                pass
            
            for _ in range(2):
                await page.mouse.wheel(0, 1000)
                await asyncio.sleep(0.2)
            
            html = await page.content()
            await page.close()
            
            if not html or len(html) < 500:
                return []
            
            # Check for blocking
            from utils.error_classifier import ErrorClassifier
            if ErrorClassifier.detect_blocking_in_html(html):
                return []
            
            listings = self._extract_listings_from_next_data(html, limit)
            if not listings:
                soup = BeautifulSoup(html, 'lxml')
                listings = self._parse_soup_to_listings(soup, limit)
                
            return listings
        except Exception as e:
            logger.error(f"[STANDVIRTUAL_PAGE] Failed: {e}")
            return []

    def _extract_listings_from_next_data(self, html: str, max_listings: int) -> List[Dict[str, object]]:
        """Extract listings from Standvirtual Next.js payload (__NEXT_DATA__)."""
        try:
            script_match = re.search(
                r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
                html,
                re.DOTALL | re.IGNORECASE,
            )
            if not script_match:
                return []

            payload = json.loads(script_match.group(1))
            candidates: List[Dict[str, Any]] = []
            self._collect_vehicle_candidates(payload, candidates)

            listings: List[Dict[str, object]] = []
            for candidate in candidates:
                listing = self._candidate_to_listing(candidate)
                if listing:
                    listings.append(listing)
                if len(listings) >= max_listings:
                    break

            return listings
        except Exception as e:
            logger.debug(f"[NEXT_DATA] Failed parsing __NEXT_DATA__: {e}")
            return []

    def _collect_vehicle_candidates(self, node: Any, out: List[Dict[str, Any]]) -> None:
        """Recursively collect listing-like nodes from nested Next.js JSON."""
        if isinstance(node, dict):
            has_url = any(k in node for k in ("url", "slug", "seoSlug", "href"))
            has_title = any(k in node for k in ("title", "name"))
            has_price = any(k in node for k in ("price", "priceValue", "priceAmount", "amount"))
            if has_url and has_title and has_price:
                out.append(node)

            for value in node.values():
                self._collect_vehicle_candidates(value, out)
        elif isinstance(node, list):
            for item in node:
                self._collect_vehicle_candidates(item, out)

    def _candidate_to_listing(self, candidate: Dict[str, Any]) -> Optional[Dict[str, object]]:
        """Normalize a listing candidate from Next.js payload into scraper schema."""
        raw_url = candidate.get("url") or candidate.get("href") or candidate.get("slug") or candidate.get("seoSlug")
        if not isinstance(raw_url, str) or not raw_url.strip():
            return None

        url = raw_url.strip()
        if url.startswith("/"):
            url = urljoin(self.base_url, url)
        if not url.startswith("http"):
            return None

        title = candidate.get("title") or candidate.get("name") or ""
        if not isinstance(title, str) or not title.strip():
            return None

        price_value = candidate.get("price")
        if isinstance(price_value, dict):
            price_value = (
                price_value.get("amount")
                or price_value.get("value")
                or price_value.get("gross")
                or price_value.get("net")
            )

        if price_value is None:
            price_value = candidate.get("priceValue") or candidate.get("priceAmount") or candidate.get("amount")

        price = self._safe_float(price_value)
        if price is None:
            return None

        location_raw = candidate.get("location")
        if isinstance(location_raw, dict):
            location = ", ".join(
                [str(v) for v in [location_raw.get("city"), location_raw.get("region")] if v]
            )
        else:
            location = str(location_raw or "")

        year = self._safe_int(candidate.get("year") or candidate.get("productionYear") or candidate.get("firstRegistrationYear"))
        km = self._safe_int(candidate.get("mileage") or candidate.get("km") or candidate.get("odometer"))

        images_raw = candidate.get("images") or candidate.get("photos") or candidate.get("imageUrls") or []
        images: List[str] = []
        if isinstance(images_raw, list):
            for item in images_raw:
                if isinstance(item, str) and item.startswith("http"):
                    images.append(item)
                elif isinstance(item, dict):
                    maybe = item.get("url") or item.get("large") or item.get("src")
                    if isinstance(maybe, str) and maybe.startswith("http"):
                        images.append(maybe)

        source_id = str(candidate.get("id") or candidate.get("adId") or candidate.get("offerId") or url)
        brand, model = self._parse_brand_model(title)

        return {
            "source": "standvirtual",
            "source_id": source_id,
            "url": url,
            "title": title.strip(),
            "brand": brand,
            "model": model,
            "price": price,
            "year": year,
            "km": km,
            "location": location,
            "images": images,
            "fuel_type": (candidate.get("fuel") or candidate.get("fuelType") or "") or "",
            "description": candidate.get("description") or "",
            "raw_data": str(candidate),
        }

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

    def _parse_soup_to_listings(self, soup: Any, max_listings: int) -> List[Dict[str, object]]:
        listings = []
        # Modern Standvirtual structure uses specific article classes
        listing_elements = soup.find_all('article', class_=re.compile(r'ooa-1pixign|e1srzcph1|ooa-ciiovr'))
        
        if not listing_elements:
             # Fallback to general article searching
             listing_elements = soup.find_all('article')
             
        for idx, elem in enumerate(listing_elements[:max_listings]):
             listing = self._parse_listing_element(elem)
             if listing:
                 listings.append(listing)
        return listings
        
    async def scrape_listing_details(self, url: str) -> Optional[Dict[str, object]]:
        """Scrape detailed information from a single listing page using browser pool."""
        from bs4 import BeautifulSoup
        from scrapers.browser_pool import get_browser_pool
        from utils.playwright_stealth import apply_stealth_async
        
        try:
            pool = get_browser_pool()
            page = await pool.new_page("standvirtual_details")
            
            try:
                await apply_stealth_async(page)
            except Exception as e:
                logger.warning(f"Stealth failed: {e}")
            
            await page.goto(url, timeout=self.timeout, wait_until='networkidle')
            # Use wait_for instead of sleep
            try:
                await page.wait_for_selector('.offer-description, .offer-params__item', timeout=5000)
            except Exception:
                pass
            
            html = await page.content()
            await page.close()
            
        except Exception as e:
            logger.error(f"[STANDVIRTUAL_DETAILS] Browser pool failed: {e}")
            return None
            
        if not html:
            return None
            
        soup = BeautifulSoup(html, 'lxml')
        return self._fetch_details_from_soup(soup)
    
    def _build_url(self, vehicle_type: str, page: int = 1, filters: Optional[Dict[str, object]] = None) -> str:
        """Build URL with filters for Standvirtual"""
        # Navigate to Lisbon page which has actual listings instead of navigation
        base_url = f"{self.base_url}/{vehicle_type}/lisboa"
        
        # Build query string
        query_params = []
        
        if page > 1:
            query_params.append(f"page={page}")
        
        if not filters:
            if query_params:
                return f"{base_url}?{'&'.join(query_params)}"
            return base_url
        
        # Add brand filter
        if filters.get("brand"):
            query_params.append(f"search[brand]={filters['brand']}")
        
        # Add model filter
        if filters.get("model"):
            query_params.append(f"search[model]={filters['model']}")
        
        # Add price filters
        if filters.get("min_price"):
            query_params.append(f"search[price_from]={filters['min_price']}")
        
        if filters.get("max_price"):
            query_params.append(f"search[price_to]={filters['max_price']}")
        
        # Add year filters
        if filters.get("min_year"):
            query_params.append(f"search[year_from]={filters['min_year']}")
        
        if filters.get("max_year"):
            query_params.append(f"search[year_to]={filters['max_year']}")
        
        # Construct final URL
        if query_params:
            query_string = "&".join(query_params)
            return f"{base_url}?{query_string}"
        
        return base_url
    
    def _handle_consent(self, page: Any) -> None:
        """Handle cookie consent popup"""
        try:
            # Look for accept cookies button
            accept_button = page.query_selector('button:has-text("Aceitar"), button:has-text("Accept")')
            if accept_button:
                accept_button.click()
                time.sleep(1)
        except Exception as e:
            logger.debug(f"Cookie consent handling failed: {e}")

    @retry_network(max_attempts=3, min_wait=2, max_wait=10)  # type: ignore[misc]
    def _scroll_to_load(self, page: Any) -> None:
        """Scroll page to load lazy-loaded content"""
        for i in range(5):
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(random.uniform(0.5, 1.0))

        # Scroll back to top
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

    def _parse_listings(self, soup: Any, max_listings: int) -> List[Dict[str, object]]:
        """Parse listings from BeautifulSoup object"""
        listings = []

        # Standvirtual listing structure
        listing_elements = soup.find_all('article', class_='offer-item')

        for idx, elem in enumerate(listing_elements[:max_listings], 1):
            try:
                listing = self._parse_listing_element(elem)
                if listing:
                    listings.append(listing)
                    if idx % 10 == 0:
                        logger.info(f"[PROGRESS] Parsed {idx}/{min(len(listing_elements), max_listings)} listings")
            except Exception as e:
                logger.warning(f"Error parsing listing {idx}: {e}")
                continue

        return listings

    def _parse_listing_element(self, element: Any) -> Optional[Dict[str, object]]:
        """Parse a single Standvirtual listing element from current DOM"""
        try:
            # Find link with /anuncio/
            link_elem = element.find('a', href=re.compile(r'/anuncio/'))
            if not link_elem:
                return None
            url = link_elem.get('href', '')
            if isinstance(url, str) and url.startswith('/'):
                url = urljoin(self.base_url, url)
            if not url.startswith('http'):
                return None

            # Title from h2
            title_elem = element.find('h2')
            title = title_elem.get_text(strip=True) if title_elem else link_elem.get_text(strip=True)
            if not title:
                return None

            # Price from h3
            price = None
            price_elem = element.find('h3')
            if price_elem:
                price = self._safe_float(price_elem.get_text(strip=True))

            # Details from dl/dt/dd
            year = None
            km = None
            fuel_type = None
            transmission = None
            location = None

            dl = element.find('dl')
            if dl:
                dts = dl.find_all('dt')
                dds = dl.find_all('dd')
                for dt, dd in zip(dts, dds):
                    dt_text = dt.get_text(strip=True).lower()
                    dd_text = dd.get_text(strip=True)
                    if dt_text == 'first_registration_year':
                        year = self._safe_int(dd_text)
                    elif dt_text == 'mileage':
                        km = self._safe_int(dd_text)
                    elif dt_text == 'fuel_type':
                        fuel_type = dd_text
                    elif dt_text == 'gearbox':
                        transmission = dd_text

            # Try to find location from text
            full_text = element.get_text(strip=True)
            loc_match = re.search(r'([A-Za-zÀ-ÿ\s\-]+)\s*\([A-Za-zÀ-ÿ\s]+\)', full_text)
            if loc_match:
                location = loc_match.group(1).strip()

            # Image
            img_elem = element.find('img')
            image_url = ''
            if img_elem:
                image_url = img_elem.get('data-src') or img_elem.get('src') or ''

            import hashlib
            source_id = hashlib.md5(str(url).encode()).hexdigest()
            brand, model = self._parse_brand_model(title)

            return {
                "source": "standvirtual",
                "source_id": source_id,
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "location": location or "",
                "images": [image_url] if image_url else [],
                "fuel_type": fuel_type or "",
                "transmission": transmission or "",
                "raw_data": str(element)
            }

        except Exception as e:
            logger.warning(f"Error parsing element: {e}")
            return None
    def _fetch_details_from_soup(self, soup: Any) -> Dict[str, Any]:
        """Helper to extract details from a listing page soup"""
        try:
            details: Dict[str, Any] = {
                "year": None, "km": None, "fuel_type": None,
                "transmission": None, "horsepower": None, "engine_size": None,
                "doors": None, "seats": None, "color": None,
                "description": "", "images": [], "seller_name": "", "seller_type": "",
                "extras": []
            }
            
            # Description
            desc_elem = soup.find('div', class_='offer-description')
            if desc_elem:
                details["description"] = desc_elem.get_text(strip=True)
            
            # Parameters
            param_items = soup.find_all('li', class_='offer-params__item')
            for item in param_items:
                label = item.find('span', class_='offer-params__label')
                value = item.find('div', class_='offer-params__value')
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    value_text = value.get_text(strip=True)
                    
                    if "ano" in label_text:
                        try: details["year"] = int(value_text)
                        except ValueError: logger.warning(f"[DETAILS] Error parsing year from '{value_text}'")
                    elif "quilómetros" in label_text or "km" in label_text:
                        try: details["km"] = int(value_text.replace(' ', '').replace('km', ''))
                        except ValueError: logger.warning(f"[DETAILS] Error parsing km from '{value_text}'")
                    elif "combustível" in label_text:
                        details["fuel_type"] = value_text.lower()
                    elif "caixa" in label_text:
                        details["transmission"] = value_text.lower()
                    elif "potência" in label_text:
                        try: details["horsepower"] = int(value_text.split()[0])
                        except (ValueError, IndexError): logger.warning(f"[DETAILS] Error parsing horsepower from '{value_text}'")
                    elif "cilindrada" in label_text:
                        try: details["engine_size"] = int(value_text.split()[0])
                        except (ValueError, IndexError): logger.warning(f"[DETAILS] Error parsing engine size from '{value_text}'")
                    elif "portas" in label_text:
                        try: details["doors"] = int(value_text)
                        except ValueError: logger.warning(f"[DETAILS] Error parsing doors from '{value_text}'")
                    elif "lugares" in label_text:
                        try: details["seats"] = int(value_text)
                        except ValueError: logger.warning(f"[DETAILS] Error parsing seats from '{value_text}'")
                    elif "cor" in label_text:
                        details["color"] = value_text
            
            # Images
            img_elems = soup.find_all('img', class_='offer-gallery__img')
            details["images"] = [img.get('data-src', '') for img in img_elems if img.get('data-src')]
            
            # Seller info
            seller_elem = soup.find('div', class_='seller-info')
            if seller_elem:
                name_elem = seller_elem.find('h4', class_='seller-name')
                if name_elem: details["seller_name"] = name_elem.get_text(strip=True)
                
                type_elem = seller_elem.find('span', class_='seller-type')
                if type_elem: details["seller_type"] = type_elem.get_text(strip=True)
            
            # Extras
            extras_items = soup.find_all('li', class_='offer-features__item')
            details["extras"] = [item.get_text(strip=True) for item in extras_items]
            
            return details
        except Exception as e:
            logger.error(f"Error parsing details soup: {e}")
            return {}
    
    def save_to_database(self, listings: List[Dict[str, object]], vehicle_type: str = "carros") -> None:
        """Save scraped listings to database with data enrichment before validation"""
        logger.info(f"[PROGRESS] Saving {len(listings)} listings to database")
        
        # Log sample of incoming data for debugging
        if listings:
            sample = listings[0]
            logger.info(f"[DEBUG] Sample listing data: title={sample.get('title')}, price={sample.get('price')}, url={sample.get('url')}")
        
        saved_count = 0
        updated_count = 0
        skipped_dedup = 0
        skipped_validation = 0
        skipped_missing_url = 0
        skipped_non_listing = 0
        
        with get_db_context() as db:
            from database.models import Vehicle, ScrapingLog
            
            # Create scraping log entry
            log = ScrapingLog(
                source=Source.STANDVIRTUAL,
                status="running"
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            
            try:
                for idx, listing_data in enumerate(listings, 1):
                    try:
                        if idx % 20 == 0:
                            logger.info(f"[PROGRESS] Processing {idx}/{len(listings)} listings")
                        url = listing_data.get("url")
                        if not isinstance(url, str) or not url.startswith("http"):
                            skipped_missing_url += 1
                            continue

                        # Filter out non-listing URLs (catalog pages, promo links, etc.)
                        # Accept actual Standvirtual URL pattern: /carros/ or /motos/ followed by listing details
                        if "/carros/" not in url and "/motos/" not in url:
                            skipped_non_listing += 1
                            logger.debug(f"[SKIP] Non-listing URL: {url}")
                            continue

                        # Check deduplication (in-memory)
                        if is_url_processed(url):
                            skipped_dedup += 1
                            continue
                        
                        # === ENRICH DATA before validation ===
                        # Add source if missing
                        if not listing_data.get("source"):
                            listing_data["source"] = "STANDVIRTUAL"
                        
                        # Add vehicle_type if missing
                        if not listing_data.get("vehicle_type"):
                            listing_data["vehicle_type"] = "car" if vehicle_type == "carros" else "moto"
                        
                        # Parse brand and model from title if missing
                        title = listing_data.get("title", "")
                        if isinstance(title, str):
                            if not listing_data.get("brand") or not listing_data.get("model"):
                                brand, model = self._parse_brand_model(title)
                                if not listing_data.get("brand"):
                                    listing_data["brand"] = brand
                                if not listing_data.get("model"):
                                    listing_data["model"] = model
                        
                        # Fix empty string fuel_type/transmission -> None
                        if listing_data.get("fuel_type") == "":
                            listing_data["fuel_type"] = None
                        if listing_data.get("transmission") == "":
                            listing_data["transmission"] = None
                        
                        # Validate scraped data using pydantic model and custom validation
                        try:
                            ScrapedVehicle(**listing_data)  # type: ignore[arg-type]
                            
                            is_valid, validation_error = validate_scraped_data(listing_data)
                            if not is_valid:
                                skipped_validation += 1
                                logger.debug(f"[SKIP] Validation failed for listing {url}: {validation_error}")
                                continue
                        except Exception as e:
                            skipped_validation += 1
                            logger.debug(f"[SKIP] Validation exception for listing {url}: {e}")
                            continue
                        
                        # Parse brand and model from title
                        if isinstance(title, str):
                            brand, model = self._parse_brand_model(title)
                        else:
                            brand, model = "Unknown", "Unknown"
                        
                        # Determine vehicle type enum
                        v_type = VehicleType.carros if vehicle_type == "carros" else VehicleType.motos
                        
                        # Check if listing already exists in database
                        existing = db.query(Vehicle).filter(
                            Vehicle.url == url
                        ).first()
                        
                        if existing:
                            # Update existing listing
                            existing.price = listing_data.get("price")  # type: ignore[assignment]
                            existing.last_seen = datetime.now(timezone.utc)  # type: ignore[assignment]
                            existing.scrape_count += 1  # type: ignore[assignment]
                            updated_count += 1
                            mark_url_processed(url)
                        else:
                            # Create new vehicle
                            vehicle = Vehicle(
                                source=Source.STANDVIRTUAL,
                                source_id=listing_data.get("source_id", ""),
                                url=url,
                                vehicle_type=v_type,
                                brand=brand,
                                model=model,
                                title=title if isinstance(title, str) else "",
                                price=listing_data.get("price"),
                                location=listing_data.get("location"),
                                images=listing_data.get("images", []),
                                image_count=0,
                                description=listing_data.get("description", ""),
                                year=listing_data.get("year"),
                                km=listing_data.get("km"),
                                horsepower=listing_data.get("horsepower"),
                                engine_size=listing_data.get("engine_size"),
                                doors=listing_data.get("doors"),
                                seats=listing_data.get("seats"),
                                color=listing_data.get("color"),
                                seller_name=listing_data.get("seller_name"),
                                seller_type=listing_data.get("seller_type"),
                                extras=listing_data.get("extras", []),
                                is_active=True
                            )
                            
                            # Map fuel type
                            fuel_type = listing_data.get("fuel_type")
                            if isinstance(fuel_type, str) and fuel_type:
                                fuel_type_lower = fuel_type.lower()
                                if "gasolina" in fuel_type_lower:
                                    vehicle.fuel_type = FuelType.GASOLINE
                                elif "diesel" in fuel_type_lower:
                                    vehicle.fuel_type = FuelType.DIESEL
                                elif "eletrico" in fuel_type_lower or "eléctrico" in fuel_type_lower:
                                    vehicle.fuel_type = FuelType.ELECTRIC
                                elif "hibrido" in fuel_type_lower or "híbrido" in fuel_type_lower:
                                    vehicle.fuel_type = FuelType.HYBRID
                                elif "gpl" in fuel_type_lower:
                                    vehicle.fuel_type = FuelType.GPL

                            # Map transmission
                            transmission = listing_data.get("transmission")
                            if isinstance(transmission, str) and transmission:
                                transmission_lower = transmission.lower()
                                if "manual" in transmission_lower:
                                    vehicle.transmission = Transmission.MANUAL
                                elif "automatic" in transmission_lower or "automático" in transmission_lower:
                                    vehicle.transmission = Transmission.AUTOMATIC
                            
                            db.add(vehicle)
                            saved_count += 1
                            mark_url_processed(url)
                        
                    except Exception as e:
                        logger.warning(f"Error saving listing: {e}")
                        continue
                
                # Update scraping log
                log.status = "completed"  # type: ignore[assignment]
                log.finished_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                log.listings_found = len(listings)  # type: ignore[assignment]
                log.listings_added = saved_count  # type: ignore[assignment]
                log.listings_updated = updated_count  # type: ignore[assignment]

                db.commit()
                logger.info(
                    f"[PROGRESS] Database save completed: {saved_count} new, {updated_count} updated, "
                    f"{skipped_dedup} skipped (dedup), {skipped_validation} skipped (validation), "
                    f"{skipped_non_listing} skipped (non-listing URL), "
                    f"{skipped_missing_url} skipped (missing URL)"
                )

            except Exception as e:
                log.status = "failed"  # type: ignore[assignment]
                log.error_message = str(e)  # type: ignore[assignment]
                log.finished_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                db.commit()
                raise
    
    def _parse_brand_model(self, title: str) -> tuple[str, str]:
        """Parse brand and model from title"""
        # Sorted longest-first to prevent partial matches
        # (e.g. "Alfa Romeo" must match before "Alfa")
        brands = [
            # Multi-word brands first
            "Alfa Romeo", "Aston Martin", "Land Rover", "Rolls-Royce",
            "CF Moto", "Royal Enfield", "Harley-Davidson", "Harley Davidson",
            "Mercedes-Benz", "Mercedes Benz",
            # Premium cars
            "Porsche", "Ferrari", "Lamborghini", "Maserati", "Bentley",
            "McLaren", "Bugatti", "Tesla", "Jaguar", "Lexus", "Infiniti",
            "Lincoln", "Genesis", "Polestar", "Cupra",
            # Mass market cars
            "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
            "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
            "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Škoda", "Volvo",
            "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini",
            "Smart", "Chevrolet", "Jeep", "Dodge", "Chrysler", "Subaru",
            "Lancia", "Saab", "DS", "MG", "BYD", "Caterham",
            # Commercial vehicles
            "Iveco", "Isuzu", "DAF", "MAN", "Scania",
            # Motorcycles
            "Ducati", "Yamaha", "Kawasaki", "Triumph", "KTM", "Aprilia",
            "Husqvarna", "Indian", "Moto Guzzi", "MV Agusta", "Benelli",
            "Beta", "Gas Gas", "GasGas", "SYM", "Kymco", "Piaggio",
            "Vespa", "Gilera", "Derbi", "SWM", "Voge", "Zontes",
            "NIU", "Super Soco", "Brixton", "Fantic", "Rieju",
        ]
        
        title_lower = title.lower()
        
        for brand in brands:
            if brand.lower() in title_lower:
                brand_idx = title_lower.index(brand.lower())
                model = title[brand_idx + len(brand):].strip()
                return brand, model
        
        parts = title.split()
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        return title, ""


if __name__ == "__main__":
    scraper = StandvirtualScraper()
    listings = scraper.scrape_listings("carros", max_listings=10)
    print(f"Scraped {len(listings)} listings")
