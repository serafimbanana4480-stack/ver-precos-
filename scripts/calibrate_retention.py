"""
Recalibra os fatores de retenção por modelo (segmentos 'desportivo' e 'premium')
contra os anúncios reais na BD — substitui os fatores manuais por medianas
observadas, com shrinkage para o valor anterior e clamps de segurança.

Método:
  implied_retention_i = price_i / (new_price * residual(age_i) * km_factor_i)
  retention_modelo    = mediana(implied) com shrinkage 50% para o fator anterior
  clamps: [0.70, 1.30] | mínimo de anúncios: MIN_N

Uso: PYTHONPATH=. python -u scripts/calibrate_retention.py [--segments desportivo,premium] [--min-n 5] [--apply]
Sem --apply corre em dry-run (só reporta).
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_db_context
from database.models import Vehicle
from valuation import market_reference as mr

logger = logging.getLogger("calibrate_retention")

REF_PATH = Path("data/market_reference_pt_2026.json")
CLAMP_LO, CLAMP_HI = 0.70, 1.30
CURRENT_YEAR = datetime.now(timezone.utc).year


def _val_str(val):
    return "unknown" if val is None else (val.value if hasattr(val, "value") else str(val))


def collect_implied_retentions() -> dict[str, list[float]]:
    """Agrupa retenções implícitas por chave de modelo da referência."""
    implied: dict[str, list[float]] = {}
    with get_db_context() as db:
        rows = db.query(Vehicle).filter(
            Vehicle.is_active == True,  # noqa: E712
            Vehicle.price > 500,
            Vehicle.price < 500000,
            Vehicle.year.isnot(None),
        ).all()
        for v in rows:
            entry, key, conf = mr.find_model_entry(v.brand, v.model)
            if not entry or conf < 0.8 or not key:
                continue
            new_price = float(entry.get("new_price") or 0)
            if new_price <= 0:
                continue
            age = max(0, CURRENT_YEAR - int(v.year))
            residual = mr.residual_factor(entry.get("segment", "media"), age)
            fuel = mr._norm(_val_str(v.fuel_type)) or "gasolina"
            is_moto = str(_val_str(v.vehicle_type)).startswith("moto")
            km_factor, _ = mr._km_correction(v.km, age, fuel, is_moto)
            base = new_price * residual * km_factor
            if base <= 0:
                continue
            r = float(v.price) / base
            if 0.3 <= r <= 2.0:  # descarta outliers grosseiros (mensalidades, erros)
                implied.setdefault(key, []).append(r)
    return implied


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", default="desportivo,premium")
    ap.add_argument("--min-n", type=int, default=5)
    ap.add_argument("--apply", action="store_true", help="Escreve as alterações no JSON")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    segments = {s.strip() for s in args.segments.split(",") if s.strip()}

    ref = json.loads(REF_PATH.read_text(encoding="utf-8"))
    models = ref.get("models", {})
    implied = collect_implied_retentions()

    print(f"\n{'modelo':40} {'seg':11} {'n':>4} {'old':>6} {'data':>6} {'new':>6}")
    print("-" * 80)
    changed, skipped_low_n = 0, 0
    for key, entry in sorted(models.items()):
        if entry.get("segment") not in segments:
            continue
        obs = implied.get(key, [])
        if len(obs) < args.min_n:
            skipped_low_n += 1
            continue
        old = float(entry.get("retention", 1.0))
        data_med = median(obs)
        # shrinkage 50%: evita saltos bruscos com poucos dados
        new = round(min(CLAMP_HI, max(CLAMP_LO, 0.5 * old + 0.5 * data_med)), 3)
        marker = " *" if abs(new - old) >= 0.02 else ""
        print(f"{key:40} {entry.get('segment','?'):11} {len(obs):>4} "
              f"{old:>6.2f} {data_med:>6.2f} {new:>6.2f}{marker}")
        if new != old:
            entry["retention"] = new
            changed += 1

    print("-" * 80)
    print(f"Modelos recalibrados: {changed} | sem volume suficiente: {skipped_low_n}")

    if args.apply and changed:
        backup = REF_PATH.with_suffix(f".backup_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.json")
        shutil.copy2(REF_PATH, backup)
        ref.setdefault("_meta", {})["retention_calibrated_at"] = datetime.now(timezone.utc).isoformat()
        ref["_meta"]["retention_calibration"] = {
            "segments": sorted(segments), "min_n": args.min_n,
            "method": "median implied retention, 50% shrinkage, clamp [0.70, 1.30]",
        }
        REF_PATH.write_text(json.dumps(ref, indent=2, ensure_ascii=False), encoding="utf-8")
        mr.reload_reference()
        print(f"Guardado em {REF_PATH} (backup: {backup.name})")
    elif not args.apply:
        print("Dry-run — passa --apply para gravar.")


if __name__ == "__main__":
    main()
