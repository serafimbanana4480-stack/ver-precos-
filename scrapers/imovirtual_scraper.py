"""
ImoVirtual Scraper
"""
from __future__ import annotations
import logging
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from urllib.parse import urljoin, quote

from config import settings
from validation.scraped_models import ScrapedVehicle
from scrapers.schema import parse_price_evidence
logger = logging.getLogger(__name__)


class ImoVirtualScraper:
    """
    Scraper for ImoVirtual vehicle listings
    """
    
    def __init__(self):
        # Imovirtual is an independent source; do not derive it from the
        # AutoSapo environment setting.
        self.base_url = "https://www.imovirtual.com"
        
    def scrape_listings(self, max_listings: int = 50, vehicle_type: str = "carros", filters: Optional[Dict[str, object]] = None) -> List[ScrapedVehicle]:
        """
        Scrape vehicle listings from ImoVirtual
        
        Args:
            max_listings: Maximum number of listings to scrape
            vehicle_type: 'carros' or 'motos'
            filters: Optional filters (brand, model, min_price, max_price, year)
            
        Returns:
            List of scraped vehicles
        """
        logger.info(f"Starting ImoVirtual scrape, max_listings={max_listings}")
        
        vehicles = []
        
        try:
            # Search URL for cars
            path = "/comprar/carros" if vehicle_type == "carros" else "/comprar/motos"
            search_url = f"{self.base_url}{path}"
            
            query_params = []
            if filters:
                if filters.get("brand"):
                    query_params.append(f"search[brand]={quote(str(filters['brand']))}")
                if filters.get("model"):
                    query_params.append(f"search[model]={quote(str(filters['model']))}")
                if filters.get("min_price"):
                    query_params.append(f"search[price_from]={filters['min_price']}")
                if filters.get("max_price"):
                    query_params.append(f"search[price_to]={filters['max_price']}")
                if filters.get("min_year"):
                    query_params.append(f"search[year_from]={filters['min_year']}")
                if filters.get("max_year"):
                    query_params.append(f"search[year_to]={filters['max_year']}")
            if query_params:
                search_url += "?" + "&".join(query_params)
            
            import requests
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(search_url, headers=headers, timeout=settings.request_timeout)
            if response.status_code == 404:
                raise RuntimeError(
                    "source_unavailable: Imovirtual no longer exposes vehicle listings at this route"
                )
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            
            listing_elements = soup.find_all("article", class_=lambda c: isinstance(c, str) and "listing" in c.lower())
            for idx, element in enumerate(listing_elements[:max_listings]):
                try:
                    vehicle = self._parse_listing(element, vehicle_type)
                    if vehicle:
                        vehicles.append(vehicle)
                        logger.debug(f"ImoVirtual scraped vehicle {idx + 1}/{min(len(listing_elements), max_listings)}")
                except Exception as e:
                    logger.warning(f"ImoVirtual error parsing listing {idx}: {e}")
                    continue
            
            logger.info(f"ImoVirtual scrape completed: {len(vehicles)} vehicles scraped")
            
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"ImoVirtual scraping failed: {e}")
        
        return vehicles
    
    def _parse_listing(self, element, vehicle_type: str) -> Optional[ScrapedVehicle]:
        try:
            title = ""
            title_elem = element.find(["h2", "h3", "a", "span"], class_=lambda c: isinstance(c, str) and "title" in c.lower())
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            price = None
            price_elem = element.find(class_=lambda c: isinstance(c, str) and "price" in c.lower())
            if price_elem:
                price = self._parse_price(price_elem.get_text(strip=True))
            
            url = ""
            link_elem = element.find("a", href=True)
            if link_elem:
                href = link_elem["href"]
                url = href if href.startswith("http") else urljoin(self.base_url, href)
            
            if not url or not price:
                return None
            
            return ScrapedVehicle(
                source="imovirtual",
                # Python's hash() is randomized per process, so it cannot be
                # used to reconcile the same advert across scrape cycles.
                source_id=hashlib.sha256(url.encode("utf-8")).hexdigest()[:32],
                url=url,
                title=title,
                brand=self._extract_brand(title),
                model=self._extract_model(title),
                price=price,
                vehicle_type=vehicle_type,
            )
        except Exception as e:
            logger.debug(f"ImoVirtual parse listing failed: {e}")
            return None
    
    def _parse_price(self, price_text: str) -> Optional[float]:
        evidence = parse_price_evidence(price_text)
        if evidence.kind.value != "total" or evidence.currency != "EUR":
            return None
        return evidence.value
    
    def _extract_brand(self, title: str) -> Optional[str]:
        if not title:
            return None
        brands = ['BMW', 'Mercedes', 'Audi', 'Volkswagen', 'Toyota', 'Renault', 'Peugeot', 'Citroën', 'Ford', 'Opel', 'Nissan', 'Hyundai', 'Kia']
        title_lower = title.lower()
        for brand in brands:
            if brand.lower() in title_lower:
                return brand
        return None
    
    def _extract_model(self, title: Optional[str]) -> Optional[str]:
        if not title:
            return None
        parts = title.split()
        return parts[1] if len(parts) > 1 else None


# Legacy compatibility alias.
ImovirtualScraper = ImoVirtualScraper

# Singleton instance
imovirtual_scraper = ImoVirtualScraper()
