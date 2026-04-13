"""
OLX.pt scraper using subprocess to call olx-tracker (Rust)
"""
import subprocess
import json
import logging
import random
import time
from typing import List, Dict, Optional
from datetime import datetime

from config import OLX_TRACKER_PATH, OLX_BASE_URL, USER_AGENTS, REQUEST_DELAY_SECONDS, MAX_RETRIES
from utils.retry import retry_network
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from database.db import get_db_context

logger = logging.getLogger(__name__)


class OLXScraper:
    """Scraper for OLX.pt using Rust olx-tracker"""
    
    def __init__(self):
        self.tracker_path = OLX_TRACKER_PATH
        self.base_url = OLX_BASE_URL
        
    @retry_network(max_attempts=3, min_wait=2, max_wait=10)
    def scrape_listings(
        self, 
        vehicle_type: str = "carros",
        max_listings: int = 100,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Scrape listings from OLX.pt
        
        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum number of listings to scrape
            filters: Optional filters (brand, model, min_price, max_price, etc.)
        
        Returns:
            List of vehicle dictionaries
        """
        logger.info(f"Starting OLX scrape for {vehicle_type}, max {max_listings} listings")
        
        try:
            # Build command for olx-tracker
            cmd = [
                self.tracker_path,
                "--url", f"{self.base_url}/{vehicle_type}",
                "--format", "json",
                "--limit", str(max_listings)
            ]
            
            # Add filters if provided
            if filters:
                if filters.get("brand"):
                    cmd.extend(["--brand", filters["brand"]])
                if filters.get("min_price"):
                    cmd.extend(["--min-price", str(filters["min_price"])])
                if filters.get("max_price"):
                    cmd.extend(["--max-price", str(filters["max_price"])])
                if filters.get("min_year"):
                    cmd.extend(["--min-year", str(filters["min_year"])])
                if filters.get("max_year"):
                    cmd.extend(["--max-year", str(filters["max_year"])])
            
            # Run olx-tracker
            logger.info(f"Running olx-tracker: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"olx-tracker failed: {result.stderr}")
                return []
            
            # Parse JSON output
            listings = json.loads(result.stdout)
            logger.info(f"Scraped {len(listings)} listings from OLX")
            
            return listings
            
        except subprocess.TimeoutExpired:
            logger.error("olx-tracker timed out")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse olx-tracker output: {e}")
            return []
        except FileNotFoundError:
            logger.error(f"olx-tracker not found at {self.tracker_path}")
            logger.info("Falling back to Python scraper")
            return self._scrape_with_playwright(vehicle_type, max_listings, filters)
        except Exception as e:
            logger.error(f"Error scraping OLX: {e}")
            return []
    
    def _scrape_with_playwright(
        self, 
        vehicle_type: str, 
        max_listings: int,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Fallback scraper using Playwright when olx-tracker is not available
        """
        try:
            from playwright.sync_api import sync_playwright
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("Playwright not installed, cannot scrape")
            return []
        
        listings = []
        url = f"{self.base_url}/{vehicle_type}"
        
        # Add query parameters for filters
        if filters:
            params = []
            if filters.get("brand"):
                params.append(f"q={filters['brand']}")
            if filters.get("min_price"):
                params.append(f"search[filter_float_price:from]={filters['min_price']}")
            if filters.get("max_price"):
                params.append(f"search[filter_float_price:to]={filters['max_price']}")
            if params:
                url += "?" + "&".join(params)
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1920, "height": 1080}
                )
                page = context.new_page()
                
                page.goto(url, timeout=30000)
                time.sleep(random.uniform(2, 4))  # Random delay
                
                # Scroll to load more listings
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(1)
                
                html = page.content()
                browser.close()
                
                soup = BeautifulSoup(html, 'lxml')
                
                # Parse listings (OLX structure)
                listing_elements = soup.find_all('div', {'data-cy': 'l-card'})
                
                for elem in listing_elements[:max_listings]:
                    try:
                        listing = self._parse_olx_element(elem)
                        if listing:
                            listings.append(listing)
                    except Exception as e:
                        logger.warning(f"Error parsing listing: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Playwright scraping error: {e}")
        
        logger.info(f"Scraped {len(listings)} listings with Playwright fallback")
        return listings
    
    def _parse_olx_element(self, element) -> Optional[Dict]:
        """Parse a single OLX listing element"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None
        
        # Extract basic information
        link_elem = element.find('a', href=True)
        if not link_elem:
            return None
        
        url = link_elem['href']
        if url.startswith('/'):
            url = self.base_url + url
        
        title_elem = element.find('h6')
        title = title_elem.text.strip() if title_elem else ""
        
        price_elem = element.find('p', {'data-testid': 'price'})
        price = None
        if price_elem:
            price_text = price_elem.text.strip()
            # Parse price (remove € and spaces)
            price = float(price_text.replace('€', '').replace(' ', '').replace('.', '').replace(',', '.'))
        
        # Extract details from data attributes
        data_id = element.get('data-id', '')
        
        # Extract location
        location_elem = element.find('p', {'data-testid': 'location-date'})
        location = location_elem.text.strip() if location_elem else ""
        
        # Extract image
        img_elem = element.find('img')
        image_url = img_elem.get('src', '') if img_elem else ''
        
        return {
            "source_id": data_id,
            "url": url,
            "title": title,
            "price": price,
            "location": location,
            "images": [image_url] if image_url else [],
            "raw_data": str(element)
        }
    
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
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=random.choice(USER_AGENTS))
                page = context.new_page()
                
                page.goto(url, timeout=30000)
                time.sleep(random.uniform(2, 3))
                
                html = page.content()
                browser.close()
                
                soup = BeautifulSoup(html, 'lxml')
                
                # Parse detailed information
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
    
    def save_to_database(self, listings: List[Dict], vehicle_type: str = "carros"):
        """Save scraped listings to database"""
        saved_count = 0
        updated_count = 0
        
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
                for listing_data in listings:
                    try:
                        # Check if listing already exists
                        existing = db.query(Vehicle).filter(
                            Vehicle.url == listing_data.get("url")
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
