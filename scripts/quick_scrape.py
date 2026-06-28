"""Quick Standvirtual scraper test - 20 pages"""
import sys, os, asyncio, re, hashlib, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(message)s")
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import httpx
from database.db import get_db_context, init_db
from database.models import Vehicle, Source, VehicleType, FuelType, Transmission
from sqlalchemy import select

init_db()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "pt-PT,pt;q=0.9",
}
FUEL_MAP = {
    "gasolina": FuelType.GASOLINE, "diesel": FuelType.DIESEL, "gasoleo": FuelType.DIESEL,
    "eletrico": FuelType.ELECTRIC, "elétrico": FuelType.ELECTRIC,
    "hibrido": FuelType.HYBRID, "gpl": FuelType.GPL,
}
TRANS_MAP = {
    "manual": Transmission.MANUAL, "automatica": Transmission.AUTOMATIC,
}
BRAND_LIST = [
    "Alfa Romeo", "BMW", "Mercedes-Benz", "Mercedes", "Audi", "Renault",
    "Peugeot", "Citroen", "Citroën", "Ford", "Toyota", "Honda", "Nissan",
    "Hyundai", "Kia", "Fiat", "Seat", "Skoda", "Volvo", "Mazda", "Mitsubishi",
    "Suzuki", "Dacia", "Opel", "Mini", "Land Rover", "Porsche", "Jeep",
    "Lexus", "Tesla", "Volkswagen", "Chevrolet", "Ducati", "Yamaha",
    "Kawasaki", "KTM",
]

def parse_brand_model(title):
    tl = title.lower()
    for brand in BRAND_LIST:
        if brand.lower() in tl:
            idx = tl.index(brand.lower())
            return brand, title[idx+len(brand):].strip()
    parts = title.split(maxsplit=1)
    return (parts[0], parts[1]) if len(parts)>=2 else (title, "")

def parse_listing(art):
    link = art.select_one('a[href*="/anuncio/"]')
    h2 = art.select_one("h2")
    if not (link and h2):
        return None
    href = link.get("href", "")
    if href.startswith("/"):
        href = "https://www.standvirtual.com" + href
    title = h2.get_text(strip=True)
    brand, model = parse_brand_model(title)
    h3 = art.select_one("h3")
    price = None
    if h3:
        pt = h3.get_text(strip=True).replace("\xa0", " ").replace(" ", "")
        nums = re.findall(r"\d+", pt)
        if nums:
            price = float(nums[0])
    if not price or price < 100:
        return None

    dl = art.select_one("dl")
    full = art.get_text(" ", strip=True)
    year = km = fuel = trans = hp = cc = None

    if dl:
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
            k = dt.get_text(strip=True).lower()
            v = dd.get_text(strip=True)
            if k == "first_registration_year":
                year = int(v) if v.isdigit() else None
            elif k == "mileage":
                cv = re.sub(r"[^\d]", "", v)
                km = int(cv) if cv else None
            elif k in ("fuel_type", "fuel"):
                for fk, fv in FUEL_MAP.items():
                    if fk in v.lower():
                        fuel = fv
                        break
            elif k in ("gearbox", "transmission"):
                for tk, tv in TRANS_MAP.items():
                    if tk in v.lower():
                        trans = tv
                        break

    # HP and CC from full text
    hp_m = re.search(r"(\d{2,3})\s*(?:cv|hp)", full, re.I)
    if hp_m and 10 < int(hp_m.group(1)) < 2000:
        hp = int(hp_m.group(1))
    cc_m = re.search(r"(\d{3,4})\s*cm3", full, re.I)
    if cc_m and 50 < int(cc_m.group(1)) < 10000:
        cc = int(cc_m.group(1))

    if not fuel:
        for fk, fv in FUEL_MAP.items():
            if fk in full.lower():
                fuel = fv
                break
    if not trans:
        for tk, tv in TRANS_MAP.items():
            if tk in full.lower():
                trans = tv
                break

    sid = hashlib.md5(href.encode()).hexdigest()
    return {
        "source": Source.STANDVIRTUAL, "source_id": sid, "url": href,
        "title": title, "brand": brand, "model": model,
        "price": price, "year": year, "km": km,
        "fuel_type": fuel, "transmission": trans,
        "horsepower": hp, "engine_size": cc, "vehicle_type": "carros",
    }

async def main():
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        all_listings = []
        for page in range(1, 21):
            r = await client.get(f"https://www.standvirtual.com/carros/?page={page}")
            soup = BeautifulSoup(r.text, "html.parser")
            for art in soup.select("article"):
                l = parse_listing(art)
                if l:
                    all_listings.append(l)
            print(f"p{page}: {len(all_listings)} total")
            await asyncio.sleep(0.3)

    saved = 0
    seen = set()
    with get_db_context() as db:
        for l in all_listings:
            k = (str(l["source"]), str(l["source_id"]))
            if k in seen:
                continue
            seen.add(k)
            existing = db.execute(
                select(Vehicle).where(Vehicle.source == l["source"], Vehicle.source_id == l["source_id"])
            ).scalar_one_or_none()
            if existing:
                if existing.price != l["price"]:
                    existing.price = l["price"]
                    existing.last_seen = datetime.now(timezone.utc)
            else:
                db.add(
                    Vehicle(
                        source=l["source"], source_id=l["source_id"], url=l["url"],
                        vehicle_type=VehicleType.carros, brand=l["brand"], model=l["model"],
                        year=l["year"], km=l["km"], price=l["price"], title=l["title"],
                        fuel_type=l["fuel_type"], transmission=l["transmission"],
                        horsepower=l["horsepower"], engine_size=l["engine_size"],
                        first_seen=datetime.now(timezone.utc),
                        last_seen=datetime.now(timezone.utc),
                    )
                )
                saved += 1
        db.commit()
    print(f"Saved: {saved} new vehicles")

asyncio.run(main())
