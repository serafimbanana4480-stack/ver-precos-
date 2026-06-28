"""
Facebook Marketplace scraper for used vehicles in Portugal.

Facebook Marketplace blocks unauthenticated requests (login required).
This scraper tries Facebook first, then falls back to OLX Portugal,
marking all results as Source.FACEBOOK.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlencode, quote

import httpx

from database.models import Source, VehicleType

logger = logging.getLogger(__name__)

FACEBOOK_BASE = "https://www.facebook.com"
MARKETPLACE_URL = f"{FACEBOOK_BASE}/marketplace/category/vehicles"
OLX_BASE = "https://www.olx.pt"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

BRANDS = [
    "Volkswagen", "BMW", "Mercedes-Benz", "Mercedes", "Audi", "Renault",
    "Peugeot", "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
    "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo", "Mazda",
    "Mitsubishi", "Suzuki", "Dacia", "Opel", "Alfa Romeo", "Mini",
    "Smart", "Land Rover", "Jeep", "Porsche", "Jaguar", "Lexus",
    "Subaru", "Tesla", "Polestar", "DS", "Cupra",
]

FUEL_KEYWORDS = {
    "gasolina": "gasolina", "gasoline": "gasolina", "petrol": "gasolina",
    "diesel": "diesel", "gasóleo": "diesel",
    "elétrico": "eletrico", "eléctrico": "eletrico", "electric": "eletrico",
    "híbrido": "hibrido", "híbrido": "hibrido", "hybrid": "hibrido",
    "gpl": "gpl", "gnv": "gpl",
}


class FacebookScraper:
    """Scraper for Facebook Marketplace Portugal with OLX fallback.

    Facebook blocks unauthenticated requests, so this scraper falls back
    to OLX Portugal and tags all results as Source.FACEBOOK.
    """

    def __init__(self) -> None:
        self.source = Source.FACEBOOK
        self.source_name = Source.FACEBOOK.value

    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        scrape_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """Scrape vehicle listings from Facebook Marketplace Portugal.

        Args:
            vehicle_type: 'carros' or 'motos'
            max_listings: Maximum number of listings to return
            filters: Optional filters dict (brand, model, min_price, max_price, ...)
            scrape_details: Whether to scrape individual detail pages (not implemented)

        Returns:
            List of standardized vehicle listing dicts with source=Source.FACEBOOK
        """
        logger.info(
            "[FACEBOOK] A iniciar scraping para %s, max %d anúncios",
            vehicle_type, max_listings,
        )

        # Step 1: Try Facebook Marketplace directly (almost always blocked)
        listings = await self._try_facebook(vehicle_type, max_listings, filters)
        if listings:
            return listings

        # Step 2: Fallback to OLX
        logger.info("Facebook bloqueou - a usar fallback OLX")
        listings = await self._fallback_olx(vehicle_type, max_listings, filters)
        if listings:
            return listings

        logger.warning("[FACEBOOK] Todas as estratégias falharam")
        return []

    # ------------------------------------------------------------------
    # Facebook direct attempt
    # ------------------------------------------------------------------

    async def _try_facebook(
        self,
        vehicle_type: str,
        max_listings: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Try to fetch Facebook Marketplace listings via HTTP request."""
        url = self._build_facebook_url(vehicle_type, filters)
        headers = self._headers()

        try:
            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, verify=False,
            ) as client:
                resp = await client.get(url, headers=headers)
                logger.debug(
                    "[FACEBOOK_HTTP] %s -> %s (%d bytes)",
                    url, resp.status_code, len(resp.text),
                )

                if resp.status_code != 200:
                    return []

                if self._is_blocked(resp.text):
                    logger.debug("[FACEBOOK_HTTP] Página de bloqueio/login detetada")
                    return []

                # Try to extract listings from HTML
                return self._extract_from_html(resp.text, max_listings)

        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.debug("[FACEBOOK_HTTP] Pedido falhou: %s", e)
            return []

    # ------------------------------------------------------------------
    # OLX fallback
    # ------------------------------------------------------------------

    async def _fallback_olx(
        self,
        vehicle_type: str,
        max_listings: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Fallback to OLX Portugal when Facebook is blocked.

        Tries the existing project OLXScraper first, then direct HTTP.
        All results are tagged as Source.FACEBOOK.
        """
        # Try using the existing OLXScraper from the project
        try:
            from scrapers.olx_scraper import OLXScraper  # type: ignore[import-untyped]

            logger.debug("[FACEBOOK_OLX] A usar OLXScraper do projeto como fallback")
            olx = OLXScraper()
            olx_listings = await olx.scrape_listings(
                vehicle_type=vehicle_type,
                max_listings=max_listings,
                filters=filters,
                scrape_details=False,
            )
            if olx_listings:
                logger.info(
                    "[FACEBOOK_OLX] OLXScraper devolveu %d anúncios",
                    len(olx_listings),
                )
                return self._retag_as_facebook(olx_listings)
        except ImportError:
            logger.debug("[FACEBOOK_OLX] OLXScraper não disponível")
        except Exception as e:
            logger.warning("[FACEBOOK_OLX] OLXScraper falhou: %s", e)

        # Direct HTTP to OLX as last resort
        url = self._build_olx_url(vehicle_type, filters)
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        }

        try:
            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, verify=False,
            ) as client:
                resp = await client.get(url, headers=headers)
                logger.debug(
                    "[FACEBOOK_OLX_HTTP] %s -> %s (%d bytes)",
                    url, resp.status_code, len(resp.text),
                )

                if resp.status_code != 200:
                    return []

                listings = self._parse_olx_html(resp.text, vehicle_type, max_listings)
                return self._retag_as_facebook(listings)

        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.debug("[FACEBOOK_OLX_HTTP] Pedido falhou: %s", e)
            return []

    # ------------------------------------------------------------------
    # HTML extraction from Facebook
    # ------------------------------------------------------------------

    def _extract_from_html(self, html: str, max_listings: int) -> List[Dict[str, Any]]:
        """Extract listings from Facebook HTML using JSON-LD and regex."""
        listings: List[Dict[str, Any]] = []

        # Try JSON-LD structured data
        json_ld = self._extract_json_ld(html)
        if json_ld:
            return json_ld[:max_listings]

        # Try regex extraction
        regex = self._extract_regex(html)
        if regex:
            return regex[:max_listings]

        return listings

    def _extract_json_ld(self, html: str) -> List[Dict[str, Any]]:
        """Extract listings from JSON-LD script blocks."""
        results: List[Dict[str, Any]] = []
        pattern = re.compile(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            try:
                import json
                data = json.loads(match.group(1).strip())
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") in (
                        "Car", "Vehicle", "Product",
                    ):
                        listing = self._json_ld_to_listing(item)
                        if listing:
                            results.append(listing)
            except Exception:
                continue
        return results

    def _extract_regex(self, html: str) -> List[Dict[str, Any]]:
        """Fallback: extract listings using regex heuristics."""
        results: List[Dict[str, Any]] = []
        seen: set = set()

        link_pattern = re.compile(
            r'href=["\'](/marketplace/(?:item|listing)/(\d+)[^"\']*)["\']',
            re.IGNORECASE,
        )
        for m in link_pattern.finditer(html):
            path, listing_id = m.group(1), m.group(2)
            url = urljoin(FACEBOOK_BASE, path)
            if url in seen:
                continue
            seen.add(url)

            start = max(0, m.start() - 500)
            end = min(len(html), m.end() + 500)
            ctx = html[start:end]

            title = ""
            price: Optional[float] = None

            pm = re.search(r"(?:€|EUR)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)", ctx)
            if pm:
                try:
                    price = float(pm.group(1).replace(".", "").replace(",", "."))
                except ValueError:
                    pass

            tm = re.search(r'<span[^>]*>([^<]{10,100})</span>', ctx)
            if tm:
                candidate = tm.group(1).strip()
                if len(candidate) > 10 and "€" not in candidate:
                    title = candidate

            if not title:
                alt_m = re.search(r'alt=["\']([^"\']{10,})["\']', ctx)
                if alt_m:
                    title = alt_m.group(1).strip()

            if not title and not price:
                continue

            year: Optional[int] = None
            km: Optional[int] = None

            ym = re.search(r"\b(19|20)\d{2}\b", ctx)
            if ym:
                y = int(ym.group(0))
                if 1990 <= y <= 2030:
                    year = y

            km_m = re.search(r"(\d{1,3}(?:[.,]\d{3})*)\s*k[Mm]", ctx)
            if km_m:
                try:
                    km = int(km_m.group(1).replace(".", "").replace(",", ""))
                except ValueError:
                    pass

            listing = self._make_listing(
                url=url,
                title=title or f"Veículo {listing_id}",
                price=price,
                year=year,
                km=km,
                source_id=listing_id,
            )
            results.append(listing)

        return results

    def _json_ld_to_listing(self, item: dict) -> Optional[Dict[str, Any]]:
        """Convert a JSON-LD item to a standardized listing dict."""
        try:
            url = item.get("url", "")
            if isinstance(url, list):
                url = url[0] if url else ""

            title = item.get("name", item.get("title", ""))

            price: Optional[float] = None
            offers = item.get("offers", {})
            if isinstance(offers, dict):
                price = self._parse_price(offers.get("price"))
            elif isinstance(offers, list) and offers:
                price = self._parse_price(offers[0].get("price"))

            year: Optional[int] = None
            km: Optional[int] = None
            if "vehicleModelDate" in item:
                year = self._parse_year(item["vehicleModelDate"])
            if "mileageFromOdometer" in item:
                km = self._parse_km(item["mileageFromOdometer"])

            if not url and not title:
                return None

            source_id = hashlib.md5(url.encode()).hexdigest()[:16] if url else ""

            return self._make_listing(
                url=url, title=title or "Veículo", price=price,
                year=year, km=km, source_id=source_id,
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # OLX HTML parsing
    # ------------------------------------------------------------------

    def _parse_olx_html(
        self, html: str, vehicle_type: str, max_listings: int,
    ) -> List[Dict[str, Any]]:
        """Parse OLX.pt HTML to extract vehicle listings."""
        listings: List[Dict[str, Any]] = []

        try:
            from bs4 import BeautifulSoup  # type: ignore[import-untyped]

            soup = BeautifulSoup(html, "lxml")
            cards = soup.select('[data-cy="l-card"]')

            for card in cards:
                if len(listings) >= max_listings:
                    break
                listing = self._parse_olx_card(card)
                if listing:
                    listings.append(listing)
        except ImportError:
            logger.debug("[FACEBOOK_OLX] BeautifulSoup não disponível, a usar regex")
            listings = self._parse_olx_regex(html, max_listings)
        except Exception:
            listings = self._parse_olx_regex(html, max_listings)

        if not listings:
            listings = self._parse_olx_regex(html, max_listings)

        return listings

    def _parse_olx_card(self, card: Any) -> Optional[Dict[str, Any]]:
        """Parse a single OLX listing card."""
        try:
            link = card.select_one("a[href]")
            if not link:
                return None
            url = link.get("href", "")
            if isinstance(url, str) and url.startswith("/"):
                url = urljoin(OLX_BASE, url)
            if not url or "olx.pt" not in url:
                return None

            title_elem = card.select_one("h6, h2")
            title = title_elem.get_text(strip=True) if title_elem else ""

            price: Optional[float] = None
            price_elem = card.select_one(
                ".price, [class*='price'], [data-testid='price']",
            )
            if price_elem:
                price = self._parse_price(price_elem.get_text(strip=True))

            full_text = card.get_text(" ", strip=True)

            year: Optional[int] = None
            ym = re.search(r"\b(19|20)\d{2}\b", full_text)
            if ym:
                y = int(ym.group(0))
                if 1990 <= y <= 2030:
                    year = y

            km: Optional[int] = None
            km_m = re.search(r"(\d{1,3}(?:[., ]\d{3})*)\s*k[Mm]", full_text)
            if km_m:
                try:
                    km = int(re.sub(r"[^0-9]", "", km_m.group(1)))
                except ValueError:
                    pass

            fuel_type: Optional[str] = None
            for keyword in FUEL_KEYWORDS:
                if keyword.lower() in full_text.lower():
                    fuel_type = FUEL_KEYWORDS[keyword]
                    break

            location = ""
            loc_m = re.search(
                r"(?:-\s*)\s*([A-Za-zÀ-ÿ\s]+)\s*$",
                full_text.split("€")[-1].strip(),
            )
            if loc_m:
                location = loc_m.group(1).strip()

            source_id = hashlib.md5(url.encode()).hexdigest()[:16]

            return self._make_listing(
                url=url, title=title or "Veículo", price=price,
                year=year, km=km, fuel_type=fuel_type,
                location=location, source_id=source_id,
            )
        except Exception:
            return None

    def _parse_olx_regex(
        self, html: str, max_listings: int,
    ) -> List[Dict[str, Any]]:
        """Parse OLX HTML using regex when BeautifulSoup is unavailable."""
        listings: List[Dict[str, Any]] = []
        seen: set = set()

        olx_urls = re.findall(
            r'href=["\'](https?://(?:www\.)?olx\.pt/d/anuncio/[^"\']+)["\']',
            html,
        )
        # Deduplicate preserving order
        seen_urls = list(dict.fromkeys(olx_urls))

        for url in seen_urls:
            if len(listings) >= max_listings:
                break
            if url in seen:
                continue
            seen.add(url)

            idx = html.find(url)
            if idx == -1:
                continue
            start = max(0, idx - 800)
            end = min(len(html), idx + 200)
            ctx = html[start:end]

            title = ""
            tm = re.search(
                r'<(?:h6|h2)[^>]*>([^<]+)',
                ctx, re.IGNORECASE,
            )
            if tm:
                title = tm.group(1).strip()

            price: Optional[float] = None
            pm = re.search(r"(?:€|EUR)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)", ctx)
            if pm:
                price = self._parse_price(pm.group(0))

            if not title and not price:
                continue

            year: Optional[int] = None
            ym = re.search(r"\b(19|20)\d{2}\b", ctx)
            if ym:
                y = int(ym.group(0))
                if 1990 <= y <= 2030:
                    year = y

            km: Optional[int] = None
            km_m = re.search(
                r"(\d{1,3}(?:[., ]\d{3})*)\s*k[Mm]", ctx, re.IGNORECASE,
            )
            if km_m:
                try:
                    km = int(re.sub(r"[^0-9]", "", km_m.group(1)))
                except ValueError:
                    pass

            fuel_type: Optional[str] = None
            for keyword in FUEL_KEYWORDS:
                if keyword.lower() in ctx.lower():
                    fuel_type = FUEL_KEYWORDS[keyword]
                    break

            source_id = hashlib.md5(url.encode()).hexdigest()[:16]

            listing = self._make_listing(
                url=url, title=title or "Veículo", price=price,
                year=year, km=km, fuel_type=fuel_type,
                source_id=source_id,
            )
            listings.append(listing)

        return listings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _retag_as_facebook(
        self, listings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Re-tag all listings as FACEBOOK source."""
        for listing in listings:
            listing["source"] = self.source_name
            if "source" in listing:
                listing["source"] = self.source_name
        return listings

    def _build_facebook_url(
        self, vehicle_type: str, filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        url = MARKETPLACE_URL
        params: Dict[str, str] = {"locale": "pt_PT"}
        if filters:
            query = filters.get("query") or filters.get("brand")
            if query:
                params["query"] = str(query).strip()
            if filters.get("min_price"):
                params["minPrice"] = str(filters["min_price"])
            if filters.get("max_price"):
                params["maxPrice"] = str(filters["max_price"])
        if params:
            url += "?" + urlencode(params)
        return url

    def _build_olx_url(
        self, vehicle_type: str, filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        path = "carros" if vehicle_type == "carros" else "motos"
        url = f"{OLX_BASE}/{path}"
        params: List[str] = []
        if filters:
            if filters.get("brand"):
                params.append(f"q={quote(str(filters['brand']))}")
            if filters.get("min_price"):
                params.append(f"search[filter_float_price:from]={filters['min_price']}")
            if filters.get("max_price"):
                params.append(f"search[filter_float_price:to]={filters['max_price']}")
        if params:
            url += "?" + "&".join(params)
        return url

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.facebook.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }

    def _is_blocked(self, html: str) -> bool:
        indicators = [
            "login.php", "login", "checkpoint",
            "Sorry, something went wrong",
            "Please log in", "Log In",
            "Sign Up for Facebook",
            "content_placeholder", "captcha",
        ]
        lower = html.lower()
        return any(ind in lower for ind in indicators)

    def _make_listing(
        self,
        url: str,
        title: str,
        price: Optional[float] = None,
        year: Optional[int] = None,
        km: Optional[int] = None,
        fuel_type: Optional[str] = None,
        location: str = "",
        source_id: str = "",
    ) -> Dict[str, Any]:
        """Create a standardized listing dict with source=Source.FACEBOOK."""
        brand, model = self._parse_brand_model(title)
        if not source_id:
            source_id = hashlib.md5(url.encode()).hexdigest()[:16]

        return {
            "source": self.source_name,
            "source_id": source_id,
            "url": url,
            "title": title,
            "brand": brand,
            "model": model,
            "price": price,
            "year": year,
            "km": km,
            "fuel_type": fuel_type,
            "location": location,
            "vehicle_type": "carros",
            "first_seen": datetime.now(timezone.utc).isoformat(),
        }

    def _parse_price(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[€$£EUR\s]", "", value, flags=re.IGNORECASE).strip()
            cleaned = cleaned.replace(".", "").replace(",", ".")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _parse_year(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value if 1990 <= value <= 2030 else None
        if isinstance(value, str):
            m = re.search(r"\b(19|20)\d{2}\b", value)
            if m:
                y = int(m.group(0))
                return y if 1990 <= y <= 2030 else None
        return None

    def _parse_km(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            digits = re.sub(r"[^0-9]", "", value)
            try:
                return int(digits) if digits else None
            except ValueError:
                return None
        return None

    def _parse_brand_model(self, title: str) -> tuple[str, str]:
        if not title:
            return "Unknown", title
        title_lower = title.lower()
        for brand in BRANDS:
            idx = title_lower.find(brand.lower())
            if idx != -1:
                model = title[idx + len(brand):].strip()
                return brand, model
        parts = title.split(maxsplit=1)
        return (parts[0], parts[1]) if len(parts) >= 2 else (title, "")
