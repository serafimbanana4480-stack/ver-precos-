"""Extract HP, cc, fuel_type from vehicle descriptions in the database."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import re
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from database.db import get_db_context, init_db
from database.models import Vehicle, FuelType

init_db()

HP_PATTERNS = [
    re.compile(r"(\d{2,3})\s*(?:cv|cavalo|cavalos|hp|horsepower)", re.I),
    re.compile(r"pot[eê]ncia\w*\s*:?\s*(\d{2,3})", re.I),
    re.compile(r"(\d{2,3})\s*ch", re.I),
]

CC_PATTERNS = [
    re.compile(r"(\d{3,4})\s*cm3", re.I),
    re.compile(r"(\d{3,4})\s*cc", re.I),
    re.compile(r"(\d{1,2}[.,]\d)\s*l(?:itros?)?\b", re.I),
    re.compile(r"cilindrada\s*:?\s*(\d{3,4})", re.I),
]

FUEL_KEYWORDS = {
    "gasolina": FuelType.GASOLINE, "gasoline": FuelType.GASOLINE, "petrol": FuelType.GASOLINE,
    "diesel": FuelType.DIESEL, "gasoleo": FuelType.DIESEL, "gasoleo": FuelType.DIESEL,
    "eletrico": FuelType.ELECTRIC, "elétrico": FuelType.ELECTRIC, "electric": FuelType.ELECTRIC,
    "hibrido": FuelType.HYBRID, "híbrido": FuelType.HYBRID, "hybrid": FuelType.HYBRID,
    "plug-in": FuelType.HYBRID, "plug-in hybrid": FuelType.HYBRID,
    "gpl": FuelType.GPL, "gnv": FuelType.GPL,
}

with get_db_context() as db:
    vehicles = db.query(Vehicle).all()
    stats = {"hp_fixed": 0, "cc_fixed": 0, "fuel_fixed": 0}

    for v in vehicles:
        if not v.description:
            continue
        changed = False
        text = v.description

        # Extract HP
        if not v.horsepower:
            for pat in HP_PATTERNS:
                m = pat.search(text)
                if m:
                    val = int(m.group(1))
                    if 10 < val < 2000:
                        v.horsepower = val
                        stats["hp_fixed"] += 1
                        changed = True
                        break

        # Extract CC/engine size
        if not v.engine_size:
            for pat in CC_PATTERNS:
                m = pat.search(text)
                if m:
                    val = m.group(1).replace(",", ".")
                    if "." in val:
                        v.engine_size = int(float(val) * 1000)
                    else:
                        cc = int(val)
                        if 50 < cc < 10000:
                            v.engine_size = cc
                            stats["cc_fixed"] += 1
                            changed = True
                    if changed:
                        break

        # Extract fuel type
        if not v.fuel_type:
            text_lower = text.lower()
            for keyword, ft in FUEL_KEYWORDS.items():
                if keyword in text_lower:
                    v.fuel_type = ft
                    stats["fuel_fixed"] += 1
                    changed = True
                    break

        if changed:
            db.add(v)

    db.commit()

for k, v in stats.items():
    logger.info(f"{k}: {v}")

# Re-check
with get_db_context() as db:
    hp = db.query(Vehicle).filter(Vehicle.horsepower.isnot(None)).count()
    cc = db.query(Vehicle).filter(Vehicle.engine_size.isnot(None)).count()
    fuel = db.query(Vehicle).filter(Vehicle.fuel_type.isnot(None)).count()
    logger.info(f"\nAfter extraction: HP={hp}, CC={cc}, Fuel={fuel}")
