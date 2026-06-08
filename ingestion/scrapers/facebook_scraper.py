"""
Facebook Marketplace scraper for car listings.
"""
import asyncio
import re
import json
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime

from .base_scraper import BaseScraper


class FacebookScraper(BaseScraper):
    """Facebook Marketplace scraper for car listings."""
    
    def __init__(self):
        """Initialize Facebook scraper."""
        super().__init__(
            name="Facebook",
            base_url="https://www.facebook.com"
        )
        self.marketplace_endpoint = "/marketplace"
        self.requires_auth = True  # Facebook requires authentication
        
    def get_search_urls(self, search_params: Dict[str, Any]) -> List[str]:
        """Get search URLs based on search parameters."""
        
        urls = []
        
        # Facebook Marketplace search URL
        url = f"{self.marketplace_endpoint}/search"
        
        # Build query parameters
        query_params = {}
        
        # Search query
        if 'query' in search_params:
            query_params['query'] = search_params['query']
        else:
            # Build query from make and model
            query_parts = []
            if 'make' in search_params:
                query_parts.append(search_params['make'])
            if 'model' in search_params:
                query_parts.append(search_params['model'])
            if query_parts:
                query_params['query'] = ' '.join(query_parts)
        
        # Category filter (cars)
        query_params['category'] = 'vehicles'
        
        # Location filter
        if 'location' in search_params:
            query_params['location'] = search_params['location']
        
        # Price range
        if 'min_price' in search_params:
            query_params['minPrice'] = search_params['min_price']
        if 'max_price' in search_params:
            query_params['maxPrice'] = search_params['max_price']
        
        # Condition filter
        if 'condition' in search_params:
            query_params['condition'] = search_params['condition']
        
        # Build query string
        if query_params:
            query_string = '&'.join([f"{k}={v}" for k, v in query_params.items()])
            url += f"?{query_string}"
        
        # Add pagination
        max_pages = search_params.get('max_pages', 5)
        
        for page in range(max_pages):
            if page == 0:
                page_url = urljoin(self.base_url, url)
            else:
                # Facebook uses cursor-based pagination
                cursor = self._generate_cursor(page)
                if '?' in url:
                    page_url = f"{urljoin(self.base_url, url)}&cursor={cursor}"
                else:
                    page_url = f"{urljoin(self.base_url, url)}?cursor={cursor}"
            
            urls.append(page_url)
        
        return urls
    
    def get_listing_elements(self, soup) -> List:
        """Get listing elements from Facebook Marketplace search page."""
        
        # Facebook uses different CSS classes for listings
        selectors = [
            '[data-testid="marketplace-search-item"]',
            '.marketplace-search-result',
            '[role="article"]',
            '.x1yztbdb'
        ]
        
        listings = []
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                listings = elements
                break
        
        return listings
    
    def extract_listing_data(self, element) -> Dict[str, Any]:
        """Extract listing data from Facebook element."""
        
        listing = {}
        
        try:
            # Facebook Marketplace often loads data via JavaScript
            # Try to extract from JSON data embedded in the page
            json_data = self._extract_json_data(element)
            
            if json_data:
                listing = self._parse_json_listing(json_data)
            else:
                # Fallback to HTML parsing
                listing = self._parse_html_listing(element)
            
            # Set Facebook-specific fields
            listing['source'] = 'Facebook'
            listing['scraped_at'] = datetime.now().isoformat()
            
        except Exception as e:
            print(f"Error extracting Facebook listing data: {e}")
            return None
        
        return listing if self.validate_listing(listing) else None
    
    def _extract_json_data(self, element) -> Optional[Dict]:
        """Extract JSON data from element."""
        
        # Look for JSON data in script tags or data attributes
        json_selectors = [
            '[data-testid="marketplace-search-item"]',
            '[data-visualcompletion="ignore"]'
        ]
        
        for selector in json_selectors:
            found_element = element.select_one(selector)
            if found_element:
                # Try to extract from data attributes
                for attr in found_element.attrs:
                    if 'data' in attr.lower():
                        try:
                            json_str = found_element[attr]
                            if json_str.startswith('{') or json_str.startswith('['):
                                return json.loads(json_str)
                        except:
                            continue
        
        return None
    
    def _parse_json_listing(self, json_data: Dict) -> Dict[str, Any]:
        """Parse listing data from JSON."""
        
        listing = {}
        
        # Extract basic information from JSON structure
        # This will depend on Facebook's actual JSON structure
        if 'listing' in json_data:
            listing_data = json_data['listing']
            
            listing['title'] = listing_data.get('title')
            listing['price'] = self.clean_price(listing_data.get('price', ''))
            listing['url'] = listing_data.get('url')
            listing['image_url'] = listing_data.get('image', {}).get('uri')
            
            # Extract location
            location_data = listing_data.get('location', {})
            listing['location'] = location_data.get('reverse_geocode', {}).get('city_name')
            
            # Extract seller information
            seller_data = listing_data.get('seller', {})
            listing['seller_name'] = seller_data.get('name')
            listing['seller_type'] = 'dealer' if seller_data.get('is_professional') else 'individual'
            
            # Extract listing ID
            listing['listing_id'] = listing_data.get('id')
            
            # Extract attributes (make, model, year, etc.)
            attributes = listing_data.get('marketplace_search_item_attributes', [])
            for attr in attributes:
                if 'structured_attribute' in attr:
                    struct_attr = attr['structured_attribute']
                    if struct_attr.get('semantic_name') == 'make':
                        listing['make'] = struct_attr.get('text_content')
                    elif struct_attr.get('semantic_name') == 'model':
                        listing['model'] = struct_attr.get('text_content')
                    elif struct_attr.get('semantic_name') == 'year':
                        listing['year'] = self.clean_year(struct_attr.get('text_content'))
                    elif struct_attr.get('semantic_name') == 'mileage':
                        listing['mileage'] = self.clean_mileage(struct_attr.get('text_content'))
                    elif struct_attr.get('semantic_name') == 'fuel_type':
                        listing['fuel_type'] = self._normalize_fuel_type(struct_attr.get('text_content'))
                    elif struct_attr.get('semantic_name') == 'transmission':
                        listing['transmission'] = self._normalize_transmission(struct_attr.get('text_content'))
        
        # Set defaults for missing fields
        for field in ['make', 'model', 'year', 'mileage', 'fuel_type', 'transmission', 'engine_size', 'condition', 'description']:
            if field not in listing:
                listing[field] = None
        
        return listing
    
    def _parse_html_listing(self, element) -> Dict[str, Any]:
        """Parse listing data from HTML element."""
        
        listing = {}
        
        # Extract title
        title_selectors = ['[data-testid="marketplace-search-item-title"]', '.title', 'h3', 'h2']
        listing['title'] = self._extract_text_by_selectors(element, title_selectors)
        
        if listing['title']:
            listing['make'], listing['model'] = self._extract_make_model_from_title(listing['title'])
        
        # Extract price
        price_selectors = ['[data-testid="marketplace-search-item-price"]', '.price']
        price_text = self._extract_text_by_selectors(element, price_selectors)
        listing['price'] = self.clean_price(price_text)
        
        # Extract location
        location_selectors = ['[data-testid="marketplace-search-item-location"]', '.location']
        location_text = self._extract_text_by_selectors(element, location_selectors)
        listing['location'] = location_text.strip() if location_text else None
        
        # Extract image
        image_selectors = ['[data-testid="marketplace-search-item-image"] img', 'img']
        image_element = self._find_element_by_selectors(element, image_selectors)
        if image_element:
            listing['image_url'] = self.extract_attribute(image_element, 'src')
        else:
            listing['image_url'] = None
        
        # Extract URL
        link_element = element.find('a')
        if link_element:
            listing['url'] = self.extract_attribute(link_element, 'href')
            if listing['url'] and not listing['url'].startswith('http'):
                listing['url'] = urljoin(self.base_url, listing['url'])
        else:
            listing['url'] = None
        
        # Extract listing ID from URL or data attributes
        listing['listing_id'] = self._extract_listing_id_from_element(element)
        
        # Set defaults for missing fields
        for field in ['make', 'model', 'year', 'mileage', 'fuel_type', 'transmission', 'engine_size', 'condition', 'description']:
            if field not in listing:
                listing[field] = None
        
        return listing
    
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
        
        # Common car makes
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
                        model = title_words[i + 1]
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
    
    def _extract_listing_id_from_element(self, element) -> str:
        """Extract listing ID from element."""
        
        # Try to extract from data attributes
        for attr in element.attrs:
            if 'id' in attr.lower():
                id_value = element[attr]
                if id_value and id_value.isdigit():
                    return id_value
        
        # Try to extract from URL
        link_element = element.find('a')
        if link_element:
            url = self.extract_attribute(link_element, 'href')
            if url:
                return self._extract_listing_id_from_url(url)
        
        return None
    
    def _extract_listing_id_from_url(self, url: str) -> str:
        """Extract listing ID from URL."""
        
        if not url:
            return None
        
        # Facebook URLs are complex, try to extract ID from various patterns
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.split('/')
            
            # Look for numeric ID in path
            for part in path_parts:
                if part.isdigit():
                    return part
            
            # Try to extract from query parameters
            if parsed.query:
                query_params = parse_qs(parsed.query)
                if 'listing_id' in query_params:
                    return query_params['listing_id'][0]
                if 'id' in query_params:
                    return query_params['id'][0]
            
        except Exception:
            pass
        
        return None
    
    def _generate_cursor(self, page: int) -> str:
        """Generate cursor for pagination."""
        
        # Facebook uses complex cursor strings
        # This is a simplified implementation
        return f"cursor_{page}"
    
    async def get_listing_details(self, listing_url: str) -> Dict[str, Any]:
        """Get detailed information for a specific listing."""
        
        content = await self.get_page_content(listing_url)
        if not content:
            return {}
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            details = {}
            
            # Facebook Marketplace details are often loaded via JavaScript
            # Try to extract from embedded JSON data
            json_data = self._extract_page_json_data(soup)
            
            if json_data:
                details = self._parse_detail_json(json_data)
            else:
                # Fallback to HTML parsing
                details = self._parse_detail_html(soup)
            
            details['scraped_at'] = datetime.now().isoformat()
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting Facebook listing details: {e}")
            return {}
    
    def _extract_page_json_data(self, soup) -> Optional[Dict]:
        """Extract JSON data from page."""
        
        # Look for JSON data in script tags
        scripts = soup.find_all('script')
        
        for script in scripts:
            if script.string:
                # Look for JSON patterns
                if '"marketplace_listing"' in script.string:
                    try:
                        # Extract JSON from script
                        json_match = re.search(r'({.*})', script.string)
                        if json_match:
                            return json.loads(json_match.group(1))
                    except:
                        continue
        
        return None
    
    def _parse_detail_json(self, json_data: Dict) -> Dict[str, Any]:
        """Parse detailed listing data from JSON."""
        
        details = {}
        
        # This would depend on Facebook's actual JSON structure
        # Implementation would need to be adapted based on actual data
        
        return details
    
    def _parse_detail_html(self, soup) -> Dict[str, Any]:
        """Parse detailed listing data from HTML."""
        
        details = {}
        
        # Extract description
        desc_selectors = ['.description', '[data-testid="listing-description"]']
        details['description'] = self._extract_text_by_selectors(soup, desc_selectors)
        
        # Extract seller information
        seller_selectors = ['.seller-info', '[data-testid="seller-name"]']
        details['seller_name'] = self._extract_text_by_selectors(soup, seller_selectors)
        
        # Extract images
        image_selectors = ['.gallery img', '.listing-photos img']
        image_elements = soup.select(','.join(image_selectors))
        details['image_urls'] = [
            self.extract_attribute(img, 'src') 
            for img in image_elements 
            if self.extract_attribute(img, 'src')
        ]
        
        return details
    
    async def search_listings(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for listings with given parameters."""
        
        urls = self.get_search_urls(search_params)
        all_listings = []
        
        for url in urls:
            page_listings = await self.search_listings_from_url(url)
            all_listings.extend(page_listings)
        
        return all_listings
    
    async def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with Facebook (placeholder implementation)."""
        
        # Facebook authentication is complex and would require proper implementation
        # This is a placeholder
        logger.warning("Facebook authentication not implemented - requires manual login")
        return False
    
    def set_authentication_token(self, token: str):
        """Set authentication token."""
        
        # Set authentication token for API requests
        self.headers['Authorization'] = f'Bearer {token}'
        logger.info("Facebook authentication token set")
    
    def get_scraper_stats(self) -> Dict[str, Any]:
        """Get scraper statistics."""
        
        stats = super().get_scraper_stats()
        stats['requires_auth'] = self.requires_auth
        stats['marketplace_endpoint'] = self.marketplace_endpoint
        
        return stats
