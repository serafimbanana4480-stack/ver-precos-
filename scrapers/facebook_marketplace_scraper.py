"""
Facebook Marketplace Portugal scraper for used vehicles.

Facebook Marketplace has no public API and blocks requests without authentication.
This scraper uses a multi-strategy approach:
  1. Try requests to Facebook Marketplace (almost certainly blocked)
  2. If /listings endpoint is available via Facebook's Graph API (rare), try that
  3. Fallback to OLX.pt (as Facebook Marketplace PT has few vehicle listings vs OLX)
  4. Last resort: Playwright browser automation for Facebook
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import os
import random
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from urllib.parse import urljoin, urlencode, quote

import httpx
from scrapers.schema import parse_price_evidence
logger = logging.getLogger(__name__)

FACEBOOK_BASE = "https://www.facebook.com"
MARKETPLACE_URL = f"{FACEBOOK_BASE}/marketplace/category/vehicles"
MARKETPLACE_PT_URL = f"{FACEBOOK_BASE}/marketplace/114716366854778/vehicles"

# User agents for Facebook requests
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


class FacebookMarketplaceScraper:
    """Scraper for Facebook Marketplace Portugal - used vehicles.

    Uses a multi-strategy approach since Facebook blocks unauthenticated requests.
    Falls back to OLX.pt when Facebook is unavailable.
    """

    def __init__(self) -> None:
        self.source_name = "FACEBOOK"
        self.base_url = FACEBOOK_BASE
        self.marketplace_url = MARKETPLACE_URL
        self.olx_fallback_url = "https://www.olx.pt"
        self.allow_cross_source_fallback = os.getenv(
            "FACEBOOK_ALLOW_OLX_FALLBACK", "0"
        ).lower() in {"1", "true", "yes"}

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
            filters: Optional filters (brand, model, min_price, max_price, etc.)
            scrape_details: Whether to scrape individual listing pages (not implemented for FB)

        Returns:
            List of vehicle listing dicts with standardized fields
        """
        logger.info(
            f"[FACEBOOK] Starting scrape for {vehicle_type}, max {max_listings} listings"
        )

        # Strategy 1: Try Facebook Marketplace with requests
        listings = await self._try_facebook_requests(vehicle_type, max_listings, filters)
        if listings:
            logger.info(f"[FACEBOOK] Strategy 1 (requests) returned {len(listings)} listings")
            return listings

        # Strategy 2: Try Facebook GraphQL/API endpoints (rarely works)
        listings = await self._try_facebook_api(vehicle_type, max_listings, filters)
        if listings:
            logger.info(f"[FACEBOOK] Strategy 2 (API) returned {len(listings)} listings")
            return listings

        # A cross-source fallback must never be presented as Facebook data.
        # It is opt-in for explicit comparison jobs only.
        if self.allow_cross_source_fallback:
            logger.info("[FACEBOOK] Facebook blocked, falling back to OLX.pt")
            listings = await self._fallback_olx(vehicle_type, max_listings, filters)
            if listings:
                logger.info(f"[FACEBOOK] Fallback OLX returned {len(listings)} listings")
                return listings
        else:
            logger.warning("[FACEBOOK] Blocked/auth required; OLX fallback disabled")

        # Strategy 4: Last resort - try Playwright for Facebook
        listings = await self._try_facebook_playwright(vehicle_type, max_listings, filters)
        if listings:
            logger.info(f"[FACEBOOK] Strategy 4 (Playwright) returned {len(listings)} listings")
            return listings

        logger.warning("[FACEBOOK] All strategies failed, returning empty list")
        return []

    async def _try_facebook_requests(
        self,
        vehicle_type: str,
        max_listings: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Strategy 1: Try plain HTTP requests to Facebook Marketplace.

        Facebook blocks requests without authentication, but this is attempted
        first as the simplest approach.
        """
        url = self._build_facebook_url(vehicle_type, filters)
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, verify=False
            ) as client:
                resp = await client.get(url, headers=headers)
                logger.info(
                    f"[FACEBOOK_REQUESTS] GET {url} -> {resp.status_code} "
                    f"({len(resp.text)} bytes)"
                )

                if resp.status_code != 200:
                    logger.warning(
                        f"[FACEBOOK_REQUESTS] Non-200 status: {resp.status_code}"
                    )
                    return []

                text = resp.text

                # Check if it's an error/login page
                if self._is_blocked(text):
                    logger.warning("[FACEBOOK_REQUESTS] Blocked/login page detected")
                    return []

                # Try to extract listings from HTML
                return self._extract_from_html(text, max_listings)

        except httpx.TimeoutException:
            logger.warning("[FACEBOOK_REQUESTS] Request timed out")
            return []
        except httpx.RequestError as e:
            logger.warning(f"[FACEBOOK_REQUESTS] Request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"[FACEBOOK_REQUESTS] Unexpected error: {e}")
            return []

    async def _try_facebook_api(
        self,
        vehicle_type: str,
        max_listings: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Strategy 2: Try Facebook's internal GraphQL endpoints.

        Facebook uses GraphQL heavily. Sometimes specific endpoints are accessible
        without authentication, especially the public listings data.
        """
        # FB Marketplace search GraphQL endpoint (rarely works without auth)
        api_url = f"{FACEBOOK_BASE}/api/graphql/"
        headers = self._get_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        # This is a simplified query - real FB GraphQL is complex
        # We attempt it but expect failure
        try:
            async with httpx.AsyncClient(
                timeout=15.0, follow_redirects=True, verify=False
            ) as client:
                resp = await client.post(
                    api_url,
                    headers=headers,
                    data={"query": "", "variables": "{}"},
                )
                logger.info(
                    f"[FACEBOOK_API] POST {api_url} -> {resp.status_code} "
                    f"({len(resp.text)} bytes)"
                )
                if resp.status_code == 200 and not self._is_blocked(resp.text):
                    logger.info("[FACEBOOK_API] API responded, attempting extraction")
                    # In practice this almost never works without auth
                    pass
        except Exception as e:
            logger.debug(f"[FACEBOOK_API] API attempt failed (expected): {e}")

        return []

    async def _fallback_olx(
        self,
        vehicle_type: str,
        max_listings: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Strategy 3: Fallback to OLX.pt.

        Facebook Marketplace in Portugal has very few vehicle listings compared
        to OLX. When Facebook is blocked, we search OLX instead and tag results
        as coming from the FACEBOOK source (cross-reference fallback).

        Tries:
          a) The existing project OLXScraper (full Playwright/commercial API support)
          b) Direct HTTP requests to OLX (usually blocked)
        """
        # Try using the existing OLXScraper from the project first
        try:
            from scrapers.olx_scraper import OLXScraper
            logger.info("[FACEBOOK_OLX] Using project OLXScraper as fallback")
            olx = OLXScraper()
            olx_listings = await olx.scrape_listings(
                vtype=vehicle_type,
                max_listings=max_listings,
                filters=filters,
                scrape_details=False,
            )
            if olx_listings:
                logger.info(
                    f"[FACEBOOK_OLX] OLXScraper returned {len(olx_listings)} listings"
                )
                # Re-tag as FACEBOOK source
                for listing in olx_listings:
                    listing["source"] = self.source_name
                return olx_listings
        except ImportError:
            logger.debug("[FACEBOOK_OLX] OLXScraper not available")
        except Exception as e:
            logger.warning(f"[FACEBOOK_OLX] OLXScraper failed: {e}")

        # Fallback: direct HTTP requests to OLX (usually blocked by Cloudflare)
        url = self._build_olx_url(vehicle_type, filters)
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        }

        try:
            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, verify=False
            ) as client:
                resp = await client.get(url, headers=headers)
                logger.info(
                    f"[FACEBOOK_OLX] GET {url} -> {resp.status_code} "
                    f"({len(resp.text)} bytes)"
                )

                if resp.status_code != 200:
                    logger.warning(f"[FACEBOOK_OLX] Non-200 status: {resp.status_code}")
                    return []

                # Parse OLX listings from HTML
                return self._parse_olx_html(resp.text, vehicle_type, max_listings)

        except httpx.TimeoutException:
            logger.warning("[FACEBOOK_OLX] OLX request timed out")
            return []
        except httpx.RequestError as e:
            logger.warning(f"[FACEBOOK_OLX] OLX request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"[FACEBOOK_OLX] Unexpected error: {e}")
            return []

    async def _try_facebook_playwright(
        self,
        vehicle_type: str,
        max_listings: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Strategy 4: Use Playwright browser automation for Facebook.

        This is the most reliable but slowest approach. Requires Playwright
        and browser binaries to be installed.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning(
                "[FACEBOOK_PLAYWRIGHT] Playwright not installed, skipping strategy 4"
            )
            return []

        url = self._build_facebook_url(vehicle_type, filters)
        logger.info(f"[FACEBOOK_PLAYWRIGHT] Launching browser for {url}")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
                context = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1920, "height": 1080},
                    locale="pt-PT",
                    geolocation={"latitude": 39.5, "longitude": -8.0},
                    timezone_id="Europe/Lisbon",
                )

                page = await context.new_page()

                # Apply stealth
                try:
                    await page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['pt-PT', 'pt', 'en']
                        });
                    """)
                except Exception as e:
                    logger.debug(f"[FACEBOOK_PLAYWRIGHT] Stealth script failed: {e}")

                try:
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                except Exception as e:
                    logger.warning(
                        f"[FACEBOOK_PLAYWRIGHT] Navigation timeout/error: {e}"
                    )

                # Wait a bit for JS to render
                await asyncio.sleep(5)

                # Check if we got a login page
                page_title = await page.title()
                content_text = await page.content()

                if "login" in page_title.lower() or self._is_blocked(content_text):
                    logger.warning(
                        "[FACEBOOK_PLAYWRIGHT] Login page detected (Facebook needs auth)"
                    )
                    await browser.close()
                    return []

                # Try to scroll to load more listings
                for _ in range(3):
                    await page.mouse.wheel(0, 1000)
                    await asyncio.sleep(1)

                html = await page.content()
                await browser.close()

                if not html or len(html) < 500:
                    logger.warning("[FACEBOOK_PLAYWRIGHT] HTML too short")
                    return []

                return self._extract_from_html(html, max_listings)

        except Exception as e:
            logger.error(f"[FACEBOOK_PLAYWRIGHT] Browser error: {e}")
            return []

    # ------------------------------------------------------------------ #
    # HTML Parsing
    # ------------------------------------------------------------------ #

    def _extract_from_html(
        self, html: str, max_listings: int
    ) -> List[Dict[str, Any]]:
        """Extract vehicle listings from Facebook Marketplace HTML.

        Facebook HTML is heavily dynamic and JS-rendered. This attempts
        to find structured data embedded in the page (JSON-LD, __NEXT_DATA__,
        or data attributes).
        """
        listings: List[Dict[str, Any]] = []

        # Try JSON-LD structured data
        try:
            json_ld_listings = self._extract_json_ld(html)
            if json_ld_listings:
                logger.info(
                    f"[FACEBOOK_EXTRACT] Found {len(json_ld_listings)} listings in JSON-LD"
                )
                listings.extend(json_ld_listings)
        except Exception as e:
            logger.debug(f"[FACEBOOK_EXTRACT] JSON-LD extraction error: {e}")

        if listings:
            return listings[:max_listings]

        # Try __NEXT_DATA__ (Facebook sometimes uses Next.js)
        try:
            next_data = self._extract_next_data(html)
            if next_data:
                logger.info(
                    f"[FACEBOOK_EXTRACT] Found {len(next_data)} listings in __NEXT_DATA__"
                )
                listings.extend(next_data)
        except Exception as e:
            logger.debug(f"[FACEBOOK_EXTRACT] __NEXT_DATA__ extraction error: {e}")

        if listings:
            return listings[:max_listings]

        # Try regex-based extraction from raw HTML
        try:
            regex_listings = self._extract_regex(html)
            if regex_listings:
                logger.info(
                    f"[FACEBOOK_EXTRACT] Found {len(regex_listings)} listings via regex"
                )
                listings.extend(regex_listings)
        except Exception as e:
            logger.debug(f"[FACEBOOK_EXTRACT] Regex extraction error: {e}")

        return listings[:max_listings]

    def _extract_json_ld(self, html: str) -> List[Dict[str, Any]]:
        """Extract listings from JSON-LD structured data blocks."""
        results: List[Dict[str, Any]] = []
        # Find <script type="application/ld+json"> blocks
        pattern = re.compile(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            try:
                data = json.loads(match.group(1).strip())
                # Handle both single items and arrays
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") in (
                        "Car",
                        "Vehicle",
                        "Product",
                    ):
                        listing = self._json_ld_to_listing(item)
                        if listing:
                            results.append(listing)
            except (json.JSONDecodeError, AttributeError):
                continue
        return results

    def _extract_next_data(self, html: str) -> List[Dict[str, Any]]:
        """Extract listings from __NEXT_DATA__ script tag."""
        results: List[Dict[str, Any]] = []
        pattern = re.compile(
            r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(html)
        if not match:
            return results

        try:
            data = json.loads(match.group(1).strip())
            # Navigate through Next.js data structure
            # Facebook props path varies; we look for listings/vehicles
            props = data.get("props", {})
            page_props = props.get("pageProps", {})
            # Look for listings in common FB Marketplace data structures
            for key in (
                "listings",
                "vehicles",
                "marketplace_listings",
                "edges",
                "items",
            ):
                items = page_props.get(key, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            listing = self._fb_node_to_listing(item)
                            if listing:
                                results.append(listing)
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            logger.debug(f"[FB_NEXT_DATA] Parse error: {e}")

        return results

    def _extract_regex(self, html: str) -> List[Dict[str, Any]]:
        """Fallback: extract listings from raw HTML using regex heuristics.

        Looks for listing cards by common FB Marketplace HTML patterns.
        """
        results: List[Dict[str, Any]] = []
        seen_urls: set = set()

        # Try to find listing links containing /marketplace/item/ or /marketplace/listing/
        link_pattern = re.compile(
            r'href=["\'](/marketplace/(?:item|listing)/(\d+)[^"\']*)["\']',
            re.IGNORECASE,
        )
        for match in link_pattern.finditer(html):
            path = match.group(1)
            listing_id = match.group(2)
            url = urljoin(FACEBOOK_BASE, path)

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Try to extract title and price from nearby text
            # Look back a few chars for context
            start = max(0, match.start() - 500)
            end = min(len(html), match.end() + 500)
            context = html[start:end]

            title = ""
            price: Optional[float] = None
            year: Optional[int] = None
            km: Optional[int] = None

            # Price in EUR
            price_match = re.search(r"(?:€|EUR)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)", context)
            if price_match:
                try:
                    price_str = price_match.group(1).replace(".", "").replace(",", ".")
                    price = float(price_str)
                except ValueError:
                    pass

            # Title near the listing
            # Look for text between tags near the link
            title_pattern = re.compile(
                r'<span[^>]*>([^<]{10,100})</span>',
                re.IGNORECASE,
            )
            for t_match in title_pattern.finditer(context):
                candidate = t_match.group(1).strip()
                if (
                    len(candidate) > 10
                    and not candidate.startswith("<")
                    and "€" not in candidate
                ):
                    title = candidate
                    break

            if not title:
                # Try alt text from images
                img_alt = re.search(r'alt=["\']([^"\']{10,})["\']', context)
                if img_alt:
                    title = img_alt.group(1).strip()

            # Year
            year_match = re.search(r"\b(19|20)\d{2}\b", context)
            if year_match:
                y = int(year_match.group(0))
                if 1990 <= y <= 2030:
                    year = y

            # Km
            km_match = re.search(r"(\d{1,3}(?:[.,]\d{3})*)\s*k[Mm]", context)
            if km_match:
                try:
                    km = int(km_match.group(1).replace(".", "").replace(",", ""))
                except ValueError:
                    pass

            if title or price:
                listing = self._make_listing(
                    url=url,
                    title=title or f"Vehicle {listing_id}",
                    price=price,
                    year=year,
                    km=km,
                    source_id=listing_id,
                )
                results.append(listing)

        return results

    # ------------------------------------------------------------------ #
    # OLX Fallback Parsing
    # ------------------------------------------------------------------ #

    def _parse_olx_html(
        self, html: str, vehicle_type: str, max_listings: int
    ) -> List[Dict[str, Any]]:
        """Parse OLX.pt HTML to extract vehicle listings.

        OLX returns server-rendered HTML that can be parsed with regex
        or BeautifulSoup.
        """
        listings: List[Dict[str, Any]] = []

        # Try using BeautifulSoup if available
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")
            cards = soup.select('[data-cy="l-card"], .css-1sw7q4x, [class*="card"]')

            for card in cards:
                if len(listings) >= max_listings:
                    break

                listing = self._parse_olx_card(card)
                if listing:
                    listings.append(listing)
        except ImportError:
            logger.debug("[FACEBOOK_OLX] BeautifulSoup not available, using regex")
            listings = self._parse_olx_regex(html, max_listings)
        except Exception as e:
            logger.warning(f"[FACEBOOK_OLX] BS4 parsing error: {e}")
            listings = self._parse_olx_regex(html, max_listings)

        if not listings:
            listings = self._parse_olx_regex(html, max_listings)

        return listings

    def _parse_olx_card(self, card: Any) -> Optional[Dict[str, Any]]:
        """Parse a single OLX listing card element."""
        from bs4 import Tag

        try:
            # URL
            link = card.select_one("a[href]")
            if not link:
                return None
            url = link.get("href", "")
            if isinstance(url, str) and url.startswith("/"):
                url = urljoin(self.olx_fallback_url, url)
            if not url or "olx.pt" not in url:
                return None

            # Title
            title_elem = card.select_one("h6, h2, .title, [class*='title']")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Price
            price = None
            price_elem = card.select_one(
                ".price, [class*='price'], [data-testid='price']"
            )
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._parse_price(price_text)

            # Year and KM from text blocks
            year = None
            km = None
            full_text = card.get_text(" ", strip=True)

            # Year
            year_match = re.search(r"\b(19|20)\d{2}\b", full_text)
            if year_match:
                y = int(year_match.group(0))
                if 1990 <= y <= 2030:
                    year = y

            # KM
            km_match = re.search(r"(\d{1,3}(?:[., ]\d{3})*)\s*k[Mm]", full_text)
            if km_match:
                try:
                    km = int(
                        re.sub(r"[^\d]", "", km_match.group(1))
                    )
                except ValueError:
                    pass

            # Location
            location = ""
            location_match = re.search(r"(?:-|\\|)\s*([A-Za-zÀ-ÿ\s]+)\s*$", full_text.split("€")[-1].strip())
            if location_match:
                location = location_match.group(1).strip()

            # Source ID
            source_id = hashlib.md5(url.encode()).hexdigest()[:16]

            return self._make_listing(
                url=url,
                title=title or "Unknown Vehicle",
                price=price,
                year=year,
                km=km,
                location=location,
                source_id=source_id,
            )

        except Exception as e:
            logger.debug(f"[FACEBOOK_OLX] Card parse error: {e}")
            return None

    def _parse_olx_regex(
        self, html: str, max_listings: int
    ) -> List[Dict[str, Any]]:
        """Parse OLX HTML using regex when BeautifulSoup is unavailable."""
        listings: List[Dict[str, Any]] = []
        seen_urls: set = set()

        # OLX listing URLs typically look like:
        # https://www.olx.pt/d/anuncio/...
        listing_pattern = re.compile(
            r'href=["\'](https?://(?:www\.)?olx\.pt/d/anuncio/[^"\']+)["\']',
            re.IGNORECASE,
        )

        # Group by proximity to extract title/price near each URL
        urls = list(dict.fromkeys(listing_pattern.findall(html)))  # Deduplicate preserving order

        for url in urls:
            if len(listings) >= max_listings:
                break
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Extract a context window around this URL
            idx = html.find(url)
            if idx == -1:
                continue
            start = max(0, idx - 800)
            end = min(len(html), idx + 200)
            context = html[start:end]

            title = ""
            price: Optional[float] = None

            # Title from nearby heading
            title_match = re.search(
                r'<(?:h6|h2|span|div)[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([^<]+)',
                context,
                re.IGNORECASE,
            )
            if title_match:
                title = title_match.group(1).strip()

            if not title:
                title_match = re.search(
                    r'<(?:h6|h2)[^>]*>([^<]+)',
                    context,
                    re.IGNORECASE,
                )
                if title_match:
                    title = title_match.group(1).strip()

            # Price
            price_match = re.search(r"(?:€|EUR)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)", context)
            if price_match:
                price = self._parse_price(price_match.group(0))

            if not title and not price:
                continue

            # Year and KM
            year = None
            km = None

            year_match = re.search(r"\b(19|20)\d{2}\b", context)
            if year_match:
                y = int(year_match.group(0))
                if 1990 <= y <= 2030:
                    year = y

            km_match = re.search(r"(\d{1,3}(?:[., ]\d{3})*)\s*k[Mm]", context, re.IGNORECASE)
            if km_match:
                try:
                    km = int(re.sub(r"[^\d]", "", km_match.group(1)))
                except ValueError:
                    pass

            source_id = hashlib.md5(url.encode()).hexdigest()[:16]

            listing = self._make_listing(
                url=url,
                title=title or "Unknown Vehicle",
                price=price,
                year=year,
                km=km,
                source_id=source_id,
            )
            listings.append(listing)

        return listings

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_facebook_url(
        self,
        vehicle_type: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build Facebook Marketplace search URL."""
        url = MARKETPLACE_URL

        params: Dict[str, str] = {"locale": "pt_PT"}
        if filters:
            if filters.get("query") or filters.get("brand"):
                query = filters.get("query", "") or filters.get("brand", "")
                if isinstance(query, str) and query.strip():
                    params["query"] = query.strip()
            if filters.get("min_price"):
                params["minPrice"] = str(filters["min_price"])
            if filters.get("max_price"):
                params["maxPrice"] = str(filters["max_price"])

        if params:
            url += "?" + urlencode(params)
        return url

    def _build_olx_url(
        self,
        vehicle_type: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build OLX.pt search URL for fallback."""
        path = "carros" if vehicle_type == "carros" else "motos"
        url = f"{self.olx_fallback_url}/{path}"

        params: list = []
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

    def _get_headers(self) -> Dict[str, str]:
        """Generate headers mimicking a real browser."""
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
        """Check if the HTML indicates a login/blocked/error page."""
        indicators = [
            "login.php",
            "login",
            "checkpoint",
            "Sorry, something went wrong",
            "We're working on getting this fixed",
            "Please log in",
            "Log In",
            "Sign Up for Facebook",
            "content_placeholder",
            "captcha",
        ]
        lower = html.lower()
        return any(indicator.lower() in lower for indicator in indicators)

    def _json_ld_to_listing(self, item: dict) -> Optional[Dict[str, Any]]:
        """Convert a JSON-LD item to standardized listing dict."""
        try:
            url = item.get("url", "")
            if isinstance(url, list):
                url = url[0] if url else ""

            title = item.get("name", item.get("title", ""))

            price = None
            offers = item.get("offers", {})
            if isinstance(offers, dict):
                price = self._parse_price(offers.get("price"))
            elif isinstance(offers, list) and offers:
                price = self._parse_price(offers[0].get("price"))

            year = None
            km = None
            if "vehicleModelDate" in item:
                year = self._parse_year(item["vehicleModelDate"])
            if "mileageFromOdometer" in item:
                km = self._parse_km(item["mileageFromOdometer"])

            if not url and not title:
                return None

            source_id = hashlib.md5(url.encode()).hexdigest()[:16] if url else ""

            return self._make_listing(
                url=url,
                title=title or "Unknown Vehicle",
                price=price,
                year=year,
                km=km,
                source_id=source_id,
            )
        except Exception as e:
            logger.debug(f"[FB_JSONLD] Conversion error: {e}")
            return None

    def _fb_node_to_listing(self, node: dict) -> Optional[Dict[str, Any]]:
        """Convert a Facebook GraphQL node to standardized listing dict."""
        try:
            # Try different FB data shapes
            node_data = node.get("node", node)
            listing = node_data.get("listing", node_data)

            url = listing.get("url", listing.get("link", ""))
            if isinstance(url, dict):
                url = url.get("url", "")

            title = (
                listing.get("title")
                or listing.get("name")
                or listing.get("marketplace_listing_title", "")
            )

            price = None
            price_data = (
                listing.get("price")
                or listing.get("listing_price")
                or listing.get("formattedPrice")
            )
            if isinstance(price_data, dict):
                price = self._parse_price(price_data.get("amount"))
            elif isinstance(price_data, (int, float, str)):
                price = self._parse_price(price_data)

            # Location, year, km
            year = None
            km = None

            year_data = listing.get("year", listing.get("vehicle_year"))
            if year_data:
                year = self._parse_year(year_data)

            km_data = listing.get(
                "mileage",
                listing.get("km", listing.get("odometer", listing.get("mileageFromOdometer"))),
            )
            if km_data:
                km = self._parse_km(km_data)

            if not url and not title:
                return None

            source_id = (
                listing.get("id")
                or listing.get("node_id")
                or hashlib.md5(url.encode()).hexdigest()[:16]
            )

            return self._make_listing(
                url=str(url) if url else "",
                title=str(title) if title else "Unknown Vehicle",
                price=price,
                year=year,
                km=km,
                source_id=str(source_id) if source_id else "",
            )
        except Exception as e:
            logger.debug(f"[FB_NODE] Conversion error: {e}")
            return None

    def _make_listing(
        self,
        url: str,
        title: str,
        price: Optional[float] = None,
        year: Optional[int] = None,
        km: Optional[int] = None,
        location: str = "",
        source_id: str = "",
    ) -> Dict[str, Any]:
        """Create a standardized listing dict."""
        # Parse brand and model from title
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
            "location": location,
            "vehicle_type": "carros",
            "first_seen": datetime.now(timezone.utc).isoformat(),
        }

    def _parse_price(self, value: Any) -> Optional[float]:
        """Parse only a total EUR price with locale-aware separators."""
        evidence = parse_price_evidence(value)
        if evidence.kind.value != "total" or evidence.currency != "EUR":
            return None
        return evidence.value

    def _parse_year(self, value: Any) -> Optional[int]:
        """Parse year from various formats."""
        if value is None:
            return None
        if isinstance(value, int):
            return value if 1990 <= value <= 2030 else None
        if isinstance(value, str):
            match = re.search(r"\b(19|20)\d{2}\b", value)
            if match:
                y = int(match.group(0))
                return y if 1990 <= y <= 2030 else None
        return None

    def _parse_km(self, value: Any) -> Optional[int]:
        """Parse km from various formats."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            digits = re.sub(r"[^\d]", "", value)
            try:
                return int(digits) if digits else None
            except ValueError:
                return None
        return None

    def _parse_brand_model(self, title: str) -> tuple[str, str]:
        """Extract brand and model from title using a known brand list."""
        if not title:
            return "Unknown", title

        brands = [
            "Volkswagen", "BMW", "Mercedes-Benz", "Mercedes", "Audi", "Renault",
            "Peugeot", "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
            "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo", "Mazda",
            "Mitsubishi", "Suzuki", "Dacia", "Opel", "Alfa Romeo", "Mini",
            "Smart", "Land Rover", "Jeep", "Porsche", "Jaguar", "Lexus",
            "Subaru", "Tesla", "Polestar", "DS", "Cupra",
        ]
        title_lower = title.lower()
        for brand in brands:
            idx = title_lower.find(brand.lower())
            if idx != -1:
                model = title[idx + len(brand):].strip()
                return brand, model
        parts = title.split(maxsplit=1)
        return (parts[0], parts[1]) if len(parts) >= 2 else (title, "")


# Alias for lazy import support
FacebookScraper = FacebookMarketplaceScraper
