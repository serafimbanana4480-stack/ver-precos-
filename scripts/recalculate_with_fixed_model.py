#!/usr/bin/env python3
"""
Recalculate all vehicle valuations using the fixed ML feature preparation.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from datetime import datetime, timezone

from intelligence.pricing.engine import HybridPricingEngine
from valuation.predict import calculate_deal_score


def recalculate_all():
    engine = HybridPricingEngine()
    
    conn = sqlite3.connect("autodeal.db")
    c = conn.cursor()
    
    c.execute("SELECT id, brand, model, year, km, price, fuel_type, transmission, location, vehicle_type, horsepower, engine_size, condition_score FROM vehicles WHERE is_active = 1")
    vehicles = c.fetchall()
    
    print(f"Recalculating {len(vehicles)} vehicles with fixed ML features...")
    
    updated = 0
    errors = 0
    
    for v in vehicles:
        vid, brand, model, year, km, price, fuel_type, transmission, location, vtype, hp, engine_size, condition = v
        
        vehicle_data = {
            'brand': brand or 'unknown',
            'model': model or 'unknown',
            'year': year or 0,
            'km': km or 0,
            'fuel_type': fuel_type or 'unknown',
            'transmission': transmission or 'unknown',
            'location': location or 'unknown',
            'district': location or 'unknown',
            'vehicle_type': vtype or 'carros',
            'horsepower': hp or 0,
            'engine_size': engine_size or 0,
            'condition_score': condition or 5.0,
            'price': price or 0,
        }
        
        try:
            pricing = engine.calculate_price(vehicle_data)
            final_price = pricing.get('final_price')
            
            if final_price is None:
                # Fallback: use statistical price or current price * 0.88
                final_price = pricing.get('statistical_price') or (price * 0.88 if price else 0)
            
            # Calculate deal score
            score_data = calculate_deal_score({
                'price': price,
                'estimated_value': final_price,
            })
            
            deal_score = score_data['deal_score']
            
            # Deal grade
            if deal_score >= 9:
                grade = "exceptional"
            elif deal_score >= 7.5:
                grade = "excellent"
            elif deal_score >= 6:
                grade = "good"
            elif deal_score >= 4:
                grade = "fair"
            else:
                grade = "poor"
            
            profit = max(0, final_price - price) if price else 0
            profit_pct = (profit / price * 100) if price else 0
            
            c.execute("""
                UPDATE vehicles 
                SET estimated_value = ?, deal_score = ?, profit_potential = ?, 
                    profit_percentage = ?, deal_grade = ?
                WHERE id = ?
            """, (round(final_price, 2), round(deal_score, 1), round(profit, 2), 
                  round(profit_pct, 2), grade, vid))
            updated += 1
            
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error on {brand} {model}: {e}")
    
    conn.commit()
    
    # Show results
    c.execute("SELECT AVG(deal_score), MIN(deal_score), MAX(deal_score) FROM vehicles WHERE is_active = 1")
    avg_score, min_score, max_score = c.fetchone()
    
    c.execute("SELECT deal_grade, COUNT(*) FROM vehicles WHERE is_active = 1 GROUP BY deal_grade")
    grades = c.fetchall()
    
    print(f"\nUpdated {updated} vehicles, {errors} errors")
    print(f"Deal score: avg={avg_score:.2f}, min={min_score:.1f}, max={max_score:.1f}")
    print("Grade distribution:")
    for g, count in sorted(grades, key=lambda x: x[1], reverse=True):
        print(f"  {g}: {count}")
    
    # Show problematic cases
    print("\n--- Cases with score < 3 (possible model failures) ---")
    c.execute("SELECT brand, model, year, price, estimated_value, deal_score FROM vehicles WHERE is_active = 1 AND deal_score < 3 ORDER BY deal_score ASC")
    for row in c.fetchall():
        print(f"  {row[0]} {row[1]} {row[2]} | Price={row[3]:.0f} | Est={row[4]:.0f} | Score={row[5]:.1f}")
    
    conn.close()


if __name__ == "__main__":
    recalculate_all()
