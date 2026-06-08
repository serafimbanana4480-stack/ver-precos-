"""
OLX scraper for Portuguese car listings.
"""
import asyncio
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime

from .base_scraper import BaseScraper


class OLXScraper(BaseScraper):
    """OLX scraper for Portuguese car listings."""
    
    def __init__(self):
        """Initialize OLX scraper."""
        super().__init__(
            name="OLX",
            base_url="https://www.olx.pt"
        )
        self.search_endpoint = "/carros-motos-e-pecas/carros-usados"
        
    def get_search_urls(self, search_params: Dict[str, Any]) -> List[str]:
        """Get search URLs based on search parameters."""
        
        urls = []
        
        # Build base search URL
        url = self.search_endpoint
        
        # Add search filters
        query_parts = []
        
        # Location filter
        if 'location' in search_params:
            location = search_params['location'].lower().replace(' ', '-')
            query_parts.append(location)
        
        # Make filter
        if 'make' in search_params:
            make = search_params['make'].lower().replace(' ', '-')
            query_parts.append(make)
        
        # Price range
        if 'min_price' in search_params or 'max_price' in search_params:
            price_parts = []
            if 'min_price' in search_params:
                price_parts.append(f"preco-min-{search_params['min_price']}")
            if 'max_price' in search_params:
                price_parts.append(f"preco-max-{search_params['max_price']}")
            
            if price_parts:
                query_parts.append('?'.join(price_parts))
        
        # Year range
        if 'min_year' in search_params or 'max_year' in search_params:
            year_parts = []
            if 'min_year' in search_params:
                year_parts.append(f"ano-min-{search_params['min_year']}")
            if 'max_year' in search_params:
                year_parts.append(f"ano-max-{search_params['max_year']}")
            
            if year_parts:
                if query_parts:
                    query_parts[-1] += '&' + '&'.join(year_parts)
                else:
                    query_parts.append('?' + '&'.join(year_parts))
        
        # Build complete URL
        if query_parts:
            url = '/'.join([self.search_endpoint] + query_parts)
        
        # Add pagination
        max_pages = search_params.get('max_pages', 5)
        
        for page in range(max_pages):
            if page == 0:
                page_url = urljoin(self.base_url, url)
            else:
                page_url = f"{urljoin(self.base_url, url)}?o={page + 1}"
            
            urls.append(page_url)
        
        return urls
    
    def get_listing_elements(self, soup) -> List:
        """Get listing elements from OLX search page."""
        
        # OLX uses different CSS classes for listings
        selectors = [
            'div[data-cy="l-card"]',
            'div.ou8row',
            'div[data-testid="ad-card"]',
            'a[data-cy="ad-card"]'
        ]
        
        listings = []
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                listings = elements
                break
        
        return listings
    
    def extract_listing_data(self, element) -> Dict[str, Any]:
        """Extract listing data from OLX element."""
        
        listing = {}
        
        try:
            # Extract URL
            link_element = element.find('a') or element
            if link_element:
                listing['url'] = self.extract_attribute(link_element, 'href')
                if listing['url'] and not listing['url'].startswith('http'):
                    listing['url'] = urljoin(self.base_url, listing['url'])
            else:
                listing['url'] = None
            
            # Extract title
            title_selectors = ['h2', 'h3', '.title', '[data-cy="ad-title"]']
            title = self._extract_text_by_selectors(element, title_selectors)
            
            if title:
                listing['title'] = title
                # Extract make and model from title
                listing['make'], listing['model'] = self._extract_make_model_from_title(title)
            else:
                listing['title'] = None
                listing['make'] = None
                listing['model'] = None
            
            # Extract price
            price_selectors = ['.price', '[data-cy="ad-price"]', '.price-value']
            price_text = self._extract_text_by_selectors(element, price_selectors)
            listing['price'] = self.clean_price(price_text)
            
            # Extract mileage
            mileage_selectors = ['.mileage', '[data-cy="ad-mileage"]', '.details-item']
            mileage_text = self._extract_text_by_selectors(element, mileage_selectors)
            listing['mileage'] = self.clean_mileage(mileage_text)
            
            # Extract year
            year_selectors = ['.year', '[data-cy="ad-year"]', '.details-item']
            year_text = self._extract_text_by_selectors(element, year_selectors)
            listing['year'] = self.clean_year(year_text)
            
            # Extract fuel type
            fuel_selectors = ['.fuel-type', '[data-cy="ad-fuel"]', '.details-item']
            fuel_text = self._extract_text_by_selectors(element, fuel_selectors)
            listing['fuel_type'] = self._normalize_fuel_type(fuel_text)
            
            # Extract transmission
            transmission_selectors = ['.transmission', '[data-cy="ad-transmission"]', '.details-item']
            transmission_text = self._extract_text_by_selectors(element, transmission_selectors)
            listing['transmission'] = self._normalize_transmission(transmission_text)
            
            # Extract location
            location_selectors = ['.location', '[data-cy="ad-location"]', '.location-text']
            location_text = self._extract_text_by_selectors(element, location_selectors)
            listing['location'] = location_text.strip() if location_text else None
            
            # Extract image URL
            image_selectors = ['img', '.image img', '[data-cy="ad-image"]']
            image_element = self._find_element_by_selectors(element, image_selectors)
            if image_element:
                listing['image_url'] = self.extract_attribute(image_element, 'src')
            else:
                listing['image_url'] = None
            
            # Extract listing ID from URL
            if listing['url']:
                listing['listing_id'] = self._extract_listing_id_from_url(listing['url'])
            else:
                listing['listing_id'] = None
            
            # Set default values for missing fields
            listing['engine_size'] = None
            listing['condition'] = None
            listing['description'] = None
            listing['date_scraped'] = datetime.now().isoformat()
            
        except Exception as e:
            print(f"Error extracting OLX listing data: {e}")
            return None
        
        return listing if self.validate_listing(listing) else None
    
    def _extract_text_by_selectors(self, element, selectors: List[str]) -> str:
        """Extract text using multiple selectors."""
        
        for selector in selectors:
            found_element = element.select_one(selector)
            if found_element:
                text = self.extract_text(found_element)
                if text:
                    return text
        
        return ""
    
    def _find_element_by_selectors(self, element, selectors: List[str]):
        """Find element using multiple selectors."""
        
        for selector in selectors:
            found_element = element.select_one(selector)
            if found_element:
                return found_element
        
        return None
    
    def _extract_make_model_from_title(self, title: str) -> tuple:
        """Extract make and model from title."""
        
        if not title:
            return None, None
        
        # Common car makes in Portugal
        makes = [
            'Toyota', 'Volkswagen', 'Ford', 'Renault', 'Opel', 'Peugeot', 'Mercedes-Benz',
            'BMW', 'Audi', 'Nissan', 'Honda', 'Mitsubishi', 'Hyundai', 'Kia',
            'Seat', 'Skoda', 'Dacia', 'Fiat', 'Citroën', 'Mini', 'Suzuki',
            'Mazda', 'Subaru', 'Volvo', 'Jaguar', 'Land Rover', 'Porsche',
            'Lexus', 'Infiniti', 'Alfa Romeo', 'Ferrari', 'Lamborghini',
            'Maserati', 'Bentley', 'Rolls Royce', 'Aston Martin', 'McLaren'
        ]
        
        title_words = title.split()
        make = None
        model = None
        
        # Find make
        for i, word in enumerate(title_words):
            for make_name in makes:
                if make_name.lower() in word.lower():
                    make = make_name
                    # Model is usually the next word(s)
                    if i + 1 < len(title_words):
                        # Take next word as model
                        model = title_words[i + 1]
                        # Sometimes model is two words
                        if i + 2 < len(title_words) and len(title_words[i + 2]) > 2:
                            model += f" {title_words[i + 2]}"
                    break
            if make:
                break
        
        return make, model
    
    def _normalize_fuel_type(self, fuel_text: str) -> str:
        """Normalize fuel type."""
        
        if not fuel_text:
            return "Unknown"
        
        fuel_lower = fuel_text.lower()
        
        if 'gasolina' in fuel_lower or 'gasol' in fuel_lower:
            return "Gasoline"
        elif 'diesel' in fuel_lower or 'gasóleo' in fuel_lower:
            return "Diesel"
        elif 'elétrico' in fuel_lower or 'electric' in fuel_lower:
            return "Electric"
        elif 'híbrido' in fuel_lower or 'hybrid' in fuel_lower:
            return "Hybrid"
        elif 'gpl' in fuel_lower:
            return "LPG"
        elif 'gnv' in fuel_lower:
            return "CNG"
        else:
            return "Unknown"
    
    def _normalize_transmission(self, transmission_text: str) -> str:
        """Normalize transmission type."""
        
        if not transmission_text:
            return "Unknown"
        
        trans_lower = transmission_text.lower()
        
        if 'automático' in trans_lower or 'automatic' in trans_lower:
            return "Automatic"
        elif 'manual' in trans_lower:
            return "Manual"
        elif 'cvt' in trans_lower:
            return "CVT"
        else:
            return "Unknown"
    
    def _extract_listing_id_from_url(self, url: str) -> str:
        """Extract listing ID from URL."""
        
        if not url:
            return None
        
        # OLX URLs usually have ID in the path
        # Example: https://www.olx.pt/anuncio/toyota-yaris-hybrid-2018-ID12345.html
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.split('/')
            
            # Look for part that contains ID
            for part in path_parts:
                if 'id' in part.lower():
                    # Extract numeric ID
                    id_match = re.search(r'(\d+)', part)
                    if id_match:
                        return id_match.group(1)
            
            # If no ID found, use last path part
            if path_parts:
                last_part = path_parts[-1]
                id_match = re.search(r'(\d+)', last_part)
                if id_match:
                    return id_match.group(1)
            
        except Exception:
            pass
        
        return None
    
    async def get_listing_details(self, listing_url: str) -> Dict[str, Any]:
        """Get detailed information for a specific listing."""
        
        content = await self.get_page_content(listing_url)
        if not content:
            return {}
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            details = {}
            
            # Extract description
            desc_selectors = ['.description', '[data-cy="ad-description"]', '.description-text']
            description = self._extract_text_by_selectors(soup, desc_selectors)
            details['description'] = description
            
            # Extract detailed specifications
            specs_selectors = ['.specifications', '.details', '.features']
            specs_element = self._find_element_by_selectors(soup, specs_selectors)
            
            if specs_element:
                # Extract engine size
                engine_text = self._extract_text_by_selectors(specs_element, ['.engine', '.motor'])
                details['engine_size'] = self._clean_engine_size(engine_text)
                
                # Extract condition
                condition_text = self._extract_text_by_selectors(specs_element, ['.condition', '.estado'])
                details['condition'] = self._normalize_condition(condition_text)
            
            # Extract seller information
            seller_selectors = ['.seller', '.user-info', '[data-cy="ad-seller"]']
            seller_element = self._find_element_by_selectors(soup, seller_selectors)
            
            if seller_element:
                details['seller_name'] = self._extract_text_by_selectors(seller_element, ['.name', '.seller-name'])
                details['seller_type'] = self._extract_text_by_selectors(seller_element, ['.type', '.seller-type'])
            
            # Extract all images
            image_selectors = ['.gallery img', '.photos img', '[data-cy="ad-image"]']
            image_elements = soup.select(','.join(image_selectors))
            details['image_urls'] = [
                self.extract_attribute(img, 'src') 
                for img in image_elements 
                if self.extract_attribute(img, 'src')
            ]
            
            details['scraped_at'] = datetime.now().isoformat()
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting OLX listing details: {e}")
            return {}
    
    def _clean_engine_size(self, engine_text: str) -> Optional[float]:
        """Clean engine size text."""
        
        if not engine_text:
            return None
        
        # Extract engine size in liters
        engine_match = re.search(r'(\d+\.?\d*)\s*l', engine_text.lower())
        if engine_match:
            try:
                return float(engine_match.group(1))
            except ValueError:
                pass
        
        return None
    
    def _normalize_condition(self, condition_text: str) -> str:
        """Normalize condition."""
        
        if not condition_text:
            return "Unknown"
        
        condition_lower = condition_text.lower()
        
        if 'excelente' in condition_lower or 'perfeito' in condition_lower:
            return "Excellent"
        elif 'bom' in condition_lower or 'ótimo' in condition_lower:
            return "Good"
        elif 'regular' in condition_lower or 'aceitável' in condition_lower:
            return "Fair"
        elif 'mau' in condition_lower or 'ruim' in condition_lower:
            return "Poor"
        else:
            return "Unknown"
    
    async def search_listings(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for listings with given parameters."""
        
        urls = self.get_search_urls(search_params)
        all_listings = []
        
        for url in urls:
            page_listings = await self.search_listings_from_url(url)
            all_listings.extend(page_listings)
        
        return all_listings
