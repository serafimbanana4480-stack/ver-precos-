#!/usr/bin/env python3
"""
Recalculate deal scores and profit potentials for all vehicles
using the realistic Portuguese market formula.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_context
from database.models import Vehicle
from valuation.predict import calculate_deal_score, calculate_profit_potential


def recalculate_all():
    with get_db_context() as db:
        vehicles = db.query(Vehicle).filter(Vehicle.is_active == True).all()
        print(f"Recalculating {len(vehicles)} vehicles...")
        
        updated = 0
        for v in vehicles:
            if not v.price or not v.estimated_value:
                continue
            
            listing = {
                "price": v.price,
                "estimated_value": v.estimated_value,
            }
            
            score_data = calculate_deal_score(listing)
            profit_data = calculate_profit_potential(listing)
            
            v.deal_score = score_data["deal_score"]
            v.profit_potential = profit_data["profit_potential"]
            v.profit_percentage = profit_data["profit_percentage"]
            
            # Set deal grade based on new score
            if v.deal_score >= 9:
                v.deal_grade = "exceptional"
            elif v.deal_score >= 7.5:
                v.deal_grade = "excellent"
            elif v.deal_score >= 6:
                v.deal_grade = "good"
            elif v.deal_score >= 4:
                v.deal_grade = "fair"
            else:
                v.deal_grade = "poor"
            
            updated += 1
        
        db.commit()
        print(f"Updated {updated} vehicles")
        
        # Show distribution
        from sqlalchemy import func
        distribution = db.query(
            Vehicle.deal_grade, 
            func.count(Vehicle.id)
        ).group_by(Vehicle.deal_grade).all()
        
        print("\nDeal grade distribution:")
        for grade, count in sorted(distribution, key=lambda x: x[1], reverse=True):
            print(f"  {grade}: {count}")
        
        avg_score = db.query(func.avg(Vehicle.deal_score)).scalar()
        print(f"\nAverage deal score: {avg_score:.2f}/10")
        
        profitable = db.query(Vehicle).filter(Vehicle.profit_potential > 0).count()
        total = db.query(Vehicle).filter(Vehicle.is_active == True).count()
        print(f"Profitable deals: {profitable}/{total} ({profitable/total*100:.1f}%)")


if __name__ == "__main__":
    recalculate_all()
