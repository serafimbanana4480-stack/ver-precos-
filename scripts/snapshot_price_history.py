"""
Backfill price_history for all existing vehicles.
Creates one PriceHistory snapshot per vehicle using its current price.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_context
from database.models import Vehicle, PriceHistory
from datetime import datetime, timezone


def snapshot_price_history():
    print("Backfilling price_history for all existing vehicles...")

    with get_db_context() as db:
        vehicles = db.query(Vehicle).all()
        total = len(vehicles)
        inserted = 0
        skipped = 0

        for vehicle in vehicles:
            # Skip if a snapshot already exists for this exact price
            existing = (
                db.query(PriceHistory)
                .filter(
                    PriceHistory.vehicle_id == vehicle.id,
                    PriceHistory.price == vehicle.price,
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

            snapshot = PriceHistory(
                vehicle_id=vehicle.id,
                price=vehicle.price,
                recorded_at=datetime.now(timezone.utc),
            )
            db.add(snapshot)
            inserted += 1

        db.commit()

    print(f"Done. Total vehicles: {total}")
    print(f"Inserted snapshots: {inserted}")
    print(f"Skipped (duplicate price): {skipped}")


if __name__ == "__main__":
    snapshot_price_history()
