"""
Leilosoc Lightweight Scraper — requests + embedded __NEXT_DATA__ JSON.
Site: leilosoc.com — Portuguese auction site with REAL transaction prices.
Framework: Next.js (data embedded in __NEXT_DATA__ <script> tag).
Extracts auction lots with adjudication prices (GROUND TRUTH for ML).
"""
from __future__ import annotations
import hashlib
import json
import logging
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from utils.scraping_log import start_scrape_log, finish_scrape_log

logger = logging.getLogger(__name__)

# Vehicle category ID = 6 ("Veículos")
VEHICLE_CATEGORY_ID = 6

# Subcategories for vehicles
VEHICLE_SUBCATEGORIES = {
    101: "veiculo_ligeiro",
    102: "veiculo_ligeiro_mercadorias",
    103: "veiculo_pesado",
    104: "veiculo_pesado_mercadorias",
    105: "motociclo",
    106: "reboque",
    107: "maquina_industrial",
    108: "outros_veiculos",
}


class LeilosocLightweight:
    """Scraper for Leilosoc.com using SSR __NEXT_DATA__ JSON.

    Leilosoc is a Portuguese auction platform. The key value proposition:
    prices are REAL transaction prices (adjudication/sold), not asking prices.
    This makes it the best source of GROUND TRUTH pricing for ML training.
    """

    BASE_URL = "https://leilosoc.com"
    CATEGORY_URL = f"{BASE_URL}/pt-PT/category/{VEHICLE_CATEGORY_ID}-veiculos"
    IMAGE_BASE = "https://s-auctions.devscope.net"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            ]),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        })

    def scrape_listings(
        self,
        max_listings: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape auction lots from Leilosoc.

        Args:
            max_listings: Maximum lots to return
            filters: Optional filters (not yet implemented)

        Returns:
            List of auction lot dicts with real transaction prices.
        """
        logger.info(f"[LEILOSOC_LIGHT] Starting scrape, max {max_listings}")
        log_id = start_scrape_log("LEILOSOC")

        listings = []
        page = 1

        while len(listings) < max_listings:
            url = f"{self.CATEGORY_URL}?page={page}" if page > 1 else f"{self.CATEGORY_URL}/"
            logger.info(f"[LEILOSOC_LIGHT] Fetching page {page}")

            try:
                resp = self.session.get(url, timeout=20)
                if resp.status_code != 200:
                    logger.warning(f"[LEILOSOC_LIGHT] HTTP {resp.status_code} on page {page}")
                    break
                html = resp.text
            except requests.RequestException as e:
                logger.error(f"[LEILOSOC_LIGHT] Request failed: {e}")
                break

            page_lots = self._parse_next_data(html)
            if not page_lots:
                logger.info(f"[LEILOSOC_LIGHT] No lots on page {page}")
                break

            logger.info(f"[LEILOSOC_LIGHT] Page {page}: {len(page_lots)} lots")
            listings.extend(page_lots)
            page += 1

            if len(page_lots) < 10:
                break

        listings = listings[:max_listings]
        logger.info(f"[LEILOSOC_LIGHT] Total extracted: {len(listings)}")
        if log_id:
            finish_scrape_log(log_id, "completed", listings_found=len(listings))
        return listings

    def _parse_next_data(self, html: str) -> List[Dict[str, Any]]:
        """Extract lot data from __NEXT_DATA__ JSON."""
        match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if not match:
            logger.debug("[LEILOSOC_LIGHT] No __NEXT_DATA__ found")
            return []

        try:
            data = json.loads(match.group(1))
            lots = (
                data.get("props", {})
                .get("pageProps", {})
                .get("lots", {})
                .get("items", [])
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[LEILOSOC_LIGHT] JSON parse error: {e}")
            return []

        if not lots:
            return []

        listings = []
        for lot in lots:
            try:
                listing = self._normalize_lot(lot)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[LEILOSOC_LIGHT] Lot normalize error: {e}")
                continue

        return listings

    def _normalize_lot(self, lot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize a Leilosoc auction lot to standard schema."""
        cf = lot.get("customFieldsValues", {}) or {}

        # --- Title ---
        title = lot.get("title", "") or lot.get("auctionTitle", "")
        if not title:
            return None

        # --- Brand & Model from custom fields ---
        brand_raw = (cf.get("brand") or "").strip()
        brand = self._normalize_brand(brand_raw)
        model = (cf.get("model") or "").strip()

        # If brand not in custom fields, parse from title
        if not brand or not model:
            brand, model = self._parse_brand_model(title)

        # --- Year ---
        year = self._safe_int(cf.get("car_year"))

        # --- KM ---
        km = None
        # Try multiple field names
        for km_field in ["mileage", "km", "odometer", "kilometers", "kms"]:
            km_val = cf.get(km_field)
            if km_val is not None:
                km = self._safe_int(km_val)
                if km is not None and km > 0:
                    break
        # If still no km, try to extract from title/description
        if not km:
            full_text = (title + " " + (lot.get("description") or "")).lower()
            km_m = re.search(r"(\d[\d\s.]*)\s*(?:km|kms|quilómetros|quilometros)", full_text)
            if km_m:
                km_str = re.sub(r"[\s.]", "", km_m.group(1))
                try:
                    km = int(km_str) if km_str else None
                except ValueError:
                    pass

        # --- Price (adjudication / base value) ---
        # Priority: valueSold (actual adjudication) > valueOpen (current bid) > valueBase (starting)
        price = None
        price_type = "unknown"
        for field, ptype in [
            ("valueSold", "adjudicado"),
            ("valueOpen", "licitacao_aberta"),
            ("valueBase", "valor_base"),
        ]:
            val = lot.get(field)
            if val is not None and val > 0:
                price = float(val)
                price_type = ptype
                break

        if not price:
            return None

        # --- Fuel type ---
        fuel_type = self._normalize_fuel(cf.get("fuel_type", ""))

        # --- Transmission ---
        transmission = "unknown"
        trans_raw = (cf.get("car_transmission") or "").lower()
        if "manual" in trans_raw:
            transmission = "manual"
        elif "auto" in trans_raw:
            transmission = "automatico"
        # Fallback: try to extract from title/description
        if transmission == "unknown":
            full_text = (title + " " + (lot.get("description") or "")).lower()
            if "manual" in full_text:
                transmission = "manual"
            elif any(t in full_text for t in ["automático", "automática", "automatico", "automatica", "auto"]):
                transmission = "automatico"

        # --- Horsepower (power/cv) ---
        hp = self._safe_int(cf.get("power"))

        # --- Engine size (cc) ---
        cc = self._safe_int(cf.get("cc"))

        # --- Color ---
        color = cf.get("colour", "")

        # --- Doors ---
        doors = self._safe_int(cf.get("doors"))

        # --- Seats ---
        seats = self._safe_int(cf.get("number_of_seats"))

        # --- Plate ---
        plate = cf.get("plate_number", "")

        # --- Auction dates ---
        auction_start = lot.get("auctionStartDate")
        auction_end = lot.get("auctionEndDate")
        auction_date = None
        if auction_end:
            try:
                auction_date = auction_end[:10]  # YYYY-MM-DD
            except Exception:
                pass

        # --- Condition (from description) ---
        condition = "unknown"
        description = (lot.get("description") or "").lower()
        if any(w in description for w in ["danos", "risco", "partido", "amolgadela", "não funciona"]):
            condition = "danificado"
        elif any(w in description for w in ["bom estado", "excelente", "como novo"]):
            condition = "bom"
        elif any(w in description for w in ["novo", "semi-novo"]):
            condition = "seminovo"

        # --- Auction type ---
        auction_type = lot.get("auctionTypeCode", "")

        # --- Country ---
        country_id = lot.get("countryId")
        country = "PT" if country_id == 14943 else str(country_id)

        # --- Location ---
        location = lot.get("auctionAddressLocation", "") or lot.get("addressLocation", "")
        zip_code = lot.get("auctionAddressZipCode", "") or lot.get("addressZipCode", "")

        # --- Process number ---
        process_number = lot.get("processNumber", "")

        # --- URL ---
        auction_id = lot.get("auctionId", "")
        batch_id = lot.get("batchId", "")
        url = f"{self.BASE_URL}/pt-PT/lot/{auction_id}/{batch_id}"

        # --- Images ---
        images = []
        for img_path in (lot.get("pictures") or []):
            if img_path:
                if img_path.startswith("/"):
                    images.append(f"{self.IMAGE_BASE}{img_path}")
                else:
                    images.append(img_path)

        # --- Subcategory ---
        subcat_id = lot.get("batchSubCategoryId", 0)
        subcategory = VEHICLE_SUBCATEGORIES.get(subcat_id, f"subcat_{subcat_id}")

        # --- Source ID ---
        source_id = f"leilosoc_{batch_id}"

        # --- Seller ---
        seller = lot.get("userName", "")

        return {
            "source": "leilosoc",
            "source_id": source_id,
            "url": url,
            "title": title,
            "brand": brand,
            "model": model,
            "price": price,
            "price_type": price_type,
            "year": year,
            "km": km,
            "fuel_type": fuel_type,
            "engine_size": cc,
            "transmission": transmission,
            "horsepower": hp,
            "color": color,
            "doors": doors,
            "seats": seats,
            "plate": plate,
            "location": location,
            "zip_code": zip_code,
            "country": country,
            "condition": condition,
            "auction_type": auction_type,
            "auction_date": auction_date,
            "auction_start": auction_start,
            "auction_end": auction_end,
            "process_number": process_number,
            "subcategory": subcategory,
            "images": images[:5],  # Limit to 5 images
            "seller": seller,
            "value_base": lot.get("valueBase"),
            "value_open": lot.get("valueOpen"),
            "value_sold": lot.get("valueSold"),
        }

    def _parse_brand_model(self, title: str) -> tuple:
        """Parse brand and model from lot title."""
        BRANDS_LIST = [
            "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz",
            "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
            "Citroën", "Citroen", "Ford", "Toyota", "Honda", "Nissan",
            "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo",
            "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini",
            "Smart", "Jeep", "Porsche", "Jaguar", "Lexus", "Subaru", "Tesla",
            "Cupra", "DS", "Iveco", "MAN", "Scania", "Volkswagen",
            "Citroen", "Lancia", "MG", "BYD", "Polestar", "Isuzu",
        ]
        title_lower = title.lower()
        for b in BRANDS_LIST:
            if b.lower() in title_lower:
                idx = title_lower.index(b.lower())
                model = title[idx + len(b):].strip()
                # Remove common separators
                model = re.sub(r'^[-·•|]\s*', '', model)
                # Remove "· Ano XXXX" suffix
                model = re.sub(r'\s*[·•]\s*Ano\s*\d{4}.*$', '', model).strip()
                return b, model
        parts = title.split(maxsplit=1)
        return (parts[0], parts[1]) if len(parts) >= 2 else (title, "")

    def _normalize_brand(self, raw: str) -> str:
        """Normalize brand name to proper capitalization."""
        if not raw:
            return "Unknown"
        brand_mapping = {
            "bmw": "BMW", "vw": "VW", "mg": "MG", "byd": "BYD",
            "ds": "DS", "man": "MAN", "iveco": "Iveco", "scania": "Scania",
            "citroen": "Citroën", "citroën": "Citroën",
            "land rover": "Land Rover", "landrover": "Land Rover",
            "mercedes": "Mercedes", "mercedes-benz": "Mercedes-Benz",
            "alfa romeo": "Alfa Romeo", "alfaromeo": "Alfa Romeo",
            "aston martin": "Aston Martin", "astonmartin": "Aston Martin",
            "range rover": "Land Rover",
            "peugeot": "Peugeot",
        }
        lower = raw.lower().strip()
        if lower in brand_mapping:
            return brand_mapping[lower]
        return raw.title()

    def _normalize_fuel(self, raw: str) -> str:
        if not raw:
            return "unknown"
        raw_lower = raw.lower().strip()
        if any(k in raw_lower for k in ("gasolina", "gasoline", "petrol")):
            return "gasolina"
        if any(k in raw_lower for k in ("diesel", "gasóleo", "gasoleo")):
            return "diesel"
        if any(k in raw_lower for k in ("elétrico", "eletrico", "electric", "eléctrico")):
            return "eletrico"
        if any(k in raw_lower for k in ("híbrido", "hibrido", "hybrid")):
            return "hibrido"
        if "gpl" in raw_lower:
            return "gpl"
        return raw_lower if raw_lower else "unknown"

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            if isinstance(value, str):
                digits = re.sub(r"\D", "", value)
                return int(digits) if digits else None
            if isinstance(value, (int, float)):
                # Handle European decimal format: 334.147 should be 334147, not 334
                val_str = str(value)
                if "." in val_str and len(val_str.split(".")[-1]) == 3:
                    # Likely European thousand separator, not decimal
                    digits = re.sub(r"\D", "", val_str)
                    return int(digits) if digits else None
                return int(value)
            digits = re.sub(r"\D", "", str(value))
            return int(digits) if digits else None
        except (ValueError, TypeError):
            return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = LeilosocLightweight()
    results = s.scrape_listings(max_listings=10)
    print(f"\n=== Scraped {len(results)} Leilosoc lots ===")
    for r in results[:10]:
        print(f"  {r.get('title','?')}")
        print(f"    Price: €{r.get('price','?')} ({r.get('price_type','?')}) | Year: {r.get('year','?')} | Km: {r.get('km','?')}")
        print(f"    Fuel: {r.get('fuel_type','?')} | Trans: {r.get('transmission','?')} | HP: {r.get('horsepower','?')}")
        print(f"    Brand: {r.get('brand','?')} | Model: {r.get('model','?')}")
        print(f"    Auction: {r.get('auction_date','?')} | Type: {r.get('auction_type','?')} | Condition: {r.get('condition','?')}")
        print(f"    Location: {r.get('location','?')} | Seller: {r.get('seller','?')}")
        print()
