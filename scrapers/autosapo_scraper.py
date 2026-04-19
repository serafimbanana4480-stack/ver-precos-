"""
AutoSapo.pt scraper using Playwright
"""
from __future__ import annotations
import logging
import random
import time
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from urllib.parse import urljoin, quote

from config import settings
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from database.db import get_db_context
from utils.retry import retry_network
from validation.scraped_models import ScrapedVehicle
from utils.data_validation import DataValidator, validate_scraped_data
from utils.production_safeguards import with_circuit_breaker, _autosapo_circuit_breaker
from utils.captcha_solver import CaptchaDetector, get_captcha_solver
from utils.proxy_manager import get_proxy_pool
from utils.selector_manager import get_selector_manager

# Optional imports - modules may not be available in simplified version
try:
    from scrapers.ai_scraper import get_ai_scraper
except ImportError:
    get_ai_scraper = None

try:
    from scrapers.regex_extractor import get_regex_extractor
except ImportError:
    get_regex_extractor = None

try:
    from scrapers.managed_client import get_managed_client
except ImportError:
    get_managed_client = None

logger = logging.getLogger(__name__)


class AutoSapoScraper:
    """Scraper for AutoSapo.pt using Playwright"""
    
    def __init__(self) -> None:
        self.base_url = settings.autosapo_base_url
        self.headless = settings.playwright_headless
        self.timeout = settings.playwright_timeout
        self.proxy_pool = get_proxy_pool()
        self.selector_manager = get_selector_manager()
        self.managed_client = get_managed_client() if get_managed_client else None
        
    @with_circuit_breaker(_autosapo_circuit_breaker, "AutoSapo scraping")
    @retry_network(max_attempts=3, min_wait=2, max_wait=10)  # type: ignore[misc]
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 100,
        filters: Optional[Dict[str, object]] = None
    ) -> List[Dict[str, object]]:
        """
        Scrape listings from AutoSapo.pt using AI-first or Playwright-first approach based on priority
        
        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum number of listings to scrape
            filters: Optional filters (brand, model, min_price, max_price, etc.)
        
        Returns:
            List of vehicle dictionaries
        """
        logger.info(f"[PROGRESS] Starting AutoSapo scrape for {vehicle_type}, max {max_listings} listings")
        logger.info(f"[PROGRESS] AI scraping priority: {settings.ai_scraper_priority}")
        
        url = self._build_url(vehicle_type, filters)
        
        # AI-First Approach (if configured as primary)
        if settings.ai_scraping_enabled and settings.ai_scraper_priority == "primary" and get_ai_scraper:
            logger.info("[AI_PRIMARY] Using AI scraper as primary method")
            try:
                ai_scraper = get_ai_scraper()
                listings = await ai_scraper.scrape_listings("autosapo", url, max_listings)
                if listings:
                    logger.info(f"[AI_PRIMARY] AI scraper successfully retrieved {len(listings)} listings")
                    return listings
                else:
                    logger.warning("[AI_PRIMARY] AI scraper returned no results, falling back to Playwright")
            except Exception as e:
                logger.error(f"[AI_PRIMARY] AI scraper failed: {e}, falling back to Playwright")
        
        # Playwright-First Approach (fallback or if AI disabled)
        logger.info(f"[PROGRESS] Phase 1/5: Building URL with filters")
        listings = await self._scrape_with_resilient_flow(vehicle_type, max_listings, filters)
        return listings

    async def _scrape_with_resilient_flow(
        self,
        vehicle_type: str,
        max_listings: int,
        filters: Optional[Dict[str, object]] = None
    ) -> List[Dict[str, object]]:
        from bs4 import BeautifulSoup
        url = self._build_url(vehicle_type, filters)
        
        # Use managed_client if available, otherwise fallback to local playwright
        if self.managed_client:
            html = await self.managed_client.get_html(url, source="autosapo")
        else:
            logger.warning("[AUTOSAPO_RESILIENT] Managed client not available, using local playwright")
            html = await self._fetch_html_with_playwright(url)
            
        if not html:
            return []
            
        # Tentar parsing tradicional primeiro
        soup = BeautifulSoup(html, 'lxml')
        listings = self._parse_soup_to_listings(soup, max_listings)
        
        # Se não encontrar listings, usar IA como fallback
        if not listings and get_ai_scraper:
            logger.info("[AI_FALLBACK] CSS selectors retornaram 0 resultados, usando IA como fallback")
            try:
                ai_scraper = get_ai_scraper()
                listings = await ai_scraper.scrape_from_html("autosapo", html, max_listings)
                if listings:
                    logger.info(f"[SIMPLE_AI] IA extraiu {len(listings)} listings do AutoSapo")
            except Exception as e:
                logger.error(f"[SIMPLE_AI] Falha no fallback IA: {e}")
        
        # Se ainda não encontrar listings, usar regex como último recurso
        if not listings and get_regex_extractor:
            logger.info("[REGEX] IA falhou, usando regex como último recurso")
            try:
                regex_extractor = get_regex_extractor()
                listings = regex_extractor.extract_listings(html, "autosapo", max_listings)
                if listings:
                    logger.info(f"[REGEX] Regex extraiu {len(listings)} listings do AutoSapo")
            except Exception as e:
                logger.error(f"[REGEX] Falha no fallback regex: {e}")
        
        return listings

    async def _fetch_html_with_playwright(self, url: str) -> Optional[str]:
        from playwright.async_api import async_playwright
        import asyncio
        try:
             async with async_playwright() as p:
                 browser = await p.chromium.launch(headless=self.headless)
                 context = await browser.new_context(user_agent=random.choice(settings.user_agents))
                 page = await context.new_page()
                 await page.goto(url, timeout=self.timeout, wait_until='networkidle')
                 await asyncio.sleep(5) # AutoSapo has lighter protection but still needs settle time
                 html = await page.content()
                 await browser.close()
                 return html
        except Exception as e:
             logger.error(f"[PLAYWRIGHT] AutoSapo local fetch failed: {e}")
             return None

    def _parse_soup_to_listings(self, soup: Any, max_listings: int) -> List[Dict[str, object]]:
        listings = []
        # Fallback to general article searching or specific autosapo classes
        listing_elements = soup.find_all('div', class_='list-item') or soup.find_all('article')
        for idx, elem in enumerate(listing_elements[:max_listings]):
             listing = self._parse_listing_element(elem)
             if listing:
                 listings.append(listing)
        return listings
    
    def _build_url(self, vehicle_type: str, filters: Optional[Dict[str, object]]) -> str:
        """Build URL with query parameters"""
        url = f"{self.base_url}/{vehicle_type}"
        
        params = []
        
        if filters:
            if filters.get("brand"):
                brand = filters["brand"]
                if isinstance(brand, str):
                    params.append(f"marca={quote(brand)}")
            if filters.get("model"):
                model = filters["model"]
                if isinstance(model, str):
                    params.append(f"modelo={quote(model)}")
            if filters.get("min_price"):
                params.append(f"precoMin={filters['min_price']}")
            if filters.get("max_price"):
                params.append(f"precoMax={filters['max_price']}")
            if filters.get("min_year"):
                params.append(f"anoMin={filters['min_year']}")
            if filters.get("max_year"):
                params.append(f"anoMax={filters['max_year']}")
            if filters.get("max_km"):
                params.append(f"quilometrosMax={filters['max_km']}")
        
        if params:
            url += "?" + "&".join(params)
        
        return url
    
    def _handle_consent(self, page: Any) -> None:
        """Handle cookie consent popup"""
        try:
            accept_button = page.query_selector('button:has-text("Aceitar"), button:has-text("Aceitar tudo")')
            if accept_button:
                accept_button.click()
                time.sleep(1)
        except Exception as e:
            logger.debug(f"Cookie consent handling failed: {e}")

    def _scroll_to_load(self, page: Any) -> None:
        """Scroll page to load lazy-loaded content"""
        for i in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            time.sleep(random.uniform(0.5, 1.0))

        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

    def _parse_listings(self, soup: Any, max_listings: int) -> List[Dict[str, object]]:
        """Parse listings from BeautifulSoup object"""
        listings = []

        # AutoSapo listing structure (may vary, adjust selectors)
        listing_elements = soup.find_all('div', class_='anuncio') or soup.find_all('article', class_='listing-item')

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
        """Parse a single AutoSapo listing element"""
        try:
            # Extract using SelectorManager fallback system
            url, _ = self.selector_manager.extract_with_fallback(element, 'autosapo', 'url')
            if not url:
                link_elem = element.find('a', href=True)
                if not link_elem: return None
                url = link_elem.get('href', '')
                
            if isinstance(url, str) and url.startswith('/'):
                url = urljoin(self.base_url, url)
                
            title, _ = self.selector_manager.extract_with_fallback(element, 'autosapo', 'title')
            title = title or ""
            
            price, _ = self.selector_manager.extract_with_fallback(element, 'autosapo', 'price')
            location, _ = self.selector_manager.extract_with_fallback(element, 'autosapo', 'location')
            location = location or ""
            
            year, _ = self.selector_manager.extract_with_fallback(element, 'autosapo', 'year')
            km, _ = self.selector_manager.extract_with_fallback(element, 'autosapo', 'km')
            
            # Extract image manually
            img_elem = element.find('img')
            image_url = img_elem.get('src', '') if img_elem else ''
            
            # Extract source ID stably
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
            
        except Exception as e:
            logger.warning(f"Error parsing element: {e}")
            return None
    
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
                browser = await p.chromium.launch(headless=self.headless)
                import random
                context = await browser.new_context(
                    user_agent=random.choice(settings.user_agents),
                    viewport={"width": 1920, "height": 1080}
                )
                page = await context.new_page()
                
                # Navigate and wait
                await page.goto(url, timeout=30000)
                await asyncio.sleep(random.uniform(2, 4))
                
                html = await page.content()
                await browser.close()
                
                soup = BeautifulSoup(html, 'lxml')

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
                desc_elem = soup.find('div', class_='description') or soup.find('div', class_='descricao')
                if desc_elem:
                    details["description"] = desc_elem.get_text(strip=True)
                
                # Parameters - look for common patterns
                param_containers = soup.find_all('div', class_='specs') or soup.find_all('ul', class_='specifications')
                for container in param_containers:
                    items = container.find_all('li') if container.name == 'ul' else container.find_all('div')
                    for item in items:
                        label = item.find('span', class_='label') or item.find('strong')
                        value = item.find('span', class_='value') or item
                        if label and value:
                            label_text = label.get_text(strip=True).lower()
                            value_text = value.get_text(strip=True)
                            
                            if "ano" in label_text:
                                try:
                                    details["year"] = int(value_text)
                                except ValueError:
                                    logger.debug(f"Could not parse year: {value_text}")
                            elif "quilómetros" in label_text or "km" in label_text:
                                try:
                                    details["km"] = int(value_text.replace(' ', '').replace('km', ''))
                                except ValueError:
                                    logger.debug(f"Could not parse km: {value_text}")
                            elif "combustível" in label_text:
                                details["fuel_type"] = value_text.lower()
                            elif "caixa" in label_text:
                                details["transmission"] = value_text.lower()
                            elif "potência" in label_text:
                                try:
                                    details["horsepower"] = int(value_text.split()[0])
                                except (ValueError, IndexError):
                                    logger.debug(f"Could not parse horsepower: {value_text}")
                            elif "cilindrada" in label_text:
                                try:
                                    details["engine_size"] = int(value_text.split()[0])
                                except (ValueError, IndexError):
                                    logger.debug(f"Could not parse engine size: {value_text}")
                            elif "portas" in label_text:
                                try:
                                    details["doors"] = int(value_text)
                                except ValueError:
                                    logger.debug(f"Could not parse doors: {value_text}")
                            elif "lugares" in label_text:
                                try:
                                    details["seats"] = int(value_text)
                                except ValueError:
                                    logger.debug(f"Could not parse seats: {value_text}")
                            elif "cor" in label_text:
                                details["color"] = value_text
                
                # Images
                img_elems = soup.find_all('img', class_='gallery-image') or soup.select('.gallery img')
                details["images"] = [img.get('src', '') or img.get('data-src', '') for img in img_elems]
                
                # Seller info
                seller_elem = soup.find('div', class_='seller-info') or soup.find('div', class_='vendedor')
                if seller_elem:
                    name_elem = seller_elem.find('h4') or seller_elem.find('span', class_='name')
                    if name_elem:
                        details["seller_name"] = name_elem.get_text(strip=True)
                
                # Extras
                extras_items = soup.find_all('li', class_='extra') or soup.select('.extras li')
                details["extras"] = [item.get_text(strip=True) for item in extras_items]
                
                return details
                
        except Exception as e:
            logger.error(f"Error scraping listing details: {e}")
            return None
    
    def save_to_database(self, listings: List[Dict[str, object]], vehicle_type: str = "carros") -> None:
        """Save scraped listings to database"""
        logger.info(f"[PROGRESS] Saving {len(listings)} listings to database")
        saved_count = 0
        updated_count = 0
        
        with get_db_context() as db:
            from database.models import Vehicle, ScrapingLog
            
            log = ScrapingLog(
                source=Source.AUTOSAPO,
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
                        # Validate scraped data using pydantic model and custom validation
                        try:
                            # First validate with pydantic
                            ScrapedVehicle(**listing_data)  # type: ignore[arg-type]
                            
                            # Then validate with custom data validation
                            is_valid, validation_error = validate_scraped_data(listing_data)
                            if not is_valid:
                                logger.warning(f"Data validation failed for listing {listing_data.get('url')}: {validation_error}")
                                continue
                        except Exception as e:
                            logger.warning(f"Validation failed for listing {listing_data.get('url')}: {e}")
                            continue
                        
                        existing = db.query(Vehicle).filter(
                            Vehicle.url == listing_data.get("url")
                        ).first()
                        
                        title = listing_data.get("title", "")
                        if isinstance(title, str):
                            brand, model = self._parse_brand_model(title)
                        else:
                            brand, model = "Unknown", "Unknown"
                        
                        v_type = VehicleType.CAR if vehicle_type == "carros" else VehicleType.MOTO
                        
                        if existing:
                            existing.price = listing_data.get("price")  # type: ignore[assignment]
                            existing.last_seen = datetime.now(timezone.utc)  # type: ignore[assignment]
                            existing.scrape_count += 1  # type: ignore[assignment]
                            updated_count += 1
                        else:
                            vehicle = Vehicle(
                                source=Source.AUTOSAPO,
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
                            
                            fuel_type = listing_data.get("fuel_type", "")
                            if isinstance(fuel_type, str) and fuel_type:
                                fuel_type_lower = fuel_type.lower()
                                if "gasolina" in fuel_type:
                                    vehicle.fuel_type = FuelType.GASOLINE
                                elif "diesel" in fuel_type:
                                    vehicle.fuel_type = FuelType.DIESEL
                                elif "eletrico" in fuel_type or "eléctrico" in fuel_type:
                                    vehicle.fuel_type = FuelType.ELECTRIC
                                elif "hibrido" in fuel_type or "híbrido" in fuel_type:
                                    vehicle.fuel_type = FuelType.HYBRID
                                elif "gpl" in fuel_type:
                                    vehicle.fuel_type = FuelType.GPL

                            transmission = listing_data.get("transmission", "")
                            if isinstance(transmission, str) and transmission:
                                transmission = transmission.lower()
                                if "manual" in transmission:
                                    vehicle.transmission = Transmission.MANUAL
                                elif "automatic" in transmission or "automático" in transmission:
                                    vehicle.transmission = Transmission.AUTOMATIC
                            
                            db.add(vehicle)
                            saved_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Error saving listing: {e}")
                        continue
                
                log.status = "completed"  # type: ignore[assignment]
                log.finished_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                log.listings_scraped = saved_count
                log.listings_updated = updated_count  # type: ignore[assignment]
                
                db.commit()
                logger.info(f"[PROGRESS] Database save completed: {saved_count} new, {updated_count} updated")
                
            except Exception as e:
                log.status = "failed"  # type: ignore[assignment]
                log.error_message = str(e)  # type: ignore[assignment]
                log.finished_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                db.commit()
                raise
    
    def _parse_brand_model(self, title: str) -> tuple[str, str]:
        """Parse brand and model from title"""
        brands = [
            "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot", 
            "Citroën", "Ford", "Toyota", "Honda", "Nissan", "Hyundai", 
            "Kia", "Fiat", "Seat", "Skoda", "Volvo", "Mazda", "Mitsubishi",
            "Suzuki", "Dacia", "Opel", "Alfa Romeo", "Mini", "Smart"
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
    scraper = AutoSapoScraper()
    listings = scraper.scrape_listings("carros", max_listings=10)
    print(f"Scraped {len(listings)} listings")
