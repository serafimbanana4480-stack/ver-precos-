"""
OLX Lightweight Scraper — requests only, no Playwright.
Site: olx.pt — usa a API JSON pública /api/v1/offers/ (categoria 378 = carros).

MUITO superior ao olx_scraper.py (Playwright): a API expõe ~52.000 anúncios com
dados estruturados (preço, ano, km, combustível, caixa, potência) sem render.
Extrai marca do título via lista BRANDS (a API não devolve marca como param).

Endpoint: https://www.olx.pt/api/v1/offers/?category_id=378&offset=N&limit=50
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

BRANDS = [
    "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz",
    "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
    "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
    "Hyundai", "Kia", "Fiat", "Seat", "SEAT", "Skoda", "Volvo",
    "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini",
    "Smart", "Jeep", "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla",
    "Cupra", "DS", "Lancia", "MG", "BYD", "Polestar", "Chevrolet", "Chrysler",
]

FUEL_MAP = {
    "gasolina": "gasolina", "diesel": "diesel", "gasóleo": "diesel",
    "elétrico": "eletrico", "eletrico": "eletrico",
    "híbrido": "hibrido", "hibrido": "hibrido",
    "hibrido-plugin": "hibrido", "gpl": "gpl",
}
TRANS_MAP = {"manual": "manual", "automatic": "automatico", "automatica": "automatico"}


class OLXLightweight:
    """Scraper leve para OLX.pt via API JSON pública.

    A categoria 378 corresponde a 'Carros'. A API devolve páginas de anúncios
    com params estruturados. Sem Playwright, sem render — rápido e robusto.
    """

    BASE_URL = "https://www.olx.pt"
    API = "https://www.olx.pt/api/v1/offers/"
    CATEGORY_CARROS = 378

    def __init__(self) -> None:
        self.session = requests.Session()
        self._rotate_headers()

    def _rotate_headers(self) -> None:
        self.session.headers.update({
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            ]),
            "Accept": "application/json",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            "Referer": "https://www.olx.pt/carros-motos-e-barcos/carros/",
        })

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info(f"[OLX_LIGHT] Starting scrape via API, max {max_listings}")
        listings: List[Dict[str, Any]] = []
        offset = 0
        page_size = 50

        while len(listings) < max_listings:
            params = {
                "category_id": self.CATEGORY_CARROS,
                "offset": offset,
                "limit": page_size,
            }
            if filters and filters.get("brand"):
                params["filter_enum_marca[0]"] = str(filters["brand"]).lower()

            data = self._fetch_json(params)
            if not data:
                logger.warning(f"[OLX_LIGHT] No data at offset {offset}")
                break

            items = data.get("data", [])
            if not items:
                logger.info(f"[OLX_LIGHT] No more items at offset {offset}")
                break

            for it in items:
                parsed = self._parse_offer(it)
                if parsed:
                    listings.append(parsed)
                if len(listings) >= max_listings:
                    break

            offset += page_size
            time.sleep(0.3)  # rate-limit educado

        listings = listings[:max_listings]
        logger.info(f"[OLX_LIGHT] Total extracted: {len(listings)}")
        return listings

    def _fetch_json(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for attempt in range(3):
            try:
                resp = self.session.get(self.API, params=params, timeout=20)
                if resp.status_code == 429:
                    time.sleep(2 * (attempt + 1))
                    self._rotate_headers()
                    continue
                if resp.status_code != 200:
                    logger.warning(f"[OLX_LIGHT] HTTP {resp.status_code}")
                    return None
                return resp.json()
            except (requests.RequestException, ValueError) as e:
                logger.error(f"[OLX_LIGHT] Request failed: {e}")
                time.sleep(1.5)
        return None

    def _parse_offer(self, it: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            title = (it.get("title") or "").strip()
            url = it.get("url") or ""
            if not title or not url:
                return None

            params = {p.get("key"): p.get("value") for p in it.get("params", [])}

            price = None
            price_p = params.get("price")
            if isinstance(price_p, dict):
                price = price_p.get("value")
            if not price or float(price) <= 0:
                return None

            year = self._enum_key_int(params.get("year"))
            km = self._enum_key_int(params.get("quilometros"))
            hp = self._enum_key_int(params.get("engine_power"))

            fuel_type = self._enum_label(params.get("combustivel"))
            fuel_type = self._normalize_fuel(fuel_type)
            transmission = self._normalize_trans(self._enum_label(params.get("gearbox")))

            model_label = self._enum_label(params.get("modelo"))
            brand, model = self._parse_brand_model(title, model_label)

            location = ""
            loc = it.get("location") or {}
            if isinstance(loc, dict):
                city = (loc.get("city") or {}).get("name") if isinstance(loc.get("city"), dict) else ""
                region = (loc.get("region") or {}).get("name") if isinstance(loc.get("region"), dict) else ""
                location = ", ".join([x for x in (city, region) if x])

            source_id = str(it.get("id") or hashlib.md5(url.encode()).hexdigest()[:16])
            seller_type = "profissional" if it.get("business") else "particular"

            return {
                "source": "OLX",
                "source_id": source_id,
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": float(price),
                "year": year,
                "km": km,
                "fuel_type": fuel_type,
                "transmission": transmission,
                "horsepower": hp,
                "location": location,
                "seller_type": seller_type,
                "images": [img.get("url") for img in (it.get("photos") or []) if img.get("url")][:5],
            }
        except Exception as e:
            logger.debug(f"[OLX_LIGHT] Parse error: {e}")
            return None

    @staticmethod
    def _enum_key_int(value: Any) -> Optional[int]:
        if isinstance(value, dict):
            k = value.get("key")
            if k and str(k).isdigit():
                return int(k)
        return None

    @staticmethod
    def _enum_label(value: Any) -> str:
        if isinstance(value, dict):
            return (value.get("label") or value.get("key") or "").strip()
        return ""

    def _parse_brand_model(self, title: str, model_label: str = "") -> tuple:
        title_lower = title.lower()
        for b in BRANDS:
            if b.lower() in title_lower:
                brand = self._normalize_brand(b)
                idx = title_lower.index(b.lower()) + len(b)
                model = model_label or title[idx:].strip()
                return brand, model[:100]
        parts = title.split(maxsplit=1)
        brand = self._normalize_brand(parts[0]) if parts else "Unknown"
        model = model_label or (parts[1] if len(parts) > 1 else "")
        return brand, model[:100]

    @staticmethod
    def _normalize_brand(raw: str) -> str:
        m = {
            "bmw": "BMW", "vw": "Volkswagen", "mg": "MG", "byd": "BYD", "ds": "DS",
            "seat": "Seat", "citroen": "Citroën", "citroën": "Citroën",
            "mercedes": "Mercedes-Benz", "mercedes-benz": "Mercedes-Benz",
            "alfa romeo": "Alfa Romeo", "land rover": "Land Rover",
        }
        return m.get(raw.lower().strip(), raw.title())

    @staticmethod
    def _normalize_fuel(raw: str) -> str:
        r = raw.lower().strip()
        for k, v in FUEL_MAP.items():
            if k in r:
                return v
        return r or "unknown"

    @staticmethod
    def _normalize_trans(raw: str) -> str:
        r = raw.lower().strip()
        for k, v in TRANS_MAP.items():
            if k in r:
                return v
        return r or "unknown"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = OLXLightweight()
    res = s.scrape_listings("carros", max_listings=10)
    print(f"\n=== Scraped {len(res)} OLX listings (API) ===")
    for r in res[:10]:
        print(f"  {r['brand']} {r['model']} | €{r['price']} | {r['year']} | {r['km']}km | {r['fuel_type']} | {r['location']}")
