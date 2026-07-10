"""Diagnóstico: quantos <3k são servidos pelo LOW vs FULL no routing two-stage."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from core.settings import settings
from valuation.predict import PricePredictor
from database.db import get_db_context
from database.models import Vehicle, VehicleType

AUCTION = {"LEILOSOC","VPAUTO","MANHEIM","AUTOROLA","BCA","MARTELO","AUTOLINE","PENHORADO"}
pp = PricePredictor("carros")

with get_db_context() as db:
    rows = db.query(Vehicle).filter(
        Vehicle.vehicle_type == VehicleType("carros"),
        Vehicle.price.isnot(None), Vehicle.price > 500, Vehicle.price < 3000,
        Vehicle.year.isnot(None), Vehicle.km.isnot(None), Vehicle.km > 0,
    ).all()
    recs = []
    for v in rows:
        if (v.source.value if v.source else "") in AUCTION:
            continue
        recs.append({
            "brand": v.brand, "model": v.model, "year": int(v.year), "km": int(v.km or 0),
            "horsepower": v.horsepower, "engine_size": v.engine_size, "doors": v.doors,
            "fuel_type": v.fuel_type.value if v.fuel_type else "unknown",
            "transmission": v.transmission.value if v.transmission else "unknown",
            "location": v.location or "", "district": v.district or "", "price": float(v.price),
        })

low_served, full_served = 0, 0
extreme_low, extreme_full = 0, 0
for r in recs:
    data = {k: r[k] for k in ("year","km","horsepower","engine_size","doors",
                              "fuel_type","transmission","brand","model","location","district")}
    feats = pp.fs.compute_features(data)
    X = np.array([[feats.get(f, 0.0) for f in pp.feature_names]])
    full_pred = float(pp.model.predict(pp.scaler.transform(X))[0])
    if pp.full_log_target:
        full_pred = float(np.expm1(full_pred))
    fp = max(full_pred, 0.0)
    if fp < pp.low_threshold:
        low_served += 1
        if r["km"] > 250000: extreme_low += 1
    else:
        full_served += 1
        if r["km"] > 250000: extreme_full += 1

print(f"Total <3k retalho: {len(recs)}")
print(f"  Servidos por LOW: {low_served}")
print(f"  Servidos por FULL (routing != LOW): {full_served}  <- estes NÃO beneficiam das features LOW")
print(f"  Desses <3k, km>250k: LOW={extreme_low}, FULL={extreme_full}")
