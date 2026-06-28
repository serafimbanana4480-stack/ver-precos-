"""Comprehensive brand normalization for all vehicles."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from database.db import get_db_context, init_db
from database.models import Vehicle

BRAND_MAP = {
    "vw": "Volkswagen", "mb": "Mercedes-Benz",
    "mercedes benz": "Mercedes-Benz", "mercedes-benz": "Mercedes-Benz",
    "mercedes": "Mercedes-Benz", "alfa romeo": "Alfa Romeo",
    "alfa": "Alfa Romeo", "land rover": "Land Rover", "land": "Land Rover",
    "range rover": "Land Rover", "range": "Land Rover",
    "citroen": "Citroën", "citroën": "Citroën",
    "harley davidson": "Harley-Davidson", "harley-davidson": "Harley-Davidson",
    "harley": "Harley-Davidson",
    "suzuki": "Suzuki", "susuki": "Suzuki",
    "kawasaki": "Kawasaki", "kawazak": "Kawasaki",
    "yamaha": "Yamaha", "ducati": "Ducati",
    "ktm": "KTM", "aprilia": "Aprilia",
    "triumph": "Triumph", "husqvarna": "Husqvarna",
    "beta": "Beta", "gas gas": "Gas Gas",
    "bmw": "BMW", "audi": "Audi",
    "porsche": "Porsche", "jaguar": "Jaguar",
    "lexus": "Lexus", "subaru": "Subaru",
    "tesla": "Tesla", "polestar": "Polestar",
    "mini": "Mini", "smart": "Smart",
    "chevrolet": "Chevrolet", "dodge": "Dodge",
    "ferrari": "Ferrari", "lamborghini": "Lamborghini",
    "maserati": "Maserati", "bentley": "Bentley",
    "fiat": "Fiat", "ford": "Ford",
    "honda": "Honda", "hyundai": "Hyundai",
    "kia": "Kia", "mazda": "Mazda",
    "mitsubishi": "Mitsubishi", "nissan": "Nissan",
    "opel": "Opel", "peugeot": "Peugeot",
    "renault": "Renault", "seat": "Seat",
    "skoda": "Skoda", "toyota": "Toyota",
    "volvo": "Volvo", "dacia": "Dacia",
    "jeep": "Jeep", "abarth": "Abarth",
    "ds": "DS", "byd": "BYD",
    "mg": "MG", "iveco": "Iveco",
    "isuzu": "Isuzu", "rover": "Rover",
    "ligier": "Ligier", "xping": "Xpeng",
    "xpeng": "Xpeng", "aion": "Aion",
    "benda": "Benda", "benelli": "Benelli",
    "qjmotor": "QJMotor", "zontes": "Zontes",
    "sym": "SYM", "sherco": "Sherco",
    "tm": "TM Racing", "mv": "MV Agusta",
    "keeway": "Keeway", "piaggio": "Piaggio",
    "seaway": "Segway", "segway": "Segway",
    "cf moto": "CFMoto", "cf": "CFMoto",
    "moto": "Mota", "mota": "Mota",
}

# Non-vehicle patterns that should be deactivated
NON_VEHICLE_KEYWORDS = [
    "pecas", "peças", "acessorio", "acessório", "ferramenta", "tool",
    "bateria", "pneu", "jante", "oleo", "óleo", "filtro",
    "troca", "vendo pecas", "compro", "precisa-se",
]

init_db()

with get_db_context() as db:
    vehicles = db.query(Vehicle).all()
    fixed = 0
    deactivated = 0

    for v in vehicles:
        changed = False

        # Normalize brand
        bl = v.brand.strip().lower() if v.brand else ""
        if bl in BRAND_MAP:
            v.brand = BRAND_MAP[bl]
            changed = True
        elif v.brand not in BRAND_MAP.values() and v.brand != "Unknown" and v.title:
            t = v.title.lower()
            for key, canonical in sorted(BRAND_MAP.items(), key=lambda x: -len(x[0])):
                if key in t:
                    v.brand = canonical
                    changed = True
                    break

        # Fix model from title if missing
        if v.model in ("Unknown", "unknown", "") and v.title:
            parts = v.title.split(maxsplit=1)
            if len(parts) > 1:
                v.model = parts[1][:100]
                changed = True

        # Deactivate non-vehicles
        if v.title:
            t = v.title.lower()
            if any(kw in t for kw in NON_VEHICLE_KEYWORDS):
                v.is_active = False
                v.brand = v.brand or "Unknown"
                deactivated += 1
                changed = True
                logger.info(f"DEACTIVATED non-vehicle: {v.title[:60]}")

        if changed:
            db.add(v)
            fixed += 1

    db.commit()
    active = db.query(Vehicle).filter(Vehicle.is_active == True).count()
    unknown = db.query(Vehicle).filter(Vehicle.brand == "Unknown").count()
    logger.info(f"Fixed: {fixed} | Deactivated non-vehicles: {deactivated} | Active: {active} | Unknown brands: {unknown}")

    brands = db.query(Vehicle.brand).distinct().order_by(Vehicle.brand).all()
    logger.info(f"Unique brands: {len(brands)}")
