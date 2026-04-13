"""
Standvirtual.com scraper using Playwright with stealth
"""
import logging
import random
import time
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin, quote

from config import (
    STANDVIRTUAL_BASE_URL, USER_AGENTS, REQUEST_DELAY_SECONDS, 
    MAX_RETRIES, PLAYWRIGHT_HEADLESS, PLAYWRIGHT_TIMEOUT
)
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from database.db import get_db_context
from utils.retry import retry_network
from utils.deduplication import is_url_processed, mark_url_processed

logger = logging.getLogger(__name__)


class StandvirtualScraper:
    """Scraper for Standvirtual.com using Playwright"""
    
    def __init__(self):
        self.base_url = STANDVIRTUAL_BASE_URL
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
        Scrape listings from Standvirtual.com
        
        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum number of listings to scrape
            filters: Optional filters (brand, model, min_price, max_price, etc.)
        
        Returns:
            List of vehicle dictionaries
        """
        logger.info(f"Starting Standvirtual scrape for {vehicle_type}, max {max_listings} listings")
        
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
                # Launch browser with stealth
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1920, "height": 1080},
                    locale="pt-PT",
                    timezone_id="Europe/Lisbon"
                )
                
                # Add stealth scripts
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                
                page = context.new_page()
                
                # Navigate to URL
                page.goto(url, timeout=self.timeout)
                time.sleep(random.uniform(2, 4))
                
                # Handle cookie consent if present
                self._handle_consent(page)
                
                # Scroll to load all listings
                self._scroll_to_load(page)
                
                # Get page content
                html = page.content()
                browser.close()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html, 'lxml')
                listings = self._parse_listings(soup, max_listings)
                
                logger.info(f"Scraped {len(listings)} listings from Standvirtual")
                
            except Exception as e:
                logger.error(f"Error scraping Standvirtual: {e}")
        
        return listings
    
    def _build_url(self, vehicle_type: str, filters: Optional[Dict]) -> str:
        """Build URL with query parameters"""
        url = f"{self.base_url}/{vehicle_type}"
        
        params = []
        
        if filters:
            if filters.get("brand"):
                params.append(f"make={quote(filters['brand'])}")
            if filters.get("model"):
                params.append(f"model={quote(filters['model'])}")
            if filters.get("min_price"):
                params.append(f"pricemin={filters['min_price']}")
            if filters.get("max_price"):
                params.append(f"pricemax={filters['max_price']}")
            if filters.get("min_year"):
                params.append(f"yearmin={filters['min_year']}")
            if filters.get("max_year"):
                params.append(f"yearmax={filters['max_year']}")
            if filters.get("max_km"):
                params.append(f"mileagefrom=0&mileageto={filters['max_km']}")
        
        if params:
            url += "?" + "&".join(params)
        
        return url
    
    def _handle_consent(self, page):
        """Handle cookie consent popup"""
        try:
            # Look for accept cookies button
            accept_button = page.query_selector('button:has-text("Aceitar"), button:has-text("Accept")')
            if accept_button:
                accept_button.click()
                time.sleep(1)
        except:
            pass
    
    @retry_network(max_attempts=3, min_wait=2, max_wait=10)
    def _scroll_to_load(self, page):
        """Scroll page to load lazy-loaded content"""
        for i in range(5):
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(random.uniform(0.5, 1.0))
        
        # Scroll back to top
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
    
    def _parse_listings(self, soup, max_listings: int) -> List[Dict]:
        """Parse listings from BeautifulSoup object"""
        listings = []
        
        # Standvirtual listing structure
        listing_elements = soup.find_all('article', class_='offer-item')
        
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
        """Parse a single Standvirtual listing element"""
        try:
            # Extract link
            link_elem = element.find('a', class_='offer-title__link')
            if not link_elem:
                return None
            
            url = link_elem.get('href', '')
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
            
            # Extract title
            title = link_elem.get('title', '').strip()
            
            # Extract price
            price_elem = element.find('span', class_='offer-price__number')
            price = None
            if price_elem:
                price_text = price_elem.text.strip()
                # Parse price (remove €, spaces, dots)
                price_text = price_text.replace('€', '').replace(' ', '').replace('.', '')
                try:
                    price = float(price_text.replace(',', '.'))
                except ValueError:
                    pass
            
            # Extract year
            year_elem = element.find('li', {'data-code': 'year'})
            year = None
            if year_elem:
                year_text = year_elem.text.strip()
                try:
                    year = int(year_text)
                except ValueError:
                    pass
            
            # Extract km
            km_elem = element.find('li', {'data-code': 'mileage'})
            km = None
            if km_elem:
                km_text = km_elem.text.strip()
                try:
                    km = int(km_text.replace(' ', '').replace('km', ''))
                except ValueError:
                    pass
            
            # Extract location
            location_elem = element.find('span', class_='item-location')
            location = location_elem.text.strip() if location_elem else ""
            
            # Extract image
            img_elem = element.find('img', class_='offer-item__photo')
            image_url = img_elem.get('data-src', '') if img_elem else ''
            
            # Extract seller type
            seller_elem = element.find('span', class_='seller-tag')
            seller_type = seller_elem.text.strip() if seller_elem else ""
            
            # Extract source ID from URL
            source_id = url.split('/')[-1].replace('.html', '') if url else ""
            
            return {
                "source_id": source_id,
                "url": url,
                "title": title,
                "price": price,
                "year": year,
                "km": km,
                "location": location,
                "images": [image_url] if image_url else [],
                "seller_type": seller_type,
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
                
                # Handle consent
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
                img_elems = soup.find_all('img', class_='offer-gallery__img')
                details["images"] = [img.get('data-src', '') for img in img_elems if img.get('data-src')]
                
                # Seller info
                seller_elem = soup.find('div', class_='seller-info')
                if seller_elem:
                    name_elem = seller_elem.find('h4', class_='seller-name')
                    if name_elem:
                        details["seller_name"] = name_elem.get_text(strip=True)
                    
                    type_elem = seller_elem.find('span', class_='seller-type')
                    if type_elem:
                        details["seller_type"] = type_elem.get_text(strip=True)
                
                # Extras
                extras_items = soup.find_all('li', class_='offer-features__item')
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
            
            # Create scraping log entry
            log = ScrapingLog(
                source=Source.STANDVIRTUAL,
                status="running"
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            
            try:
                for listing_data in listings:
                    try:
                        url = listing_data.get("url")
                        
                        # Check deduplication (in-memory)
                        if is_url_processed(url):
                            logger.debug(f"Skipping already processed URL: {url}")
                            continue
                        
                        # Check if listing already exists in database
                        existing = db.query(Vehicle).filter(
                            Vehicle.url == url
                        ).first()
                        
                        # Parse brand and model from title
                        title = listing_data.get("title", "")
                        brand, model = self._parse_brand_model(title)
                        
                        # Determine vehicle type enum
                        v_type = VehicleType.CAR if vehicle_type == "carros" else VehicleType.MOTO
                        
                        if existing:
                            # Update existing listing
                            existing.price = listing_data.get("price")
                            existing.last_seen = datetime.utcnow()
                            existing.scrape_count += 1
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
                            
                            # Map fuel type
                            fuel_type = listing_data.get("fuel_type", "")
                            if fuel_type:
                                fuel_type = fuel_type.lower()
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
                            
                            # Map transmission
                            transmission = listing_data.get("transmission", "")
                            if transmission:
                                transmission = transmission.lower()
                                if "manual" in transmission:
                                    vehicle.transmission = Transmission.MANUAL
                                elif "automatic" in transmission or "automático" in transmission:
                                    vehicle.transmission = Transmission.AUTOMATIC
                            
                            db.add(vehicle)
                            saved_count += 1
                            mark_url_processed(url)
                        
                    except Exception as e:
                        logger.warning(f"Error saving listing: {e}")
                        continue
                
                # Update scraping log
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
    scraper = StandvirtualScraper()
    listings = scraper.scrape_listings("carros", max_listings=10)
    print(f"Scraped {len(listings)} listings")
