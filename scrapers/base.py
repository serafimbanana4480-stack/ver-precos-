"""
Abstract Base Scraper - all scrapers inherit from this.
Eliminates duplicated _parse_brand_model, fuel/transmission mapping, rate limiting, etc.
"""
from __future__ import annotations
import asyncio
import hashlib
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from core.settings import settings
from scrapers.browser_pool import get_browser_pool

logger = logging.getLogger(__name__)

FUEL_MAP: Dict[str, str] = {
    "gasolina": "gasolina", "gasoline": "gasolina", "petrol": "gasolina",
    "diesel": "diesel", "gasóleo": "diesel",
    "elétrico": "eletrico", "eléctrico": "eletrico", "electric": "eletrico",
    "híbrido": "hibrido", "híbrido plug-in": "hibrido", "hybrid": "hibrido",
    "gpl": "gpl", "gnv": "gpl",
    "gas natural": "gas natural",
}

TRANSMISSION_MAP: Dict[str, str] = {
    "manual": "manual", "manual": "manual",
    "automático": "automatico", "automático": "automatico",
    "automatic": "automatico",
    "semi-automático": "semi-automatico", "semi-automatic": "semi-automatico",
}

BRANDS: List[str] = [
    "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
    "Citroën", "Ford", "Toyota", "Honda", "Nissan", "Hyundai",
    "Kia", "Fiat", "Seat", "Skoda", "Volvo", "Mazda", "Mitsubishi",
    "Suzuki", "Dacia", "Opel", "Alfa Romeo", "Mini", "Smart", "Land Rover",
    "Jeep", "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla", "Polestar",
    "Yamaha", "Kawasaki", "Ducati", "KTM", "Aprilia", "Triumph",
    "Harley Davidson", "BMW Motorrad", "Husqvarna", "Beta", "Gas Gas",
]


class BaseScraper(ABC):
    def __init__(self, source_name: str):
        self.source_name = source_name
        self._user_agents = settings.user_agents

    @abstractmethod
    async def scrape_listings(
        self, vehicle_type: str, max_listings: int = 50, scrape_details: bool = True
    ) -> List[Dict[str, Any]]:
        ...

    async def _rate_limit(self) -> None:
        delay = settings.request_delay_seconds + random.uniform(0, settings.request_delay_jitter)
        await asyncio.sleep(delay)

    def _make_id(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def _ensure_source_id(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        if not listing.get("source_id"):
            listing["source_id"] = self._make_id(listing.get("url", ""))
        listing["source"] = self.source_name
        return listing

    def parse_brand_model(self, title: str) -> tuple[str, str]:
        if not title:
            return "Unknown", title
        title_lower = title.lower()
        for brand in BRANDS:
            idx = title_lower.find(brand.lower())
            if idx != -1:
                model = title[idx + len(brand):].strip()
                return brand, model
        parts = title.split(maxsplit=1)
        return (parts[0], parts[1]) if len(parts) >= 2 else (title, "")

    def normalize_fuel(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        raw_lower = raw.lower().strip()
        for key, val in FUEL_MAP.items():
            if key in raw_lower:
                return val
        return None

    def normalize_transmission(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        raw_lower = raw.lower().strip()
        for key, val in TRANSMISSION_MAP.items():
            if key in raw_lower:
                return val
        return None

    def build_vehicle_dict(
        self, url: str, title: str, price: float, vehicle_type: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        brand, model = self.parse_brand_model(title)
        vehicle = {
            "source": self.source_name,
            "source_id": self._make_id(url),
            "url": url,
            "title": title,
            "brand": brand,
            "model": model,
            "price": price,
            "vehicle_type": vehicle_type,
            "first_seen": datetime.now(timezone.utc).isoformat(),
        }
        vehicle.update(kwargs)
        return vehicle


class PlaywrightScraper(BaseScraper):
    def __init__(self, source_name: str):
        super().__init__(source_name)
        self._pool = None

    async def _get_page(self):
        if self._pool is None:
            self._pool = get_browser_pool()
        return await self._pool.new_page(self.source_name)
