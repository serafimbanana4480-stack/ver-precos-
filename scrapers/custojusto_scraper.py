"""
CustoJusto.pt scraper using Playwright with resilient extraction
CustoJusto is a general classifieds site in Portugal with vehicle listings.
"""
from __future__ import annotations
import logging
import re
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from urllib.parse import urljoin

from config import settings
from database.models import Vehicle, VehicleType, FuelType, Transmission
from database.db import get_db_context
from utils.observability import track_scrape

logger = logging.getLogger(__name__)


class CustoJustoScraper:
    """Scraper for CustoJusto.pt vehicle listings"""

    def __init__(self):
        self.base_url = "https://www.custojusto.pt"
        self.vehicle_types = {
            "carros": "carros",
            "motos": "motos",
        }

    @track_scrape(source='custojusto')
    async def scrape_listings(
        self,
        vehicle_type: str = "carros",
        max_listings: int = 100,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False
    ) -> List[Dict[str, object]]:
        from playwright.async_api import async_playwright

        all_listings = []
        page = 1

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=getattr(settings, 'playwright_headless', True))
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                
                while len(all_listings) < max_listings:
                    search_url = self._build_search_url(vehicle_type, page, filters)
                    playwright_page = await context.new_page()

                    logger.info(f"[CUSTOJUSTO] Scraping page {page}: {search_url}")
                    await playwright_page.goto(search_url, wait_until="networkidle", timeout=getattr(settings, 'playwright_timeout', 45000))
                    await playwright_page.wait_for_timeout(2000)

                    await self._dismiss_cookie_banner(playwright_page)

                    raw_items = await playwright_page.evaluate(
                        """() => {
                          const props = window.__NEXT_DATA__?.props?.pageProps;
                          if (!props) return [];
                          const items = props.listItems || props.galleryAds || [];
                          return Array.isArray(items) ? items : [];
                        }"""
                    )
                    
                    page_listings = []
                    for item in raw_items:
                        listing = self._parse_next_listing(item, vehicle_type)
                        if listing:
                            page_listings.append(listing)

                    if not page_listings:
                        listing_elements = await playwright_page.query_selector_all(
                            'a[href*="/veiculos/"], article a[href]'
                        )
                        for element in listing_elements:
                            try:
                                listing = await self._extract_listing(element, vehicle_type)
                                if listing:
                                    page_listings.append(listing)
                            except Exception:
                                continue

                    if not page_listings:
                        await playwright_page.close()
                        break
                        
                    all_listings.extend(page_listings)
                    logger.info(f"[CUSTOJUSTO] Page {page} extracted {len(page_listings)} listings. Total: {len(all_listings)}")
                    
                    await playwright_page.close()
                    
                    if len(page_listings) < 20:
                        break
                        
                    page += 1
                    if page > 10:
                        break

                await browser.close()

        except Exception as e:
            logger.error(f"[CUSTOJUSTO] Scraping failed: {e}")

        logger.info(f"[CUSTOJUSTO] Successfully scraped {len(all_listings)} listings")
        return all_listings[:max_listings]

    def _build_search_url(self, vehicle_type: str, page: int = 1, filters: Optional[Dict[str, object]] = None) -> str:
        """Build search URL for CustoJusto"""
        if vehicle_type == "motos":
            path = "/portugal/veiculos/motos-usadas"
        else:
            path = "/portugal/veiculos/carros-usados"

        url = f"{self.base_url}{path}"
        
        params = []
        if page > 1:
            params.append(f"o={page}")

        # Add query parameters if filters provided
        if filters:
            params = []
            if filters.get("brand"):
                params.append(f"mk={filters['brand']}")
            if filters.get("price_min"):
                params.append(f"ps={filters['price_min']}")
            if filters.get("price_max"):
                params.append(f"pe={filters['price_max']}")
            if filters.get("year_min"):
                params.append(f"rs={filters['year_min']}")
            if filters.get("year_max"):
                params.append(f"re={filters['year_max']}")

            if params:
                url += "?" + "&".join(params)

        return url

    async def _dismiss_cookie_banner(self, page) -> None:
        """Dismiss Cookiebot/consent overlay when present."""
        try:
            await page.evaluate(
                """() => {
                  const btn = document.querySelector(
                    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll'
                  );
                  if (btn) btn.click();
                }"""
            )
            await page.wait_for_timeout(1000)
        except Exception:
            pass
        for label in ("Consentir", "Aceitar", "Accept"):
            try:
                btn = page.get_by_role("button", name=label)
                if await btn.count() > 0:
                    await btn.first.click()
                    await page.wait_for_timeout(800)
                    break
            except Exception:
                continue

    def _parse_next_listing(self, item: Dict[str, Any], vehicle_type: str) -> Optional[Dict[str, object]]:
        """Parse listing from CustoJusto __NEXT_DATA__ listItems entry."""
        try:
            rel_url = item.get("url") or ""
            if not rel_url:
                return None
            url = urljoin(self.base_url, rel_url)
            title = (item.get("title") or "Unknown").strip()
            price = int(item.get("price") or 0)
            if price <= 0:
                return None

            brand, model, year = self._parse_title(title)
            params = item.get("params") or {}
            if params.get("regdate"):
                try:
                    year = int(params["regdate"])
                except (TypeError, ValueError):
                    pass

            loc = item.get("locationNames") or {}
            location = ", ".join(
                x for x in (
                    loc.get("district"),
                    loc.get("county"),
                    loc.get("parish"),
                ) if x
            ) or "Portugal"

            list_id = str(item.get("listID") or hash(url) % 100000000)
            image_url = item.get("imageFullURL") or ""

            fuel = params.get("fuel")
            gearbox = params.get("gearbox")
            # --- Extract KM from params or title ---
            km = 0
            # Try params first
            mileage_raw = params.get("mileage") or params.get("km") or params.get("quilometros")
            if mileage_raw:
                try:
                    km = int(re.sub(r"[^\d]", "", str(mileage_raw)))
                except (ValueError, TypeError):
                    pass
            # Fallback: extract from title (e.g. "73 Mil Kms", "150000 km")
            if not km:
                km_match = re.search(r"(\d{1,3}(?:[.,]\d{3})*)\s*(?:mil\s*)?(?:kms?|km|quil)[^\w]", title, re.I)
                if km_match:
                    km_str = re.sub(r"[.,\s]", "", km_match.group(1))
                    try:
                        km = int(km_str)
                        if "mil" in title.lower():
                            km *= 1000
                    except ValueError:
                        pass
            # Fallback: estimate from year (15,000 km/year)
            if not km and year:
                age = max(1, datetime.now().year - year)
                km = age * 15000

            return {
                "source": "custojusto",
                "source_id": f"custojusto_{list_id}",
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "year": year,
                "price": price,
                "km": km,
                "vehicle_type": vehicle_type,
                "description": (item.get("body") or title).strip(),
                "images": [image_url] if image_url else [],
                "location": location,
                "fuel_type": fuel,
                "transmission": gearbox,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.warning(f"[CUSTOJUSTO] Error parsing list item: {e}")
            return None

    async def _extract_listing(self, element, vehicle_type: str) -> Optional[Dict[str, object]]:
        """Extract data from a single listing element"""
        try:
            # Extract URL
            href = await element.get_attribute("href")
            if not href:
                return None

            url = urljoin(self.base_url, href)

            # Extract title
            title_elem = await element.query_selector("h2, .title, h3, [data-testid='search-title']")
            title = await title_elem.inner_text() if title_elem else "Unknown"

            # Extract price
            price_elem = await element.query_selector(".price, [data-testid='search-price'], .valor")
            price_text = await price_elem.inner_text() if price_elem else "0"
            price = self._extract_price(price_text)

            # Extract location
            location_elem = await element.query_selector(".location, [data-testid='search-location']")
            location = await location_elem.inner_text() if location_elem else "Portugal"

            # Extract image
            img_elem = await element.query_selector("img")
            image_url = await img_elem.get_attribute("src") if img_elem else ""

            # Extract description (from nearby text)
            desc_elem = await element.query_selector(".description, .descricao")
            description = await desc_elem.inner_text() if desc_elem else ""

            # Parse title for brand/model/year
            brand, model, year = self._parse_title(title)

            # Skip if no price or price is 0
            if price == 0:
                return None

            # Extract KM from title or nearby text
            km = 0
            km_match = re.search(r"(\d{1,3}(?:[.,]\d{3})*)\s*(?:mil\s*)?(?:kms?|km|quil)", title + " " + description, re.I)
            if km_match:
                km_str = re.sub(r"[.,\s]", "", km_match.group(1))
                try:
                    km = int(km_str)
                    if "mil" in (title + description).lower():
                        km *= 1000
                except ValueError:
                    pass
            if not km and year:
                age = max(1, datetime.now().year - year)
                km = age * 15000

            return {
                "source": "custojusto",
                "source_id": f"custojusto_{hash(url) % 100000000}",
                "url": url,
                "title": title.strip(),
                "brand": brand,
                "model": model,
                "year": year,
                "price": price,
                "km": km,
                "vehicle_type": vehicle_type,
                "description": description.strip() if description else title.strip(),
                "images": [image_url] if image_url else [],
                "location": location.strip() if location else "Portugal",
                "fuel_type": None,
                "transmission": None,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.warning(f"[CUSTOJUSTO] Error extracting listing element: {e}")
            return None

    def _extract_price(self, price_text: str) -> int:
        """Extract numeric price from text"""
        if not price_text:
            return 0

        # Remove currency symbols, dots, spaces
        cleaned = re.sub(r'[^\d]', '', price_text)
        try:
            return int(cleaned) if cleaned else 0
        except ValueError:
            return 0

    def _parse_title(self, title: str) -> tuple[str, str, int]:
        """Parse title to extract brand, model, and year"""
        brand = "Unknown"
        model = "Unknown"
        year = 2020

        if not title:
            return brand, model, year

        # Try to extract year (4-digit number between 1900-2030)
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', title)
        if year_match:
            year = int(year_match.group(1))

        # Common brands
        common_brands = [
            "audi", "bmw", "mercedes", "mercedes-benz", "vw", "volkswagen",
            "ford", "renault", "peugeot", "citroen", "toyota", "honda",
            "nissan", "hyundai", "kia", "seat", "skoda", "opel", "fiat",
            "mazda", "mitsubishi", "suzuki", "volvo", "jeep", "dacia",
            "land rover", "range rover", "jaguar", "porsche", "tesla",
            "mini", "smart", "alfa romeo", "lexus", "subaru", "isuzu",
            "cfmoto", "cf moto", "yamaha", "kawasaki", "ducati", "ktm", "triumph",
            "vespa", "piaggio", "kymco", "sym"
        ]

        title_lower = title.lower()
        for b in common_brands:
            if b in title_lower:
                brand = b.title()
                break

        # Extract model (text after brand, before year)
        if brand != "Unknown":
            brand_pos = title_lower.find(brand.lower())
            if brand_pos >= 0:
                after_brand = title[brand_pos + len(brand):].strip()
                # Remove year from model string
                after_brand = re.sub(r'\b(19\d{2}|20\d{2})\b', '', after_brand).strip()
                # Take first 2-3 words as model
                model_parts = after_brand.split()[:3]
                if model_parts:
                    model = " ".join(model_parts)

        return brand, model, year


# Singleton instance
custojusto_scraper = CustoJustoScraper()
