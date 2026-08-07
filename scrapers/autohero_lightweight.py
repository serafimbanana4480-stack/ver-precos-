"""
AutoHero Lightweight Scraper — requests only, no Playwright.
Site: autohero.com (FR/ES/DE/IT) — React SSR vehicle marketplace.

Uses the public search endpoint that returns JSON via SSR data hydration:
  https://www.autohero.com/fr/listing/...  → embedded __NEXT_DATA__ payload

AutoHero focuses on dealer-certified pre-owned vehicles with structured specs:
price, mileage, year, fuel, transmission, engine_size, horsepower, color.
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FUEL_MAP = {
    "gasoline": "gasolina", "gasolina": "gasolina", "petrol": "gasolina",
    "diesel": "diesel", "gasoleo": "diesel", "gazole": "diesel",
    "electric": "eletrico", "electrico": "eletrico", "électrique": "eletrico",
    "hybrid": "hibrido", "hibrido": "hibrido", "hybride": "hibrido",
    "plug-in hybrid": "hibrido", "hybride rechargeable": "hibrido",
    "lpg": "gpl", "gpl": "gpl", "essence": "gasolina",
}
TRANS_MAP = {
    "manual": "manual", "manuelle": "manual",
    "automatic": "automatico", "automatique": "automatico",
    "automatico": "automatico", "automatique": "automatico",
    "steptronic": "automatico", "dsG": "automatico",
}
BRANDS = [
    "Alfa Romeo", "Aston Martin", "Audi", "Bmw", "Citroen", "Citroën",
    "Cupra", "Dacia", "Daimler", "Fiat", "Ford", "Genesis", "Honda",
    "Hyundai", "Infiniti", "Jaguar", "Jeep", "Kia", "Land Rover",
    "Lexus", "Maserati", "Mazda", "Mb mercedes", "Mercedes", "Mercedes-Benz",
    "Mg", "Mini", "Mitsubishi", "Nissan", "Opel", "Peugeot", "Porsche",
    "Renault", "Seat", "Skoda", "Smart", "Suzuki", "Tesla", "Toyota",
    "Volkswagen", "Volkswagen commercial vehicles", "Volvo", "Polestar",
    "Ds", "Lancia", "Alpine", "Abarth",
]


class AutoHeroLightweight:
    """Lightweight scraper for AutoHero via SSR JSON extraction.

    AutoHero uses Next.js with ``__NEXT_DATA__`` payload. The listing search
    pages embed vehicle records as structured JSON, avoiding full HTML parsing.
    """

    BASE_URL = "https://www.autohero.com"
    USER_AGENTS = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.6",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    )

    def __init__(self) -> None:
        self.session = requests.Session()
        self._rotate_ua()

    def _rotate_ua(self) -> None:
        self.session.headers.update({
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Referer": f"{self.BASE_URL}/fr/",
        })

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("[AUTOHERO] Starting scrape, max %d", max_listings)
        listings: List[Dict[str, Any]] = []
        country = filters.get("country", "fr") if filters else "fr"
        seen: set[str] = set()
        page = 1
        while len(listings) < max_listings:
            url = f"{self.BASE_URL}/{country}/voitures?page={page}"
            html = self._fetch_html(url)
            if not html:
                break
            data = self._extract_next_data(html)
            if not data:
                logger.warning("[AUTOHERO] No __NEXT_DATA__ on page %d", page)
                break

            vehicles = self._find_vehicles(data)
            if not vehicles:
                break

            for v in vehicles:
                parsed = self._parse_vehicle(v, vehicle_type)
                if parsed and parsed["url"] not in seen:
                    seen.add(parsed["url"])
                    listings.append(parsed)
                if len(listings) >= max_listings:
                    break

            if len(vehicles) < 24:
                break
            page += 1
            time.sleep(random.uniform(0.5, 1.5))

        logger.info("[AUTOHERO] Total extracted: %d", len(listings))
        return listings[:max_listings]

    def _fetch_html(self, url: str, attempts: int = 3) -> Optional[str]:
        for attempt in range(attempts):
            try:
                resp = self.session.get(url, timeout=20)
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code in (403, 429, 503):
                    wait = 2 ** attempt + random.uniform(0.5, 1.5)
                    logger.warning("[AUTOHERO] HTTP %s — waiting %.1fs", resp.status_code, wait)
                    self._rotate_ua()
                    time.sleep(wait)
                    continue
                logger.warning("[AUTOHERO] HTTP %s for %s", resp.status_code, url)
                return None
            except requests.RequestException as exc:
                logger.warning("[AUTOHERO] Network error: %s", exc)
                time.sleep(1.5)
        return None

    @staticmethod
    def _extract_next_data(html: str) -> Optional[Dict[str, Any]]:
        match = re.search(
            r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return None
        import json
        try:
            return json.loads(match.group(1))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _find_vehicles(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Traverse __NEXT_DATA__ tree to find vehicle listing arrays."""
        results: List[Dict[str, Any]] = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                if "vehicles" in node and isinstance(node["vehicles"], list):
                    results.extend(node["vehicles"])
                elif "listings" in node and isinstance(node["listings"], list):
                    results.extend(node["listings"])
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(data)
        return results

    def _parse_vehicle(self, v: Dict[str, Any], vtype: str) -> Optional[Dict[str, Any]]:
        try:
            title = (
                v.get("title")
                or v.get("headline")
                or f"{v.get('brand', '')} {v.get('model', '')}".strip()
            )
            if not title:
                return None

            price_raw = v.get("price") or v.get("displayPrice")
            price = self._parse_price(price_raw)
            if not price or price < 100:
                return None

            url = v.get("url") or ""
            if not url:
                return None
            if not url.startswith("http"):
                url = f"{self.BASE_URL}{url}" if url.startswith("/") else f"{self.BASE_URL}/{url}"

            brand = self._normalize_brand(v.get("brand", ""))
            model = v.get("model", "")

            fuel = self._normalize_fuel(v.get("fuelType") or v.get("fuel", ""))
            trans = self._normalize_trans(v.get("transmission") or v.get("gearbox", ""))

            hp = self._parse_int(v.get("power") or v.get("horsepower"))
            engine = self._parse_int(v.get("engineSize") or v.get("engineDisplacement"))

            km = self._parse_int(v.get("mileage") or v.get("kilometers"))
            year = self._parse_int(v.get("firstRegistrationYear") or v.get("year"))

            color = v.get("color") or ""
            location = v.get("city") or v.get("location") or ""
            seller_type = "profissional" if v.get("dealerName") or v.get("business") else "particular"

            return {
                "source": "AUTOHERO",
                "source_id": str(v.get("id") or hashlib.md5(url.encode()).hexdigest()[:16]),
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
                "location": location[:200],
                "seller_type": seller_type,
                "images": [img.get("url") for img in (v.get("images") or []) if img.get("url")][:20],
                "vehicle_type": vtype,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("[AUTOHERO] Parse error: %s", exc)
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
        r = raw.lower().strip()
        for b in BRANDS:
            if b.lower() in r:
                if "volkswagen" in b.lower():
                    return "Volkswagen"
                if "mercedes" in b.lower():
                    return "Mercedes"
                if "vw" == b.lower():
                    return "Volkswagen"
                return b
        # Common aliases
        aliases = {
            "vw": "Volkswagen", "vwc": "Volkswagen",
            "mercedes-benz": "Mercedes-Benz",
        }
        return aliases.get(r, raw.title()) if raw else "Unknown"

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
    s = AutoHeroLightweight()
    res = s.scrape_listings("carros", max_listings=10)
    print(f"\n=== Scraped {len(res)} AutoHero listings ===")
    for r in res[:10]:
        print(f"  {r['brand']} {r['model']} | €{r['price']} | {r['year']} | {r['km']}km | {r['fuel_type']} | {r['location']}")
