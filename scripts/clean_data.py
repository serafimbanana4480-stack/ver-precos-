"""Clean dirty data in the database: fix prices, brands, remove non-vehicles."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from database.db import get_db_context, init_db
from database.models import Vehicle, FuelType, Transmission
from scrapers.base import BRANDS

init_db()

with get_db_context() as db:
    vehicles = db.query(Vehicle).all()
    stats = {"fixed_brand": 0, "fixed_price": 0, "deactivated": 0, "fixed_fuel": 0, "fixed_trans": 0}

    brand_lower = {b.lower(): b for b in BRANDS}
    brand_lower.update({
        "vw": "Volkswagen", "mb": "Mercedes-Benz", "mercedes benz": "Mercedes-Benz",
        "mercedes-benz": "Mercedes-Benz", "land rover": "Land Rover",
        "alfa romeo": "Alfa Romeo", "opel": "Opel", "toyota": "Toyota",
        "hyundai": "Hyundai", "kia": "Kia", "mitsubishi": "Mitsubishi",
        "suzuki": "Suzuki", "dacia": "Dacia", "mazda": "Mazda", "seat": "Seat",
        "skoda": "Skoda", "fiat": "Fiat", "citroen": "Citroen",
        "peugeot": "Peugeot", "renault": "Renault", "audi": "Audi",
        "bmw": "BMW", "mercedes": "Mercedes-Benz", "nissan": "Nissan",
        "volkswagen": "Volkswagen", "volvo": "Volvo", "ford": "Ford",
        "honda": "Honda", "yamaha": "Yamaha", "kawasaki": "Kawasaki",
        "ducati": "Ducati", "ktm": "KTM", "aprilia": "Aprilia",
        "triumph": "Triumph", "harley": "Harley Davidson",
        "harley davidson": "Harley Davidson", "husqvarna": "Husqvarna",
        "beta": "Beta", "gas gas": "Gas Gas", "jeep": "Jeep",
        "porsche": "Porsche", "jaguar": "Jaguar", "landrover": "Land Rover",
        "lexus": "Lexus", "subaru": "Subaru", "tesla": "Tesla",
        "polestar": "Polestar", "mini": "Mini", "smart": "Smart",
        "chevrolet": "Chevrolet", "dodge": "Dodge", "chrysler": "Chrysler",
        "ferrari": "Ferrari", "lamborghini": "Lamborghini",
        "maserati": "Maserati", "bentley": "Bentley", "rolls royce": "Rolls Royce",
    })

    fuel_map = {
        "gasolina": FuelType.GASOLINE, "gasoline": FuelType.GASOLINE, "petrol": FuelType.GASOLINE,
        "diesel": FuelType.DIESEL, "gasoleo": FuelType.DIESEL, "gasóleo": FuelType.DIESEL,
        "eletrico": FuelType.ELECTRIC, "elétrico": FuelType.ELECTRIC, "electric": FuelType.ELECTRIC,
        "hibrido": FuelType.HYBRID, "híbrido": FuelType.HYBRID, "hybrid": FuelType.HYBRID,
        "gpl": FuelType.GPL, "gas natural": FuelType.GAS,
    }

    trans_map = {
        "manual": Transmission.MANUAL,
        "automatico": Transmission.AUTOMATIC, "automático": Transmission.AUTOMATIC,
        "automatic": Transmission.AUTOMATIC, "auto": Transmission.AUTOMATIC,
        "semi-automatico": Transmission.SEMI_AUTOMATIC, "semi-automático": Transmission.SEMI_AUTOMATIC,
    }

    for v in vehicles:
        changed = False

        # Fix brand
        if v.brand and v.brand not in BRANDS and v.brand != "Unknown":
            bl = v.brand.lower().strip()
            if bl in brand_lower:
                v.brand = brand_lower[bl]
                changed = True
                stats["fixed_brand"] += 1

        # Fix Unknown brand from title
        if v.brand == "Unknown" and v.title:
            t = v.title.lower()
            for bl, canonical in sorted(brand_lower.items(), key=lambda x: -len(x[0])):
                if bl in t:
                    v.brand = canonical
                    changed = True
                    stats["fixed_brand"] += 1
                    break

        # Fix EUR 1 prices (non-vehicle or placeholder)
        if v.price and v.price < 100:
            old_price = v.price
            if v.title and "peças" not in v.title.lower() and "pecas" not in v.title.lower():
                v.is_active = False
                stats["deactivated"] += 1
                changed = True
                logger.info(f"Deactivated EUR{v.price:.0f} vehicle: {v.id} {v.title[:60]}")

        # Fix fuel_type from description if missing
        if v.fuel_type is None and v.description:
            desc = v.description.lower()
            for key, ft in fuel_map.items():
                if key in desc:
                    v.fuel_type = ft
                    changed = True
                    stats["fixed_fuel"] += 1
                    break

        # Fix transmission from description if missing
        if v.transmission is None and v.description:
            desc = v.description.lower()
            for key, tr in trans_map.items():
                if key in desc:
                    v.transmission = tr
                    changed = True
                    stats["fixed_trans"] += 1
                    break

        if changed:
            db.add(v)

    db.commit()

for k, v in stats.items():
    logger.info(f"{k}: {v}")

# Now deduplicate: merge vehicles with same URL or same source+source_id
logger.info("\n=== DEDUPLICATING ===")
with get_db_context() as db:
    from sqlalchemy import func
    # URL-based duplicates
    dup_urls = db.query(Vehicle.url, func.count(Vehicle.id)).group_by(Vehicle.url).having(func.count(Vehicle.id) > 1).all()
    for url, cnt in dup_urls:
        vehicles = db.query(Vehicle).filter(Vehicle.url == url).order_by(Vehicle.id).all()
        keeper = vehicles[0]
        for dup in vehicles[1:]:
            logger.info(f"Merging {dup.id} into {keeper.id} (same URL)")
            db.delete(dup)
        db.commit()

    # Source+source_id duplicates
    dup_src = db.query(Vehicle.source, Vehicle.source_id, func.count(Vehicle.id)).group_by(Vehicle.source, Vehicle.source_id).having(func.count(Vehicle.id) > 1).all()
    for src, sid, cnt in dup_src:
        vehicles = db.query(Vehicle).filter(Vehicle.source == src, Vehicle.source_id == sid).order_by(Vehicle.id).all()
        keeper = vehicles[0]
        for dup in vehicles[1:]:
            logger.info(f"Merging {dup.id} into {keeper.id} (same source+source_id)")
            db.delete(dup)
        db.commit()

total = db.query(Vehicle).count()
active = db.query(Vehicle).filter(Vehicle.is_active == True).count()
logger.info(f"\nFinal: {total} total, {active} active")
