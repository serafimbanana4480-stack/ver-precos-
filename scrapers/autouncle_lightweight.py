"""
AutoUncle Lightweight Scraper — requests + BeautifulSoup, no Playwright.
Site: autouncle.pt — aggregates prices from ALL Portuguese car sites.
Uses Next.js with data embedded in DOM (article elements).
Extracts listing data + market price analysis (valuation, savings).
"""
from __future__ import annotations
import hashlib
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Portuguese brands
BRANDS = [
    "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz",
    "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
    "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
    "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo",
    "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini",
    "Smart", "Jeep", "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla",
    "Cupra", "DS", "Lancia", "MG", "BYD", "Polestar",
]

FUEL_MAP = {
    "gasolina": "gasolina", "gasoline": "gasolina", "petrol": "gasolina",
    "diesel": "diesel", "gasóleo": "diesel",
    "elétrico": "eletrico", "eletrico": "eletrico", "electric": "eletrico",
    "elétrico/petrol": "hibrido", "híbrido": "hibrido", "hibrido": "hibrido", "hybrid": "hibrido",
    "gpl": "gpl",
}

TRANS_MAP = {
    "manual": "manual",
    "automática": "automatico", "automático": "automatico", "automatico": "automatico",
}

VALUATION_LABELS = {
    "super preço": "super_preco",
    "bom preço": "bom_preco",
    "preço justo": "preco_justo",
    "preço elevado": "preco_elevado",
    "caro": "caro",
}


class AutoUncleLightweight:
    """Scraper for AutoUncle.pt using requests + BeautifulSoup.

    AutoUncle aggregates listings from all Portuguese car sites
    and provides market price analysis (valuation label + savings amount).
    This is the MOST valuable data source for ML training.
    """

    BASE_URL = "https://www.autouncle.pt"

    def __init__(self):
        self.session = requests.Session()
        self._rotate_headers()

    def _rotate_headers(self):
        """Rotate user-agent to avoid blocks."""
        self.session.headers.update({
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            ]),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            "Referer": "https://www.autouncle.pt/",
            "DNT": "1",
        })

    def _is_blocked(self, text: str) -> bool:
        checks = ["cf-browser-verification", "cloudflare", "Just a moment",
                   "attention required", "challenge-platform"]
        text_lower = text.lower()
        return any(check in text_lower for check in checks)

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape listings from AutoUncle.pt.

        Args:
            vehicle_type: 'carros' (only type supported currently)
            max_listings: Maximum listings to return
            filters: Optional brand filter dict (e.g. {'brand': 'BMW'})

        Returns:
            List of vehicle dicts with market price analysis fields.
        """
        logger.info(f"[AUTOUNCLE_LIGHT] Starting scrape, max {max_listings}")

        listings = []
        page = 0

        while len(listings) < max_listings:
            url = self._build_url(page, filters)
            logger.info(f"[AUTOUNCLE_LIGHT] Fetching page {page}: {url}")

            html = None
            for attempt in range(3):
                try:
                    resp = self.session.get(url, timeout=20)
                    if resp.status_code != 200:
                        logger.warning(f"[AUTOUNCLE_LIGHT] HTTP {resp.status_code} on page {page}")
                        continue
                    if self._is_blocked(resp.text):
                        logger.warning(f"[AUTOUNCLE_LIGHT] Blocked on page {page}, retry {attempt + 1}")
                        self._rotate_headers()
                        time.sleep(2)
                        continue
                    html = resp.text
                    break
                except requests.RequestException as e:
                    logger.error(f"[AUTOUNCLE_LIGHT] Request failed: {e}")
                    time.sleep(2)
                    continue

            if not html:
                logger.warning(f"[AUTOUNCLE_LIGHT] Failed to get HTML for page {page}")
                break

            page_listings = self._parse_page(html, page)
            if not page_listings:
                logger.info(f"[AUTOUNCLE_LIGHT] No more listings on page {page}")
                break

            logger.info(f"[AUTOUNCLE_LIGHT] Page {page}: {len(page_listings)} listings")
            listings.extend(page_listings)
            page += 1

            if len(page_listings) < 20:
                break

        listings = listings[:max_listings]
        logger.info(f"[AUTOUNCLE_LIGHT] Total extracted: {len(listings)}")
        return listings

    def _build_url(self, page: int = 0, filters: Optional[Dict[str, Any]] = None) -> str:
        """Build search URL."""
        path = "/pt/carros-usados"
        params = []
        if page > 0:
            params.append(f"page={page}")
        if filters and filters.get("brand"):
            path = f"{path}/{filters['brand']}"
        url = f"{self.BASE_URL}{path}"
        if params:
            url += "?" + "&".join(params)
        return url

    def _parse_page(self, html: str, page: int) -> List[Dict[str, Any]]:
        """Extract vehicle listings from article elements."""
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.find_all("article", class_="_qzVn4")

        if not articles:
            logger.debug(f"[AUTOUNCLE_LIGHT] No article._qzVn4 on page {page}")
            return []

        listings = []
        for article in articles:
            try:
                listing = self._parse_article(article)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[AUTOUNCLE_LIGHT] Article parse error: {e}")
                continue

        return listings

    def _parse_article(self, article) -> Optional[Dict[str, Any]]:
        """Parse a single article element into a vehicle dict."""
        text = article.get_text(" ", strip=True)

        # --- Title (from h3) ---
        h3 = article.find("h3")
        title = h3.get_text(strip=True) if h3 else ""

        # --- Subtitle / model variant ---
        subtitle_el = article.select_one("p._GXVfV")
        subtitle = subtitle_el.get_text(strip=True) if subtitle_el else ""

        # --- Link (detail page) ---
        detail_link = article.find("a", class_="_p9jqN")
        detail_url = ""
        if detail_link and detail_link.get("href"):
            detail_url = urljoin(self.BASE_URL, detail_link["href"])

        # --- External link (source dealer site) ---
        ext_link = article.find("a", class_=re.compile(r"_Nj0SF"))
        ext_url = ""
        if ext_link and ext_link.get("href"):
            ext_url = urljoin(self.BASE_URL, ext_link["href"])

        # --- Price ---
        price = None
        price_match = re.search(r'(?:Bom\s*preço|Super\s*Preço|Preço\s*justo|Preço\s*elevado|Caro)\s*€\s*([\d.]+(?:,\d{2})?)', text)
        if not price_match:
            price_match = re.search(r'€\s*([\d.]+(?:,\d{2})?)', text)
        if price_match:
            price = self._parse_euro(price_match.group(1))

        if not price:
            return None

        # --- Valuation label ---
        valuation = "unknown"
        for label, key in VALUATION_LABELS.items():
            if label in text.lower():
                valuation = key
                break

        # --- Market savings ("Abaixo do mercado €X") ---
        market_savings = None
        save_match = re.search(r'Abaixo\s+do\s+mercado\s*€\s*([\d.]+(?:,\d{2})?)', text)
        if save_match:
            market_savings = self._parse_euro(save_match.group(1))

        # --- Year ---
        year = None
        year_match = re.search(r'(?:Usado|Novo)\s*\((\d{4})\)', text)
        if year_match:
            year = int(year_match.group(1))

        # --- KM ---
        km = None
        km_match = re.search(r'(\d[\d.]*)\s*km', text)
        if km_match:
            km = self._safe_int(km_match.group(1))

        # --- Fuel type and engine size ---
        fuel_type = "unknown"
        engine_size = None
        fuel_match = re.search(r'(\d\.\dL)\s*(Diesel|Gasolina|Elétrico|Híbrido|Petrol|Electric|Elétrico/Petrol)', text)
        if fuel_match:
            engine_str = fuel_match.group(1).replace("L", "").strip()
            try:
                engine_size = int(float(engine_str) * 1000)
            except ValueError:
                pass
            fuel_raw = fuel_match.group(2).lower().strip()
            fuel_type = self._normalize_fuel(fuel_raw)

        # --- Transmission ---
        transmission = "unknown"
        for key, val in TRANS_MAP.items():
            if key.lower() in text.lower():
                transmission = val
                break

        # --- Horsepower ---
        hp = None
        hp_match = re.search(r'(\d{2,3})\s*HP\s*\((\d+)\s*kW\)', text)
        if hp_match:
            hp = int(hp_match.group(1))

        # --- Body type ---
        body_type = ""
        body_types = ["Coupé", "Sedan", "SUV", "Citadino", "Cabrio", "Hatchback",
                       "Minivan", "Station", "Pick-up", "Monovolume"]
        for bt in body_types:
            if bt.lower() in text.lower():
                body_type = bt.lower()
                break

        # --- Location and dealer ---
        location = ""
        dealer = ""
        # The bottom div _yxZqT contains dealer name and location
        bottom_div = article.select_one("div._yxZqT")
        if bottom_div:
            bottom_text = bottom_div.get_text(" ", strip=True)
            # Pattern: "DealerName ZipCode City, Region"
            parts = bottom_text.split("Ver o carro")[0].strip()
            parts = re.sub(r'Disponibilidade\s+verificada', '', parts).strip()
            # First word(s) are dealer name, last words are location
            dealer = parts.strip()

        # --- Brand and model from title ---
        brand, model = self._parse_brand_model(title, subtitle)

        # --- Source ID from detail URL ---
        source_id = hashlib.md5((detail_url or title).encode()).hexdigest()[:16]

        return {
            "source": "AUTOUNCLE",
            "source_id": source_id,
            "url": detail_url,
            "external_url": ext_url,
            "title": title,
            "brand": brand,
            "model": model,
            "price": price,
            "year": year,
            "km": km,
            "fuel_type": fuel_type,
            "engine_size": engine_size,
            "transmission": transmission,
            "horsepower": hp,
            "body_type": body_type,
            "location": dealer,
            "valuation": valuation,
            "market_savings": market_savings,
            "subtitle": subtitle,
        }

    def _parse_brand_model(self, title: str, subtitle: str = "") -> tuple:
        """Extract brand and model from listing title."""
        # Title format: "Usado (2023) BMW 216 116 HP | Bom preço"
        # Subtitle has: "Serie 2 Gran Coupé d Pack M"

        # Try subtitle first (it has cleaner model info)
        model_from_subtitle = subtitle.strip() if subtitle else ""

        # Strip "Usado (YEAR)" prefix from title
        clean_title = re.sub(r'^(?:Usado|Novo)\s*\(\d{4}\)\s*', '', title).strip()
        # Strip "| Bom preço" etc suffix
        clean_title = re.sub(r'\s*\|\s*(?:Super Preço|Bom preço|Preço justo|Preço elevado|Caro).*$', '', clean_title).strip()
        # Strip HP part
        clean_title = re.sub(r'\s+\d+\s*HP.*$', '', clean_title).strip()

        # Try to find brand in title
        brand = "Unknown"
        model = ""

        title_lower = clean_title.lower()
        for b in BRANDS:
            if b.lower() in title_lower:
                brand = b
                # Model is everything after brand
                idx = title_lower.index(b.lower()) + len(b)
                model = clean_title[idx:].strip()
                break

        if brand == "Unknown":
            parts = clean_title.split(maxsplit=1)
            brand = parts[0] if parts else "Unknown"
            model = parts[1] if len(parts) > 1 else ""

        brand = self._normalize_brand(brand)

        # If subtitle has more detail, use it for model
        if model_from_subtitle and len(model_from_subtitle) > len(model):
            model = model_from_subtitle

        return brand, model

    def _normalize_brand(self, raw: str) -> str:
        """Normalize brand name to proper capitalization."""
        if not raw:
            return "Unknown"
        brand_mapping = {
            "bmw": "BMW", "vw": "VW", "mg": "MG", "byd": "BYD",
            "ds": "DS", "man": "MAN", "iveco": "Iveco", "scania": "Scania",
            "citroen": "Citroën", "citroën": "Citroën",
            "land rover": "Land Rover", "landrover": "Land Rover",
            "mercedes": "Mercedes", "mercedes-benz": "Mercedes-Benz",
            "alfa romeo": "Alfa Romeo", "alfaromeo": "Alfa Romeo",
            "aston martin": "Aston Martin", "astonmartin": "Aston Martin",
            "range rover": "Land Rover",
            "peugeot": "Peugeot",
        }
        lower = raw.lower().strip()
        if lower in brand_mapping:
            return brand_mapping[lower]
        return raw.title()

    def _parse_euro(self, value: str) -> float:
        """Parse European price format (e.g. '29.500' or '29.500,00')."""
        value = value.strip()
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(".", "")
        try:
            return float(value)
        except ValueError:
            return 0.0

    def _normalize_fuel(self, raw: str) -> str:
        raw_lower = raw.lower().strip()
        for key, val in FUEL_MAP.items():
            if key.lower() in raw_lower:
                return val
        return raw_lower if raw_lower else "unknown"

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return int(value)
            digits = re.sub(r"\D", "", str(value))
            return int(digits) if digits else None
        except (ValueError, TypeError):
            return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = AutoUncleLightweight()
    results = s.scrape_listings("carros", max_listings=5)
    print(f"\n=== Scraped {len(results)} AutoUncle listings ===")
    for r in results[:5]:
        print(f"  {r.get('title','?')}")
        print(f"    Price: €{r.get('price','?')} | Year: {r.get('year','?')} | Km: {r.get('km','?')}")
        print(f"    Fuel: {r.get('fuel_type','?')} | Trans: {r.get('transmission','?')} | HP: {r.get('horsepower','?')}")
        print(f"    Valuation: {r.get('valuation','?')} | Savings: €{r.get('market_savings','?')}")
        print(f"    Brand: {r.get('brand','?')} | Model: {r.get('model','?')}")
        print()


def get_top_brand_model_pages() -> List[str]:
    """Get list of top brand-model page URLs from sitemap."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(
            f"{AutoUncleLightweight.BASE_URL}/sitemaps/pt/autouncle_brand-car_model-pages_links.xml",
            headers=headers, timeout=15,
        )
        urls = re.findall(r"<loc>(.*?)</loc>", r.text)
        return urls
    except Exception:
        return []
