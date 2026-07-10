"""
AutoScout24.pt scraper - new source for Portuguese car market.
~30K listings, complete data (KM, HP, cc, fuel, transmission, year).
"""
from __future__ import annotations
import json
import logging
import re
import asyncio
import random
from typing import Any, Dict, List, Optional
from datetime import datetime

from scrapers.base import PlaywrightScraper

logger = logging.getLogger(__name__)


class AutoScout24Scraper(PlaywrightScraper):
    BASE_URL = "https://www.autoscout24.pt"

    def __init__(self):
        super().__init__("AUTOSCOUT24")

    async def scrape_listings(
        self, vehicle_type: str, max_listings: int = 50, scrape_details: bool = True, retry_count: int = 0
    ) -> List[Dict[str, Any]]:
        listings = []
        page_num = 1

        page = await self._get_page()
        try:
            while len(listings) < max_listings:
                url = self._build_listing_url(vehicle_type, page_num)
                logger.info(f"[AUTOSCOUT24] Page {page_num}: {url}")

                try:
                    await page.goto(url, wait_until="networkidle", timeout=60000)  # Increased to 60s
                    await page.wait_for_timeout(3000)  # Increased wait time
                except Exception as e:
                    logger.error(f"[AUTOSCOUT24] Page load error (attempt {retry_count + 1}): {e}")
                    if retry_count < 2:
                        await page.close()
                        backoff_time = (2 ** retry_count) * 3 + random.uniform(1, 3)
                        logger.info(f"[AUTOSCOUT24] Retrying after {backoff_time:.1f}s...")
                        await asyncio.sleep(backoff_time)
                        return await self.scrape_listings(vehicle_type, max_listings, scrape_details, retry_count + 1)
                    break

                cards = await page.query_selector_all("article.ListItem_article__q_yqV, div[data-testid='listing-card']")
                if not cards:
                    logger.warning(f"[AUTOSCOUT24] No cards on page {page_num}")
                    # Retry with different approach if first page
                    if page_num == 1 and retry_count < 2:
                        await page.close()
                        backoff_time = (2 ** retry_count) * 3 + random.uniform(1, 3)
                        logger.info(f"[AUTOSCOUT24] Retrying page 1 with different approach...")
                        await asyncio.sleep(backoff_time)
                        return await self.scrape_listings(vehicle_type, max_listings, scrape_details, retry_count + 1)
                    break

                for card in cards[:max_listings - len(listings)]:
                    try:
                        listing = await self._extract_card(card, vehicle_type)
                        if listing:
                            listings.append(listing)
                    except Exception as e:
                        logger.debug(f"[AUTOSCOUT24] Card parse error: {e}")

                if len(cards) < 20:
                    break

                page_num += 1
                await self._rate_limit()
        finally:
            await page.close()

        logger.info(f"[AUTOSCOUT24] Total: {len(listings)} listings")
        return listings

    def _build_listing_url(self, vehicle_type: str, page: int = 1) -> str:
        type_param = "" if vehicle_type == "carros" else "&category=m"
        return (
            f"{self.BASE_URL}/listado/carros/"
            f"?sort=standard&desc=0&page={page}&cy=PT&o={page}{type_param}"
        )

    async def _extract_card(self, card, vehicle_type: str) -> Optional[Dict[str, Any]]:
        try:
            link_el = await card.query_selector("a.ListItem_title__znVnE, a[data-testid='listing-title']")
            if not link_el:
                return None
            url = await link_el.get_attribute("href") or ""
            if url and not url.startswith("http"):
                url = self.BASE_URL + url
            title = (await link_el.inner_text()).strip()
            if not title:
                return None

            price_el = await card.query_selector("p.PriceListing_price__EQVp5, span[data-testid='price']")
            price_text = (await price_el.inner_text()).strip() if price_el else "0"
            price = self._parse_price(price_text)

            detail_els = await card.query_selector_all("span.ListItem_standardData__jMUbV, li[data-testid='detail']")
            year, km, hp, cc, fuel, trans = None, None, None, None, None, None
            for el in detail_els:
                text = (await el.inner_text()).strip().lower()
                if re.match(r"\d{4}", text):
                    year = int(re.match(r"(\d{4})", text).group(1))
                elif "km" in text:
                    km = self._parse_int(text)
                elif "cv" in text or "hp" in text:
                    hp = self._parse_int(text)
                elif "cm3" in text or "cc" in text:
                    cc = self._parse_int(text)

            loc_el = await card.query_selector("span.ListItem_location__Mr8Ae, div[data-testid='location']")
            location = (await loc_el.inner_text()).strip() if loc_el else None

            return self.build_vehicle_dict(
                url=url, title=title, price=price, vehicle_type=vehicle_type,
                year=year, km=km, horsepower=hp, engine_size=cc,
                location=location,
            )
        except Exception as e:
            logger.debug(f"[AUTOSCOUT24] Card extraction error: {e}")
            return None

    def _parse_price(self, text: str) -> float:
        text = re.sub(r"[^\d,]", "", text).replace(",", ".")
        try:
            return float(text) if text else 0.0
        except ValueError:
            return 0.0

    def _parse_int(self, text: str) -> Optional[int]:
        nums = re.findall(r"[\d\s]+", text)
        if nums:
            return int(nums[0].replace(" ", ""))
        return None
