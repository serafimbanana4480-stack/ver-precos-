"""Mede MAPE por faixa via PricePredictor (ANTES ou DEPOIS consoante o modelo em disco).
Uso: python scripts/_measure_map.py <antes|depois> [out.json]
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from sklearn.metrics import mean_absolute_percentage_error, mean_absolute_error, r2_score
from core.settings import settings
from valuation.predict import PricePredictor
from database.db import get_db_context
from database.models import Vehicle, VehicleType

AUCTION = {"LEILOSOC","VPAUTO","MANHEIM","AUTOROLA","BCA","MARTELO","AUTOLINE","PENHORADO"}

phase = sys.argv[1] if len(sys.argv) > 1 else "antes"
out_path = sys.argv[2] if len(sys.argv) > 2 else None

pp = PricePredictor("carros")
print(f"[phase={phase}] modelo={pp.model_name} LOW={pp.low_model is not None} thr={pp.low_threshold} "
      f"features={len(pp.feature_names)}")

with get_db_context() as db:
    rows = db.query(Vehicle).filter(
        Vehicle.vehicle_type == VehicleType("carros"),
        Vehicle.price.isnot(None), Vehicle.price > 500, Vehicle.price < 500000,
        Vehicle.year.isnot(None), Vehicle.km.isnot(None), Vehicle.km > 0,
    ).all()
    recs = []
    for v in rows:
        if (v.source.value if v.source else "") in AUCTION:
            continue
        recs.append({
            "brand": v.brand, "model": v.model, "year": int(v.year),
            "km": int(v.km or 0), "horsepower": v.horsepower,
            "engine_size": v.engine_size, "doors": v.doors,
            "fuel_type": v.fuel_type.value if v.fuel_type else "unknown",
            "transmission": v.transmission.value if v.transmission else "unknown",
            "location": v.location or "", "district": v.district or "",
            "price": float(v.price),
        })

yt, yp = [], []
extreme_examples = []
for r in recs:
    data = {k: r[k] for k in ("year","km","horsepower","engine_size","doors",
                              "fuel_type","transmission","brand","model","location","district")}
    pred = pp.predict(data)
    if pred is None or pred <= 0:
        continue
    yt.append(r["price"]); yp.append(pred)
    if r["price"] < 3000 and 240000 <= r["km"] <= 285000:
        extreme_examples.append({"brand": r["brand"], "model": r["model"], "year": r["year"],
                                  "km": r["km"], "fuel_type": r["fuel_type"],
                                  "transmission": r["transmission"], "price": r["price"], "pred": pred})

yt = np.array(yt); yp = np.array(yp)

def mape_mask(mask):
    if mask.sum() < 1:
        return None
    return float(mean_absolute_percentage_error(yt[mask], yp[mask]) * 100)

f_lt3k = yt < 3000
f_3_5k = (yt >= 3000) & (yt < 5000)
f_5_10k = (yt >= 5000) & (yt < 10000)
f_10_20k = (yt >= 10000) & (yt < 20000)

res = {
    "phase": phase,
    "n": int(len(yt)),
    "global_mape": mape_mask(np.ones(len(yt), bool)),
    "lt3k_mape": mape_mask(f_lt3k),
    "lt3k_n": int(f_lt3k.sum()),
    "3_5k_mape": mape_mask(f_3_5k),
    "3_5k_n": int(f_3_5k.sum()),
    "5_10k_mape": mape_mask(f_5_10k),
    "10_20k_mape": mape_mask(f_10_20k),
    "extreme_examples": extreme_examples[:5],
}
print(json.dumps(res, indent=2))
if out_path:
    with open(out_path, "w") as f:
        json.dump(res, f, indent=2)
