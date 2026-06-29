"""Process scraped HTML files from Standvirtual (JSON-LD) and AutoSapo (HTML cards).

Reads HTML files from the kilo tool-output directory, extracts vehicle listings,
normalizes fuel types, and saves them to the database with dedup by (source, source_id).
"""
import sys
import os

sys.path.insert(0, '.')

import glob
import hashlib
import json
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from database.db import get_db_context, init_db
from database.models import Vehicle, Source, FuelType, VehicleType

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TOOL_OUTPUT_DIR = Path.home() / ".local" / "share" / "kilo" / "tool-output"
FILE_GLOB = "tool_*"
AUTOSAPO_BASE = "https://www.autosapo.pt"
STANDVIRTUAL_BASE = "https://www.standvirtual.com"

FUEL_MAP_RULES = [
    ("gasolina", FuelType.GASOLINE),
    ("diesel", FuelType.DIESEL),
    ("elétrico", FuelType.ELECTRIC),
    ("electrico", FuelType.ELECTRIC),
    ("híbrido", FuelType.HYBRID),
    ("hibrido", FuelType.HYBRID),
    ("gpl", FuelType.GPL),
]


def normalize_fuel(raw: str):
    if not raw:
        return None
    low = raw.lower().strip()
    for key, ft in FUEL_MAP_RULES:
        if key in low:
            return ft
    return None


def to_int(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        return None
    return int(digits)


def source_id_for(url_or_name: str) -> str:
    return hashlib.md5(url_or_name.encode("utf-8")).hexdigest()


def split_brand_model(brand: str, name: str):
    """Split a listing name into (brand, model) using the known brand prefix."""
    brand = (brand or "").strip()
    name = (name or "").strip()
    if brand and name.lower().startswith(brand.lower()):
        model = name[len(brand):].strip()
    elif brand:
        model = name
    else:
        parts = name.split(maxsplit=1)
        brand = parts[0] if parts else "Unknown"
        model = parts[1] if len(parts) > 1 else name
    if not model:
        model = name or "Unknown"
    return brand or "Unknown", model[:100]


def parse_standvirtual_jsonld(soup: BeautifulSoup):
    """Extract listings from <script id="listing-json-ld"> JSON-LD blocks."""
    listings = []
    for tag in soup.find_all("script", id="listing-json-ld"):
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        items = []
        if isinstance(data, dict):
            me = data.get("mainEntity") or data
            if isinstance(me, dict):
                items = me.get("itemListElement") or []
            elif isinstance(me, list):
                items = me
        elif isinstance(data, list):
            items = data

        for el in items:
            if not isinstance(el, dict):
                continue
            offer = el.get("itemOffered") if "@type" in el else el
            if isinstance(el.get("itemOffered"), dict):
                offer = el["itemOffered"]
            if not isinstance(offer, dict):
                continue

            name = offer.get("name") or ""
            brand = offer.get("brand")
            if isinstance(brand, dict):
                brand = brand.get("name")
            brand = brand or ""

            price_spec = el.get("priceSpecification") or offer.get("priceSpecification") or {}
            if isinstance(price_spec, dict):
                price = price_spec.get("price")
            else:
                price = None
            if price is None:
                price = el.get("price") or offer.get("price")
            price = to_int(price) if price is not None else None
            if price is None:
                continue

            year = to_int(offer.get("modelDate") or el.get("modelDate"))
            mileage = offer.get("mileageFromOdometer") or el.get("mileageFromOdometer")
            if isinstance(mileage, dict):
                mileage = mileage.get("value")
            km = to_int(mileage)
            fuel = normalize_fuel(offer.get("fuelType") or el.get("fuelType"))

            url = el.get("url") or offer.get("url") or name
            if url and not str(url).startswith("http"):
                url = STANDVIRTUAL_BASE + str(url) if str(url).startswith("/") else STANDVIRTUAL_BASE + "/" + str(url)

            listings.append({
                "source": Source.STANDVIRTUAL,
                "url": url,
                "name": name,
                "brand": brand,
                "price": float(price),
                "year": year,
                "km": km,
                "fuel": fuel,
            })
    return listings


def parse_autosapo_cards(soup: BeautifulSoup):
    """Extract listings from <article class="vehicle-card"> elements."""
    listings = []
    for art in soup.find_all("article", class_="vehicle-card"):
        h3 = art.find("h3", attrs={"itemprop": "name"})
        link = h3.find("a", attrs={"itemprop": "url"}) if h3 else None
        if not link:
            continue
        href = link.get("href") or ""
        if href and not href.startswith("http"):
            href = AUTOSAPO_BASE + href if href.startswith("/") else AUTOSAPO_BASE + "/" + href
        # Title text without the inner <span> (which holds "136cv - 5P")
        title_text = link.get_text(strip=True)
        # The span text is appended; strip it by taking only the text node before the span
        span = link.find("span")
        if span:
            span_text = span.get_text(strip=True)
            title_text = title_text.replace(span_text, "").strip()

        lis = art.find_all("li")
        year = km = None
        fuel = None
        for li in lis:
            txt = li.get_text(strip=True)
            if re.fullmatch(r"\d{4}", txt):
                year = int(txt)
            elif "km" in txt.lower():
                km = to_int(txt)
            else:
                ft = normalize_fuel(txt)
                if ft is not None:
                    fuel = ft

        price = None
        price_div = art.find("div", class_="price")
        if price_div:
            span_price = price_div.find("span")
            if span_price:
                # Price like "19.490" -> 19490
                ptext = span_price.get_text(strip=True)
                # remove the euro sign / inner small
                ptext = re.sub(r"[€\s]", "", ptext)
                ptext = ptext.replace(".", "").replace(",", "")
                digits = re.sub(r"[^\d]", "", ptext)
                if digits:
                    price = float(int(digits))
        if price is None:
            continue

        brand, model = split_brand_model("", title_text)
        listings.append({
            "source": Source.AUTOSAPO,
            "url": href,
            "name": title_text,
            "brand": brand,
            "price": price,
            "year": year,
            "km": km,
            "fuel": fuel,
        })
    return listings


def process_file(path: Path):
    try:
        html = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        logger.warning(f"Could not read {path.name}: {e}")
        return []
    soup = BeautifulSoup(html, "html.parser")
    listings = parse_standvirtual_jsonld(soup)
    listings += parse_autosapo_cards(soup)
    return listings


def save_listings(listings):
    added = updated = skipped = 0
    with get_db_context() as db:
        for item in listings:
            price = item["price"]
            if price is None or price < 100:
                skipped += 1
                continue

            url = item["url"] or item["name"]
            sid = source_id_for(url)
            brand, model = split_brand_model(item["brand"], item["name"])

            existing = (
                db.query(Vehicle)
                .filter(Vehicle.source == item["source"], Vehicle.source_id == sid)
                .first()
            )
            if existing:
                existing.price = price
                if item["year"]:
                    existing.year = item["year"]
                if item["km"] is not None:
                    existing.km = item["km"]
                if item["fuel"] is not None:
                    existing.fuel_type = item["fuel"]
                existing.brand = brand
                existing.model = model
                existing.title = item["name"]
                existing.is_active = True
                db.add(existing)
                updated += 1
                continue

            vehicle = Vehicle(
                source=item["source"],
                source_id=sid,
                url=url,
                vehicle_type=VehicleType.carros,
                brand=brand,
                model=model,
                year=item["year"],
                km=item["km"],
                price=price,
                title=item["name"],
                fuel_type=item["fuel"],
                is_active=True,
            )
            db.add(vehicle)
            added += 1
        db.commit()
    return added, updated, skipped


def main():
    init_db()
    files = sorted(glob.glob(str(TOOL_OUTPUT_DIR / FILE_GLOB)))
    logger.info(f"Found {len(files)} scraped HTML files")
    all_listings = []
    standvirtual_count = autosapo_count = 0
    for f in files:
        listings = process_file(Path(f))
        if listings:
            sv = sum(1 for l in listings if l["source"] == Source.STANDVIRTUAL)
            ap = sum(1 for l in listings if l["source"] == Source.AUTOSAPO)
            standvirtual_count += sv
            autosapo_count += ap
            logger.info(f"  {Path(f).name}: {len(listings)} listings (SV={sv}, AS={ap})")
        all_listings.extend(listings)

    logger.info(f"\nTotal parsed: {len(all_listings)} (Standvirtual={standvirtual_count}, AutoSapo={autosapo_count})")
    added, updated, skipped = save_listings(all_listings)
    logger.info(f"Saved: added={added}, updated={updated}, skipped(<100EUR)={skipped}")


if __name__ == "__main__":
    main()
