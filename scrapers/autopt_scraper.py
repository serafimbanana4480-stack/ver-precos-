"""
Auto.pt scraper using Playwright and AI fallback
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
import hashlib

from config import settings
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from database.db import get_db_context
from utils.retry import retry_network
from validation.schemas import ScrapedVehicle, VehicleType as SchemaVehicleType
from utils.observability import track_scrape
from scrapers.browser_pool import get_browser_pool
from scrapers.ai_extractor import get_ai_extractor

logger = logging.getLogger(__name__)

class AutoPtScraper:
    """Scraper for Auto.pt using Playwright and AI"""
    
    def __init__(self) -> None:
        self.base_url = "https://www.auto.pt"
        self.timeout = getattr(settings, 'playwright_timeout', 30000)
        self.headless = getattr(settings, 'playwright_headless', True)
        
    @track_scrape(source='autopt')
    @retry_network(max_attempts=3, min_wait=2, max_wait=10)
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        scrape_details: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scrape listings from Auto.pt
        """
        logger.info(f"[AUTOPT] Starting scrape for {vehicle_type}, max {max_listings} listings")
        
        url = self._build_url(vehicle_type, filters)
        
        # We'll use the AI-first approach for better resilience as Auto.pt is new
        html = await self._fetch_html_with_playwright(url)
        
        if not html:
            logger.error("[AUTOPT] Failed to fetch HTML")
            return []
            
        # Use AI Extractor
        ai_extractor = get_ai_extractor()
        listings = await ai_extractor.extract_from_html(html, "autopt", max_listings)
        
        if not listings:
            logger.info("[AUTOPT] AI extractor returned 0 results, using BS4 fallback")
            listings = self._parse_with_bs4(html, vehicle_type, max_listings)
            
        if not listings:
            return []
            
        logger.info(f"[AUTOPT] Extracted {len(listings)} listings")
        
        # Normalize and add source-specific data
        for listing in listings:
            if not listing.get('source'):
                listing['source'] = 'autopt'
            if not listing.get('source_id'):
                listing['source_id'] = hashlib.md5(listing.get('url', '').encode()).hexdigest()
            if not listing.get('vehicle_type'):
                listing['vehicle_type'] = vehicle_type
        
        return listings

    def _parse_with_bs4(self, html: str, vehicle_type: str, max_listings: int) -> List[Dict[str, Any]]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        listings = []
        
        # Identify common listing patterns for Auto.pt
        cards = soup.select('.vehicle-card, .listing-item, article')
        for card in cards:
            try:
                link = card.select_one('a[href*="/anuncio/"]')
                if not link: continue
                
                url = link.get('href')
                if url.startswith('/'):
                    url = urljoin(self.base_url, url)
                
                title_elem = card.select_one('h2, h3, .title')
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                price_elem = card.select_one('.price, [class*="price"]')
                price_text = price_elem.get_text(strip=True) if price_elem else "0"
                price = self._parse_price(price_text)
                
                img_elem = card.select_one('img')
                img_url = img_elem.get('src') or img_elem.get('data-src') if img_elem else ""
                
                # Brand/Model extraction from title
                brand, model = self._parse_brand_model(title)

                listings.append({
                    "title": title,
                    "url": url,
                    "price": price,
                    "brand": brand,
                    "model": model,
                    "images": [img_url] if img_url else []
                })
                
                if len(listings) >= max_listings:
                    break
            except Exception as e:
                continue
        
        return listings

    def _parse_brand_model(self, title: str) -> tuple[str, str]:
        """Parse brand and model from title"""
        brands = [
            "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz",
            "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot", 
            "Citroën", "Ford", "Toyota", "Honda", "Nissan", "Hyundai", 
            "Kia", "Fiat", "Seat", "Skoda", "Volvo", "Mazda", "Mitsubishi",
            "Suzuki", "Dacia", "Opel", "Mini", "Smart"
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

    def _parse_price(self, text: str) -> float:
        try:
            digits = re.sub(r'[^\d]', '', text)
            return float(digits) if digits else 0.0
        except:
            return 0.0

    async def _fetch_html_with_playwright(self, url: str) -> Optional[str]:
        from utils.playwright_stealth import apply_stealth_async
        try:
            pool = get_browser_pool()
            page = await pool.new_page("autopt")
            
            try:
                await apply_stealth_async(page)
            except Exception as e:
                logger.warning(f"Failed to apply stealth: {e}")
            
            await page.goto(url, timeout=self.timeout, wait_until='networkidle')
            
            # Wait for any vehicle listing elements
            try:
                await page.wait_for_selector('a[href*="/anuncio/"], .vehicle-card, .listing-item', timeout=10000)
            except Exception:
                pass
                
            # Scroll to load more
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(0.5)
                
            html = await page.content()
            await page.close()
            return html
        except Exception as e:
             logger.error(f"[PLAYWRIGHT] Auto.pt fetch failed: {e}")
             return None

    def _build_url(self, vehicle_type: str, filters: Optional[Dict[str, Any]]) -> str:
        """Build URL for Auto.pt"""
        # Base Auto.pt search URL pattern
        path = "/carros-usados" if vehicle_type == "carros" else "/motos-usadas"
        url = f"{self.base_url}{path}"
        
        # Add basic filters if present
        params = []
        if filters:
            if filters.get('brand'):
                params.append(f"marca={quote(str(filters['brand']))}")
            if filters.get('model'):
                params.append(f"modelo={quote(str(filters['model']))}")
        
        if params:
            url += "?" + "&".join(params)
            
        return url
