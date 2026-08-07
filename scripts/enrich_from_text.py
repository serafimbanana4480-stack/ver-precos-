"""
Backfill de especificações a partir do texto (Fase 15).

Para anúncios ativos com campos em falta, extrai ano/km/cv/combustível/
transmissão do título + modelo via processing.text_enrich e preenche APENAS
os campos vazios (nunca sobrescreve dados existentes).

Uso: PYTHONPATH=. python -u scripts/enrich_from_text.py [--apply]
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_db_context
from database.models import Vehicle, FuelType, Transmission
from processing.text_enrich import extract_specs

logger = logging.getLogger("enrich_from_text")

_FUEL = {f.value: f for f in FuelType}
_TRANS = {t.value: t for t in Transmission}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.ERROR)
    filled = Counter()
    samples = []

    with get_db_context() as db:
        rows = db.query(Vehicle).filter(Vehicle.is_active == True).all()  # noqa: E712
        for v in rows:
            if v.year and v.km and v.fuel_type and v.transmission and v.horsepower:
                continue
            text = f"{v.title or ''} {v.model or ''}"
            specs = extract_specs(text)
            if not specs:
                continue
            changed = []
            if not v.year and specs.get("year"):
                if args.apply:
                    v.year = specs["year"]
                changed.append(f"year={specs['year']}")
                filled["year"] += 1
            if (not v.km or v.km == 0) and specs.get("km"):
                if args.apply:
                    v.km = specs["km"]
                changed.append(f"km={specs['km']}")
                filled["km"] += 1
            if not v.horsepower and specs.get("horsepower"):
                if args.apply:
                    v.horsepower = specs["horsepower"]
                changed.append(f"cv={specs['horsepower']}")
                filled["horsepower"] += 1
            if v.fuel_type is None and specs.get("fuel_type") in _FUEL:
                if args.apply:
                    v.fuel_type = _FUEL[specs["fuel_type"]]
                changed.append(f"fuel={specs['fuel_type']}")
                filled["fuel_type"] += 1
            if v.transmission is None and specs.get("transmission") in _TRANS:
                if args.apply:
                    v.transmission = _TRANS[specs["transmission"]]
                changed.append(f"trans={specs['transmission']}")
                filled["transmission"] += 1
            if changed and len(samples) < 15:
                src = v.source.value if v.source else "?"
                samples.append(f"[{src}] {v.brand} {v.model} → {', '.join(changed)}")
        if args.apply:
            db.commit()

    print("\n".join(samples))
    print("-" * 70)
    print(f"Campos preenchidos: {dict(filled)}")
    print(f"Total: {sum(filled.values())} campos em anúncios existentes")
    if not args.apply:
        print("Dry-run — passa --apply para gravar.")


if __name__ == "__main__":
    main()
