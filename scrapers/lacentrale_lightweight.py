"""
LaCentrale Lightweight Scraper (France) — requests only, no Playwright.
Site: lacentrale.fr — French automotive pricing & classifieds platform.

Uses the LaCentrale public listing API:
  https://api.lacentrale.fr/v1/ads/search

LaCentrale.fr is the French automotive reference for used-car pricing.
Data includes professional valuations, ad prices, and structured specs.
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
    "boite manuelle": "manual", "boite 5": "manual", "boite 6": "manual",
    "automatique": "automatico", "automatic": "automatico",
    "boite auto": "automatico", "boite automatique": "automatico",
    "robotisee": "semi-automatico", "semi-automatique": "semi-automatico",
}
BRANDS = [
    "Alfa Romeo", "Abarth", "Audi", "Bmw", "Citroen", "Citroën",
    "Cupra", "Dacia", "DS", "DS Automobiles", "Fiat", "Ford",
    "Honda", "Hyundai", "Jaguar", "Jeep", "Kia", "Land Rover",
    "Lexus", "Mazda", "Mitsubishi", "Nissan", "Opel", "Peugeot",
    "Porsche", "Renault", "Seat", "Skoda", "Smart", "Suzuki",
    "Tesla", "Toyota", "Volkswagen", "Vag", "Volvo", "Mini", "MG",
    "Mercedes", "Mercedes-Benz", "Infiniti", "Acura", "Lancia",
    "Alpine", "Jensen", "Bentley", "Rolls Royce", "Rolls-Royce",
]


class LaCentraleLightweight:
    """Lightweight scraper for LaCentrale.fr via public API."""

    BASE_URL = "https://api.lacentrale.fr"
    WEB_URL = "https://www.lacentrale.fr"
    USER_AGENTS = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    )

    def __init__(self) -> None:
        self.session = requests.Session()
        self._rotate_ua()

    def _rotate_ua(self) -> None:
        self.session.headers.update({
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Referer": f"{self.WEB_URL}/",
            "Origin": self.WEB_URL,
        })

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("[LACENTRALE] Starting scrape, max %d", max_listings)
        listings: List[Dict[str, Any]] = []
        seen: set[str] = set()

        category = "voitures"
        if vehicle_type.lower().startswith("moto"):
            category = "motos"

        page = 1
        while len(listings) < max_listings:
            data = self._fetch_page(category, page, filters)
            if not data:
                break
            items = data.get("ads", []) or data.get("results", [])
            if not items:
                break

            for it in items:
                parsed = self._parse_ad(it, vehicle_type)
                if parsed and parsed["url"] not in seen:
                    seen.add(parsed["url"])
                    listings.append(parsed)
                if len(listings) >= max_listings:
                    break

            pagination = data.get("pagination", {})
            total_pages = pagination.get("total_pages", page)
            if page >= total_pages or len(items) < 30:
                break
            page += 1
            time.sleep(random.uniform(0.3, 0.7))

        logger.info("[LACENTRALE] Total extracted: %d", len(listings))
        return listings[:max_listings]

    def _fetch_page(
        self, category: str, page: int, filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE_URL}/v1/ads/search"
        params = {
            "category": category,
            "page": str(page),
            "per_page": "30",
            "sort": "created_at",
            "direction": "desc",
        }
        if filters:
            for k, v in filters.items():
                params[k] = str(v)

        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=20)
                if resp.status_code == 429:
                    wait = 2 * (attempt + 1) + random.uniform(0.5, 1.5)
                    logger.warning("[LACENTRALE] Rate limited — waiting %.1fs", wait)
                    self._rotate_ua()
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    logger.warning("[LACENTRALE] HTTP %s", resp.status_code)
                    return None
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                logger.warning("[LACENTRALE] Error (attempt %d): %s", attempt + 1, exc)
                time.sleep(1.5 * (attempt + 1))
        return None

    def _parse_ad(self, ad: Dict[str, Any], vtype: str) -> Optional[Dict[str, Any]]:
        try:
            title = (ad.get("title") or "").strip()
            ad_id = str(ad.get("id") or ad.get("listing_id") or "")
            if not title or not ad_id:
                return None

            price = self._parse_price(ad.get("price") or ad.get("price_amount"))
            if not price or price < 500:
                return None

            url = f"{self.WEB_URL}/annonce/{ad_id}"
            if ad.get("url") or ad.get("slug"):
                slug = ad.get("url") or ad.get("slug") or ""
                if slug.startswith("/"):
                    url = f"{self.WEB_URL}{slug}"
                elif slug.startswith("http"):
                    url = slug

            brand = self._normalize_brand(ad.get("brand") or "")
            model = ad.get("model") or ""

            if not brand or brand == "Unknown":
                brand, model_from_title = self._parse_brand_model(title)
                model = model or model_from_title

            km = self._parse_int(ad.get("mileage") or ad.get("km"))
            year = self._parse_int(ad.get("year") or ad.get("first_registration_year"))
            hp = self._parse_int(ad.get("horsepower") or ad.get("power") or ad.get("engine_power"))
            engine = self._parse_int(ad.get("engine_size") or ad.get("displacement"))

            fuel = self._normalize_fuel(ad.get("fuel") or ad.get("fuel_type") or "")
            trans = self._normalize_trans(ad.get("transmission") or ad.get("gearbox") or "")

            color = ad.get("color") or ""
            location = ad.get("city") or ad.get("location") or ""
            seller_type = "profissional" if ad.get("is_professional") or ad.get("dealer") else "particular"

            return {
                "source": "LACENTRALE",
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
                "color": color,
                "location": str(location)[:200],
                "seller_type": seller_type,
                "images": [img.get("url") for img in (ad.get("photos") or []) if img.get("url")][:20],
                "vehicle_type": vtype,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("[LACENTRALE] Parse error: %s", exc)
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
    def _parse_brand_model(title: str) -> tuple:
        t = title.lower()
        for b in BRANDS:
            bl = b.lower()
            if bl in t:
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
    s = LaCentraleLightweight()
    res = s.scrape_listings("carros", max_listings=10)
    print(f"\n=== Scraped {len(res)} LaCentrale listings ===")
    for r in res[:10]:
        print(f"  {r['brand']} {r['model']} | €{r['price']} | {r['year']} | {r['km']}km | {r['fuel_type']} | {r['location']}")
