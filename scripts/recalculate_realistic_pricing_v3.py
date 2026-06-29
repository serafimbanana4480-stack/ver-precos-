#!/usr/bin/env python3
"""
Recalculate vehicle valuations using a robust, conservative approach.
V3: Uses segment medians with strong fallback and sanity checks.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import numpy as np


def get_comparable_median(c, brand, model, year, km):
    """Get median price from comparable vehicles with KM adjustment."""
    
    # Level 1: Same brand + model word + year ±2
    model_word = model.split()[0] if model else ''
    c.execute("""
        SELECT price, km FROM vehicles 
        WHERE brand = ? AND model LIKE ? AND year BETWEEN ? AND ? 
        AND is_active = 1 AND price > 0
    """, (brand, f"{model_word}%", year - 2, year + 2))
    rows = c.fetchall()
    
    if len(rows) >= 3:
        prices = [r[0] for r in rows]
        return np.median(prices), len(rows), "model_year"
    
    # Level 2: Same brand + year ±3
    c.execute("""
        SELECT price, km FROM vehicles 
        WHERE brand = ? AND year BETWEEN ? AND ? 
        AND is_active = 1 AND price > 0
    """, (brand, year - 3, year + 3))
    rows = c.fetchall()
    
    if len(rows) >= 3:
        prices = [r[0] for r in rows]
        return np.median(prices), len(rows), "brand_year"
    
    # Level 3: Same brand (any year)
    c.execute("""
        SELECT price, km FROM vehicles 
        WHERE brand = ? AND is_active = 1 AND price > 0
    """, (brand,))
    rows = c.fetchall()
    
    if len(rows) >= 3:
        prices = [r[0] for r in rows]
        return np.median(prices), len(rows), "brand"
    
    return None, 0, "none"


def recalculate_all():
    conn = sqlite3.connect("autodeal.db")
    c = conn.cursor()
    
    c.execute("SELECT id, brand, model, year, km, price FROM vehicles WHERE is_active = 1")
    vehicles = c.fetchall()
    
    print(f"Recalculating {len(vehicles)} vehicles with robust v3 pricing...")
    
    updated = 0
    level_counts = {"model_year": 0, "brand_year": 0, "brand": 0, "price_fallback": 0}
    
    for v in vehicles:
        vid, brand, model, year, km, price = v
        
        median_price, n_comp, level = get_comparable_median(c, brand, model, year, km)
        
        if median_price is not None:
            # Adjust for KM difference from median of comparables
            c.execute("SELECT km FROM vehicles WHERE brand = ? AND year BETWEEN ? AND ? AND is_active = 1 AND price > 0 AND km > 0",
                      (brand, year - 3, year + 3))
            comp_kms = [r[0] for r in c.fetchall()]
            if comp_kms and km:
                comp_median_km = np.median(comp_kms)
                km_diff_pct = (km - comp_median_km) / max(comp_median_km, 1)
                # Cap adjustment at ±20%
                km_adjustment = max(-0.20, min(0.20, km_diff_pct * -0.3))
                est_value = median_price * (1 + km_adjustment)
            else:
                est_value = median_price
            level_counts[level] += 1
        else:
            # Ultimate fallback: use vehicle's own price as market reference
            # This gives a neutral deal score (no info = no edge)
            est_value = price * 0.95 if price else 0
            level_counts["price_fallback"] += 1
        
        # Sanity clamp: estimated_value must be within [price * 0.4, price * 1.3]
        # This prevents wildly wrong estimates from distorting scores
        if price > 0:
            est_value = max(price * 0.4, min(price * 1.3, est_value))
        
        # Calculate deal score
        market_asking = est_value * 1.15  # 15% typical PT margin
        
        if market_asking > 0 and price > 0:
            discount = (market_asking - price) / market_asking
            raw_score = 6.0 + (discount * 20.0)
            deal_score = max(0.0, min(10.0, raw_score))
        else:
            deal_score = 5.0
        
        # Grade
        if deal_score >= 8.5:
            grade = "exceptional"
        elif deal_score >= 7.0:
            grade = "excellent"
        elif deal_score >= 5.5:
            grade = "good"
        elif deal_score >= 4.0:
            grade = "fair"
        else:
            grade = "poor"
        
        profit = max(0, est_value - price) if price else 0
        profit_pct = (profit / price * 100) if price else 0
        
        c.execute("""
            UPDATE vehicles 
            SET estimated_value = ?, deal_score = ?, profit_potential = ?, 
                profit_percentage = ?, deal_grade = ?
            WHERE id = ?
        """, (round(est_value, 2), round(deal_score, 1), round(profit, 2), 
              round(profit_pct, 2), grade, vid))
        updated += 1
    
    conn.commit()
    
    print(f"\nUpdated {updated} vehicles")
    print("Pricing source distribution:")
    for level, count in sorted(level_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {level}: {count}")
    
    c.execute("SELECT AVG(deal_score), MIN(deal_score), MAX(deal_score) FROM vehicles WHERE is_active = 1")
    avg_score, min_score, max_score = c.fetchone()
    print(f"\nDeal score: avg={avg_score:.2f}, min={min_score:.1f}, max={max_score:.1f}")
    
    c.execute("SELECT deal_grade, COUNT(*) FROM vehicles WHERE is_active = 1 GROUP BY deal_grade")
    grades = c.fetchall()
    print("Grade distribution:")
    for g, count in sorted(grades, key=lambda x: x[1], reverse=True):
        print(f"  {g}: {count}")
    
    print("\n--- TOP 10 DEALS ---")
    c.execute("SELECT brand, model, year, km, price, estimated_value, deal_score, deal_grade FROM vehicles WHERE is_active = 1 ORDER BY deal_score DESC LIMIT 10")
    for row in c.fetchall():
        km_str = f"{row[3]:,} km" if row[3] else "N/A km"
        print(f"  Score {row[6]:.1f} | {row[0]} {row[1]} {row[2]} | {km_str} | {row[4]:.0f} EUR | est={row[5]:.0f} | {row[7]}")
    
    print("\n--- BOTTOM 10 DEALS ---")
    c.execute("SELECT brand, model, year, km, price, estimated_value, deal_score, deal_grade FROM vehicles WHERE is_active = 1 ORDER BY deal_score ASC LIMIT 10")
    for row in c.fetchall():
        km_str = f"{row[3]:,} km" if row[3] else "N/A km"
        print(f"  Score {row[6]:.1f} | {row[0]} {row[1]} {row[2]} | {km_str} | {row[4]:.0f} EUR | est={row[5]:.0f} | {row[7]}")
    
    print("\n--- PREVIOUSLY PROBLEMATIC CASES ---")
    cases = [
        ("Polestar", "2"),
        ("BMW", "420"),
        ("Mercedes-Benz", "CLA 250"),
        ("Ford", "Escort"),
        ("Opel", "Corsa D"),
    ]
    for brand, model in cases:
        c.execute("SELECT brand, model, year, price, estimated_value, deal_score FROM vehicles WHERE brand = ? AND model LIKE ?",
                  (brand, f"%{model}%"))
        for row in c.fetchall():
            print(f"  {row[0]} {row[1]} {row[2]} | Price={row[3]:.0f} | Est={row[4]:.0f} | Score={row[5]:.1f}")
    
    conn.close()


if __name__ == "__main__":
    recalculate_all()
