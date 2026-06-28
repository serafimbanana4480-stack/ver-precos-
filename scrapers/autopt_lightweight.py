"""
AutoPt Lightweight Scraper
Uses requests + BeautifulSoup only (no Playwright).
Site: auto.pt - PHP/Laravel, server-rendered car listing site.
Extracts data from <article> elements inside <a data-testid="car_listing_entry">.
"""
from __future__ import annotations
import hashlib
import logging
import random
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from database.models import Source, VehicleType

logger = logging.getLogger(__name__)

BRANDS = [
    "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz",
    "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
    "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
    "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo",
    "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini",
    "Smart", "Jeep", "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla",
    "Ducati", "Yamaha", "Kawasaki", "Triumph", "KTM",
]


class AutoPtLightweightScraper:
    """Lightweight scraper for Auto.pt using requests + BeautifulSoup.

    Auto.pt is a PHP/Laravel server-rendered site. Each page has 20 <article>
    elements inside <a data-testid="car_listing_entry"> with complete data:
    brand, model, price, year, km, fuel type, and location.
    """

    BASE_URL = "https://www.auto.pt"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(self._headers())

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            ]),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            "Referer": "https://www.auto.pt/",
            "DNT": "1",
        }

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[Dict[str, object]]:
        """Scrape listings from Auto.pt using requests + BS4.

        Auto.pt has clean HTML with <article> elements for each listing.
        Data is present in the HTML including title, price, year, km, fuel.

        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum listings to return
            filters: Optional filters dict with keys: brand, model, min_price, max_price

        Returns:
            List of vehicle dicts with keys: title, price, year, km, brand,
            model, fuel_type, transmission, url, source_id, source, location
        """
        logger.info(f"[AUTOPT_LIGHT] Starting scrape for {vehicle_type}, max {max_listings}")
        url = self._build_url(vehicle_type, filters)
        html = self._fetch(url)

        if not html:
            logger.warning("[AUTOPT_LIGHT] No HTML fetched")
            return []

        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: Parse a[data-testid="car_listing_entry"] elements (preferred)
        listings = self._parse_listing_links(soup, max_listings)
        if listings:
            logger.info(f"[AUTOPT_LIGHT] Extracted {len(listings)} listings from listing links")
            return listings

        # Strategy 2: Parse <article> elements
        listings = self._parse_articles(soup, max_listings)
        if listings:
            logger.info(f"[AUTOPT_LIGHT] Extracted {len(listings)} listings from articles")
            return listings

        # Strategy 3: Extract from schema.org JSON-LD (limited data)
        listings = self._extract_from_schema(soup, max_listings)
        logger.info(f"[AUTOPT_LIGHT] Extracted {len(listings)} listings from schema")
        return listings

    def _build_url(self, vehicle_type: str, filters: Optional[Dict[str, object]] = None) -> str:
        path = "/carros-usados" if vehicle_type == "carros" else "/motos-usadas"
        url = f"{self.BASE_URL}{path}"
        params = []
        if filters:
            if filters.get("brand"):
                params.append(f"marca={filters['brand']}")
            if filters.get("model"):
                params.append(f"modelo={filters['model']}")
            if filters.get("min_price"):
                params.append(f"preco_min={filters['min_price']}")
            if filters.get("max_price"):
                params.append(f"preco_max={filters['max_price']}")
        if params:
            url += "?" + "&".join(params)
        return url

    def _fetch(self, url: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=20, allow_redirects=True)
            if resp.status_code != 200:
                logger.warning(f"[AUTOPT_LIGHT] HTTP {resp.status_code}")
                return None
            return resp.text
        except requests.RequestException as e:
            logger.error(f"[AUTOPT_LIGHT] Request failed: {e}")
            return None

    def _parse_listing_links(self, soup: BeautifulSoup, max_listings: int) -> List[Dict[str, object]]:
        """Parse a[data-testid='car_listing_entry'] elements - the main card wrapper."""
        listings = []
        links = soup.select('a[data-testid="car_listing_entry"]')
        if not links:
            # Try fallback selector
            links = soup.select('a[id^="item_"]')

        logger.debug(f"[AUTOPT_LIGHT] Found {len(links)} listing links")

        for a_tag in links[:max_listings]:
            try:
                listing = self._parse_card(a_tag)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[AUTOPT_LIGHT] Card parse error: {e}")
                continue

        return listings

    def _parse_card(self, card) -> Optional[Dict[str, object]]:
        """Parse a single card element (a[data-testid] or article)."""
        try:
            # URL from the <a> tag
            url = card.get("href", "") if card.name == "a" else ""
            if not url:
                parent_a = card.find_parent("a", href=True)
                if parent_a:
                    url = parent_a.get("href", "")
                else:
                    a_inside = card.find("a", href=True)
                    if a_inside:
                        url = a_inside.get("href", "")

            if not url:
                return None

            if url and not url.startswith("http"):
                full_url = urljoin(self.BASE_URL, url)
            else:
                full_url = url

            # Source ID from URL
            source_id = hashlib.md5(full_url.encode()).hexdigest()

            # Image and alt text
            img = card.find("img")
            img_alt = img.get("alt", "").strip() if img else ""
            img_url = img.get("src", "") if img else ""

            # Title: from h2 or img alt
            h2 = card.find("h2")
            title_from_h2 = h2.get_text(strip=True) if h2 else ""

            # Model/version from p tag after h2
            p_model = card.find("p")
            model_version = p_model.get_text(strip=True) if p_model else ""

            # Build title
            title = title_from_h2 or img_alt or ""
            if title and model_version and model_version not in title:
                # Check if model_version is a known model continuation or version
                title = f"{title} {model_version}"

            if not title:
                return None

            # Price
            price = None
            # Price is in a div with "€" text
            price_elem = card.find("div", string=re.compile(r"[\d\s]+\s*[€€]"))
            if not price_elem:
                # Try finding by class pattern
                price_elem = card.select_one("div.rounded-3xl")
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._parse_price(price_text)

            if not price:
                # Try full text search
                full_text = card.get_text(" ", strip=True)
                price_m = re.search(r"(\d[\d\s]*(?:[.,]\d{2})?)\s*[€€]", full_text)
                if price_m:
                    price = self._parse_price(price_m.group(1))

            if not price:
                return None

            # Get details from the <ul> grid (fuel, year, km)
            ul = card.find("ul")
            li_items = ul.find_all("li") if ul else []

            fuel_type = None
            year = None
            km = None

            for li in li_items:
                li_text = li.get_text(" ", strip=True)
                li_lower = li_text.lower()

                # Check fuel type - handle both "elétrico" and "eléctrico" spelling
                if any(f in li_lower for f in ["gasolina", "diesel", "elétrico", "eletrico",
                                                  "eléctrico", "electrico",
                                                  "híbrido", "hibrido", "gpl", "hidrogénio"]):
                    fuel_type = self._normalize_fuel(li_text)

                # Check year (4 digits)
                year_m = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", li_text)
                if year_m:
                    year = int(year_m.group(1))

                # Check km
                km_m = re.search(r"([\d\s.]+)\s*km", li_text, re.I)
                if km_m:
                    km_str = re.sub(r"[\s.]", "", km_m.group(1))
                    try:
                        km = int(km_str) if km_str else None
                    except ValueError:
                        pass

            # Alternative: parse from full text if ul parsing didn't work
            if not any([fuel_type, year, km]):
                full_text_lower = card.get_text(" ", strip=True).lower()
                for f in ["gasolina", "diesel", "elétrico", "eletrico", "híbrido", "hibrido", "gpl"]:
                    if f in full_text_lower:
                        fuel_type = self._normalize_fuel(f)
                        break
                if not year:
                    year_m = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", card.get_text())
                    if year_m:
                        year = int(year_m.group(1))
                if not km:
                    km_m = re.search(r"([\d\s.]+)\s*km", card.get_text(), re.I)
                    if km_m:
                        km_str = re.sub(r"[\s.]", "", km_m.group(1))
                        try:
                            km = int(km_str) if km_str else None
                        except ValueError:
                            pass

            # Location from the location div
            location = ""
            location_div = card.find("div", class_=lambda c: c and "mt-5" in c.split())
            if location_div:
                location_text = location_div.get_text(" ", strip=True)
                # Pattern: "V252 | Location" or just "Location"
                if "|" in location_text:
                    location = location_text.split("|")[-1].strip()
                else:
                    location = location_text.strip()

            # Transmission is usually not shown on listing cards, try to infer from text
            transmission = None
            full_text_lower = card.get_text(" ", strip=True).lower()
            if "manual" in full_text_lower and "automático" not in full_text_lower and "automatico" not in full_text_lower:
                transmission = "manual"
            elif any(t in full_text_lower for t in ["automático", "automatico", "automática"]):
                transmission = "automatico"

            # Brand/Model from title
            brand, model = self._parse_brand_model(title)

            return {
                "source": Source.AUTOPT.value if hasattr(Source.AUTOPT, 'value') else "AUTOPT",
                "source_id": source_id,
                "url": full_url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "fuel_type": fuel_type,
                "transmission": transmission,
                "location": location,
                "images": [img_url] if img_url else [],
            }

        except Exception as e:
            logger.debug(f"[AUTOPT_LIGHT] Card parse error: {e}")
            return None

    def _parse_articles(self, soup: BeautifulSoup, max_listings: int) -> List[Dict[str, object]]:
        """Fallback: parse <article> elements directly."""
        articles = soup.find_all("article")
        listings = []
        for art in articles[:max_listings]:
            listing = self._parse_card(art)
            if listing:
                listings.append(listing)
        return listings

    def _extract_from_schema(self, soup: BeautifulSoup, max_listings: int) -> List[Dict[str, object]]:
        """Fallback: extract listings from schema.org ItemList JSON-LD (limited data)."""
        import json as json_module

        for script in soup.find_all("script"):
            text = script.string
            if not text or not text.strip():
                continue
            try:
                data = json_module.loads(text.strip())
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    elements = data.get("itemListElement", [])
                    listings = []
                    for item in elements[:max_listings]:
                        url = item.get("url", "")
                        if not url:
                            continue

                        if not url.startswith("http"):
                            url = urljoin(self.BASE_URL, url)

                        # Extract title from URL path
                        path_parts = url.rstrip("/").split("/")
                        title_from_url = path_parts[-1] if path_parts else ""
                        title = re.sub(r"-id-[a-zA-Z0-9]+$", "", title_from_url)
                        title = title.replace("-", " ").title()

                        brand, model = self._parse_brand_model(title)

                        listings.append({
                            "source": Source.AUTOPT.value if hasattr(Source.AUTOPT, 'value') else "AUTOPT",
                            "source_id": hashlib.md5(url.encode()).hexdigest(),
                            "url": url,
                            "title": title,
                            "brand": brand,
                            "model": model,
                            "price": None,
                            "year": None,
                            "km": None,
                            "fuel_type": None,
                            "transmission": None,
                            "location": None,
                            "images": [],
                        })
                    return listings
            except (json_module.JSONDecodeError, AttributeError):
                continue
        return []

    def _parse_brand_model(self, title: str) -> tuple[str, str]:
        if not title:
            return "Unknown", ""
        title_lower = title.lower()
        for brand in BRANDS:
            idx = title_lower.find(brand.lower())
            if idx != -1:
                model = title[idx + len(brand):].strip()
                return brand, model
        parts = title.split(maxsplit=1)
        return (parts[0], parts[1]) if len(parts) >= 2 else (title, "")

    def _parse_price(self, text: str) -> Optional[float]:
        try:
            if not text:
                return None
            # Remove currency symbols and normalize
            text = re.sub(r"[^\d.,]", "", text)
            text = text.strip()
            if not text:
                return None
            # Portuguese format: 1.234,56 or 1234,56 or 1234
            if "," in text and "." in text:
                # Check if dots are thousands separators
                if text.rindex(",") > text.rindex("."):
                    text = text.replace(".", "")
                else:
                    text = text.replace(",", "")
            elif "," in text:
                text = text.replace(",", ".")
            return float(text)
        except (ValueError, TypeError):
            return None

    def _normalize_fuel(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        raw_lower = raw.lower().strip()
        if any(k in raw_lower for k in ("gasolina", "gasoline", "petrol")):
            return "gasolina"
        if any(k in raw_lower for k in ("diesel", "gasóleo")):
            return "diesel"
        if any(k in raw_lower for k in ("elétrico", "eletrico", "electric", "eléctrico", "electrico")):
            return "eletrico"
        if any(k in raw_lower for k in ("híbrido", "hibrido", "hybrid")):
            return "hibrido"
        if "gpl" in raw_lower:
            return "gpl"
        return raw if raw else None


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    scraper = AutoPtLightweightScraper()
    results = asyncio.run(scraper.scrape_listings("carros", max_listings=5))
    print(f"\n=== Scraped {len(results)} listings === ")
    for r in results[:5]:
        print(f"  {r.get('title','?')} - €{r.get('price','?')} ({r.get('year','?')}) - {r.get('km','?')} km - {r.get('fuel_type','?')} - {r.get('location','?')}")
