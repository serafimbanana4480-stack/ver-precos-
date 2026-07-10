"""Valida o novo modelo segmentado: 5 exemplos reais da BD por faixa."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.settings import settings
from valuation.predict import PricePredictor
from database.db import get_db_context
from database.models import Vehicle, VehicleType

pp = PricePredictor("carros")
print(f"Modelo carregado: {pp.model_name} | R²(meta)={pp.metrics.get('r2')} | "
      f"LOW carregado: {pp.low_model is not None} | threshold={pp.low_threshold}")

AUCTION = {"LEILOSOC","VPAUTO","MANHEIM","AUTOROLA","BCA","MARTELO","AUTOLINE","PENHORADO"}

with get_db_context() as db:
    rows = db.query(Vehicle).filter(
        Vehicle.vehicle_type == VehicleType("carros"),
        Vehicle.price.isnot(None), Vehicle.price > 500, Vehicle.price < 500000,
        Vehicle.year.isnot(None), Vehicle.km.isnot(None), Vehicle.km > 0,
    ).all()
    # materializar dentro da sessão para evitar DetachedInstanceError
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

def faixa(p):
    if p < 3000: return "baixo (<3k)"
    if p < 10000: return "medio-baixo (5-10k)"
    if p > 30000: return "alto (>30k)"
    return "mid"

# escolher 5 exemplos: 2 em <3k, 2 em 5-10k, 1 em >30k
picks = []
seen = {"<3k":0,"5-10k":0,">30k":0}
for v in recs:
    p = v["price"]
    if p < 3000 and seen["<3k"] < 2:
        picks.append(v); seen["<3k"]+=1
    elif 5000 <= p < 10000 and seen["5-10k"] < 2:
        picks.append(v); seen["5-10k"]+=1
    elif p > 30000 and seen[">30k"] < 1:
        picks.append(v); seen[">30k"]+=1
    if all(seen[k] >= (2 if k!=">30k" else 1) for k in seen):
        break

print("\n=== 5 EXEMPLOS REAIS (predict vs preço real) ===")
for v in picks:
    data = {"year": v["year"], "km": v["km"], "horsepower": v["horsepower"],
            "engine_size": v["engine_size"], "doors": v["doors"], "fuel_type": v["fuel_type"],
            "transmission": v["transmission"], "brand": v["brand"] or "Unknown", "model": v["model"] or "",
            "location": v["location"], "district": v["district"]}
    pred = pp.predict(data)
    real = v["price"]
    err = (pred - real) if pred else None
    err_pct = (err/real*100) if err is not None else None
    print(f"\n• {v['brand']} {v['model']} {v['year']} | {v['km']}km | {v['fuel_type']}/{v['transmission']}")
    print(f"  Faixa: {faixa(real)}")
    print(f"  Preço real: €{real:.0f}")
    print(f"  Predição  : €{pred:.0f}" if pred else "  Predição: ERRO")
    print(f"  Erro      : €{err:.0f} ({err_pct:+.1f}%)" if err is not None else "")
