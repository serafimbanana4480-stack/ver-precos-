"""
AutoHub Lightweight Scraper — requests + BeautifulSoup, no Playwright.
Site: autohub.pt — WordPress + tema STM Motors (server-rendered).

Estratégia:
1. Sitemap /listings-sitemap.xml devolve todas as URLs de viaturas (~55).
2. Cada detail page tem preço em .single-listing-price e specs inline
   (Ano, Quilometragem, Combustível, Transmissão, Potência, Cor).
Fallback: parsing por regex do texto da página.
"""
from __future__ import annotations
import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BRANDS = [
    "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz",
    "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
    "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
    "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo", "Mazda",
    "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini", "Smart", "Jeep",
    "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla", "Cupra", "DS",
    "MG", "BYD", "Ferrari", "Lamborghini", "Bentley", "Maserati",
]

FUEL_MAP = {
    "gasolina": "gasolina", "diesel": "diesel", "gasóleo": "diesel",
    "elétrico": "eletrico", "eletrico": "eletrico",
    "híbrido": "hibrido", "hibrido": "hibrido", "gpl": "gpl",
}
TRANS_MAP = {"manual": "manual", "automática": "automatico",
             "automatica": "automatico", "automático": "automatico"}


class AutohubLightweight:
    """Scraper leve para autohub.pt (WordPress/STM Motors) via sitemap + BS4."""

    BASE_URL = "https://www.autohub.pt"
    SITEMAP = "https://www.autohub.pt/listings-sitemap.xml"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            "Referer": "https://www.autohub.pt/",
        })

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info(f"[AUTOHUB_LIGHT] Starting scrape, max {max_listings}")
        urls = self._get_listing_urls()
        if not urls:
            logger.warning("[AUTOHUB_LIGHT] No listing URLs from sitemap")
            return []

        listings: List[Dict[str, Any]] = []
        for url in urls[:max_listings]:
            html = self._fetch(url)
            if not html:
                continue
            parsed = self._parse_detail(html, url)
            if parsed:
                listings.append(parsed)
            if len(listings) >= max_listings:
                break
            time.sleep(0.3)

        logger.info(f"[AUTOHUB_LIGHT] Total extracted: {len(listings)}")
        return listings

    def _get_listing_urls(self) -> List[str]:
        html = self._fetch(self.SITEMAP)
        if not html:
            return []
        locs = re.findall(r"<loc>(.*?)</loc>", html)
        return [l for l in locs if "/listings/" in l and l.rstrip("/") != f"{self.BASE_URL}/listings"]

    def _fetch(self, url: str) -> Optional[str]:
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=20)
                if resp.status_code != 200:
                    logger.warning(f"[AUTOHUB_LIGHT] HTTP {resp.status_code} {url}")
                    return None
                return resp.text
            except requests.RequestException as e:
                logger.error(f"[AUTOHUB_LIGHT] Request failed: {e}")
                time.sleep(1.5)
        return None

    def _parse_detail(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        try:
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else ""
            if not title:
                return None

            price = None
            pr = soup.select_one(".single-listing-price")
            if pr:
                price = self._parse_euro(pr.get_text(strip=True))
            if not price or price <= 0:
                return None  # "Preço por consulta" ou sem preço

            txt = soup.get_text(" ", strip=True)

            year = self._grab(txt, "Ano", r"(\d{4})")
            year = int(year) if year else None
            km = self._grab(txt, "Quilometragem", r"([\d. ]+?)\s*(?:km|Km|KM)")
            km = self._safe_int(km)
            hp = self._grab(txt, "Potência", r"(\d+)\s*cv")
            hp = int(hp) if hp else None
            fuel = self._grab(txt, "Combustível", r"(Gasolina|Diesel|Elétrico|Eléctrico|Híbrido|GPL)")
            trans = self._grab(txt, "Transmissão", r"(Manual|Autom\wtica)")
            color = self._grab(txt, "Exterior", r"([A-Za-zÀ-ÿ]+)")

            brand, model = self._parse_brand_model(title)
            source_id = hashlib.md5(url.encode()).hexdigest()[:16]

            return {
                "source": "AUTOHUB",
                "source_id": source_id,
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": float(price),
                "year": year,
                "km": km,
                "fuel_type": self._normalize_fuel(fuel or ""),
                "transmission": self._normalize_trans(trans or ""),
                "horsepower": hp,
                "color": color or "",
                "location": "",
                "seller_type": "profissional",
                "images": [],
            }
        except Exception as e:
            logger.debug(f"[AUTOHUB_LIGHT] Parse error: {e}")
            return None

    @staticmethod
    def _grab(text: str, label: str, pat: str) -> Optional[str]:
        m = re.search(re.escape(label) + r"\s*" + pat, text)
        return m.group(1).strip() if m else None

    def _parse_brand_model(self, title: str) -> tuple:
        title_lower = title.lower()
        for b in BRANDS:
            if b.lower() in title_lower:
                brand = self._normalize_brand(b)
                idx = title_lower.index(b.lower()) + len(b)
                return brand, title[idx:].strip()[:100]
        parts = title.split(maxsplit=1)
        return (self._normalize_brand(parts[0]) if parts else "Unknown",
                parts[1][:100] if len(parts) > 1 else "")

    @staticmethod
    def _normalize_brand(raw: str) -> str:
        m = {"bmw": "BMW", "vw": "Volkswagen", "mg": "MG", "ds": "DS",
             "mercedes": "Mercedes-Benz", "mercedes-benz": "Mercedes-Benz",
             "citroen": "Citroën", "alfa romeo": "Alfa Romeo",
             "land rover": "Land Rover"}
        return m.get(raw.lower().strip(), raw.title())

    @staticmethod
    def _parse_euro(value: str) -> Optional[float]:
        digits = re.sub(r"[^\d]", "", str(value))
        return float(digits) if digits else None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        digits = re.sub(r"\D", "", str(value))
        return int(digits) if digits else None

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
    s = AutohubLightweight()
    res = s.scrape_listings("carros", max_listings=10)
    print(f"\n=== Scraped {len(res)} AutoHub listings ===")
    for r in res[:10]:
        print(f"  {r['brand']} {r['model']} | €{r['price']} | {r['year']} | {r['km']}km | {r['fuel_type']} | {r['horsepower']}cv")
