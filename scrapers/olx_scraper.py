"""
OLX.pt Scraper using Playwright with stealth
Site: olx.pt — React-based, requires JavaScript rendering.
Extracts: title, price, year, km, fuel_type, transmission, location, images
"""
from __future__ import annotations
import hashlib
import logging
import re
import random
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from utils.scraping_log import start_scrape_log, finish_scrape_log

logger = logging.getLogger(__name__)

BASE_URL = "https://www.olx.pt"
BRANDS_LIST = [
    "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz",
    "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
    "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
    "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo",
    "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini",
    "Smart", "Jeep", "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla",
    "Cupra", "DS", "MG", "BYD", "Polestar", "Iveco", "MAN", "Scania",
]


class OlxScraper:
    """Scraper for OLX.pt using Playwright."""

    def __init__(self):
        self.base_url = BASE_URL

    async def scrape_listings(
        self,
        vtype: str = "carros",
        max_listings: int = 50,
        filters: Optional[Dict[str, object]] = None,
        scrape_details: bool = False,
    ) -> List[Dict[str, object]]:
        """Scrape car listings from OLX.pt.

        Args:
            max_listings: Maximum listings to return
            filters: Optional filters

        Returns:
            List of vehicle dicts
        """
        logger.info(f"[OLX] Starting scrape, max {max_listings}")
        log_id = start_scrape_log("OLX")
        listings = []
        page_num = 1

        while len(listings) < max_listings:
            url = self._build_url(page_num, filters)
            logger.info(f"[OLX] Fetching page {page_num}: {url}")

            html = await self._fetch_page(url)
            if not html:
                break

            page_listings = self._parse_html(html, max_listings - len(listings))
            if not page_listings:
                logger.info(f"[OLX] No listings on page {page_num}")
                break

            logger.info(f"[OLX] Page {page_num}: {len(page_listings)} listings")
            listings.extend(page_listings)
            page_num += 1

            if len(page_listings) < 10:
                break
            if page_num > 10:
                break

        logger.info(f"[OLX] Total: {len(listings)} listings")
        if log_id:
            finish_scrape_log(log_id, "completed", listings_found=len(listings))
        
        # Enrich with details if requested
        if scrape_details and listings:
            logger.info(f"[OLX] Enriching {len(listings)} listings with details...")
            listings = await self._enrich_listings_with_details(listings)
        
        return listings[:max_listings]
    
    async def _enrich_listings_with_details(self, listings: List[Dict[str, object]], max_concurrent: int = 5) -> List[Dict[str, object]]:
        """Enrich OLX listing cards with details - concurrent for speed."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_one(listing: Dict[str, object]) -> Dict[str, object]:
            # Check if listing already has detailed info
            needs_details = not listing.get("horsepower") and not listing.get("engine_size") and not listing.get("doors")
            listing_url = listing.get("url")
            
            if needs_details and isinstance(listing_url, str) and listing_url.startswith("http"):
                async with semaphore:
                    try:
                        details = await self.scrape_listing_details(listing_url)
                        if details:
                            # Merge details into listing
                            listing.update(details)
                            logger.debug(f"[OLX] Enriched: {listing.get('title', 'Unknown')}")
                    except Exception as e:
                        logger.warning(f"[OLX] Failed to enrich {listing_url}: {e}")
                    await asyncio.sleep(random.uniform(0.3, 0.6))
            return listing
        
        tasks = [enrich_one(lst.copy()) for lst in listings]
        return await asyncio.gather(*tasks)
    
    async def scrape_listing_details(self, url: str) -> Optional[Dict[str, object]]:
        """Scrape detailed information from a single OLX listing page."""
        try:
            from bs4 import BeautifulSoup
            from playwright.async_api import async_playwright
            from utils.playwright_stealth import apply_stealth_async
        except ImportError as e:
            logger.error(f"[OLX_DETAILS] Missing dependency: {e}")
            return None
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                    ],
                )
                context = await browser.new_context(
                    user_agent=random.choice(settings.user_agents),
                    viewport={"width": 1920, "height": 1080},
                    locale="pt-PT",
                )
                page = await context.new_page()
                
                try:
                    await apply_stealth_async(page)
                except Exception as e:
                    logger.warning(f"[OLX_DETAILS] Stealth failed: {e}")
                
                await page.goto(url, timeout=30000, wait_until='networkidle')
                await asyncio.sleep(random.uniform(2, 4))
                
                html = await page.content()
                await browser.close()
                
                soup = BeautifulSoup(html, 'lxml')
                
                details: Dict[str, object] = {
                    "description": "",
                    "horsepower": None,
                    "engine_size": None,
                    "doors": None,
                    "color": None,
                    "seller_name": "",
                    "seller_type": "",
                    "extras": [],
                }
                
                # Extract description
                desc_elem = soup.find('div', class_=re.compile(r'description|desc'))
                if desc_elem:
                    details["description"] = desc_elem.get_text(strip=True)
                
                # Extract specs/parameters
                spec_items = soup.find_all('li', class_=re.compile(r'spec|param|attr'))
                for item in spec_items:
                    text = item.get_text(strip=True).lower()
                    
                    if "potência" in text or "cv" in text:
                        try:
                            match = re.search(r'(\d+)\s*cv', text)
                            if match:
                                details["horsepower"] = int(match.group(1))
                        except (ValueError, IndexError):
                            pass
                    elif "cilindrada" in text or "cc" in text:
                        try:
                            match = re.search(r'(\d+)\s*cc', text)
                            if match:
                                details["engine_size"] = int(match.group(1))
                        except (ValueError, IndexError):
                            pass
                    elif "porta" in text:
                        try:
                            match = re.search(r'(\d+)\s*porta', text)
                            if match:
                                details["doors"] = int(match.group(1))
                        except (ValueError, IndexError):
                            pass
                    elif "cor" in text or "color" in text:
                        try:
                            color_text = item.get_text(strip=True)
                            details["color"] = color_text.split(':')[-1].strip() if ':' in color_text else color_text
                        except Exception:
                            pass
                
                return details
                
        except Exception as e:
            logger.error(f"[OLX_DETAILS] Failed to scrape {url}: {e}")
            return None

    def _build_url(self, page: int = 1, filters: Optional[Dict[str, object]] = None) -> str:
        """Build OLX search URL."""
        url = f"{self.base_url}/carros/"
        params = []
        if page > 1:
            params.append(f"page={page}")
        if filters:
            if filters.get("brand"):
                params.append(f"search[brand]={filters['brand']}")
            if filters.get("model"):
                params.append(f"search[model]={filters['model']}")
            if filters.get("min_price"):
                params.append(f"search[price_from]={filters['min_price']}")
            if filters.get("max_price"):
                params.append(f"search[price_to]={filters['max_price']}")
            if filters.get("min_year"):
                params.append(f"search[year_from]={filters['min_year']}")
            if filters.get("max_year"):
                params.append(f"search[year_to]={filters['max_year']}")
        if params:
            url += "?" + "&".join(params)
        return url

    async def _fetch_page(self, url: str, retry_count: int = 0) -> Optional[str]:
        """Fetch page HTML using Playwright with stealth and retry logic."""
        try:
            from playwright.async_api import async_playwright
            from utils.playwright_stealth import apply_stealth_async
        except ImportError:
            logger.error("[OLX] Playwright not installed, cannot scrape")
            return None

        try:
            async with async_playwright() as p:
                # Randomize browser args to avoid fingerprinting
                browser_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-web-security",
                    "--disable-features=BlockInsecurePrivateNetworkRequests",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                    f"--window-size={random.randint(1200, 1920)},{random.randint(800, 1080)}",
                ]
                
                browser = await p.chromium.launch(
                    headless=True,
                    args=browser_args,
                )
                
                # Rotate user agents
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ]
                
                context = await browser.new_context(
                    user_agent=random.choice(user_agents),
                    viewport={"width": random.randint(1200, 1920), "height": random.randint(800, 1080)},
                    locale="pt-PT",
                    timezone_id="Europe/Lisbon",
                    permissions=["geolocation"],
                    extra_http_headers={
                        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Referer": "https://www.google.pt/",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                    },
                )
                page = await context.new_page()

                # Enhanced stealth script
                await page.add_init_script("""
                    // Override navigator.webdriver
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Override plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Override languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['pt-PT', 'pt', 'en-US', 'en']
                    });
                    
                    // Override chrome runtime
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                    
                    // Override permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    
                    // Override plugin detection
                    Object.defineProperty(navigator, 'maxTouchPoints', {
                        get: () => 1
                    });
                    
                    // Override iframe detection
                    Object.defineProperty(window, 'frameElement', {
                        get: () => null
                    });
                """)

                try:
                    await apply_stealth_async(page)
                except Exception as e:
                    logger.debug(f"[OLX] Stealth init warning: {e}")

                # Try mobile site on retry
                fetch_url = url
                if retry_count > 0:
                    # Try mobile site as fallback
                    fetch_url = url.replace("www.olx.pt", "m.olx.pt")
                    logger.info(f"[OLX] Retry {retry_count}: Trying mobile site")
                
                # Add random delay before request
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
                try:
                    await page.goto(fetch_url, timeout=30000, wait_until="domcontentloaded")
                except Exception as e:
                    logger.warning(f"[OLX] Navigation timeout: {e}")
                    # Wait a bit and try to get content anyway
                    await asyncio.sleep(3)
                
                # Human-like delays
                await asyncio.sleep(random.uniform(2, 4))
                
                # Handle cookie consent if present
                try:
                    consent_btn = await page.query_selector('button:has-text("Aceitar")')
                    if consent_btn:
                        await consent_btn.click()
                        await asyncio.sleep(random.uniform(0.5, 1))
                except Exception:
                    pass

                # Scroll to trigger lazy loading with human-like behavior
                for i in range(random.randint(2, 4)):
                    scroll_amount = random.randint(400, 800)
                    await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                
                # Check if blocked
                try:
                    page_title = await page.title()
                    if "problema" in page_title.lower() or "captcha" in page_title.lower() or "houston" in page_title.lower():
                        logger.warning(f"[OLX] Blocked by anti-bot (attempt {retry_count + 1}): {page_title}")
                        
                        # Retry with exponential backoff
                        if retry_count < 2:
                            await browser.close()
                            backoff_time = (2 ** retry_count) * 3 + random.uniform(1, 3)
                            logger.info(f"[OLX] Retrying after {backoff_time:.1f}s...")
                            await asyncio.sleep(backoff_time)
                            return await self._fetch_page(url, retry_count + 1)
                        
                        await browser.close()
                        return None
                except Exception:
                    pass

                html = await page.content()
                
                # Check if HTML is valid (not just error page)
                if html and len(html) > 5000:
                    await browser.close()
                    return html
                else:
                    logger.warning(f"[OLX] HTML too short ({len(html) if html else 0} chars), possible blocking")
                    if retry_count < 2:
                        await browser.close()
                        backoff_time = (2 ** retry_count) * 3 + random.uniform(1, 3)
                        logger.info(f"[OLX] Retrying after {backoff_time:.1f}s...")
                        await asyncio.sleep(backoff_time)
                        return await self._fetch_page(url, retry_count + 1)
                    
                    await browser.close()
                    return None
                    
        except Exception as e:
            logger.error(f"[OLX] Playwright fetch failed: {e}")
            if retry_count < 2:
                backoff_time = (2 ** retry_count) * 2 + random.uniform(1, 2)
                logger.info(f"[OLX] Retrying after error in {backoff_time:.1f}s...")
                await asyncio.sleep(backoff_time)
                return await self._fetch_page(url, retry_count + 1)
            return None

    def _parse_html(self, html: str, max_listings: int) -> List[Dict[str, object]]:
        """Parse OLX listings from HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        listings = []

        # OLX uses data-cy attributes for listing cards
        cards = soup.select('[data-cy="l-card"]')
        if not cards:
            # Fallback: look for article elements with listing data
            cards = soup.select('article[data-cy]')
        if not cards:
            # Generic fallback: any link to /anuncio/
            return self._parse_fallback_links(soup, max_listings)

        for card in cards[:max_listings]:
            try:
                listing = self._parse_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[OLX] Card parse error: {e}")
                continue

        return listings

    def _parse_card(self, card) -> Optional[Dict[str, object]]:
        """Parse a single OLX listing card."""
        # Title
        title_elem = card.select_one('[data-cy="ad-card-title"]')
        title = title_elem.get_text(strip=True) if title_elem else ""
        if not title:
            return None

        # URL
        link = card.select_one("a")
        url = ""
        if link:
            href = link.get("href", "")
            if href and not href.startswith("http"):
                url = urljoin(self.base_url, href)
            else:
                url = href
        if not url:
            return None

        # Price
        price = None
        price_elem = card.select_one('[data-testid="ad-price"]')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r"(\d[\d\s]*(?:[.,]\d+)?)", price_text)
            if price_match:
                digits = re.sub(r"[^\d]", "", price_match.group(1))
                if digits:
                    price = float(digits)
        if not price:
            # Try other price selectors
            price_elem = card.select_one('[class*="price"]')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r"(\d[\d\s]*(?:[.,]\d+)?)", price_text)
                if price_match:
                    digits = re.sub(r"[^\d]", "", price_match.group(1))
                    if digits:
                        price = float(digits)

        if not price:
            return None

        # Image
        img_elem = card.select_one("img")
        image_url = ""
        if img_elem:
            image_url = img_elem.get("src") or img_elem.get("data-src") or ""

        # Full card text for details extraction
        full_text = card.get_text(" ", strip=True)
        full_text_lower = full_text.lower()

        # Find details section (usually spans/divs with attributes)
        # Year, km, fuel, transmission typically in spans near the bottom
        year = None
        km = None
        fuel_type = None
        transmission = None

        # Collect all small text elements (spans, divs) that might contain details
        detail_items = card.select("span, div[class*='detail'], div[class*='param'], li")
        for item in detail_items:
            text = item.get_text(strip=True)
            if not text:
                continue
            text_lower = text.lower()

            # Year
            if not year:
                ym = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", text)
                if ym:
                    year = int(ym.group(1))

            # KM
            if not km:
                km_m = re.search(r"(\d[\d\s.]*)\s*(?:km|kms|quilómetros|quilometros)", text_lower)
                if km_m:
                    km_str = re.sub(r"[\s.]", "", km_m.group(1))
                    try:
                        km = int(km_str) if km_str else None
                    except ValueError:
                        pass

            # Fuel type
            if not fuel_type:
                if any(f in text_lower for f in ["gasolina", "diesel", "elétrico", "eletrico",
                                                    "eléctrico", "híbrido", "hibrido", "gpl"]):
                    fuel_type = self._normalize_fuel(text)

            # Transmission
            if not transmission:
                if "manual" in text_lower:
                    transmission = "manual"
                elif any(t in text_lower for t in ["automático", "automática", "automatico", "automatica"]):
                    transmission = "automático"

        # Fallback: parse from full text
        if not year:
            ym = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", full_text)
            if ym:
                year = int(ym.group(1))
        if not km:
            km_m = re.search(r"(\d[\d\s.]*)\s*(?:km|kms|quilómetros|quilometros)", full_text_lower)
            if km_m:
                km_str = re.sub(r"[\s.]", "", km_m.group(1))
                try:
                    km = int(km_str) if km_str else None
                except ValueError:
                    pass
        if not fuel_type:
            for f in ["gasolina", "diesel", "elétrico", "eletrico", "híbrido", "hibrido", "gpl"]:
                if f in full_text_lower:
                    fuel_type = self._normalize_fuel(f)
                    break
        if not transmission:
            if "manual" in full_text_lower and "automático" not in full_text_lower:
                transmission = "manual"
            elif any(t in full_text_lower for t in ["automático", "automatico"]):
                transmission = "automático"

        # Location
        location = ""
        location_elem = card.select_one('[data-cy="ad-card-location"], [class*="location"], [class*="local"]')
        if location_elem:
            location = location_elem.get_text(strip=True)

        # Extract missing fields
        horsepower = None
        engine_size = None
        doors = None
        color = None
        seller_name = None
        seller_type = None
        trim_level = None
        extras = []

        # Search in full text
        full_text_lower = full_text.lower()

        # Horsepower (e.g., "150 cv", "150 hp")
        hp_match = re.search(r'(\d+)\s*(?:cv|hp|potência)', full_text_lower)
        if hp_match:
            horsepower = int(hp_match.group(1))

        # Engine size (e.g., "2000 cc", "2.0")
        engine_match = re.search(r'(\d{3,5})\s*(?:cc|cilindrada)', full_text_lower)
        if engine_match:
            engine_size = int(engine_match.group(1))
        else:
            # Try format like "2.0" (liters)
            liter_match = re.search(r'(\d+[.,]\d+)\s*l', full_text_lower)
            if liter_match:
                engine_size = int(float(liter_match.group(1).replace(',', '.')) * 1000)

        # Doors (e.g., "5 portas", "3 drs")
        doors_match = re.search(r'(\d+)\s*(?:portas|door|drs)', full_text_lower)
        if doors_match:
            doors = int(doors_match.group(1))

        # Color (e.g., "Cor: Preto", "Black")
        color_match = re.search(r'cor:?\s*([A-Za-zÀ-ÿ\s]+?)(?:\s|$|,)', full_text_lower)
        if color_match:
            color = color_match.group(1).strip()

        # Seller type detection (check if it's a dealer)
        seller_type = 'particular'  # default
        if any(word in full_text_lower for word in ['stand', 'concessionário', 'profissional', 'dealer']):
            seller_type = 'profissional'

        # Trim level - look for version info in title
        trim_patterns = [r'version[:\s]*(.+)', r'acabamento[:\s]*(.+)', r'trim[:\s]*(.+)']
        for pattern in trim_patterns:
            trim_match = re.search(pattern, title.lower())
            if trim_match:
                trim_level = trim_match.group(1).strip()
                break

        # Extras - look for common extra keywords
        extra_keywords = ['ar condicionado', 'gps', 'nav', 'sensores', 'câmara', 'camara',
                        'jantes', 'alloy', 'leather', 'pele', 'couro', 'sunroof', 'tejadilho']
        for keyword in extra_keywords:
            if keyword in full_text_lower:
                extras.append(keyword)

        source_id = hashlib.md5(url.encode()).hexdigest()
        brand, model = self._parse_brand_model(title)

        return {
            "source": "OLX",
            "source_id": source_id,
            "url": url,
            "title": title,
            "brand": brand,
            "model": model,
            "price": price,
            "year": year,
            "km": km,
            "fuel_type": fuel_type or "",
            "transmission": transmission or "",
            "location": location,
            "images": [image_url] if image_url and image_url.startswith("http") else [],
            "horsepower": horsepower,
            "engine_size": engine_size,
            "doors": doors,
            "color": color or "",
            "seller_name": seller_name or "",
            "seller_type": seller_type,
            "trim_level": trim_level or "",
            "extras": extras,
        }

    def _parse_fallback_links(self, soup, max_listings: int) -> List[Dict[str, object]]:
        """Fallback parser: extract data from links to /anuncio/."""
        listings = []
        seen_urls: set = set()
        for link in soup.select("a[href*='/anuncio/']"):
            href = link.get("href", "")
            if not href:
                continue
            url = href if href.startswith("http") else urljoin(self.base_url, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = link.get_text(strip=True) or link.get("title", "")
            if not title or len(title) < 5:
                continue

            full_text = link.get_text(" ", strip=True)
            price = None
            pm = re.search(r"(\d[\d\s]*(?:[.,]\d+)?)\s*[€€]", full_text)
            if pm:
                digits = re.sub(r"[^\d]", "", pm.group(1))
                if digits:
                    price = float(digits)
            if not price:
                continue

            year = None
            ym = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", full_text)
            if ym:
                year = int(ym.group(1))

            km = None
            km_m = re.search(r"(\d[\d\s.]*)\s*(?:km|kms)", full_text, re.I)
            if km_m:
                km_str = re.sub(r"[\s.]", "", km_m.group(1))
                try:
                    km = int(km_str) if km_str else None
                except ValueError:
                    pass

            fuel_type = None
            full_lower = full_text.lower()
            for f in ["gasolina", "diesel", "elétrico", "eletrico", "híbrido", "hibrido", "gpl"]:
                if f in full_lower:
                    fuel_type = self._normalize_fuel(f)
                    break

            transmission = None
            if "manual" in full_lower:
                transmission = "manual"
            elif any(t in full_lower for t in ["automático", "automatico"]):
                transmission = "automático"

            img = link.find_previous("img") or link.find("img")
            img_url = ""
            if img:
                img_url = img.get("src") or img.get("data-src") or ""

            source_id = hashlib.md5(url.encode()).hexdigest()
            brand, model = self._parse_brand_model(title)

            listings.append({
                "source": "OLX",
                "source_id": source_id,
                "url": url,
                "title": title,
                "brand": brand,
                "model": model,
                "price": price,
                "year": year,
                "km": km,
                "fuel_type": fuel_type or "",
                "transmission": transmission or "",
                "location": "",
                "images": [img_url] if img_url and img_url.startswith("http") else [],
            })
            if len(listings) >= max_listings:
                break
        return listings

    def _normalize_fuel(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        raw_lower = raw.lower().strip()
        if any(k in raw_lower for k in ("gasolina", "gasoline", "petrol")):
            return "gasolina"
        if any(k in raw_lower for k in ("diesel", "gasóleo", "gasoleo")):
            return "diesel"
        if any(k in raw_lower for k in ("elétrico", "eletrico", "electric", "eléctrico", "electrico")):
            return "eletrico"
        if any(k in raw_lower for k in ("híbrido", "hibrido", "hybrid")):
            return "hibrido"
        if "gpl" in raw_lower:
            return "gpl"
        return raw if raw else None

    def _parse_brand_model(self, title: str) -> tuple[str, str]:
        if not title:
            return "Unknown", ""
        title_lower = title.lower()
        for brand in BRANDS_LIST:
            idx = title_lower.find(brand.lower())
            if idx != -1:
                model = title[idx + len(brand):].strip()
                model = re.sub(r"^[-·•|]\s*", "", model)
                return brand, model
        parts = title.split(maxsplit=1)
        return (parts[0], parts[1]) if len(parts) >= 2 else (title, "")


OLXScraper = OlxScraper


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    scraper = OlxScraper()
    results = asyncio.run(scraper.scrape_listings(max_listings=5))
    print(f"\n=== Scraped {len(results)} listings ===")
    for r in results[:5]:
        print(f"  {r.get('title','?')} - €{r.get('price','?')} ({r.get('year','?')}) - {r.get('km','?')} km - {r.get('fuel_type','?')} - {r.get('transmission','?')}")
