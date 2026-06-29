"""Mass scraping script - runs all available scrapers and saves to DB."""
import sys, os, asyncio, logging, time, re, hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("mass_scrape")

import httpx
from bs4 import BeautifulSoup
from database.db import get_db_context, init_db
from database.models import Vehicle, Source, FuelType, Transmission
from sqlalchemy import select

init_db()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}

BRAND_MAP = {
    "vw": "Volkswagen", "mercedes": "Mercedes-Benz", "mercedes-benz": "Mercedes-Benz",
    "bmw": "BMW", "audi": "Audi", "peugeot": "Peugeot", "renault": "Renault",
    "citroen": "Citroën", "ford": "Ford", "toyota": "Toyota", "honda": "Honda",
    "nissan": "Nissan", "hyundai": "Hyundai", "kia": "Kia", "fiat": "Fiat",
    "seat": "Seat", "skoda": "Skoda", "volvo": "Volvo", "mazda": "Mazda",
    "mitsubishi": "Mitsubishi", "suzuki": "Suzuki", "dacia": "Dacia",
    "opel": "Opel", "alfa romeo": "Alfa Romeo", "mini": "Mini", "smart": "Smart",
    "land rover": "Land Rover", "jeep": "Jeep", "porsche": "Porsche",
    "jaguar": "Jaguar", "lexus": "Lexus", "subaru": "Subaru", "tesla": "Tesla",
    "yamaha": "Yamaha", "kawasaki": "Kawasaki", "ducati": "Ducati", "ktm": "KTM",
    "triumph": "Triumph", "harley davidson": "Harley-Davidson",
    "harley-davidson": "Harley-Davidson", "husqvarna": "Husqvarna",
    "aprilia": "Aprilia", "beta": "Beta", "piaggio": "Piaggio",
    "sym": "SYM", "keeway": "Keeway", "benelli": "Benelli", "zontes": "Zontes",
    "cf moto": "CFMoto", "polestar": "Polestar", "byd": "BYD", "mg": "MG",
    "chevrolet": "Chevrolet", "dodge": "Dodge", "ferrari": "Ferrari",
    "lamborghini": "Lamborghini", "maserati": "Maserati", "bentley": "Bentley",
    "abarth": "Abarth", "ds": "DS", "isuzu": "Isuzu", "iveco": "Iveco",
    "ligier": "Ligier",
}

FUEL_MAP = {
    "gasolina": FuelType.GASOLINE, "gasoline": FuelType.GASOLINE,
    "diesel": FuelType.DIESEL, "gazoleo": FuelType.DIESEL,
    "eletrico": FuelType.ELECTRIC, "elétrico": FuelType.ELECTRIC,
    "hibrido": FuelType.HYBRID, "híbrido": FuelType.HYBRID,
    "gpl": FuelType.GPL,
}

TRANS_MAP = {
    "manual": Transmission.MANUAL,
    "automatico": Transmission.AUTOMATIC, "automático": Transmission.AUTOMATIC,
    "automatic": Transmission.AUTOMATIC,
    "semi-automatico": Transmission.SEMI_AUTOMATIC,
}


def parse_brand(title):
    if not title:
        return "Unknown", title
    tl = title.lower()
    for bl, canonical in sorted(BRAND_MAP.items(), key=lambda x: -len(x[0])):
        if bl in tl:
            idx = tl.find(bl)
            model = title[idx + len(bl):].strip()
            return canonical, model
    parts = title.split(maxsplit=1)
    return (parts[0], parts[1]) if len(parts) >= 2 else (title, "")


def parse_price(text):
    nums = re.findall(r"[\d.,]+", text.replace(",", "."))
    if nums:
        try:
            return float(nums[0])
        except ValueError:
            return 0.0
    return 0.0


def parse_km(text):
    m = re.search(r"([\d\s.]+)\s*km", text, re.I)
    if m:
        return int(m.group(1).replace(" ", "").replace(".", ""))
    return None


def parse_year(text):
    m = re.search(r"\b(19[4-9]\d|20[0-3]\d)\b", text)
    return int(m.group(1)) if m else None


def extract_hp(text):
    for pat in [r"(\d{2,3})\s*(?:cv|hp|cavalo)", r"pot[eê]ncia\w*\s*:?\s*(\d{2,3})"]:
        m = re.search(pat, text, re.I)
        if m and 10 < int(m.group(1)) < 2000:
            return int(m.group(1))
    return None


def extract_cc(text):
    for pat in [r"(\d{3,4})\s*cm3", r"(\d{3,4})\s*cc", r"(\d[.,]\d)\s*l(?:itros?)?"]:
        m = re.search(pat, text, re.I)
        if m:
            val = m.group(1).replace(",", ".")
            if "." in val:
                return int(float(val) * 1000)
            cc = int(val)
            if 50 < cc < 10000:
                return cc
    return None


async def scrape_standvirtual(max_listings=150):
    listings = []
    base = "https://www.standvirtual.com"
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for page in range(1, 11):
            if len(listings) >= max_listings:
                break
            url = f"{base}/carros/?page={page}"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("article")
                if not cards:
                    break
                for card in cards[:max_listings - len(listings)]:
                    try:
                        link = card.select_one("a[href]")
                        if not link:
                            continue
                        href = link.get("href", "")
                        if href.startswith("/"):
                            href = base + href
                        title_el = card.select_one("h2, h3, a")
                        title = title_el.get_text(strip=True) if title_el else ""
                        if not title or len(title) < 5:
                            continue
                        price_el = card.select_one("[class*='price'], h3")
                        price = parse_price(price_el.get_text(strip=True)) if price_el else 0
                        if price < 100:
                            continue
                        text = card.get_text(" ", strip=True).lower()
                        year = parse_year(text)
                        km = parse_km(text)
                        hp = extract_hp(text)
                        cc = extract_cc(text)
                        fuel = None
                        for k, v in FUEL_MAP.items():
                            if k in text:
                                fuel = v
                                break
                        trans = None
                        for k, v in TRANS_MAP.items():
                            if k in text:
                                trans = v
                                break
                        loc_el = card.select_one("[class*='location'], .location")
                        location = loc_el.get_text(strip=True) if loc_el else ""
                        brand, model = parse_brand(title)
                        sid = hashlib.md5(href.encode()).hexdigest()
                        listings.append({
                            "source": "STANDVIRTUAL", "source_id": sid, "url": href,
                            "title": title, "brand": brand, "model": model,
                            "price": price, "year": year, "km": km,
                            "horsepower": hp, "engine_size": cc,
                            "fuel_type": fuel, "transmission": trans,
                            "location": location, "vehicle_type": "carros",
                        })
                    except Exception:
                        pass
                logger.info(f"Standvirtual p{page}: {len(listings)} total")
                if len(cards) < 20:
                    break
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Standvirtual p{page}: {e}")
                break
    return listings


async def scrape_autosapo(max_listings=100):
    listings = []
    base = "https://www.autosapo.pt"
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for page in range(1, 11):
            if len(listings) >= max_listings:
                break
            url = f"{base}/carros?page={page}"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("article, div[class*='card'], div[class*='listing'], div[class*='vehicle'], div[class*='ad']")
                if not cards:
                    break
                for card in cards[:max_listings - len(listings)]:
                    try:
                        link = card.select_one("a[href]")
                        if not link:
                            continue
                        href = link.get("href", "")
                        if href.startswith("/"):
                            href = base + href
                        title = link.get_text(strip=True) or ""
                        if not title or len(title) < 5:
                            continue
                        price_el = card.select_one("[class*='price'], .price")
                        price = parse_price(price_el.get_text(strip=True)) if price_el else 0
                        if price < 100:
                            continue
                        text = card.get_text(" ", strip=True).lower()
                        year = parse_year(text)
                        km = parse_km(text)
                        hp = extract_hp(text)
                        cc = extract_cc(text)
                        fuel = None
                        for k, v in FUEL_MAP.items():
                            if k in text:
                                fuel = v
                                break
                        brand, model = parse_brand(title)
                        sid = hashlib.md5(href.encode()).hexdigest()
                        listings.append({
                            "source": "AUTOSAPO", "source_id": sid, "url": href,
                            "title": title, "brand": brand, "model": model,
                            "price": price, "year": year, "km": km,
                            "horsepower": hp, "engine_size": cc,
                            "fuel_type": fuel, "transmission": None,
                            "location": "", "vehicle_type": "carros",
                        })
                    except Exception:
                        pass
                logger.info(f"AutoSapo p{page}: {len(listings)} total")
                if len(cards) < 20:
                    break
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"AutoSapo p{page}: {e}")
                break
    return listings


async def scrape_custojusto(max_listings=100):
    listings = []
    base = "https://www.custojusto.pt"
    urls = [f"{base}/veiculos/carros", f"{base}/carros", f"{base}/portugal/carros"]
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for url in urls:
            if len(listings) >= max_listings:
                break
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("article, div[class*='card'], div[class*='listing'], li[class*='item']")
                if not cards:
                    continue
                for card in cards[:max_listings - len(listings)]:
                    try:
                        link = card.select_one("a[href]")
                        if not link:
                            continue
                        href = link.get("href", "")
                        if href.startswith("/"):
                            href = base + href
                        title = link.get_text(strip=True) or ""
                        if not title or len(title) < 5:
                            continue
                        price_el = card.select_one("[class*='price'], .price")
                        price = parse_price(price_el.get_text(strip=True)) if price_el else 0
                        if price < 100:
                            continue
                        text = card.get_text(" ", strip=True).lower()
                        year = parse_year(text)
                        km = parse_km(text)
                        fuel = None
                        for k, v in FUEL_MAP.items():
                            if k in text:
                                fuel = v
                                break
                        brand, model = parse_brand(title)
                        sid = hashlib.md5(href.encode()).hexdigest()
                        listings.append({
                            "source": "CUSTOJUSTO", "source_id": sid, "url": href,
                            "title": title, "brand": brand, "model": model,
                            "price": price, "year": year, "km": km,
                            "fuel_type": fuel, "vehicle_type": "carros",
                        })
                    except Exception:
                        pass
                logger.info(f"CustoJusto {url}: {len(listings)} total")
                if len(cards) >= 20:
                    break
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"CustoJusto {url}: {e}")
    return listings


async def scrape_olx_api(max_listings=100):
    listings = []
    base = "https://www.olx.pt"
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for page in range(1, 11):
            if len(listings) >= max_listings:
                break
            for url in [f"{base}/api/v1/offers/?category_id=378&page={page}&limit=40",
                        f"{base}/api/v2/offers/?category_id=378&page={page}"]:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    offers = data.get("data", [])
                    if isinstance(offers, dict):
                        offers = offers.get("offers", [])
                    if not offers:
                        break
                    for offer in offers[:max_listings - len(listings)]:
                        try:
                            title = offer.get("title", "")
                            o_url = offer.get("url", f"{base}/item/{offer.get('id', '')}")
                            p_data = offer.get("price", {})
                            price = float(p_data.get("value", 0) if isinstance(p_data, dict) else p_data)
                            if price < 100:
                                continue
                            params = offer.get("params", [])
                            year = km = fuel = trans = None
                            if isinstance(params, list):
                                for p in params:
                                    key = p.get("key", "")
                                    val = str(p.get("value", ""))
                                    if key in ("year", "ano"):
                                        year = parse_year(val)
                                    elif key in ("mileage", "km"):
                                        km = parse_km(val + " km")
                                    elif key in ("fuel", "combustivel"):
                                        for k, v in FUEL_MAP.items():
                                            if k in val.lower():
                                                fuel = v
                                                break
                                    elif key in ("transmission", "caixa"):
                                        for k, v in TRANS_MAP.items():
                                            if k in val.lower():
                                                trans = v
                                                break
                            loc_data = offer.get("location", {})
                            location = loc_data.get("city", "") if isinstance(loc_data, dict) else ""
                            desc = offer.get("description", "")
                            hp = extract_hp(desc) if desc else None
                            cc = extract_cc(desc) if desc else None
                            brand, model = parse_brand(title)
                            sid = str(offer.get("id", hashlib.md5(o_url.encode()).hexdigest()))
                            listings.append({
                                "source": "OLX", "source_id": sid, "url": o_url,
                                "title": title, "brand": brand, "model": model,
                                "price": price, "year": year, "km": km,
                                "horsepower": hp, "engine_size": cc,
                                "fuel_type": fuel, "transmission": trans,
                                "location": str(location), "vehicle_type": "carros",
                                "description": str(desc)[:2000] if desc else "",
                            })
                        except Exception:
                            pass
                    logger.info(f"OLX API p{page}: {len(listings)} total")
                    break
                except Exception as e:
                    logger.debug(f"OLX API {url}: {e}")
                    continue
            if len(listings) < (page - 1) * 40:
                break
            await asyncio.sleep(2)
    return listings


def save_listings(listings):
    saved = 0
    updated = 0
    with get_db_context() as db:
        for l in listings:
            sid = str(l.get("source_id", ""))
            if not sid:
                continue
            try:
                src = Source(l["source"])
            except (ValueError, KeyError):
                continue
            existing = db.execute(
                select(Vehicle).where(Vehicle.source == src, Vehicle.source_id == sid)
            ).scalar_one_or_none()
            if existing:
                new_price = float(l.get("price", 0))
                if new_price > 0 and existing.price != new_price:
                    existing.price = new_price
                    existing.last_seen = datetime.now(timezone.utc)
                    existing.scrape_count = (existing.scrape_count or 1) + 1
                    updated += 1
                for field in ["horsepower", "engine_size", "fuel_type", "transmission", "km", "year"]:
                    val = l.get(field)
                    if val and not getattr(existing, field, None):
                        setattr(existing, field, val)
                        updated += 1
            else:
                v = Vehicle(
                    source=src, source_id=sid,
                    url=str(l.get("url", "")),
                    vehicle_type=l.get("vehicle_type", "carros"),
                    brand=str(l.get("brand", "Unknown")),
                    model=str(l.get("model", "Unknown")),
                    year=l.get("year"), km=l.get("km"),
                    price=float(l.get("price", 0)),
                    title=str(l.get("title", "")),
                    location=str(l.get("location", "")),
                    fuel_type=l.get("fuel_type"), transmission=l.get("transmission"),
                    horsepower=l.get("horsepower"), engine_size=l.get("engine_size"),
                    description=str(l.get("description", ""))[:2000] if l.get("description") else None,
                    first_seen=datetime.now(timezone.utc),
                    last_seen=datetime.now(timezone.utc),
                )
                db.add(v)
                saved += 1
        db.commit()
    logger.info(f"Saved: {saved} new, {updated} updated")
    return saved


async def main():
    logger.info("=" * 60)
    logger.info("MASS SCRAPING SESSION")
    logger.info("=" * 60)
    start = time.time()
    all_listings = []
    
    tasks = [
        ("Standvirtual", scrape_standvirtual(200)),
        ("AutoSapo", scrape_autosapo(150)),
        ("CustoJusto", scrape_custojusto(150)),
        ("OLX_API", scrape_olx_api(150)),
    ]
    
    results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
    
    for (name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error(f"{name} FAILED: {result}")
        elif isinstance(result, list):
            logger.info(f"{name}: {len(result)} listings")
            all_listings.extend(result)
    
    logger.info(f"Total collected: {len(all_listings)} listings")
    
    if all_listings:
        saved = save_listings(all_listings)
    
    elapsed = time.time() - start
    logger.info(f"Time: {elapsed:.1f}s")
    
    with get_db_context() as db:
        total = db.query(Vehicle).count()
        active = db.query(Vehicle).filter(Vehicle.is_active == True).count()
        logger.info(f"Database: {total} total, {active} active")


if __name__ == "__main__":
    asyncio.run(main())
