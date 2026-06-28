"""
Carplus Lightweight Scraper
Uses requests + BeautifulSoup only (no Playwright).
Site: carplus.pt - Nuxt/Vue-based car listing site.
Extracts data from application/ld+json <script> blocks with @type Vehicle.
"""
from __future__ import annotations
import hashlib
import json
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


class CarplusLightweightScraper:
    """Lightweight scraper for Carplus.pt using requests + BeautifulSoup.

    Extracts vehicle listings from application/ld+json <script> blocks
    with @type Vehicle (16 per page), which contain complete structured data.
    """

    BASE_URL = "https://www.carplus.pt"

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
            "Referer": "https://www.carplus.pt/",
            "DNT": "1",
        }

    def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[Dict[str, object]]:
        """Scrape listings from Carplus.pt using requests + BS4.

        Strategy:
        1. Extract from application/ld+json <script> blocks with @type Vehicle
        2. Fallback to DOM parsing of vehicle-card elements

        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum listings to return
            filters: Optional filters dict with keys: brand, max_price, min_year

        Returns:
            List of vehicle dicts with keys: title, price, year, km, brand,
            model, fuel_type, transmission, url, source_id, source
        """
        logger.info(f"[CARPLUS_LIGHT] Starting scrape for {vehicle_type}, max {max_listings}")
        url = self._build_url(vehicle_type, filters)
        html = self._fetch(url)

        if not html:
            logger.warning("[CARPLUS_LIGHT] No HTML fetched")
            return []

        # Strategy 1: Extract from LD+JSON Vehicle blocks (fastest, most complete)
        listings = self._extract_from_ldjson(html, max_listings)
        if listings:
            logger.info(f"[CARPLUS_LIGHT] Extracted {len(listings)} listings from LD+JSON")
            return listings

        # Strategy 2: Try application/json Nuxt state
        listings = self._extract_from_nuxt_json(html, max_listings)
        if listings:
            logger.info(f"[CARPLUS_LIGHT] Extracted {len(listings)} listings from Nuxt JSON")
            return listings

        # Fallback to DOM parsing
        logger.info("[CARPLUS_LIGHT] JSON extraction returned 0, trying DOM parsing")
        soup = BeautifulSoup(html, "html.parser")
        listings = self._parse_dom(soup, max_listings)
        logger.info(f"[CARPLUS_LIGHT] Extracted {len(listings)} listings from DOM")
        return listings

    def _build_url(self, vehicle_type: str, filters: Optional[Dict[str, object]] = None) -> str:
        path = "/carros-usados/" if vehicle_type == "carros" else "/motos-usadas/"
        url = f"{self.BASE_URL}{path}"
        params = []
        if filters:
            if filters.get("brand"):
                params.append(f"marca={filters['brand']}")
            if filters.get("max_price"):
                params.append(f"preco_ate={filters['max_price']}")
            if filters.get("min_year"):
                params.append(f"ano_min={filters['min_year']}")
        if params:
            url += "?" + "&".join(params)
        return url

    def _fetch(self, url: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=20, allow_redirects=True)
            if resp.status_code != 200:
                logger.warning(f"[CARPLUS_LIGHT] HTTP {resp.status_code}")
                return None
            return resp.text
        except requests.RequestException as e:
            logger.error(f"[CARPLUS_LIGHT] Request failed: {e}")
            return None

    def _extract_from_ldjson(self, html: str, max_listings: int) -> List[Dict[str, object]]:
        """Extract vehicle data from application/ld+json script blocks with @type Vehicle."""
        try:
            ld_blocks = re.findall(
                r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                html, re.DOTALL
            )
            if not ld_blocks:
                logger.debug("[CARPLUS_LIGHT] No LD+JSON blocks found")
                return []

            vehicles = []
            for block in ld_blocks:
                try:
                    data = json.loads(block.strip())
                    if isinstance(data, dict) and data.get("@type") == "Vehicle":
                        vehicles.append(data)
                except (json.JSONDecodeError, AttributeError):
                    continue

            logger.debug(f"[CARPLUS_LIGHT] Found {len(vehicles)} Vehicle LD+JSON blocks")

            listings = []
            for v in vehicles[:max_listings]:
                listing = self._normalize_from_ldjson(v)
                if listing:
                    listings.append(listing)

            return listings

        except Exception as e:
            logger.debug(f"[CARPLUS_LIGHT] LD+JSON extraction error: {e}")
            return []

    def _normalize_from_ldjson(self, data: Dict[str, Any]) -> Optional[Dict[str, object]]:
        """Normalize a Vehicle LD+JSON object to standard schema."""
        try:
            # Name
            name = data.get("name", "") or ""

            # Brand
            brand_obj = data.get("brand", {})
            if isinstance(brand_obj, dict):
                brand = brand_obj.get("name", "")
            else:
                brand = str(brand_obj) if brand_obj else ""

            # Model
            model = data.get("model", "") or ""

            # Build title from brand + model (more complete than 'name' field)
            if brand and model:
                title = f"{brand} {model}".strip()
            else:
                title = name or ""
            if not title:
                return None

            # Price from offers
            offers = data.get("offers", {})
            if isinstance(offers, dict):
                price = self._safe_float(offers.get("price"))
                url = offers.get("url", "")
            else:
                price = None
                url = ""

            if not price:
                return None

            # Normalize URL
            if url and not url.startswith("http"):
                url = urljoin(self.BASE_URL, url)

            # Mileage
            mileage = data.get("mileageFromOdometer", {})
            if isinstance(mileage, dict):
                km = self._safe_int(mileage.get("value"))
            else:
                km = None

            # Production date -> year
            prod_date = data.get("productionDate", "")
            year = None
            if prod_date:
                m = re.search(r"(\d{4})", str(prod_date))
                if m:
                    year = int(m.group(1))

            # Fuel type
            fuel_type = str(data.get("fuelType", "") or "")

            # Transmission
            transmission = str(data.get("vehicleTransmission", "") or "")

            # Image
            image = data.get("image", "") or ""

            # Source ID from URL
            source_id = hashlib.md5(url.encode()).hexdigest() if url else hashlib.md5(title.encode()).hexdigest()

            return {
                "source": Source.CARPLUS.value if hasattr(Source.CARPLUS, 'value') else "CARPLUS",
                "source_id": source_id,
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "fuel_type": self._normalize_fuel(fuel_type),
                "transmission": self._normalize_transmission(transmission),
                "images": [image] if image else [],
            }

        except Exception as e:
            logger.debug(f"[CARPLUS_LIGHT] LD+JSON normalize error: {e}")
            return None

    def _extract_from_nuxt_json(self, html: str, max_listings: int) -> List[Dict[str, object]]:
        """Extract vehicle data from embedded Nuxt JSON payload (fallback)."""
        try:
            json_blocks = re.findall(
                r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
                html, re.DOTALL
            )
            if not json_blocks:
                return []

            vehicles = []
            for block in json_blocks:
                if len(block) < 1000:
                    continue
                try:
                    data = json.loads(block)
                    vehicles = self._find_vehicles_in_nuxt(data)
                    if vehicles:
                        break
                except json.JSONDecodeError:
                    continue

            if not vehicles:
                return []

            listings = []
            for v in vehicles[:max_listings]:
                listing = self._normalize_vehicle(v)
                if listing:
                    listings.append(listing)
            return listings

        except Exception as e:
            logger.debug(f"[CARPLUS_LIGHT] Nuxt JSON extraction error: {e}")
            return []

    def _find_vehicles_in_nuxt(self, data: Any, depth: int = 0) -> List[Dict[str, Any]]:
        """Recursively search Nuxt state for vehicle arrays."""
        if depth > 10:
            return []

        vehicles = []

        if isinstance(data, dict):
            if self._is_vehicle_dict(data):
                vehicles.append(data)
            else:
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 2:
                        for item in value:
                            if isinstance(item, dict) and self._is_vehicle_dict(item):
                                vehicles.append(item)
                    elif isinstance(value, (dict, list)):
                        vehicles.extend(self._find_vehicles_in_nuxt(value, depth + 1))

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and self._is_vehicle_dict(item):
                    vehicles.append(item)
                elif isinstance(item, (dict, list)):
                    vehicles.extend(self._find_vehicles_in_nuxt(item, depth + 1))

        return vehicles

    def _is_vehicle_dict(self, node: Dict[str, Any]) -> bool:
        """Check if a dict likely represents a vehicle listing."""
        has_price = any(k in node for k in ("price", "preco", "priceValue", "precoVenda"))
        has_title_or_brand = any(
            k in node for k in ("title", "titulo", "modelo", "model", "name", "marca", "marca_id", "brand")
        )
        price_val = node.get("price") or node.get("preco") or node.get("precoVenda")
        price_is_number = isinstance(price_val, (int, float)) or (
            isinstance(price_val, str) and bool(re.search(r"\d", price_val))
        )
        return has_price and has_title_or_brand and price_is_number

    def _normalize_vehicle(self, data: Dict[str, Any]) -> Optional[Dict[str, object]]:
        """Normalize a vehicle dict from Nuxt JSON to standard schema."""
        try:
            url = data.get("url") or data.get("link") or data.get("slug") or ""
            if url and not url.startswith("http"):
                url = urljoin(self.BASE_URL, url)
            if not url:
                return None

            title = data.get("title") or data.get("titulo") or data.get("name") or ""
            if not title:
                brand_name = data.get("marca") or data.get("brand") or data.get("marca_nome") or ""
                model_name = data.get("modelo") or data.get("model") or ""
                if isinstance(brand_name, dict):
                    brand_name = brand_name.get("name", "")
                if isinstance(model_name, dict):
                    model_name = model_name.get("name", "")
                if brand_name and model_name:
                    title = f"{brand_name} {model_name}"
            if not title:
                return None

            price_raw = data.get("price") or data.get("preco") or data.get("precoVenda") or data.get("priceValue")
            price = self._safe_float(price_raw)
            if not price:
                return None

            year = self._safe_int(data.get("year") or data.get("ano") or data.get("anoRegisto"))
            km = self._safe_int(data.get("mileage") or data.get("km") or data.get("quilometragem") or data.get("kms"))
            fuel = str(data.get("fuel") or data.get("combustivel") or data.get("fuelType") or data.get("tipoCombustivel") or "")
            transmission = str(data.get("transmission") or data.get("caixa") or data.get("transmissao") or "")

            brand, model = self._parse_brand_model(title)

            return {
                "source": Source.CARPLUS.value if hasattr(Source.CARPLUS, 'value') else "CARPLUS",
                "source_id": str(data.get("id") or data.get("_id") or data.get("uuid") or hashlib.md5(url.encode()).hexdigest()),
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "fuel_type": self._normalize_fuel(fuel),
                "transmission": self._normalize_transmission(transmission),
            }

        except Exception as e:
            logger.debug(f"[CARPLUS_LIGHT] Normalize error: {e}")
            return None

    def _parse_dom(self, soup: BeautifulSoup, max_listings: int) -> List[Dict[str, object]]:
        """Fallback: parse vehicle cards from DOM."""
        listings = []

        selectors = [
            "div.vehicle-card",
            "div.vehicle-card-container",
            "div.card.linkable",
            "div[class*=vehicle-card]",
            "div[class*=card]",
        ]

        cards = []
        for sel in selectors:
            cards = soup.select(sel)
            if cards:
                logger.debug(f"[CARPLUS_LIGHT] Found {len(cards)} cards with selector '{sel}'")
                break

        for card in cards[:max_listings]:
            try:
                link = card.find("a", href=True)
                if not link:
                    continue
                url = link.get("href", "")
                if url and not url.startswith("http"):
                    url = urljoin(self.BASE_URL, url)

                card_text = card.get_text(" ", strip=True)
                link_text = link.get_text(" ", strip=True)

                # Extract title before fuel type appears
                title = ""
                for sep in ["Gasolina", "Diesel", "Elétrico", "Eletrico", "Híbrido", "Hibrido",
                            "gasolina", "diesel", "elétrico", "eletrico"]:
                    if sep in link_text:
                        idx = link_text.index(sep)
                        title = link_text[:idx].strip()
                        break

                if not title:
                    img = card.find("img")
                    if img and img.get("alt"):
                        title = img.get("alt", "").strip()

                if not title:
                    title = card_text[:80].strip()

                if not title:
                    continue

                # Price
                price = None
                price_m = re.search(r"(\d[\d\s]*(?:[.,]\d{2})?)\s*[€€]", card_text)
                if price_m:
                    price_text = price_m.group(1).strip()
                    price_text = re.sub(r"\s+", "", price_text)
                    if "," in price_text:
                        price_text = price_text.replace(".", "").replace(",", ".")
                    try:
                        price = float(price_text)
                    except ValueError:
                        pass

                if not price:
                    continue

                # Year
                year = None
                year_m = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", card_text)
                if year_m:
                    year = int(year_m.group(1))

                # KM
                km = None
                km_m = re.search(r"(\d[\d\s]*(?:\.?\d{3})*)\s*km", card_text, re.I)
                if km_m:
                    km_str = re.sub(r"\s+", "", km_m.group(1))
                    km = int(km_str) if km_str else None

                brand, model = self._parse_brand_model(title)

                card_lower = card_text.lower()
                fuel = None
                for f in ["gasolina", "diesel", "elétrico", "eletrico", "híbrido", "hibrido", "gpl", "electrico"]:
                    if f in card_lower:
                        fuel = f.replace("electrico", "eletrico")
                        break

                trans = None
                if "manual" in card_lower and "automático" not in card_lower and "automatico" not in card_lower and "automática" not in card_lower:
                    trans = "manual"
                elif any(t in card_lower for t in ["automático", "automatico", "automática"]):
                    trans = "automatico"

                listings.append({
                    "source": Source.CARPLUS.value if hasattr(Source.CARPLUS, 'value') else "CARPLUS",
                    "source_id": hashlib.md5(url.encode()).hexdigest(),
                    "url": url,
                    "title": title,
                    "brand": brand,
                    "model": model,
                    "price": price,
                    "year": year,
                    "km": km,
                    "fuel_type": fuel,
                    "transmission": trans,
                })

            except Exception as e:
                logger.debug(f"[CARPLUS_LIGHT] DOM parse error: {e}")
                continue

        return listings

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

    def _normalize_transmission(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        raw_lower = raw.lower().strip()
        if "manual" in raw_lower:
            return "manual"
        if any(k in raw_lower for k in ("automático", "automatico", "automatic", "automática")):
            return "automatico"
        return raw if raw else None


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    scraper = CarplusLightweightScraper()
    results = asyncio.run(scraper.scrape_listings("carros", max_listings=5))
    print(f"\n=== Scraped {len(results)} listings === ")
    for r in results[:5]:
        print(f"  {r.get('title','?')} - €{r.get('price','?')} ({r.get('year','?')}) - {r.get('km','?')} km - {r.get('fuel_type','?')}")
