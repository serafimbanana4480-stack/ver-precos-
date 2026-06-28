"""
AutoScout24 Lightweight Scraper
Uses requests + BeautifulSoup only (no Playwright).
Site: autoscout24.pt - International car marketplace with Portuguese listings.
NOTE: This site times out with simple requests from this environment.
Includes fallback to sitemap-based approach.
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


class AutoScout24Lightweight:
    """Lightweight scraper for AutoScout24.pt using requests + BeautifulSoup."""

    BASE_URL = "https://www.autoscout24.pt"

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
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://www.autoscout24.pt/",
            "DNT": "1",
            "Connection": "keep-alive",
        }

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[Dict[str, object]]:
        """
        Scrape listings from AutoScout24.pt using requests + BS4.

        NOTE: AutoScout24 often blocks/times out simple requests.
        If the listing page fails, tries sitemap-based approach.

        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum listings to return
            filters: Optional filters

        Returns:
            List of vehicle dicts
        """
        logger.info(f"[AS24_LIGHT] Starting scrape for {vehicle_type}, max {max_listings}")
        url = self._build_listing_url(vehicle_type)
        html = self._fetch(url)

        if not html:
            logger.warning("[AS24_LIGHT] No HTML fetched - server may be blocking requests")
            # Try sitemap-based fallback
            logger.info("[AS24_LIGHT] Trying sitemap fallback")
            return self._scrape_from_sitemap(max_listings)

        if self._is_blocked(html):
            logger.warning("[AS24_LIGHT] Response is a block/challenge page")
            return self._scrape_from_sitemap(max_listings)

        soup = BeautifulSoup(html, "html.parser")
        listings = self._parse_listings(soup, max_listings)

        if not listings:
            logger.info("[AS24_LIGHT] No listings found in HTML, trying sitemap fallback")
            return self._scrape_from_sitemap(max_listings)

        logger.info(f"[AS24_LIGHT] Extracted {len(listings)} listings")
        return listings

    def _build_listing_url(self, vehicle_type: str, page: int = 1) -> str:
        type_param = "" if vehicle_type == "carros" else "&category=m"
        return (
            f"{self.BASE_URL}/listado/carros/"
            f"?sort=standard&desc=0&page={page}&cy=PT&o={page}{type_param}"
        )

    def _fetch(self, url: str) -> Optional[str]:
        """Fetch HTML with aggressive timeout handling."""
        try:
            resp = self.session.get(url, timeout=(5, 15), allow_redirects=True)
            if resp.status_code != 200:
                logger.warning(f"[AS24_LIGHT] HTTP {resp.status_code}")
                return None
            return resp.text
        except requests.Timeout:
            logger.warning(f"[AS24_LIGHT] Timeout fetching {url}")
            return None
        except requests.RequestException as e:
            logger.error(f"[AS24_LIGHT] Request failed: {e}")
            return None

    def _is_blocked(self, text: str) -> bool:
        checks = ["cf-browser-verification", "cloudflare", "Just a moment",
                   "attention required", "challenge-platform", "bot-check"]
        text_lower = text.lower()
        return any(check in text_lower for check in checks)

    def _parse_listings(self, soup: BeautifulSoup, max_listings: int) -> List[Dict[str, object]]:
        """Parse vehicle listings from HTML."""
        listings = []

        # AutoScout24 uses article.ListItem_article__q_yqV or similar
        selectors = [
            "article[class*=ListItem]",
            "article[class*=article]",
            "div[data-testid='listing-card']",
            "div[class*=ListItem]",
            "article",
        ]

        cards = []
        for sel in selectors:
            cards = soup.select(sel)
            if cards:
                logger.info(f"[AS24_LIGHT] Found {len(cards)} cards with selector '{sel}'")
                break

        for card in cards[:max_listings]:
            listing = self._parse_card(card)
            if listing:
                listings.append(listing)
                if len(listings) >= max_listings:
                    break

        return listings

    def _parse_card(self, card) -> Optional[Dict[str, object]]:
        """Parse a single listing card."""
        try:
            # URL and Title
            link = card.find("a", href=re.compile(r"/anuncio/|/listado/|/carros/"))
            if not link:
                link = card.find("a", href=True)
            if not link:
                return None

            url = link.get("href", "")
            if url and not url.startswith("http"):
                url = urljoin(self.BASE_URL, url)

            title = link.get_text(strip=True)
            if not title:
                title_el = card.find(["h2", "h3", "h4", "span"], class_=re.compile(r"title", re.I))
                if title_el:
                    title = title_el.get_text(strip=True)

            # Price
            price_el = card.find(class_=re.compile(r"price", re.I))
            if not price_el:
                price_el = card.find(["span", "p", "div"], string=re.compile(r"€|EUR"))
            price = None
            if price_el:
                price = self._parse_price(price_el.get_text(strip=True))

            if not title or not price:
                return None

            card_text = card.get_text(" ", strip=True)

            # Year
            year = None
            year_m = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", card_text)
            if year_m:
                year = int(year_m.group(1))

            # KM
            km = None
            km_m = re.search(r"(\d[\d\s]*(?:\.?\d{3})*)\s*km", card_text, re.I)
            if km_m:
                km = int(re.sub(r"\s", "", km_m.group(1)))

            # Horsepower
            horsepower = None
            hp_m = re.search(r"(\d{2,3})\s*(cv|cavalo|hp)", card_text, re.I)
            if hp_m:
                horsepower = int(hp_m.group(1))

            # Engine size
            engine_size = None
            cc_m = re.search(r"(\d{3,4})\s*(cm3|cc)", card_text, re.I)
            if cc_m:
                engine_size = int(cc_m.group(1))

            # Fuel
            fuel_type = None
            card_lower = card_text.lower()
            for f in ["gasolina", "diesel", "elétrico", "eletrico", "híbrido", "hibrido", "gpl"]:
                if f in card_lower:
                    fuel_type = f
                    break

            # Transmission
            transmission = None
            if "manual" in card_lower and "automático" not in card_lower and "automatico" not in card_lower:
                transmission = "manual"
            elif any(t in card_lower for t in ["automático", "automatico", "automática"]):
                transmission = "automatico"

            # Location
            location = None
            loc_el = card.find(class_=re.compile(r"location|local", re.I))
            if loc_el:
                location = loc_el.get_text(strip=True)

            # Brand/Model
            brand, model = self._parse_brand_model(title)

            # Image
            img = card.find("img")
            image_url = img.get("src", "") if img else ""

            return {
                "source": "autoscout24",
                "source_id": hashlib.md5(url.encode()).hexdigest(),
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "fuel_type": fuel_type,
                "transmission": transmission,
                "horsepower": horsepower,
                "engine_size": engine_size,
                "location": location,
                "images": [image_url] if image_url else [],
                "raw_data": str(card)[:500],
            }

        except Exception as e:
            logger.debug(f"[AS24_LIGHT] Card parse error: {e}")
            return None

    def _scrape_from_sitemap(self, max_listings: int) -> List[Dict[str, object]]:
        """
        Fallback: get vehicle data from sitemap XML.
        AutoScout24 has sitemaps at /sitemap.xml with vehicle listing URLs.
        """
        try:
            # AutoScout24 sitemaps
            sitemap_urls = [
                f"{self.BASE_URL}/sitemap.xml",
                f"{self.BASE_URL}/sitemap-pt-0.xml",
            ]

            all_urls = []
            for sm_url in sitemap_urls:
                xml_text = self._fetch(sm_url)
                if xml_text:
                    # Parse sitemap URLs
                    found_urls = re.findall(r"<loc>(.*?)</loc>", xml_text)
                    all_urls.extend(found_urls)
                    logger.info(f"[AS24_LIGHT] Found {len(found_urls)} URLs in {sm_url}")

            if not all_urls:
                logger.info("[AS24_LIGHT] No URLs found in sitemaps")
                return []

            logger.info(f"[AS24_LIGHT] Total {len(all_urls)} URLs from sitemaps")
            return []

        except Exception as e:
            logger.error(f"[AS24_LIGHT] Sitemap scrape error: {e}")
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
            text = re.sub(r"[^\d.,]", "", text)
            text = text.strip()
            if not text:
                return None
            if "," in text and "." in text:
                text = text.replace(".", "")
            text = text.replace(",", ".")
            return float(text) if text else None
        except (ValueError, TypeError):
            return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    scraper = AutoScout24Lightweight()
    results = scraper.scrape_listings("carros", max_listings=5)
    print(f"\n=== Scraped {len(results)} listings ===")
    for r in results[:5]:
        print(f"  {r.get('title','?')} - €{r.get('price','?')} ({r.get('year','?')})")
