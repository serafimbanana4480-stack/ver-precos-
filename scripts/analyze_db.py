"""Analyze price distribution and auction share in the autodeal DB."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import get_db_context
from database.models import Vehicle, VehicleType, Source
import numpy as np
import pandas as pd

AUCTION_SOURCES = {"LEILOSOC","VPAUTO","MANHEIM","AUTOROLA","BCA","MARTELO","AUTOLINE","PENHORADO"}

with get_db_context() as db:
    rows = db.query(Vehicle).filter(
        Vehicle.vehicle_type == VehicleType("carros"),
        Vehicle.price.isnot(None),
        Vehicle.price > 500, Vehicle.price < 500000,
        Vehicle.year.isnot(None),
        Vehicle.km.isnot(None), Vehicle.km > 0,
    ).all()
    recs = [{
        "price": float(v.price),
        "year": int(v.year), "km": int(v.km or 0),
        "source": v.source.value if v.source else "",
        "is_auction": v.source.value in AUCTION_SOURCES if v.source else False,
    } for v in rows]

df = pd.DataFrame(recs)
print(f"TOTAL carros elegíveis (preço/km/ano): {len(df)}")
print(f"Leilões: {int(df['is_auction'].sum())} ({df['is_auction'].mean()*100:.1f}%)")
print(f"Retalho: {int((~df['is_auction']).sum())}")
print()
print("=== DISTRIBUIÇÃO POR FAIXA (retalho) ===")
ret = df[~df["is_auction"]]
bins = [0,3000,5000,10000,20000,30000,50000,1e9]
labels = ["<3k","3-5k","5-10k","10-20k","20-30k","30-50k",">50k"]
ret = ret.copy()
ret["fx"] = pd.cut(ret["price"], bins=bins, labels=labels)
print(ret.groupby("fx", observed=True).agg(n=("price","size"), median=("price","median"), mean=("price","mean")))
print()
print("=== ESTATÍSTICAS GLOBAIS (retalho) ===")
print(f"min={ret['price'].min():.0f} median={ret['price'].median():.0f} mean={ret['price'].mean():.0f} max={ret['price'].max():.0f}")
# current model metrics context
print()
print(f"Retalho <3k: {int((ret['price']<3000).sum())} veículos")
print(f"Retalho 5-10k: {int(((ret['price']>=5000)&(ret['price']<10000)).sum())} veículos")
print(f"Retalho >30k: {int((ret['price']>30000).sum())} veículos")
