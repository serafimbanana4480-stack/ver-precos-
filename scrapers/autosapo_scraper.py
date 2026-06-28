"""
AutoSapo.pt scraper using Playwright
"""
from __future__ import annotations
import logging
import random
import time
import asyncio
import re
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
from utils.observability import track_scrape

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
        self.headless = getattr(settings, 'playwright_headless', True)
        self.timeout = getattr(settings, 'playwright_timeout', 30000)
        self.proxy_pool = get_proxy_pool()
        self.selector_manager = get_selector_manager()
        self.managed_client = get_managed_client() if get_managed_client else None
        
    @track_scrape(source='autosapo')
    @with_circuit_breaker(_autosapo_circuit_breaker, "AutoSapo scraping")
    @retry_network(max_attempts=3, min_wait=2, max_wait=10)  # type: ignore[misc]
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 100,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False
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
        logger.info(f"[PROGRESS] AI scraping priority: {getattr(settings, 'ai_scraper_priority', 'fallback')}")
        
        url = self._build_url(vehicle_type, page=1, filters=filters)
        
        # AI-First Approach (if configured as primary)
        if getattr(settings, 'ai_scraping_enabled', False) and getattr(settings, 'ai_scraper_priority', 'fallback') == "primary" and get_ai_scraper:
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

        if scrape_details and listings:
            listings = await self._enrich_listings_with_details(listings)

        return listings

    async def _enrich_listings_with_details(self, listings: List[Dict[str, object]], max_concurrent: int = 5) -> List[Dict[str, object]]:
        """Enrich AutoSapo listing cards with details - concurrent for speed."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_one(listing: Dict[str, object]) -> Dict[str, object]:
            needs_details = not listing.get("description") or not listing.get("km") or not listing.get("year")
            listing_url = listing.get("url")
            if needs_details and isinstance(listing_url, str) and listing_url.startswith("http"):
                async with semaphore:
                    details = await self.scrape_listing_details(listing_url)
                    if details:
                        listing.update(details)
                    await asyncio.sleep(random.uniform(0.3, 0.6))
            return listing
        
        tasks = [enrich_one(lst.copy()) for lst in listings]
        return await asyncio.gather(*tasks)

    async def _scrape_with_resilient_flow(
        self,
        vehicle_type: str,
        max_listings: int,
        filters: Optional[Dict[str, object]] = None
    ) -> List[Dict[str, object]]:
        from bs4 import BeautifulSoup
        all_listings = []
        page = 1
        
        while len(all_listings) < max_listings:
            url = self._build_url(vehicle_type, page, filters)
            logger.info(f"[AUTOSAPO] Scraping page {page}: {url}")
            
            # Use local playwright first (fast and reliable)
            html = await self._fetch_html_with_playwright(url)
            
            if not html and self.managed_client:
                # Fallback to managed_client
                html = await self.managed_client.get_html(url, source="autosapo")
            
            if not html:
                break
                
            soup = BeautifulSoup(html, 'lxml')
            page_listings = self._parse_soup_to_listings(soup, max_listings - len(all_listings))
            
            if not page_listings:
                logger.info(f"[AUTOSAPO] No more listings found at page {page}")
                break
                
            all_listings.extend(page_listings)
            logger.info(f"[AUTOSAPO] Total listings so far: {len(all_listings)}")
            
            if len(page_listings) < 10:
                break
                
            page += 1
            if page > 10:
                break
        
        return all_listings[:max_listings]

    async def _fetch_html_with_playwright(self, url: str) -> Optional[str]:
        from bs4 import BeautifulSoup
        from utils.playwright_stealth import apply_stealth_async
        from scrapers.browser_pool import get_browser_pool
        try:
            pool = get_browser_pool()
            page = await pool.new_page("autosapo")
            
            try:
                await apply_stealth_async(page)
            except Exception as e:
                logger.warning(f"Failed to apply stealth: {e}")
            
            await page.goto(url, timeout=self.timeout, wait_until='networkidle')
            # Use wait_for instead of fixed 5s sleep
            try:
                await page.wait_for_selector('article.vehicle-card, .vehicle-card', timeout=4000)
            except Exception:
                pass
            
            html = await page.content()
            await page.close()
            return html
        except Exception as e:
             logger.error(f"[PLAYWRIGHT] AutoSapo local fetch failed: {e}")
             return None

    def _parse_soup_to_listings(self, soup: Any, max_listings: int) -> List[Dict[str, object]]:
        listings = []
        # Modern AutoSapo uses article.vehicle-card
        listing_elements = soup.find_all('article', class_='vehicle-card')
        if not listing_elements:
            # Fallback to description divs
            listing_elements = soup.find_all('div', class_='description')

        for idx, elem in enumerate(listing_elements[:max_listings]):
             listing = self._parse_listing_element(elem)
             if listing:
                 listings.append(listing)

        if listings:
            return listings

        fallback_listings = self._parse_links_fallback(soup, max_listings)
        if fallback_listings:
            logger.info(f"[AUTOSAPO_FALLBACK] Link parser extracted {len(fallback_listings)} listings")
            return fallback_listings

        return listings

    def _parse_links_fallback(self, soup: Any, max_listings: int) -> List[Dict[str, object]]:
        """Fallback parser for changed AutoSapo HTML structures."""
        listings: List[Dict[str, object]] = []
        seen_urls: set[str] = set()

        for link in soup.select("a[href*='/anuncio/'], a[href*='/carros/']"):
            href = link.get("href", "")
            if not isinstance(href, str) or not href:
                continue

            url = href if href.startswith("http") else urljoin(self.base_url, href)
            if not url.startswith("http") or url in seen_urls:
                continue

            container = link.find_parent(["article", "li", "div"]) or link
            text_block = container.get_text(" ", strip=True)

            title = (link.get_text(" ", strip=True) or link.get("title", "") or "").strip()
            if len(title) < 5:
                title = self._extract_title_from_block(text_block)
            if not title:
                continue

            price = self._extract_price_from_text(text_block)
            year = self._extract_year_from_text(text_block)
            km = self._extract_km_from_text(text_block)

            location = ""
            location_elem = container.select_one("[class*='location'], [class*='local'], [class*='city']")
            if location_elem:
                location = location_elem.get_text(" ", strip=True)

            img_elem = container.select_one("img")
            image_url = ""
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src") or ""
                if isinstance(image_url, str) and image_url.startswith("/"):
                    image_url = urljoin(self.base_url, image_url)

            brand, model = self._parse_brand_model(title)

            import hashlib
            source_id = hashlib.md5(url.encode()).hexdigest()

            listings.append({
                "source": "AUTOSAPO",
                "source_id": source_id,
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "location": location,
                "images": [image_url] if isinstance(image_url, str) and image_url.startswith("http") else [],
                "description": "",
            })
            seen_urls.add(url)

            if len(listings) >= max_listings:
                break

        return listings

    def _extract_title_from_block(self, text: str) -> str:
        parts = [p.strip() for p in re.split(r"[\|\-]", text) if p.strip()]
        if not parts:
            return ""
        return parts[0][:120]

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

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            digits = re.sub(r"\D", "", str(value))
            return int(digits) if digits else None
        except Exception:
            return None

    def _extract_price_from_text(self, text: str) -> Optional[float]:
        match = re.search(r"(\d{1,3}(?:[\.\s]\d{3})+|\d{3,6})\s*€", text)
        if not match:
            return None
        digits = re.sub(r"\D", "", match.group(1))
        return float(digits) if digits else None

    def _extract_year_from_text(self, text: str) -> Optional[int]:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
        return int(match.group(1)) if match else None

    def _extract_km_from_text(self, text: str) -> Optional[int]:
        match = re.search(r"(\d{1,3}(?:[\.\s]\d{3})+|\d{2,6})\s*km", text, re.IGNORECASE)
        if not match:
            return None
        digits = re.sub(r"\D", "", match.group(1))
        return int(digits) if digits else None
    
    def _build_url(self, vehicle_type: str, page: int = 1, filters: Optional[Dict[str, object]] = None) -> str:
        """Build URL with query parameters"""
        # AutoSapo uses /carros-usados for listings
        url = f"{self.base_url}/carros-usados"
        if page > 1:
            url += f"/p-{page}"
        
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
        """Parse a single AutoSapo listing element from current DOM"""
        try:
            # Resolve the container: if element is a div.description, find parent article
            container = element
            if element.name == 'div' and 'description' in (element.get('class') or []):
                container = element.find_parent('article') or element.find_parent('div')

            # Find link with /carro-usado/
            link_elem = (container or element).find('a', href=re.compile(r'/carro-usado/'))
            if not link_elem:
                return None
            url = link_elem.get('href', '')
            if isinstance(url, str) and url.startswith('/'):
                url = urljoin(self.base_url, url)
            if not url.startswith('http'):
                return None

            # Use description div if available
            desc = (container or element).find('div', class_='description') or element

            # Title from h3 or link text
            title_elem = desc.find('h3')
            title = title_elem.get_text(strip=True) if title_elem else link_elem.get_text(strip=True)
            if not title:
                return None

            # Price from div.price
            price = None
            price_elem = desc.find('div', class_='price')
            if price_elem:
                price = self._safe_float(price_elem.get_text(strip=True))
            if price is None:
                price = self._extract_price_from_text(desc.get_text(strip=True))

            # Year, km, fuel from div.features > ul > li
            year = None
            km = None
            fuel_type = None

            features = desc.find('div', class_='features')
            if features:
                ul = features.find('ul')
                if ul:
                    for li in ul.find_all('li'):
                        text = li.get_text(strip=True)
                        if re.match(r'^\d{4}$', text):
                            year = int(text)
                        elif 'km' in text.lower():
                            km_val = re.sub(r"\D", "", text)
                            if km_val:
                                km = int(km_val)
                        else:
                            fuel_type = text

            # Image
            img_elem = (container or element).find('img')
            image_url = ''
            if img_elem:
                image_url = img_elem.get('data-src') or img_elem.get('src') or ''
                if isinstance(image_url, str) and image_url.startswith('/'):
                    image_url = urljoin(self.base_url, image_url)

            import hashlib
            source_id = hashlib.md5(str(url).encode()).hexdigest()
            brand, model = self._parse_brand_model(title)

            return {
                "source": "autosapo",
                "source_id": source_id,
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "location": "",
                "images": [image_url] if image_url and image_url.startswith('http') else [],
                "fuel_type": fuel_type or "",
                "description": "",
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
            from utils.playwright_stealth import apply_stealth_async
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
                try:
                    await apply_stealth_async(page)
                except Exception as e:
                    logger.warning(f"Failed to apply stealth: {e}")
                
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
                        
                        v_type = VehicleType.carros if vehicle_type == "carros" else VehicleType.motos
                        
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
                log.listings_found = len(listings)  # type: ignore[assignment]
                log.listings_added = saved_count  # type: ignore[assignment]
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
            # Multi-word brands first
            "Alfa Romeo", "Aston Martin", "Land Rover", "Rolls-Royce",
            "CF Moto", "CF-Moto", "CFMOTO", "Royal Enfield", "Harley-Davidson", "Harley Davidson",
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
    scraper = AutoSapoScraper()
    listings = scraper.scrape_listings("carros", max_listings=10)
    print(f"Scraped {len(listings)} listings")
