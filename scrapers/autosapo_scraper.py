"""
AutoSapo.pt scraper using Playwright
"""
import logging
import random
import time
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin, quote

from config import (
    AUTOSAPO_BASE_URL, USER_AGENTS, REQUEST_DELAY_SECONDS,
    MAX_RETRIES, PLAYWRIGHT_HEADLESS, PLAYWRIGHT_TIMEOUT
)
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from database.db import get_db_context
from utils.retry import retry_network
from validation.scraped_models import ScrapedVehicle

logger = logging.getLogger(__name__)


class AutoSapoScraper:
    """Scraper for AutoSapo.pt using Playwright"""
    
    def __init__(self):
        self.base_url = AUTOSAPO_BASE_URL
        self.headless = PLAYWRIGHT_HEADLESS
        self.timeout = PLAYWRIGHT_TIMEOUT
        
    @retry_network(max_attempts=3, min_wait=2, max_wait=10)
    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 100,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Scrape listings from AutoSapo.pt
        
        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum number of listings to scrape
            filters: Optional filters (brand, model, min_price, max_price, etc.)
        
        Returns:
            List of vehicle dictionaries
        """
        logger.info(f"Starting AutoSapo scrape for {vehicle_type}, max {max_listings} listings")
        
        try:
            from playwright.sync_api import sync_playwright
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("Playwright not installed")
            return []
        
        listings = []
        
        # Build URL with filters
        url = self._build_url(vehicle_type, filters)
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1920, "height": 1080},
                    locale="pt-PT",
                    timezone_id="Europe/Lisbon"
                )
                
                # Add stealth
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                
                page = context.new_page()
                
                page.goto(url, timeout=self.timeout)
                time.sleep(random.uniform(2, 4))
                
                # Handle cookie consent
                self._handle_consent(page)
                
                # Scroll to load listings
                self._scroll_to_load(page)
                
                html = page.content()
                browser.close()
                
                soup = BeautifulSoup(html, 'lxml')
                listings = self._parse_listings(soup, max_listings)
                
                logger.info(f"Scraped {len(listings)} listings from AutoSapo")
                
            except Exception as e:
                logger.error(f"Error scraping AutoSapo: {e}")
        
        return listings
    
    def _build_url(self, vehicle_type: str, filters: Optional[Dict]) -> str:
        """Build URL with query parameters"""
        url = f"{self.base_url}/{vehicle_type}"
        
        params = []
        
        if filters:
            if filters.get("brand"):
                params.append(f"marca={quote(filters['brand'])}")
            if filters.get("model"):
                params.append(f"modelo={quote(filters['model'])}")
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
    
    def _handle_consent(self, page):
        """Handle cookie consent popup"""
        try:
            accept_button = page.query_selector('button:has-text("Aceitar"), button:has-text("Aceitar tudo")')
            if accept_button:
                accept_button.click()
                time.sleep(1)
        except:
            pass
    
    def _scroll_to_load(self, page):
        """Scroll page to load lazy-loaded content"""
        for i in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            time.sleep(random.uniform(0.5, 1.0))
        
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
    
    def _parse_listings(self, soup, max_listings: int) -> List[Dict]:
        """Parse listings from BeautifulSoup object"""
        listings = []
        
        # AutoSapo listing structure (may vary, adjust selectors)
        listing_elements = soup.find_all('div', class_='anuncio') or soup.find_all('article', class_='listing-item')
        
        for elem in listing_elements[:max_listings]:
            try:
                listing = self._parse_listing_element(elem)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.warning(f"Error parsing listing: {e}")
                continue
        
        return listings
    
    def _parse_listing_element(self, element) -> Optional[Dict]:
        """Parse a single AutoSapo listing element"""
        try:
            # Extract link
            link_elem = element.find('a', href=True)
            if not link_elem:
                return None
            
            url = link_elem.get('href', '')
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
            
            # Extract title
            title_elem = element.find('h3') or element.find('h2')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Extract price
            price_elem = element.find('span', class_='price') or element.find('span', class_='preco')
            price = None
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_text = price_text.replace('€', '').replace(' ', '').replace('.', '')
                try:
                    price = float(price_text.replace(',', '.'))
                except ValueError:
                    pass
            
            # Extract year
            year_elem = element.find('span', class_='year') or element.find('span', class_='ano')
            year = None
            if year_elem:
                year_text = year_elem.get_text(strip=True)
                try:
                    year = int(year_text)
                except ValueError:
                    pass
            
            # Extract km
            km_elem = element.find('span', class_='km') or element.find('span', class_='quilometros')
            km = None
            if km_elem:
                km_text = km_elem.get_text(strip=True)
                try:
                    km = int(km_text.replace(' ', '').replace('km', ''))
                except ValueError:
                    pass
            
            # Extract location
            location_elem = element.find('span', class_='location') or element.find('span', class_='localizacao')
            location = location_elem.get_text(strip=True) if location_elem else ""
            
            # Extract image
            img_elem = element.find('img')
            image_url = img_elem.get('src', '') if img_elem else ''
            
            # Extract source ID from URL
            source_id = url.split('/')[-1] if url else ""
            
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
    
    def scrape_listing_details(self, url: str) -> Optional[Dict]:
        """Scrape detailed information from a single listing page"""
        try:
            from playwright.sync_api import sync_playwright
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("Playwright not installed")
            return None
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1920, "height": 1080}
                )
                page = context.new_page()
                
                page.goto(url, timeout=self.timeout)
                time.sleep(random.uniform(2, 3))
                
                self._handle_consent(page)
                
                html = page.content()
                browser.close()
                
                soup = BeautifulSoup(html, 'lxml')
                
                details = {
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
                            elif "lugares" in label_text:
                                try:
                                    details["seats"] = int(value_text)
                                except ValueError:
                                    pass
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
    
    def save_to_database(self, listings: List[Dict], vehicle_type: str = "carros"):
        """Save scraped listings to database"""
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
                for listing_data in listings:
                    try:
                        # Validate scraped data using pydantic model
                        try:
                            ScrapedVehicle(**listing_data)
                        except Exception as e:
                            logger.warning(f"Validation failed for listing {listing_data.get('url')}: {e}")
                            continue
                        
                        existing = db.query(Vehicle).filter(
                            Vehicle.url == listing_data.get("url")
                        ).first()
                        
                        title = listing_data.get("title", "")
                        brand, model = self._parse_brand_model(title)
                        
                        v_type = VehicleType.CAR if vehicle_type == "carros" else VehicleType.MOTO
                        
                        if existing:
                            existing.price = listing_data.get("price")
                            existing.last_seen = datetime.utcnow()
                            existing.scrape_count += 1
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
                                image_count=len(listing_data.get("images", [])),
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
                            if fuel_type:
                                fuel_type = fuel_type.lower()
                                if "gasolina" in fuel_type:
                                    vehicle.fuel_type = FuelType.GASOLINE
                                elif "diesel" in fuel_type:
                                    vehicle.fuel_type = FuelType.DIESEL
                                elif "eletrico" in fuel_type:
                                    vehicle.fuel_type = FuelType.ELECTRIC
                                elif "hibrido" in fuel_type:
                                    vehicle.fuel_type = FuelType.HYBRID
                                elif "gpl" in fuel_type:
                                    vehicle.fuel_type = FuelType.GPL
                            
                            transmission = listing_data.get("transmission", "")
                            if transmission:
                                transmission = transmission.lower()
                                if "manual" in transmission:
                                    vehicle.transmission = Transmission.MANUAL
                                elif "automatic" in transmission:
                                    vehicle.transmission = Transmission.AUTOMATIC
                            
                            db.add(vehicle)
                            saved_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Error saving listing: {e}")
                        continue
                
                log.status = "completed"
                log.finished_at = datetime.utcnow()
                log.listings_found = len(listings)
                log.listings_added = saved_count
                log.listings_updated = updated_count
                
                db.commit()
                logger.info(f"Saved {saved_count} new listings, updated {updated_count} existing")
                
            except Exception as e:
                log.status = "failed"
                log.error_message = str(e)
                log.finished_at = datetime.utcnow()
                db.commit()
                raise
    
    def _parse_brand_model(self, title: str) -> tuple:
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
