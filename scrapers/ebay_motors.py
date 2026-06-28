"""
eBay Motors API client for ground truth transaction prices.
Uses official eBay Browse API (free tier: 5,000 calls/day).
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class eBayMotorsAPI(BaseScraper):
    """Scrapes eBay Motors via official Browse API for real transaction data."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("EBAY_MOTORS")
        self.api_key = api_key or os.getenv("EBAY_API_KEY", "")
        if not self.api_key:
            logger.warning("EBAY_API_KEY not set; eBay scraper will be non-functional")
        self.base_url = "https://api.ebay.com/buy/browse/v1"

    async def scrape_listings(
        self, vehicle_type: str, max_listings: int = 50, scrape_details: bool = True
    ) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.error("Cannot scrape eBay: EBAY_API_KEY not configured")
            return []

        listings = []
        offset = 0
        limit = min(max_listings, 50)

        while len(listings) < max_listings:
            try:
                results = await self._search_vehicles(
                    limit=limit, offset=offset, condition="USED"
                )
                if not results:
                    break

                for item in results:
                    listing = self._normalize_item(item, vehicle_type)
                    if listing:
                        listings.append(listing)

                offset += limit
                if len(results) < limit:
                    break
            except Exception as e:
                logger.error(f"eBay search error: {e}")
                break

        logger.info(f"[EBAY_MOTORS] Total: {len(listings)} listings")
        return listings

    async def _search_vehicles(
        self, limit: int = 50, offset: int = 0, condition: str = "USED"
    ) -> List[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "Content-Type": "application/json",
        }
        params = {
            "q": "car",
            "limit": str(limit),
            "offset": str(offset),
            "filter": f"conditions:{{{condition}}}",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/item_summary/search",
                headers=headers, params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("itemSummaries", [])

    def _normalize_item(self, item: Dict[str, Any], vehicle_type: str) -> Optional[Dict[str, Any]]:
        try:
            title = item.get("title", "")
            url = item.get("itemWebUrl", "")
            price_amount = 0.0
            price_data = item.get("price", {})
            if price_data:
                price_amount = float(price_data.get("value", "0"))

            vehicle = self.build_vehicle_dict(
                url=url, title=title, price=price_amount,
                vehicle_type=vehicle_type,
                source_id=item.get("itemId", self._make_id(url)),
                year=self._extract_year(title),
                km=None,
                location=item.get("itemLocation", {}).get("city"),
                currency=price_data.get("currency", "USD"),
                condition=item.get("condition", "Used"),
                is_auction="auction" in item.get("buyingOptions", []),
            )
            return vehicle
        except Exception as e:
            logger.debug(f"eBay item normalize error: {e}")
            return None

    def _extract_year(self, title: str) -> Optional[int]:
        import re
        match = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", title)
        return int(match.group(1)) if match else None
