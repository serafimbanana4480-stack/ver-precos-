"""
OLX.pt scraper using subprocess to call olx-tracker (Rust)
"""
from __future__ import annotations
import json
import logging
import random
import asyncio
import subprocess
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from config import settings
from utils.retry import retry_network
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from database.db import get_db_context
from validation.scraped_models import ScrapedVehicle
from utils.data_validation import DataValidator, validate_scraped_data
from utils.selector_manager import get_selector_manager, initialize_default_selectors
from utils.ml_parser import get_ml_parser
from utils.html_change_detector import get_html_change_detector
from utils.production_safeguards import with_circuit_breaker, _olx_circuit_breaker
from utils.captcha_solver import CaptchaDetector, get_captcha_solver
from utils.captcha_rate_limiter import get_captcha_rate_limiter, get_captcha_delay_escalator
from utils.proxy_manager import get_proxy_pool

# Optional imports - these modules may not be available in simplified version
try:
    from scrapers.ai_scraper import get_ai_scraper
except ImportError:
    get_ai_scraper = None

try:
    from scrapers.ai_extractor import get_ai_extractor
except ImportError:
    get_ai_extractor = None

try:
    from scrapers.managed_client import get_managed_client
except ImportError:
    get_managed_client = None

logger = logging.getLogger(__name__)


class OLXScraper:
    """Scraper for OLX.pt using Rust olx-tracker"""
    
    def __init__(self) -> None:
        self.tracker_path = settings.olx_tracker_path
        self.base_url = settings.olx_base_url
        self.timeout = settings.playwright_timeout
        self.headless = settings.playwright_headless
        
        # Initialize selector manager and ML parser
        initialize_default_selectors()
        self.selector_manager = get_selector_manager()
        self.ml_parser = get_ml_parser()
        self.html_detector = get_html_change_detector()
        self.captcha_rate_limiter = get_captcha_rate_limiter()
        self.captcha_delay_escalator = get_captcha_delay_escalator()
        self.proxy_pool = get_proxy_pool()
        self.managed_client = get_managed_client() if get_managed_client else None

    @with_circuit_breaker(_olx_circuit_breaker, "OLX scraping")
    async def _try_commercial_apis(self, vehicle_type: str, max_listings: int, filters: Optional[Dict[str, object]]) -> List[Dict[str, Any]]:
        """
        Try commercial scraping APIs first for OLX (known to be heavily blocked).
        Order: ZenRows -> ScraperAPI -> return empty
        """
        if not self.managed_client:
            logger.warning("[OLX_COMMERCIAL] Managed client not available, skipping commercial APIs")
            return []
            
        url = self._build_url(vehicle_type, filters=filters)
        
        # Try ZenRows first (best for Cloudflare)
        if settings.zenrows_api_key:
            logger.info("[OLX_COMMERCIAL] Trying ZenRows for OLX (Cloudflare-protected)")
            try:
                html = await self.managed_client.scrape_with_zenrows(url)
                if html and len(html) > 1000:
                    from utils.error_classifier import ErrorClassifier
                    if not ErrorClassifier.detect_blocking_in_html(html):
                        logger.info("[OLX_COMMERCIAL] ZenRows succeeded, extracting listings")
                        # Extract listings from HTML
                        listings = await self._extract_from_html(html, vehicle_type, max_listings)
                        if listings:
                            logger.info(f"[OLX_COMMERCIAL] ZenRows extracted {len(listings)} listings")
                            return listings
                    else:
                        logger.warning("[OLX_COMMERCIAL] ZenRows returned blocked page")
            except Exception as e:
                logger.warning(f"[OLX_COMMERCIAL] ZenRows failed: {e}")
        
        # Try ScraperAPI as fallback
        if settings.scraperapi_key:
            logger.info("[OLX_COMMERCIAL] Trying ScraperAPI for OLX")
            try:
                html = await self.managed_client.scrape_with_scraperapi(url, params={"render": "true"})
                if html and len(html) > 1000:
                    from utils.error_classifier import ErrorClassifier
                    if not ErrorClassifier.detect_blocking_in_html(html):
                        logger.info("[OLX_COMMERCIAL] ScraperAPI succeeded, extracting listings")
                        listings = await self._extract_from_html(html, vehicle_type, max_listings)
                        if listings:
                            logger.info(f"[OLX_COMMERCIAL] ScraperAPI extracted {len(listings)} listings")
                            return listings
                    else:
                        logger.warning("[OLX_COMMERCIAL] ScraperAPI returned blocked page")
            except Exception as e:
                logger.warning(f"[OLX_COMMERCIAL] ScraperAPI failed: {e}")
        
        logger.info("[OLX_COMMERCIAL] No commercial APIs available or all failed")
        return []

    @retry_network(max_attempts=3, min_wait=2, max_wait=10)  # type: ignore[misc]
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 100,
        filters: Optional[Dict[str, object]] = None
    ) -> List[Dict[str, object]]:
        """
        Scrape listings from OLX.pt using Commercial API-first approach (since OLX is heavily blocked)

        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum number of listings to scrape
            filters: Optional filters (brand, model, min_price, max_price, etc.)

        Returns:
            List of vehicle dictionaries
        """
        logger.info(f"[PROGRESS] Starting OLX scrape for {vehicle_type}, max {max_listings} listings")
        
        # PHASE 0: Try Internal API first (often works when web is blocked)
        try:
            from scrapers.api_clients import fetch_olx_api
            logger.info(f"[OLX_API] Trying internal API for {vehicle_type}")
            api_listings = await fetch_olx_api(vehicle_type=vehicle_type, limit=max_listings, filters=filters)
            if api_listings:
                logger.info(f"[OLX_SUCCESS] Internal API returned {len(api_listings)} listings")
                return api_listings
        except Exception as e:
            logger.warning(f"[OLX_API] Internal API failed: {e}")

        # PHASE 1: Try Commercial APIs first (OLX is heavily Cloudflare-protected)
        listings = await self._try_commercial_apis(vehicle_type, max_listings, filters)
        if listings:
            logger.info(f"[OLX_SUCCESS] Commercial APIs returned {len(listings)} listings")
            return listings
        
        # PHASE 2: Try AI scraper if enabled and commercial APIs failed
        if settings.ai_scraping_enabled and get_ai_scraper:
            logger.info(f"[PROGRESS] AI scraping enabled, trying AI scraper")
            url = self._build_url(vehicle_type, filters=filters)
            try:
                ai_scraper = get_ai_scraper()
                listings = await ai_scraper.scrape_listings("olx", url, max_listings)
                if listings:
                    logger.info(f"[AI_SUCCESS] AI scraper retrieved {len(listings)} listings")
                    return listings
                else:
                    logger.warning("[AI_FAIL] AI scraper returned no results")
            except Exception as e:
                logger.error(f"[AI_FAIL] AI scraper failed: {e}")
        
        # PHASE 3: Last resort - try local Playwright with enhanced stealth
        logger.info("[PROGRESS] Trying local Playwright with enhanced stealth (last resort)")
        listings = await self._scrape_with_resilient_flow(vehicle_type, max_listings, filters)
        
        return listings
    
    def _build_url(self, vehicle_type: str, page: int = 1, filters: Optional[Dict[str, object]] = None) -> str:
        """Build URL with query parameters for OLX"""
        from urllib.parse import quote
        url = f"{self.base_url}/{vehicle_type}"
        
        params = []
        if page > 1:
            params.append(f"page={page}")
            
        if filters:
            if filters.get("brand"):
                brand = filters["brand"]
                if isinstance(brand, str):
                    params.append(f"q={quote(brand)}")
            if filters.get("min_price"):
                params.append(f"search[filter_float_price:from]={filters['min_price']}")
            if filters.get("max_price"):
                params.append(f"search[filter_float_price:to]={filters['max_price']}")

        if params:
            url += "?" + "&".join(params)

        return url

    async def _scrape_with_simple_playwright(self, vehicle_type: str, max_listings: int, filters: Optional[Dict[str, object]]) -> List[Dict[str, Any]]:
        """
        Simple Playwright fallback when managed_client is not available
        """
        try:
            from playwright.async_api import async_playwright
            from bs4 import BeautifulSoup
        except ImportError as e:
            logger.error(f"[OLX_SIMPLE] Missing dependencies: {e}")
            return []
        
        url = self._build_url(vehicle_type, 1, filters)
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                context = await browser.new_context(
                    user_agent=random.choice(settings.user_agents),
                    viewport={'width': 1920, 'height': 1080},
                    locale='pt-PT'
                )
                
                page = await context.new_page()
                logger.info(f"[OLX_SIMPLE] Navigating to {url}")
                await page.goto(url, timeout=self.timeout, wait_until='networkidle')
                
                # Wait for content to load
                await asyncio.sleep(3)
                
                html = await page.content()
                await browser.close()
                
                if not html or len(html) < 500:
                    logger.warning("[OLX_SIMPLE] HTML too short, likely blocked")
                    return []
                
                # Check for blocking
                from utils.error_classifier import ErrorClassifier
                if ErrorClassifier.detect_blocking_in_html(html):
                    logger.warning("[OLX_SIMPLE] Blocked page detected")
                    return []
                
                # Parse listings
                soup = BeautifulSoup(html, 'lxml')
                listings = self._parse_soup_to_listings(soup, max_listings)
                
                logger.info(f"[OLX_SIMPLE] Extracted {len(listings)} listings")
                return listings
                
        except Exception as e:
            logger.error(f"[OLX_SIMPLE] Failed: {e}")
            return []

    async def _scrape_with_resilient_flow(self, vehicle_type: str, max_listings: int, filters: Optional[Dict[str, object]]) -> List[Dict[str, Any]]:
        """
        Resilient flow: Playwright -> CSS Selectors -> AI Extraction
        """
        from bs4 import BeautifulSoup
        
        # If managed_client is not available, use simple Playwright fallback
        if not self.managed_client:
            logger.warning("[OLX_RESILIENT] Managed client not available, using simple Playwright fallback")
            return await self._scrape_with_simple_playwright(vehicle_type, max_listings, filters)
            
        items_per_page = 40
        pages_to_scan = (max_listings // items_per_page) + 1
        pages_to_scan = min(pages_to_scan, 3)
        
        tasks = []
        for p in range(1, pages_to_scan + 1):
            url = self._build_url(vehicle_type, p, filters)
            tasks.append(self.managed_client.get_html(url, source="olx"))
            
        html_responses = await asyncio.gather(*tasks)
        
        all_listings = []
        for html in html_responses:
            if html:
                # Try CSS selectors first
                soup = BeautifulSoup(html, 'lxml')
                parsed = self._parse_soup_to_listings(soup, items_per_page)
                
                if parsed:
                    all_listings.extend(parsed)
                elif get_ai_extractor:
                    # CSS selectors failed -> Use AI extraction
                    logger.info("[AI_EXTRACT] CSS selectors returned 0 results, switching to AI extraction")
                    ai_extractor = get_ai_extractor()
                    ai_results = await ai_extractor.extract_from_html(html, "olx", items_per_page)
                    if ai_results:
                        logger.info(f"[AI_EXTRACT] AI extracted {len(ai_results)} OLX listings")
                        all_listings.extend(ai_results)
                
        return all_listings[:max_listings]

    async def _extract_from_html(self, html: str, vehicle_type: str, max_listings: int) -> List[Dict[str, Any]]:
        """
        Extract listings from HTML using CSS selectors and AI extraction.
        Used by commercial API flow.
        """
        from bs4 import BeautifulSoup
        
        if not html or len(html) < 200:
            logger.warning("[EXTRACT] HTML too short, skipping extraction")
            return []
        
        # Check for blocking patterns
        from utils.error_classifier import ErrorClassifier
        if ErrorClassifier.detect_blocking_in_html(html):
            logger.warning("[EXTRACT] Blocked HTML detected, cannot extract")
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Try CSS selectors first
        listings = self._parse_soup_to_listings(soup, max_listings)
        
        if listings:
            logger.info(f"[EXTRACT] CSS selectors extracted {len(listings)} listings")
            return listings
        
        # CSS selectors failed -> Use AI extraction if available
        if get_ai_extractor:
            logger.info("[EXTRACT] CSS selectors returned 0 results, switching to AI extraction")
            ai_extractor = get_ai_extractor()
            ai_results = await ai_extractor.extract_from_html(html, "olx", max_listings)
            
            if ai_results:
                logger.info(f"[EXTRACT] AI extracted {len(ai_results)} listings")
            
            return ai_results
        else:
            logger.warning("[EXTRACT] AI extractor not available, returning empty")
            return []

    def _parse_soup_to_listings(self, soup: Any, max_listings: int) -> List[Dict[str, object]]:
        listings = []
        listing_elements = soup.find_all('div', {'data-cy': 'l-card'})
        # (Rest of the parsing logic using SelectorManager)
        for idx, elem in enumerate(listing_elements[:max_listings]):
             listing = self._parse_olx_element(elem)
             if listing:
                 listings.append(listing)
        return listings
    

    def _parse_olx_element(self, element: Any) -> Optional[Dict[str, object]]:
        """Parse a single OLX listing element"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        # Extract using SelectorManager fallback system
        url, _ = self.selector_manager.extract_with_fallback(element, 'olx', 'url')
        if not url:
            # Manual fallback for URL if selector manager fails
            link_elem = element.find('a', href=True)
            if not link_elem: return None
            url = link_elem['href']
        
        if isinstance(url, str) and url.startswith('/'):
            url = self.base_url + url
            
        title, _ = self.selector_manager.extract_with_fallback(element, 'olx', 'title')
        title = title or ""
        
        price, _ = self.selector_manager.extract_with_fallback(element, 'olx', 'price')
        location, _ = self.selector_manager.extract_with_fallback(element, 'olx', 'location')
        location = location or ""
        
        year, _ = self.selector_manager.extract_with_fallback(element, 'olx', 'year')
        km, _ = self.selector_manager.extract_with_fallback(element, 'olx', 'km')
        
        # Extract image manually (usually more complex)
        img_elem = element.find('img')
        image_url = img_elem.get('src', '') if img_elem else ''
        
        # Generate stable source_id
        import hashlib
        source_id = hashlib.md5(str(url).encode()).hexdigest()
        
        return {
            "source_id": source_id,
            "url": url,
            "title": title,
            "price": price,
            "year": year,
            "km": km,
            "location": location,
            "images": [image_url] if image_url else [],
            "raw_data": str(element)
        }
    
    async def scrape_listing_details(self, url: str) -> Optional[Dict[str, object]]:
        """Scrape detailed information from a single listing page"""
        try:
            from playwright.async_api import async_playwright
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("Playwright not installed")
            return None
        
        import asyncio
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    channel="chrome",
                    args=['--disable-blink-features=AutomationControlled']
                )
                import random
                context = await browser.new_context(user_agent=random.choice(settings.user_agents))
                page = await context.new_page()
                
                await page.goto(url, timeout=30000)
                await asyncio.sleep(random.uniform(2, 3))
                
                html = await page.content()
                await browser.close()
                
                soup = BeautifulSoup(html, 'lxml')

                # Parse detailed information
                details: Dict[str, object] = {
                    "description": "",
                    "year": None,
                    "km": None,
                    "fuel_type": None,
                    "transmission": None,
                    "horsepower": None,
                    "engine_size": None,
                    "doors": None,
                    "seats": None,
                    "color": None,
                    "seller_name": "",
                    "seller_type": "",
                    "images": [],
                    "extras": []
                }
                
                # Description
                desc_elem = soup.find('div', {'data-cy': 'description_content'})
                if desc_elem:
                    details["description"] = desc_elem.text.strip()
                
                # Specifications
                spec_items = soup.find_all('li', {'data-testid': 'ad-parameters-item'})
                for item in spec_items:
                    label = item.find('p', class_='css-6s1iq5')
                    value = item.find('p', class_='css-1ks2pr4')
                    if label and value:
                        label_text = label.text.strip().lower()
                        value_text = value.text.strip()
                        
                        if "ano" in label_text:
                            try:
                                details["year"] = int(value_text)
                            except ValueError:
                                pass
                        elif "quilómetros" in label_text or "km" in label_text:
                            try:
                                details["km"] = int(value_text.replace(' ', '').replace('km', ''))
                            except ValueError:
                                pass
                        elif "combustível" in label_text:
                            details["fuel_type"] = value_text.lower()
                        elif "caixa" in label_text:
                            details["transmission"] = value_text.lower()
                        elif "potência" in label_text:
                            try:
                                details["horsepower"] = int(value_text.split()[0])
                            except (ValueError, IndexError):
                                pass
                        elif "cilindrada" in label_text:
                            try:
                                details["engine_size"] = int(value_text.split()[0])
                            except (ValueError, IndexError):
                                pass
                        elif "portas" in label_text:
                            try:
                                details["doors"] = int(value_text)
                            except ValueError:
                                pass
                        elif "lugares" in label_text or "assentos" in label_text:
                            try:
                                details["seats"] = int(value_text)
                            except ValueError:
                                pass
                        elif "cor" in label_text:
                            details["color"] = value_text
                
                # Images
                img_elems = soup.find_all('img', {'data-testid': 'ad-gallery-image'})
                details["images"] = [img.get('src', '') for img in img_elems if img.get('src')]
                
                # Seller info
                seller_elem = soup.find('div', {'data-testid': 'seller-info'})
                if seller_elem:
                    details["seller_name"] = seller_elem.text.strip()
                
                return details
                
        except Exception as e:
            logger.error(f"Error scraping listing details: {e}")
            return None
    
    def save_to_database(self, listings: List[Dict[str, object]], vehicle_type: str = "carros") -> None:
        """Save scraped listings to database with enhanced error handling"""
        logger.info(f"[PROGRESS] Saving {len(listings)} listings to database")
        saved_count = 0
        updated_count = 0
        validation_errors = 0

        with get_db_context() as db:
            from database.models import Vehicle, ScrapingLog

            # Create scraping log entry
            log = ScrapingLog(
                source=Source.OLX,
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
                            validation_errors += 1
                            continue
                        
                        # === ENRICH DATA before validation ===
                        if not listing_data.get("source"):
                            listing_data["source"] = "olx"
                        if not listing_data.get("vehicle_type"):
                            listing_data["vehicle_type"] = "car" if vehicle_type == "carros" else "moto"
                        
                        title = listing_data.get("title", "")
                        if isinstance(title, str) and (not listing_data.get("brand") or not listing_data.get("model")):
                            brand, model = self._parse_brand_model(title)
                            if not listing_data.get("brand"):
                                listing_data["brand"] = brand
                            if not listing_data.get("model"):
                                listing_data["model"] = model
                        
                        if listing_data.get("fuel_type") == "":
                            listing_data["fuel_type"] = None
                        if listing_data.get("transmission") == "":
                            listing_data["transmission"] = None
                        
                        # Validate scraped data using pydantic model and custom validation
                        try:
                            ScrapedVehicle(**listing_data)  # type: ignore[arg-type]
                            
                            is_valid, validation_error = validate_scraped_data(listing_data)
                            if not is_valid:
                                logger.debug(f"Data validation failed for listing {url}: {validation_error}")
                                validation_errors += 1
                                continue
                        except Exception as e:
                            logger.debug(f"Validation failed for listing {url}: {e}")
                            validation_errors += 1
                            continue

                        # Check if listing already exists
                        existing = db.query(Vehicle).filter(
                            Vehicle.url == listing_data.get("url")
                        ).first()

                        # Parse brand and model from title
                        title = listing_data.get("title", "")
                        if isinstance(title, str):
                            brand, model = self._parse_brand_model(title)
                        else:
                            brand, model = "Unknown", "Unknown"

                        # Determine vehicle type enum
                        v_type = VehicleType.CAR if vehicle_type == "carros" else VehicleType.MOTO

                        if existing:
                            # Update existing listing
                            existing.price = listing_data.get("price")  # type: ignore[assignment]
                            existing.last_seen = datetime.now(timezone.utc)  # type: ignore[assignment]
                            existing.scrape_count += 1  # type: ignore[assignment]
                            updated_count += 1
                        else:
                            # Create new vehicle
                            vehicle = Vehicle(
                                source=Source.OLX,
                                source_id=listing_data.get("source_id", ""),
                                url=listing_data.get("url"),
                                vehicle_type=v_type,
                                brand=brand,
                                model=model,
                                title=title,
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
                            fuel_type = listing_data.get("fuel_type", "")
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
                            transmission = listing_data.get("transmission", "")
                            if isinstance(transmission, str) and transmission:
                                transmission_lower = transmission.lower()
                                if "manual" in transmission_lower:
                                    vehicle.transmission = Transmission.MANUAL
                                elif "automatic" in transmission_lower or "automático" in transmission_lower:
                                    vehicle.transmission = Transmission.AUTOMATIC

                            db.add(vehicle)
                            saved_count += 1

                    except Exception as e:
                        logger.error(f"Error saving listing {listing_data.get('url', 'unknown')}: {e}", exc_info=True)
                        continue

                # Update scraping log
                log.status = "completed"  # type: ignore[assignment]
                log.finished_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                log.listings_found = len(listings)  # type: ignore[assignment]
                log.listings_added = saved_count  # type: ignore[assignment]
                log.listings_updated = updated_count  # type: ignore[assignment]
                log.validation_errors = validation_errors  # type: ignore[assignment]

                db.commit()
                logger.info(f"[PROGRESS] Database save completed: {saved_count} new, {updated_count} updated, {validation_errors} validation errors")

            except Exception as e:
                log.status = "failed"  # type: ignore[assignment]
                log.error_message = str(e)  # type: ignore[assignment]
                log.finished_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                db.commit()
                logger.error(f"OLX scrape failed: {e}", exc_info=True)
                raise
    
    def _parse_brand_model(self, title: str) -> tuple[str, str]:
        """Parse brand and model from title"""
        # Common Portuguese car brands
        brands = [
            "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot", 
            "Citroën", "Ford", "Toyota", "Honda", "Nissan", "Hyundai", 
            "Kia", "Fiat", "Seat", "Skoda", "Volvo", "Mazda", "Mitsubishi",
            "Suzuki", "Dacia", "Opel", "Alfa Romeo", "Mini", "Smart",
            "Yamaha", "Kawasaki", "Honda", "Suzuki", "Ducati", "KTM"
        ]
        
        title_lower = title.lower()
        
        for brand in brands:
            if brand.lower() in title_lower:
                # Extract model (everything after brand)
                brand_idx = title_lower.index(brand.lower())
                model = title[brand_idx + len(brand):].strip()
                return brand, model
        
        # Fallback
        parts = title.split()
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        return title, ""


if __name__ == "__main__":
    # Test scraper
    scraper = OLXScraper()
    listings = scraper.scrape_listings("carros", max_listings=10)
    print(f"Scraped {len(listings)} listings")
    if listings:
        scraper.save_to_database(listings)
