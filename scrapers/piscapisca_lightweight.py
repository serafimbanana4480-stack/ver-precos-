"""
PiscaPisca Lightweight Scraper — requests + BS4, sem Playwright.
O site usa Angular SSR com dados embutidos em <script id="ssr-app-state">.
Extrai listings diretamente do JSON state — sem parsing DOM.
Se bloqueado por Cloudflare, tenta novamente com retry.
"""
from __future__ import annotations
import hashlib
import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

FUEL_MAP = {
    "gasolina": "gasolina",
    "diesel": "diesel",
    "elétrico": "eletrico",
    "eléctrico": "eletrico",
    "eletrico": "eletrico",
    "híbrido": "hibrido",
    "hibrido": "hibrido",
    "gpl": "gpl",
}

TRANS_MAP = {
    "manual": "manual",
    "automática": "automatico",
    "automático": "automatico",
    "auto": "automatico",
}


class PiscaPiscaLightweight:
    """Scraper for PiscaPisca.pt using requests + SSR state JSON."""

    BASE_URL = "https://www.piscapisca.pt"

    def __init__(self):
        self.session = requests.Session()
        self._rotate_headers()

    def _rotate_headers(self):
        """Rotate user-agent to help avoid Cloudflare blocks."""
        self.session.headers.update({
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            ]),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            "Referer": "https://www.piscapisca.pt/",
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
        """
        Scrape listings from PiscaPisca.pt.

        Tenta obter o HTML (com retry se bloqueado por Cloudflare)
        e extrai listings do JSON Angular SSR embutido.
        """
        logger.info(f"[PISCAPISCA_LIGHT] Starting scrape for {vehicle_type}, max {max_listings}")

        listings = []
        page = 0

        while len(listings) < max_listings:
            url = f"{self.BASE_URL}/{vehicle_type}?page={page}"

            # Try up to 3 times per page (Cloudflare is intermittent)
            html = None
            for attempt in range(3):
                try:
                    resp = self.session.get(url, timeout=15)
                    if resp.status_code != 200:
                        logger.warning(f"[PISCAPISCA_LIGHT] HTTP {resp.status_code} on page {page}")
                        continue
                    if self._is_blocked(resp.text):
                        logger.warning(f"[PISCAPISCA_LIGHT] Cloudflare block on page {page}, retry {attempt + 1}")
                        self._rotate_headers()
                        time.sleep(2)
                        continue
                    html = resp.text
                    break
                except requests.RequestException as e:
                    logger.error(f"[PISCAPISCA_LIGHT] Request failed: {e}")
                    time.sleep(2)
                    continue

            if not html:
                logger.warning(f"[PISCAPISCA_LIGHT] Failed to get HTML for page {page}")
                break

            page_listings = self._parse_page(html)
            if not page_listings:
                logger.info(f"[PISCAPISCA_LIGHT] No more listings on page {page}")
                break

            logger.info(f"[PISCAPISCA_LIGHT] Page {page}: {len(page_listings)} listings")
            listings.extend(page_listings)
            page += 1

            if len(page_listings) < 20:  # Less than a full page means we're done
                break

        listings = listings[:max_listings]
        logger.info(f"[PISCAPISCA_LIGHT] Total extracted: {len(listings)}")
        return listings

    def _parse_page(self, html: str) -> List[Dict[str, Any]]:
        """Extract vehicle listings from the Angular SSR state JSON."""
        # Try SSR app state first (Angular Universal)
        match = re.search(
            r'<script[^>]*id="ssr-app-state"[^>]*type="application/json"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if match:
            try:
                state = json.loads(match.group(1))
                raw_vehicles = state.get("SEARCH_VEHICLES", [])
                if raw_vehicles:
                    listings = []
                    for v in raw_vehicles:
                        try:
                            listing = self._vehicle_to_dict(v)
                            if listing:
                                listings.append(listing)
                        except Exception as e:
                            logger.debug(f"[PISCAPISCA_LIGHT] Skipping vehicle: {e}")
                            continue
                    return listings
            except json.JSONDecodeError as e:
                logger.error(f"[PISCAPISCA_LIGHT] Failed to parse SSR state JSON: {e}")

        # Fallback: try __NEXT_DATA__ (in case they migrate)
        match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if match:
            try:
                data = json.loads(match.group(1))
                # Recursively find vehicles in the Next.js data
                vehicles = []
                self._find_vehicles_recursive(data, vehicles)
                if vehicles:
                    listings = []
                    for v in vehicles[:50]:  # Limit per page
                        listing = self._normalize_vehicle(v)
                        if listing:
                            listings.append(listing)
                    return listings
            except json.JSONDecodeError:
                pass

        # Last resort: DOM parsing with BeautifulSoup
        return self._parse_dom(html)

    def _find_vehicles_recursive(self, data: Any, found: List[Dict[str, Any]]) -> None:
        if isinstance(data, dict):
            if self._is_vehicle_node(data):
                found.append(data)
            else:
                for v in data.values():
                    self._find_vehicles_recursive(v, found)
        elif isinstance(data, list):
            for item in data:
                self._find_vehicles_recursive(item, found)

    def _is_vehicle_node(self, node: Dict[str, Any]) -> bool:
        has_price = any(k in node for k in ('price', 'preco', 'priceValue'))
        has_title = any(k in node for k in ('title', 'titulo', 'name'))
        has_url = any(k in node for k in ('url', 'link', 'slug'))
        return has_price and has_title and has_url

    def _normalize_vehicle(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            url = data.get('url') or data.get('link') or data.get('slug') or ''
            if not url:
                return None
            if url.startswith('/'):
                url = self.BASE_URL + url
            title = data.get('title') or data.get('titulo') or data.get('name') or ''
            if not title:
                return None
            price_raw = data.get('price') or data.get('preco')
            price = self._safe_float(price_raw)
            if not price:
                return None
            year = self._safe_int(data.get('year') or data.get('ano'))
            km_raw = data.get('mileage') or data.get('km')
            km = self._clean_km(km_raw) if km_raw else None
            fuel = str(data.get('fuel') or data.get('combustivel') or '')
            trans = str(data.get('transmission') or data.get('caixa') or '')

            return {
                "source": "piscapisca",
                "source_id": str(data.get('id') or url),
                "url": url,
                "title": title,
                "brand": str(data.get('brand') or self._parse_brand(title)),
                "model": str(data.get('model') or ''),
                "price": price,
                "year": year,
                "km": km,
                "fuel_type": fuel,
                "transmission": trans,
            }
        except Exception as e:
            logger.debug(f"[PISCAPISCA_LIGHT] Normalize error: {e}")
            return None

    def _vehicle_to_dict(self, v: dict) -> Optional[Dict[str, Any]]:
        """Convert a single vehicle from SSR state to our standard format."""
        prices = v.get("prices", {})
        price = prices.get("private") or prices.get("stand") or 0

        brand = (v.get("brand") or "").strip()
        model = (v.get("model") or "").strip()
        year = v.get("year")
        km_raw = v.get("km", "0")
        km = 0
        if km_raw:
            km_str = re.sub(r"[^\d]", "", str(km_raw))
            km = int(km_str) if km_str else 0

        fuel_raw = v.get("fuel", "")
        fuel_type = "unknown"
        for key, val in FUEL_MAP.items():
            if key.lower() in fuel_raw.lower():
                fuel_type = val
                break

        trans_raw = v.get("transmission", "")
        transmission = "unknown"
        for key, val in TRANS_MAP.items():
            if key.lower() in trans_raw.lower():
                transmission = val
                break

        link = v.get("link", "")
        url = f"{self.BASE_URL}{link}" if link and not link.startswith("http") else (link or "")

        if not url or not price or not brand:
            return None

        return {
            "title": f"{brand} {model} {year}" if year else f"{brand} {model}",
            "brand": brand,
            "model": model,
            "year": int(year) if year else None,
            "km": km,
            "price": float(price),
            "fuel_type": fuel_type,
            "transmission": transmission,
            "horsepower": None,
            "engine_size": None,
            "url": url,
            "source": "piscapisca",
            "source_id": hashlib.md5(url.encode()).hexdigest()[:16],
        }

    def _parse_dom(self, html: str) -> List[Dict[str, Any]]:
        """Fallback DOM parsing."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", class_=re.compile(r"flip-card", re.I))
        if not cards:
            cards = soup.find_all("div", class_=re.compile(r"card", re.I))
        listings = []
        for card in cards[:50]:
            try:
                text = card.get_text(" ", strip=True)
                price_m = re.search(r"(\d[\d\s]*(?:[.,]\d{2})?)\s*[€€]", text)
                price = self._safe_float(price_m.group(1)) if price_m else None
                if not price:
                    continue
                img = card.find("img")
                title = img.get("alt", "") if img else ""
                if not title:
                    title = text[:80]
                year_m = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", text)
                year = int(year_m.group(1)) if year_m else None
                km_m = re.search(r"(\d[\d\s]*(?:\.?\d{3})*)\s*km", text, re.I)
                km = self._clean_km(km_m.group(1)) if km_m else None
                listings.append({
                    "source": "piscapisca",
                    "source_id": hashlib.md5(title.encode()).hexdigest()[:16],
                    "url": "",
                    "title": title,
                    "brand": self._parse_brand(title),
                    "model": "",
                    "price": price,
                    "year": year,
                    "km": km,
                })
            except Exception as e:
                continue
        return listings

    def _parse_brand(self, title: str) -> str:
        brands = [
            "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz",
            "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
            "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
            "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo",
            "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini",
            "Smart", "Jeep", "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla",
        ]
        for brand in brands:
            if brand.lower() in title.lower():
                return brand
        return title.split()[0] if title else "Unknown"

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

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            text = re.sub(r"[^\d.,]", "", str(value))
            if not text.strip():
                return None
            if "," in text and "." in text:
                text = text.replace(".", "")
            text = text.replace(",", ".")
            return float(text) if text else None
        except (ValueError, TypeError):
            return None

    def _clean_km(self, raw: Any) -> int:
        if isinstance(raw, (int, float)):
            return int(raw)
        digits = re.sub(r"[^\d]", "", str(raw))
        return int(digits) if digits else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = PiscaPiscaLightweight()
    results = s.scrape_listings("carros", max_listings=5)
    print(f"\n=== Scraped {len(results)} listings ===")
    for r in results[:5]:
        print(f"  {r.get('title','?')} - €{r.get('price','?')}")
