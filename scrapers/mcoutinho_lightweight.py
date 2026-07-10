"""
M. Coutinho Usados Lightweight Scraper — requests only, no Playwright.
Site: usados.mcoutinho.pt (grupo automóvel M. Coutinho) — Nuxt SPA.

Usa a API JSON pública do backend: https://backend.mcoutinho.pt/api/v1/vehicles
Devolve ~1100 viaturas (101 páginas) com dados completos e estruturados:
preço, km, ano, combustível, caixa, potência, cilindrada, extras, cor.
"""
from __future__ import annotations
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

FUEL_MAP = {
    "gasolina": "gasolina", "diesel": "diesel", "gasóleo": "diesel",
    "elétrico": "eletrico", "eletrico": "eletrico", "electrico": "eletrico",
    "hibrido": "hibrido", "híbrido": "hibrido", "plug": "hibrido", "gpl": "gpl",
}
TRANS_MAP = {"manual": "manual", "automática": "automatico", "automatica": "automatico",
             "automático": "automatico", "automatico": "automatico"}


class McoutinhoLightweight:
    """Scraper leve para usados.mcoutinho.pt via API JSON backend.

    Fonte de alto volume (~1100 viaturas de stand, dados verificados) e alta
    qualidade — todos os campos vêm estruturados da API, sem parsing de HTML.
    """

    BASE_URL = "https://usados.mcoutinho.pt"
    API = "https://backend.mcoutinho.pt/api/v1/vehicles"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "pt-PT,pt;q=0.9",
            "Referer": "https://usados.mcoutinho.pt/",
            "Origin": "https://usados.mcoutinho.pt",
        })

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info(f"[MCOUTINHO_LIGHT] Starting scrape via API, max {max_listings}")
        listings: List[Dict[str, Any]] = []
        page = 1
        per_page = 24

        while len(listings) < max_listings:
            data = self._fetch_json({"page": page, "per_page": per_page})
            if not data:
                break
            items = data.get("data", [])
            if not items:
                break

            for it in items:
                parsed = self._parse_vehicle(it)
                if parsed:
                    listings.append(parsed)
                if len(listings) >= max_listings:
                    break

            meta = data.get("meta", {})
            last_page = meta.get("last_page", page)
            if page >= last_page:
                break
            page += 1
            time.sleep(0.3)

        listings = listings[:max_listings]
        logger.info(f"[MCOUTINHO_LIGHT] Total extracted: {len(listings)}")
        return listings

    def _fetch_json(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for attempt in range(3):
            try:
                resp = self.session.get(self.API, params=params, timeout=20)
                if resp.status_code != 200:
                    logger.warning(f"[MCOUTINHO_LIGHT] HTTP {resp.status_code}")
                    return None
                return resp.json()
            except (requests.RequestException, ValueError) as e:
                logger.error(f"[MCOUTINHO_LIGHT] Request failed: {e}")
                time.sleep(1.5)
        return None

    def _parse_vehicle(self, it: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            brand = (it.get("brand") or "").strip()
            model = (it.get("model") or "").strip()
            if not brand:
                return None

            price = it.get("current_sell_price") or it.get("promotion_price")
            if not price:
                display = it.get("display_price")
                price = self._parse_euro(display) if display else None
            if not price or float(price) <= 0:
                return None

            slug = it.get("slug") or ""
            url = f"{self.BASE_URL}/carros/usados/{slug}" if slug else self.BASE_URL

            km = self._parse_int(it.get("kms"))
            year = it.get("year") or it.get("build_year") or it.get("plate_date")
            year = int(year) if year and str(year).isdigit() else None
            hp = self._parse_int(it.get("power"))
            engine = self._parse_int(it.get("engine_size"))

            version = (it.get("version") or "").strip()
            full_model = f"{model} {version}".strip() if version else model

            extras = it.get("extras")
            extras = extras if isinstance(extras, list) else []

            images = []
            vi = it.get("vehicle_image")
            if vi:
                images.append(vi)

            return {
                "source": "MCOUTINHO",
                "source_id": str(it.get("hash") or slug),
                "url": url,
                "title": f"{brand} {full_model}".strip(),
                "brand": self._normalize_brand(brand),
                "model": full_model[:100],
                "price": float(price),
                "year": year,
                "km": km,
                "fuel_type": self._normalize_fuel(it.get("fuel_type", "")),
                "transmission": self._normalize_trans(it.get("transmission", "")),
                "horsepower": hp,
                "engine_size": engine,
                "doors": it.get("doors"),
                "color": it.get("color_name") or "",
                "location": it.get("sale_point") or "",
                "seller_type": "profissional",
                "extras": extras,
                "images": images,
            }
        except Exception as e:
            logger.debug(f"[MCOUTINHO_LIGHT] Parse error: {e}")
            return None

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        digits = re.sub(r"\D", "", str(value))
        return int(digits) if digits else None

    @staticmethod
    def _parse_euro(value: str) -> Optional[float]:
        digits = re.sub(r"[^\d]", "", str(value))
        return float(digits) if digits else None

    @staticmethod
    def _normalize_brand(raw: str) -> str:
        m = {
            "bmw": "BMW", "vw": "Volkswagen", "mg": "MG", "ds": "DS",
            "ds automobiles": "DS", "mercedes": "Mercedes-Benz",
            "mercedes-benz": "Mercedes-Benz", "citroen": "Citroën",
            "alfa romeo": "Alfa Romeo", "land rover": "Land Rover",
        }
        return m.get(raw.lower().strip(), raw)

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
    s = McoutinhoLightweight()
    res = s.scrape_listings("carros", max_listings=10)
    print(f"\n=== Scraped {len(res)} M.Coutinho listings (API) ===")
    for r in res[:10]:
        print(f"  {r['brand']} {r['model']} | €{r['price']} | {r['year']} | {r['km']}km | {r['fuel_type']} | {r['horsepower']}cv | {r['location']}")
