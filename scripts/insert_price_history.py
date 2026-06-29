"""
Script to insert realistic price history records for demo vehicles
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_context
from database.models import Vehicle, PriceHistory
from datetime import datetime, timezone, timedelta

def insert_price_history():
    print("Initializing price history insertion...")
    
    with get_db_context() as db:
        # Clean existing price history
        db.query(PriceHistory).delete()
        db.commit()
        
        # Get demo vehicles
        duke = db.query(Vehicle).filter(Vehicle.source_id == "demo_moto1").first()
        mt07 = db.query(Vehicle).filter(Vehicle.source_id == "demo_moto2").first()
        golf = db.query(Vehicle).filter(Vehicle.source_id == "demo_car1").first()
        bmw = db.query(Vehicle).filter(Vehicle.source_id == "demo_car2").first()
        
        now = datetime.now(timezone.utc)
        
        if duke:
            print(f"Adding price history for Duke 125 (ID: {duke.id})")
            h1 = PriceHistory(vehicle_id=duke.id, price=3600.0, recorded_at=now - timedelta(days=15))
            h2 = PriceHistory(vehicle_id=duke.id, price=3450.0, recorded_at=now - timedelta(days=10))
            h3 = PriceHistory(vehicle_id=duke.id, price=3300.0, recorded_at=now - timedelta(days=5))
            h4 = PriceHistory(vehicle_id=duke.id, price=3200.0, recorded_at=now) # Current price
            db.add_all([h1, h2, h3, h4])
            
        if mt07:
            print(f"Adding price history for Yamaha MT-07 (ID: {mt07.id})")
            h1 = PriceHistory(vehicle_id=mt07.id, price=5900.0, recorded_at=now - timedelta(days=10))
            h2 = PriceHistory(vehicle_id=mt07.id, price=5650.0, recorded_at=now - timedelta(days=5))
            h3 = PriceHistory(vehicle_id=mt07.id, price=5400.0, recorded_at=now) # Current price
            db.add_all([h1, h2, h3])
            
        if golf:
            print(f"Adding price history for VW Golf VII (ID: {golf.id})")
            h1 = PriceHistory(vehicle_id=golf.id, price=15500.0, recorded_at=now - timedelta(days=20))
            h2 = PriceHistory(vehicle_id=golf.id, price=14700.0, recorded_at=now - timedelta(days=10))
            h3 = PriceHistory(vehicle_id=golf.id, price=13900.0, recorded_at=now) # Current price
            db.add_all([h1, h2, h3])
            
        if bmw:
            print(f"Adding price history for BMW 320d (ID: {bmw.id})")
            h1 = PriceHistory(vehicle_id=bmw.id, price=31000.0, recorded_at=now - timedelta(days=12))
            h2 = PriceHistory(vehicle_id=bmw.id, price=29500.0, recorded_at=now - timedelta(days=6))
            h3 = PriceHistory(vehicle_id=bmw.id, price=27900.0, recorded_at=now) # Current price
            db.add_all([h1, h2, h3])
            
        db.commit()
        print("Price history records successfully inserted!")

if __name__ == "__main__":
    insert_price_history()
