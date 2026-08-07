"""
Wallapop Lightweight Scraper — requests only, no Playwright.
Site: wallapop.com (ES/PT) — Mobile-first classified ads platform.

Uses the Wallapop public search API:
  https://api.wallapop.com/v2/listings/search

Wallapop covers private sellers and dealers across Spain and Portugal.
Prices in EUR (ES) / EUR (PT). Data is well-structured via API.
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

FUEL_MAP = {
    "gasolina": "gasolina", "petrol": "gasolina", "essence": "gasolina",
    "diesel": "diesel", "gazole": "diesel",
    "electrico": "eletrico", "eléctrico": "eletrico", "electric": "eletrico",
    "hibrido": "hibrido", "híbrido": "hibrido", "hybrid": "hibrido",
    "plug-in": "hibrido", "hibrido enchufable": "hibrido",
    "gpl": "gpl", "lpg": "gpl",
    "gas natural": "gas natural", "cng": "gas natural",
}
TRANS_MAP = {
    "manual": "manual", "manuela": "manual", "boite manuelle": "manual",
    "automático": "automatico", "automático": "automatico", "automatique": "automatico",
    "automatic": "automatico", "cambio automatico": "automatico",
    "semi-automático": "semi-automatico", "semi-automatic": "semi-automatico",
    "robotizada": "semi-automatico", "robotisee": "semi-automatico",
}
BRANDS = [
    "Alfa Romeo", "Abarth", "Audi", "Bmw", "Citroen", "Citroën",
    "Cupra", "Dacia", "DS", "DS Automobiles", "Fiat", "Ford",
    "Honda", "Hyundai", "Jaguar", "Jeep", "Kia", "Land Rover",
    "Lexus", "Mazda", "Mitsubishi", "Nissan", "Opel", "Peugeot",
    "Porsche", "Renault", "Seat", "Skoda", "Smart", "Suzuki",
    "Tesla", "Toyota", "Volkswagen", "Vag", "Volvo", "Mini", "MG",
    "Mercedes", "Mercedes-Benz", "Infiniti",
]


class WallapopLightweight:
    """Lightweight scraper for Wallapop via public API."""

    BASE_URL = "https://api.wallapop.com"
    WEB_URL = "https://es.wallapop.com"
    USER_AGENTS = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/605.1.15",
        "Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/113.0 Firefox/113.0",
    )

    def __init__(self) -> None:
        self.session = requests.Session()
        self._rotate_ua()

    def _rotate_ua(self) -> None:
        self.session.headers.update({
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "es-ES,es;q=0.9,pt-PT,pt;q=0.8",
            "Referer": f"{self.WEB_URL}/",
        })

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("[WALLAPOP] Starting scrape, max %d", max_listings)
        listings: List[Dict[str, Any]] = []
        seen: set[str] = set()

        country = "es"
        if filters and filters.get("country"):
            country = str(filters["country"])
        web_url = "https://pt.wallapop.com" if country == "pt" else self.WEB_URL

        category = "coches"
        if vehicle_type.lower().startswith("moto"):
            category = "motos"

        offset = 0
        while len(listings) < max_listings:
            data = self._fetch_search(category, offset)
            if not data:
                break
            items = data.get("results", [])
            if not items:
                break

            for it in items:
                parsed = self._parse_item(it, vehicle_type, web_url)
                if parsed and parsed["url"] not in seen:
                    seen.add(parsed["url"])
                    listings.append(parsed)
                if len(listings) >= max_listings:
                    break

            if len(items) < 30:
                break
            offset += len(items)
            time.sleep(random.uniform(0.3, 0.7))

        logger.info("[WALLAPOP] Total extracted: %d", len(listings))
        return listings[:max_listings]

    def _fetch_search(self, category: str, offset: int) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/v2/listings/search"
        params = {
            "category": category,
            "offset": str(offset),
            "limit": "30",
            "latitude": "40.4168",
            "longitude": "-3.7038",
            "distance": "200",
        }
        headers = dict(self.session.headers)
        headers["X-Encoded-Device-ID"] = hashlib.sha256(
            "device_id".encode()
        ).hexdigest()[:32]

        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=20)
                if resp.status_code == 429:
                    wait = 2 * (attempt + 1) + random.uniform(0.5, 1.5)
                    logger.warning("[WALLAPOP] Rate limited — waiting %.1fs", wait)
                    self._rotate_ua()
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    logger.warning("[WALLAPOP] HTTP %s", resp.status_code)
                    return None
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                logger.warning("[WALLAPOP] Error (attempt %d): %s", attempt + 1, exc)
                time.sleep(1.0 * (attempt + 1))
        return None

    def _parse_item(
        self, item: Dict[str, Any], vtype: str, web_url: str
    ) -> Optional[Dict[str, Any]]:
        try:
            title = (item.get("title") or "").strip()
            item_id = str(item.get("id") or item.get("listing_id") or "")
            if not title or not item_id:
                return None

            price_info = item.get("price", {})
            if isinstance(price_info, dict):
                price = float(price_info.get("price") or 0)
            else:
                price = self._parse_price(price_info)

            if not price or price < 100:
                return None

            url = f"{web_url}/detail/{item_id}"
            if item.get("web_slug"):
                url = f"{web_url}/detail/{item_id}-{item['web_slug']}"

            brand = self._normalize_brand(item.get("brand") or "")
            model = item.get("model") or ""

            km = self._parse_int(item.get("km") or item.get("mileage"))
            year = self._parse_int(item.get("year") or item.get("first_plate_year"))
            hp = self._parse_int(item.get("horsepower") or item.get("power"))
            engine = self._parse_int(item.get("engine_cc") or item.get("engine_size"))

            fuel = self._normalize_fuel(item.get("fuel") or item.get("fuel_type") or "")
            trans = self._normalize_trans(item.get("transmission") or "")

            location = item.get("city") or item.get("location") or ""
            seller_type = "profissional" if item.get("business") else "particular"

            return {
                "source": "WALLAPOP",
                "source_id": item_id,
                "url": url,
                "title": title[:500],
                "brand": brand,
                "model": model[:100],
                "price": float(price),
                "currency": "EUR",
                "price_kind": "total",
                "year": year,
                "km": km,
                "horsepower": hp,
                "engine_size": engine,
                "fuel_type": fuel,
                "transmission": trans,
                "location": str(location)[:200],
                "seller_type": seller_type,
                "images": [img.get("url") for img in (item.get("photos") or []) if img.get("url")][:20],
                "vehicle_type": vtype,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("[WALLAPOP] Parse error: %s", exc)
            return None

    @staticmethod
    def _parse_price(raw: Any) -> Optional[float]:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)
        digits = re.sub(r"[^\d]", "", str(raw))
        return float(digits) if digits else None

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        digits = re.sub(r"\D", "", str(value))
        return int(digits) if digits else None

    @staticmethod
    def _normalize_brand(raw: str) -> str:
        r = str(raw).lower().strip()
        for b in BRANDS:
            bl = b.lower()
            if bl in r:
                if "volkswagen" in bl:
                    return "Volkswagen"
                if "mercedes" in bl:
                    return "Mercedes"
                return b
        return r.title() if raw else "Unknown"

    @staticmethod
    def _normalize_fuel(raw: str) -> str:
        r = str(raw).lower().strip()
        for k, v in FUEL_MAP.items():
            if k in r:
                return v
        return r or "unknown"

    @staticmethod
    def _normalize_trans(raw: str) -> str:
        r = str(raw).lower().strip()
        for k, v in TRANS_MAP.items():
            if k in r:
                return v
        return r or "unknown"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = WallapopLightweight()
    res = s.scrape_listings("carros", max_listings=10)
    print(f"\n=== Scraped {len(res)} Wallapop listings ===")
    for r in res[:10]:
        print(f"  {r['brand']} {r['model']} | €{r['price']} | {r['year']} | {r['km']}km | {r['fuel_type']} | {r['location']}")
