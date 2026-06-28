"""MEGA SCRAPER V2 - scrapes ALL Standvirtual pages using article HTML.
Extracts real URLs, horsepower, engine_size, transmission from article <dl> and text.
Runs autonomously until reaching target vehicle count.
"""
import sys, os, asyncio, logging, time, re, hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MEGA_SCRAPE")

import httpx
from bs4 import BeautifulSoup
from database.db import get_db_context, init_db
from database.models import Vehicle, Source, FuelType, Transmission, VehicleType
from sqlalchemy import select

init_db()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}

FUEL_MAP = {
    "gasolina": FuelType.GASOLINE, "gasoline": FuelType.GASOLINE,
    "diesel": FuelType.DIESEL, "gasoleo": FuelType.DIESEL,
    "eletrico": FuelType.ELECTRIC, "elétrico": FuelType.ELECTRIC,
    "hibrido": FuelType.HYBRID, "híbrido": FuelType.HYBRID,
    "gpl": FuelType.GPL,
}

TRANS_MAP = {
    "manual": Transmission.MANUAL,
    "automatica": Transmission.AUTOMATIC, "automática": Transmission.AUTOMATIC,
    "semi-automatica": Transmission.SEMI_AUTOMATIC,
}

BRAND_LIST = [
    "Alfa Romeo", "Aston Martin", "Land Rover", "Rolls-Royce",
    "Mercedes-Benz", "Harley-Davidson", "CF Moto", "Royal Enfield",
    "Porsche", "Ferrari", "Lamborghini", "Maserati", "Bentley",
    "McLaren", "Bugatti", "Tesla", "Jaguar", "Lexus", "Infiniti",
    "Polestar", "Cupra",
    "Volkswagen", "BMW", "Mercedes", "Audi", "Renault", "Peugeot",
    "Citroen", "Citroën", "Ford", "Toyota", "Honda", "Nissan",
    "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo",
    "Mazda", "Mitsubishi", "Suzuki", "Dacia", "Opel", "Mini",
    "Smart", "Chevrolet", "Jeep", "Dodge", "Chrysler", "Subaru",
    "DS", "MG", "BYD", "Iveco", "Isuzu", "MAN",
    "Ducati", "Yamaha", "Kawasaki", "Triumph", "KTM", "Aprilia",
    "Husqvarna", "Benelli", "Piaggio", "SYM",
]


def parse_brand_model(title: str):
    tl = title.lower()
    for brand in BRAND_LIST:
        if brand.lower() in tl:
            idx = tl.index(brand.lower())
            model = title[idx + len(brand):].strip()
            return brand, model
    parts = title.split(maxsplit=1)
    return (parts[0], parts[1]) if len(parts) >= 2 else (title, "")


def extract_hp_cc(text: str):
    hp, cc = None, None
    m = re.search(r"(\d{2,3})\s*(?:cv|hp)", text, re.I)
    if m and 10 < int(m.group(1)) < 2000:
        hp = int(m.group(1))
    m = re.search(r"(\d{3,4})\s*cm3?", text, re.I)
    if m and 50 < int(m.group(1)) < 10000:
        cc = int(m.group(1))
    return hp, cc


def scrape_standvirtual_page(html: str, vehicle_type: str = "carros") -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    for art in soup.select("article"):
        link = art.select_one('a[href*="/anuncio/"]')
        h2 = art.select_one("h2")
        if not (link and h2):
            continue

        href = link.get("href", "")
        if href.startswith("/"):
            href = "https://www.standvirtual.com" + href

        title = h2.get_text(strip=True)
        brand, model = parse_brand_model(title)

        # Price from h3
        h3 = art.select_one("h3")
        price = None
        if h3:
            pt = h3.get_text(strip=True).replace("\xa0", " ").replace(" ", "")
            nums = re.findall(r"\d+", pt)
            if nums: price = float(nums[0])

        if not price or price < 100:
            continue

        # Extract structured data from <dl>
        year = km = None
        fuel = trans = None
        hp = cc = None

        dl = art.select_one("dl")
        full_text = art.get_text(" ", strip=True)
        if dl:
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt_el, dd_el in zip(dts, dds):
                key = dt_el.get_text(strip=True).lower()
                val = dd_el.get_text(strip=True)
                if key == "first_registration_year":
                    year = int(val) if val.isdigit() else None
                elif key == "mileage":
                    cval = re.sub(r"[^\d]", "", val)
                    km = int(cval) if cval else None
                elif key in ("fuel_type", "fuel"):
                    for k, v in FUEL_MAP.items():
                        if k in val.lower(): fuel = v; break
                elif key in ("gearbox", "transmission"):
                    for k, v in TRANS_MAP.items():
                        if k in val.lower(): trans = v; break
            hp, cc = extract_hp_cc(full_text)
            if not fuel:
                fuel = None
                for k, v in FUEL_MAP.items():
                    if k in full_text.lower(): fuel = v; break
        else:
            # Fallback: extract from full text
            text = art.get_text(" ", strip=True)
            year_m = re.search(r"first_registration_year\s*[:\s]*(\d{4})", text, re.I)
            if year_m: year = int(year_m.group(1))
            km_m = re.search(r"mileage\s*[:\s]*([\d\s.]+)", text, re.I)
            if km_m:
                c = km_m.group(1).replace(" ", "").replace(".", "")
                km = int(c) if c.isdigit() else None
            hp, cc = extract_hp_cc(text)
            fuel = None
            for k, v in FUEL_MAP.items():
                if k in text.lower(): fuel = v; break
            for k, v in TRANS_MAP.items():
                if k in text.lower(): trans = v; break

        sid = hashlib.md5(href.encode()).hexdigest()
        listings.append({
            "source": Source.STANDVIRTUAL, "source_id": sid, "url": href,
            "title": title, "brand": brand, "model": model,
            "price": price, "year": year, "km": km,
            "fuel_type": fuel, "transmission": trans,
            "horsepower": hp, "engine_size": cc,
            "vehicle_type": vehicle_type,
        })
    return listings


async def scrape_standvirtual(max_pages: int = 500, vehicle_type: str = "carros") -> List[Dict]:
    all_listings = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for page in range(1, max_pages + 1):
            url = f"https://www.standvirtual.com/{vehicle_type}/?page={page}"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"SV p{page}: HTTP {resp.status_code}")
                    break
                listings = scrape_standvirtual_page(resp.text, vehicle_type)
                if not listings:
                    logger.warning(f"SV p{page}: no listings")
                    break
                all_listings.extend(listings)
                logger.info(f"SV {vehicle_type} p{page}: {len(listings)} (total: {len(all_listings)})")
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"SV p{page}: {e}")
                break
    return all_listings


def save_listings(listings: List[Dict]) -> int:
    saved = 0
    updated = 0
    skipped = 0
    seen = set()
    with get_db_context() as db:
        for l in listings:
            sid = l.get("source_id", "")
            src = l.get("source")
            if not sid or not src:
                skipped += 1
                continue
            dup_key = (str(src), str(sid))
            if dup_key in seen:
                skipped += 1
                continue
            seen.add(dup_key)
            try:
                existing = db.execute(
                    select(Vehicle).where(Vehicle.source == src, Vehicle.source_id == sid)
                ).scalar_one_or_none()
            except Exception:
                existing = None
            if existing:
                np = float(l.get("price", 0))
                if np > 0 and existing.price != np:
                    existing.price = np
                    existing.last_seen = datetime.now(timezone.utc)
                    existing.scrape_count = (existing.scrape_count or 1) + 1
                    updated += 1
                for f in ["horsepower", "engine_size", "fuel_type", "transmission", "km", "year"]:
                    v = l.get(f)
                    if v is not None and not getattr(existing, f, None):
                        setattr(existing, f, v)
                        updated += 1
            else:
                try:
                    v = Vehicle(
                        source=src, source_id=sid,
                        url=str(l.get("url", "")),
                        vehicle_type=VehicleType.carros,
                        brand=str(l.get("brand", "Unknown"))[:100],
                        model=str(l.get("model", "Unknown"))[:100],
                        year=l.get("year"), km=l.get("km"),
                        price=float(l.get("price", 0)),
                        title=str(l.get("title", ""))[:200],
                        fuel_type=l.get("fuel_type"),
                        transmission=l.get("transmission"),
                        horsepower=l.get("horsepower"),
                        engine_size=l.get("engine_size"),
                        first_seen=datetime.now(timezone.utc),
                        last_seen=datetime.now(timezone.utc),
                    )
                    db.add(v)
                    saved += 1
                except Exception:
                    skipped += 1
        try:
            db.commit()
        except Exception:
            db.rollback()
    logger.info(f"Saved: {saved} new, {updated} updated, {skipped} skipped")
    return saved


async def scrape_with_batch_save(max_pages=500, vehicle_type="carros", batch_size=100):
    """Scrape and save in batches to avoid losing progress on timeout."""
    total_saved = 0
    batch = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for page in range(1, max_pages + 1):
            url = f"https://www.standvirtual.com/{vehicle_type}/?page={page}"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    break
                listings = scrape_standvirtual_page(resp.text, vehicle_type)
                if not listings:
                    break
                batch.extend(listings)
                logger.info(f"SV {vehicle_type} p{page}: {len(listings)} (batch: {len(batch)})")
                if len(batch) >= batch_size * 35:
                    saved = save_listings(batch)
                    total_saved += saved
                    logger.info(f"Batch saved: {saved} (total: {total_saved})")
                    batch = []
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"SV p{page}: {e}")
                break
    if batch:
        saved = save_listings(batch)
        total_saved += saved
    return total_saved


async def main():
    start = time.time()

    saved = await scrape_with_batch_save(500, "carros", batch_size=50)
    if saved < 50000:
        saved += await scrape_with_batch_save(100, "motos", batch_size=50)

    elapsed = time.time() - start
    logger.info(f"Total time: {elapsed:.1f}s")

    with get_db_context() as db:
        total = db.query(Vehicle).count()
        active = db.query(Vehicle).filter(Vehicle.is_active == True).count()
        hp = db.query(Vehicle).filter(Vehicle.horsepower.isnot(None)).count()
        logger.info(f"Database: {total} total, {active} active, {hp} with HP")


if __name__ == "__main__":
    asyncio.run(main())
