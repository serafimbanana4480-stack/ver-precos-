"""
LeBonCoin Lightweight Scraper — requests only, no Playwright.
Site: leboncoin.fr — French classified ads platform.

Uses the public search API endpoint:
  https://api.leboncoin.fr/v0/search

Returns structured vehicle data for FR market. Prices are always in EUR.
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

FUEL_MAP = {
    "essence": "gasolina", "gasoline": "gasolina", "gasolina": "gasolina",
    "diesel": "diesel", "gazole": "diesel",
    "electrique": "eletrico", "electric": "eletrico",
    "hybride": "hibrido", "hybrid": "hibrido",
    "plug-in": "hibrido", "hybride rechargeable": "hibrido",
    "lpg": "gpl", "gpl": "gpl", "cng": "gas natural",
}
TRANS_MAP = {
    "manuelle": "manual", "manual": "manual",
    "automatique": "automatico", "automatic": "automatico",
    "automatico": "automatico", "robotisee": "semi-automatico",
    "boite manuelle": "manual", "boite automatique": "automatico",
}
BRANDS = [
    "Alfa Romeo", "Abarth", "Audi", "Bmw", "Citroen", "Citroën",
    "Cupra", "Dacia", "DS", "DS Automobiles", "Fiat", "Ford",
    "Honda", "Hyundai", "Jaguar", "Jeep", "Kia", "Land Rover",
    "Lexus", "Mazda", "Mitsubishi", "Nissan", "Opel", "Peugeot",
    "Porsche", "Renault", "Seat", "Skoda", "Smart", "Suzuki",
    "Tesla", "Toyota", "Volkswagen", "Volvo", "Mini", "MG",
    "Mercedes", "Mercedes-Benz", "Infiniti", "Acura",
]


class LeBonCoinLightweight:
    """Lightweight scraper for LeBonCoin via public search API."""

    BASE_URL = "https://api.leboncoin.fr"
    USER_AGENTS = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    )

    CATEGORY_CARS = 378  # "Voitures - Campings-car" parent category
    CATEGORY_MOTOS = 379

    def __init__(self) -> None:
        self.session = requests.Session()
        self._rotate_ua()

    def _rotate_ua(self) -> None:
        self.session.headers.update({
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Referer": "https://www.leboncoin.fr/",
            "Origin": "https://www.leboncoin.fr",
        })

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("[LEBONCOIN] Starting scrape, max %d", max_listings)
        listings: List[Dict[str, Any]] = []
        seen: set[str] = set()

        cat_id = self.CATEGORY_MOTOS if vehicle_type.lower().startswith("moto") else self.CATEGORY_CARS
        page = 0
        while len(listings) < max_listings:
            data = self._fetch_search(cat_id, page)
            if not data:
                break
            items = data.get("ads", []) or data.get("data", [])
            if not items:
                break
            for it in items:
                parsed = self._parse_ad(it, vehicle_type)
                if parsed and parsed["url"] not in seen:
                    seen.add(parsed["url"])
                    listings.append(parsed)
                if len(listings) >= max_listings:
                    break
            if len(items) < 50:
                break
            page += 1
            time.sleep(random.uniform(0.3, 0.8))

        logger.info("[LEBONCOIN] Total extracted: %d", len(listings))
        return listings[:max_listings]

    def _fetch_search(self, category_id: int, page: int) -> Optional[Dict[str, Any]]:
        params = {
            "category": category_id,
            "limit": 50,
            "offset": page * 50,
            "filters": '{"category": {"id": "VI"}}' if category_id == self.CATEGORY_CARS else "",
        }
        for attempt in range(3):
            try:
                resp = self.session.get(
                    f"{self.BASE_URL}/v0/search", params=params, timeout=20
                )
                if resp.status_code == 429:
                    wait = 3 * (attempt + 1)
                    logger.warning("[LEBONCOIN] Rate limited — waiting %.1fs", wait)
                    time.sleep(wait)
                    self._rotate_ua()
                    continue
                if resp.status_code != 200:
                    logger.warning("[LEBONCOIN] HTTP %s", resp.status_code)
                    return None
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                logger.warning("[LEBONCOIN] Error (attempt %d): %s", attempt + 1, exc)
                time.sleep(1.5 * (attempt + 1))
        return None

    def _parse_ad(self, ad: Dict[str, Any], vtype: str) -> Optional[Dict[str, Any]]:
        try:
            title = (ad.get("title") or "").strip()
            url = ad.get("url") or ad.get("link") or ""
            if not title or not url:
                return None

            ad_id = str(ad.get("id") or hashlib.md5(url.encode()).hexdigest()[:16])
            price = self._parse_price(ad.get("price") or ad.get("price_label"))
            if not price or price < 100:
                return None

            location = ad.get("location") or {}
            if isinstance(location, dict):
                city = location.get("city") or ""
                region = location.get("region") or ""
                location = ", ".join(x for x in (city, region) if x)

            brand, model = self._parse_brand_model(title)
            params = ad.get("param") or {}

            km = self._parse_int(params.get("mileage") or ad.get("mileage"))
            year = self._parse_int(params.get("year") or ad.get("regdate"))
            hp = self._parse_int(params.get("power") or params.get("horsepower"))
            engine = self._parse_int(params.get("engine_size"))
            fuel = self._normalize_fuel(
                params.get("fuel") or ad.get("fuel_type") or ""
            )
            trans = self._normalize_trans(
                params.get("gearbox") or params.get("transmission") or ""
            )

            return {
                "source": "LEBONCOIN",
                "source_id": ad_id,
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
                "seller_type": "profissional" if ad.get("professional") else "particular",
                "vehicle_type": vtype,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("[LEBONCOIN] Parse error: %s", exc)
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
    def _parse_brand_model(title: str) -> tuple:
        t = title.lower()
        for b in BRANDS:
            bl = b.lower()
            if bl in t or bl.replace(" ", "") in t.replace(" ", ""):
                idx = t.find(bl)
                rest = title[idx + len(b):].strip(" -—")
                return b, rest[:100]
        parts = title.split(maxsplit=1)
        return parts[0].strip(), parts[1].strip()[:100] if len(parts) > 1 else ""

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
    s = LeBonCoinLightweight()
    res = s.scrape_listings("carros", max_listings=10)
    print(f"\n=== Scraped {len(res)} LeBonCoin listings ===")
    for r in res[:10]:
        print(f"  {r['brand']} {r['model']} | €{r['price']} | {r['year']} | {r['km']}km | {r['fuel_type']} | {r['location']}")
