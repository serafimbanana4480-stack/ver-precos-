"""
Base scraper class for web scraping.
"""
import asyncio
import aiohttp
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
import random
import time

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base scraper class for web scraping."""
    
    def __init__(self, name: str, base_url: str = None):
        """Initialize base scraper."""
        self.name = name
        self.base_url = base_url
        self.session = None
        self.headers = self._get_default_headers()
        self.rate_limit_delay = 1.0
        self.max_retries = 3
        self.timeout = 30
        self.user_agents = self._get_user_agents()
        
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default HTTP headers."""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def _get_user_agents(self) -> List[str]:
        """Get list of user agents for rotation."""
        return [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
    
    async def initialize(self):
        """Initialize the scraper session."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info(f"Initialized scraper: {self.name}")
    
    async def close(self):
        """Close the scraper session."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info(f"Closed scraper: {self.name}")
    
    def rotate_user_agent(self):
        """Rotate user agent."""
        self.headers['User-Agent'] = random.choice(self.user_agents)
    
    async def make_request(self, url: str, method: str = 'GET', **kwargs) -> Optional[aiohttp.ClientResponse]:
        """Make HTTP request with retry logic."""
        
        if not self.session:
            await self.initialize()
        
        self.rotate_user_agent()
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.request(method, url, headers=self.headers, **kwargs) as response:
                    if response.status == 200:
                        return response
                    elif response.status == 429:  # Rate limited
                        retry_after = int(response.headers.get('Retry-After', self.rate_limit_delay * 2))
                        logger.warning(f"Rate limited. Retrying after {retry_after} seconds...")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        logger.error(f"HTTP {response.status} for URL: {url}")
                        return None
                        
            except asyncio.TimeoutError:
                logger.error(f"Timeout for URL: {url} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.rate_limit_delay * (attempt + 1))
                    continue
                    
            except Exception as e:
                logger.error(f"Error requesting {url}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.rate_limit_delay * (attempt + 1))
                    continue
        
        return None
    
    async def get_page_content(self, url: str) -> Optional[str]:
        """Get page content as string."""
        
        response = await self.make_request(url)
        if response:
            try:
                content = await response.text()
                await self.rate_limit()
                return content
            except Exception as e:
                logger.error(f"Error getting content from {url}: {e}")
                return None
        
        return None
    
    async def rate_limit(self):
        """Apply rate limiting."""
        await asyncio.sleep(self.rate_limit_delay)
    
    def extract_text(self, element, default: str = "") -> str:
        """Extract text from HTML element."""
        if element is None:
            return default
        
        text = element.get_text(strip=True)
        return text if text else default
    
    def extract_attribute(self, element, attribute: str, default: str = "") -> str:
        """Extract attribute from HTML element."""
        if element is None:
            return default
        
        value = element.get(attribute)
        return value if value else default
    
    def clean_price(self, price_text: str) -> Optional[float]:
        """Clean and convert price text to float."""
        if not price_text:
            return None
        
        # Remove currency symbols and whitespace
        cleaned = price_text.replace('€', '').replace('$', '').replace(' ', '').strip()
        
        # Remove thousands separators
        cleaned = cleaned.replace('.', '').replace(',', '')
        
        try:
            return float(cleaned)
        except ValueError:
            logger.warning(f"Could not convert price: {price_text}")
            return None
    
    def clean_mileage(self, mileage_text: str) -> Optional[int]:
        """Clean and convert mileage text to int."""
        if not mileage_text:
            return None
        
        # Extract numbers
        import re
        numbers = re.findall(r'\d+', mileage_text)
        
        if numbers:
            try:
                return int(numbers[0])
            except ValueError:
                logger.warning(f"Could not convert mileage: {mileage_text}")
                return None
        
        return None
    
    def clean_year(self, year_text: str) -> Optional[int]:
        """Clean and convert year text to int."""
        if not year_text:
            return None
        
        # Extract 4-digit year
        import re
        year_match = re.search(r'\b(19|20)\d{2}\b', year_text)
        
        if year_match:
            try:
                return int(year_match.group())
            except ValueError:
                logger.warning(f"Could not convert year: {year_text}")
                return None
        
        return None
    
    def parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse date text to datetime object."""
        if not date_text:
            return None
        
        # Common date patterns
        import re
        from datetime import datetime, timedelta
        
        # Handle relative dates
        if 'hoje' in date_text.lower():
            return datetime.now()
        elif 'ontem' in date_text.lower():
            return datetime.now() - timedelta(days=1)
        elif 'anteontem' in date_text.lower():
            return datetime.now() - timedelta(days=2)
        
        # Handle X days ago
        days_match = re.search(r'(\d+)\s*dias?', date_text.lower())
        if days_match:
            days = int(days_match.group(1))
            return datetime.now() - timedelta(days=days)
        
        # Handle X hours ago
        hours_match = re.search(r'(\d+)\s*horas?', date_text.lower())
        if hours_match:
            hours = int(hours_match.group(1))
            return datetime.now() - timedelta(hours=hours)
        
        # Try to parse standard date formats
        date_formats = [
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%Y-%m-%d',
            '%d/%m/%Y %H:%M',
            '%d-%m-%Y %H:%M'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_text.strip(), fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_text}")
        return None
    
    @abstractmethod
    async def search_listings(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for listings with given parameters."""
        pass
    
    @abstractmethod
    async def get_listing_details(self, listing_url: str) -> Dict[str, Any]:
        """Get detailed information for a specific listing."""
        pass
    
    @abstractmethod
    def get_search_urls(self, search_params: Dict[str, Any]) -> List[str]:
        """Get URLs to search based on parameters."""
        pass
    
    async def scrape_listings(self, search_params: Dict[str, Any], max_pages: int = 5) -> List[Dict[str, Any]]:
        """Scrape listings from multiple pages."""
        
        all_listings = []
        
        try:
            search_urls = self.get_search_urls(search_params)
            
            for page_num in range(min(max_pages, len(search_urls))):
                url = search_urls[page_num]
                logger.info(f"Scraping page {page_num + 1}: {url}")
                
                page_listings = await self.search_listings_from_url(url)
                all_listings.extend(page_listings)
                
                if not page_listings:
                    logger.info(f"No listings found on page {page_num + 1}, stopping")
                    break
                
                # Rate limiting between pages
                await self.rate_limit()
            
            logger.info(f"Scraped {len(all_listings)} listings from {self.name}")
            
        except Exception as e:
            logger.error(f"Error scraping listings from {self.name}: {e}")
        
        return all_listings
    
    async def search_listings_from_url(self, url: str) -> List[Dict[str, Any]]:
        """Search listings from a specific URL."""
        
        content = await self.get_page_content(url)
        if not content:
            return []
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            listings = []
            listing_elements = self.get_listing_elements(soup)
            
            for element in listing_elements:
                try:
                    listing = self.extract_listing_data(element)
                    if listing:
                        listing['source'] = self.name
                        listing['scraped_at'] = datetime.now().isoformat()
                        listings.append(listing)
                        
                except Exception as e:
                    logger.error(f"Error extracting listing from {self.name}: {e}")
                    continue
            
            return listings
            
        except Exception as e:
            logger.error(f"Error parsing content from {self.name}: {e}")
            return []
    
    @abstractmethod
    def get_listing_elements(self, soup) -> List:
        """Get listing elements from parsed HTML."""
        pass
    
    @abstractmethod
    def extract_listing_data(self, element) -> Dict[str, Any]:
        """Extract listing data from HTML element."""
        pass
    
    def validate_listing(self, listing: Dict[str, Any]) -> bool:
        """Validate listing data."""
        
        required_fields = ['make', 'model', 'price']
        
        for field in required_fields:
            if field not in listing or not listing[field]:
                return False
        
        # Validate price
        try:
            price = float(listing['price'])
            if price <= 0 or price > 1000000:
                return False
        except (ValueError, TypeError):
            return False
        
        return True
    
    def get_scraper_stats(self) -> Dict[str, Any]:
        """Get scraper statistics."""
        
        return {
            'name': self.name,
            'base_url': self.base_url,
            'rate_limit_delay': self.rate_limit_delay,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'user_agents_count': len(self.user_agents)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the scraper."""
        
        health_status = {
            'scraper': self.name,
            'status': 'healthy',
            'checks': {},
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Check if session is active
            if self.session is None:
                await self.initialize()
            
            # Test connectivity
            if self.base_url:
                response = await self.make_request(self.base_url)
                if response:
                    health_status['checks']['connectivity'] = 'pass'
                else:
                    health_status['checks']['connectivity'] = 'fail'
                    health_status['status'] = 'unhealthy'
            else:
                health_status['checks']['connectivity'] = 'skip'
            
            # Check rate limiting
            start_time = time.time()
            await self.rate_limit()
            rate_limit_time = time.time() - start_time
            health_status['checks']['rate_limit'] = 'pass'
            health_status['rate_limit_time'] = rate_limit_time
            
        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['error'] = str(e)
        
        return health_status
