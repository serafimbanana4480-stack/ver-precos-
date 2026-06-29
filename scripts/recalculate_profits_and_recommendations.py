#!/usr/bin/env python3
"""
Recalculate profit potential, recommendations, and deal grades for all vehicles
using the updated DealProfitCalculator logic.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from intelligence.profit.deal_profit_calculator import DealProfitCalculator


def recalculate_all():
    conn = sqlite3.connect("autodeal.db")
    c = conn.cursor()
    
    calc = DealProfitCalculator()
    
    c.execute("""
        SELECT id, brand, model, year, km, price, vehicle_type,
               estimated_value, deal_score, condition_score, ai_risk_score
        FROM vehicles WHERE is_active = 1
    """)
    vehicles = c.fetchall()
    
    print(f"Recalculating profits for {len(vehicles)} vehicles...")
    
    updated = 0
    recommendations = {}
    
    for v in vehicles:
        vid, brand, model, year, km, price, vtype, est_val, deal_score, cond_score, ai_risk = v
        
        vehicle = {
            'brand': brand,
            'model': model,
            'year': year,
            'km': km,
            'price': price,
            'vehicle_type': vtype,
            'estimated_value': est_val or price,
            'condition_score': cond_score or 6.0,
            'ai_risk_score': ai_risk or 5.0,
        }
        
        try:
            result = calc.calculate_deal_profit(vehicle)
            
            c.execute("""
                UPDATE vehicles
                SET profit_potential = ?,
                    profit_percentage = ?,
                    deal_grade = ?,
                    price_discount_percentage = ?,
                    buyer_profit = ?,
                    buyer_profit_margin = ?
                WHERE id = ?
            """, (
                round(result.buyer_profit, 2),
                round(result.buyer_profit_margin, 2),
                result.deal_grade,
                round(result.price_discount_percentage, 2),
                round(result.buyer_profit, 2),
                round(result.buyer_profit_margin, 2),
                vid
            ))
            
            recommendations[result.deal_grade] = recommendations.get(result.deal_grade, 0) + 1
            updated += 1
            
        except Exception as e:
            print(f"Error on vehicle {vid}: {e}")
    
    conn.commit()
    
    print(f"\nUpdated {updated} vehicles")
    print("Grade distribution:")
    for grade, count in sorted(recommendations.items(), key=lambda x: x[1], reverse=True):
        print(f"  {grade}: {count}")
    
    # Show sample recommendations
    print("\n=== SAMPLE RECOMMENDATIONS ===")
    c.execute("""
        SELECT brand, model, price, estimated_value, deal_score, deal_grade, profit_potential
        FROM vehicles WHERE is_active = 1
        ORDER BY deal_score DESC LIMIT 5
    """)
    for row in c.fetchall():
        print(f"  {row[0]} {row[1]} | Price={row[2]:.0f} | Est={row[3]:.0f} | Score={row[4]:.1f} | Grade={row[5]} | Profit={row[6]:.0f}")
    
    print("\n=== BOTTOM 5 ===")
    c.execute("""
        SELECT brand, model, price, estimated_value, deal_score, deal_grade, profit_potential
        FROM vehicles WHERE is_active = 1
        ORDER BY deal_score ASC LIMIT 5
    """)
    for row in c.fetchall():
        print(f"  {row[0]} {row[1]} | Price={row[2]:.0f} | Est={row[3]:.0f} | Score={row[4]:.1f} | Grade={row[5]} | Profit={row[6]:.0f}")
    
    conn.close()


if __name__ == "__main__":
    recalculate_all()
