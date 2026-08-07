"""
Backfill de canonização marca/modelo nos anúncios existentes (Fase 14).

Aplica processing.model_canon.canon_listing a todos os anúncios ativos:
* extrai preço colado ao texto (modelo/título) quando o preço está em falta;
* limpa nº de lote AUTOLINE, sufixos MARTELO, preço colado AUTOPT;
* normaliza aliases de marca (VW → Volkswagen…);
* aplica a forma canónica do modelo da referência de mercado (conf ≥ 0.8).

Uso: PYTHONPATH=. python -u scripts/canonicalize_models.py [--apply]
Sem --apply corre em dry-run (mostra amostras e contagens).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_db_context
from database.models import Vehicle
from processing.model_canon import canon_listing

logger = logging.getLogger("canonicalize_models")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--sample", type=int, default=25)
    args = ap.parse_args()

    logging.basicConfig(level=logging.ERROR)

    stats = {"brand": 0, "model_cleaned": 0, "model_canonicalized": 0,
             "price_from_text": 0, "unchanged": 0}
    samples = []

    with get_db_context() as db:
        rows = db.query(Vehicle).filter(Vehicle.is_active == True).all()  # noqa: E712
        for v in rows:
            src = v.source.value if v.source else ""
            r = canon_listing(v.brand, v.model, v.title, v.price, src)
            changed = False
            if r["brand"] != v.brand:
                stats["brand"] += 1
                changed = True
            if r["model"] != (v.model or ""):
                if r["model_canonicalized"]:
                    stats["model_canonicalized"] += 1
                else:
                    stats["model_cleaned"] += 1
                changed = True
            if r["price_from_text"] and r["price"] and r["price"] != v.price:
                stats["price_from_text"] += 1
                changed = True
            if not changed:
                stats["unchanged"] += 1
                continue
            if len(samples) < args.sample:
                samples.append((src, v.brand, v.model, v.price,
                                r["brand"], r["model"], r["price"]))
            if args.apply:
                v.brand = r["brand"]
                v.model = r["model"]
                if r["price_from_text"] and r["price"]:
                    v.price = float(r["price"])
        if args.apply:
            db.commit()

    print(f"\n{'fonte':9} | ANTES → DEPOIS")
    print("-" * 100)
    for s in samples:
        print(f"{s[0]:9} | {s[1]} {str(s[2])[:32]!r} €{s[3]}  →  {s[4]} {str(s[5])[:32]!r} €{s[6]}")
    print("-" * 100)
    print(f"Marca normalizada:        {stats['brand']}")
    print(f"Modelo limpo (ruído):     {stats['model_cleaned']}")
    print(f"Modelo canonizado (ref):  {stats['model_canonicalized']}")
    print(f"Preço extraído do texto:  {stats['price_from_text']}")
    print(f"Sem alteração:            {stats['unchanged']}")
    if not args.apply:
        print("\nDry-run — passa --apply para gravar.")


if __name__ == "__main__":
    main()
