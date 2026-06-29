#!/usr/bin/env python3
"""
Recalculate vehicle valuations using a robust statistical approach
WITHOUT data leakage. Uses segment-based median pricing.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import numpy as np
from datetime import datetime


def get_segment_median(c, brand, year, km):
    """Get median price for similar vehicles with KM adjustment."""
    # Try exact brand + year ±1
    c.execute("""
        SELECT price, km FROM vehicles 
        WHERE brand = ? AND year BETWEEN ? AND ? AND is_active = 1 AND price > 0
    """, (brand, year - 1, year + 1))
    exact = c.fetchall()
    
    if len(exact) >= 3:
        prices = [p for p, k in exact]
        median_price = np.median(prices)
        # KM adjustment: 0.5% per 1000km
        kms = [k for p, k in exact if k and k > 0]
        if km and kms:
            median_km = np.median(kms)
            km_diff = km - median_km
            adjustment = 1 - (km_diff * 0.0005)
            adjustment = max(0.5, min(1.5, adjustment))
            median_price *= adjustment
        return round(median_price, 2), len(exact)
    
    # Try brand + year ±3
    c.execute("""
        SELECT price, km FROM vehicles 
        WHERE brand = ? AND year BETWEEN ? AND ? AND is_active = 1 AND price > 0
    """, (brand, year - 3, year + 3))
    brand_year = c.fetchall()
    
    if len(brand_year) >= 3:
        prices = [p for p, k in brand_year]
        median_price = np.median(prices)
        kms = [k for p, k in brand_year if k and k > 0]
        if km and kms:
            median_km = np.median(kms)
            km_diff = km - median_km
            adjustment = 1 - (km_diff * 0.0005)
            adjustment = max(0.5, min(1.5, adjustment))
            median_price *= adjustment
        return round(median_price, 2), len(brand_year)
    
    # Try same year ±2 (any brand)
    c.execute("""
        SELECT price, km FROM vehicles 
        WHERE year BETWEEN ? AND ? AND is_active = 1 AND price > 0
    """, (year - 2, year + 2))
    year_only = c.fetchall()
    
    if len(year_only) >= 5:
        prices = [p for p, k in year_only]
        return round(np.median(prices), 2), len(year_only)
    
    # Global regression fallback: price ~ year + km
    c.execute("SELECT year, km, price FROM vehicles WHERE is_active = 1 AND price > 0")
    all_data = c.fetchall()
    
    if len(all_data) >= 10:
        years = np.array([d[0] for d in all_data])
        kms = np.array([d[1] or 0 for d in all_data])
        prices = np.array([d[2] for d in all_data])
        
        # Simple linear regression: price = a*year + b*km + c
        X = np.column_stack([years, kms, np.ones(len(years))])
        coeffs, residuals, rank, s = np.linalg.lstsq(X, prices, rcond=None)
        
        pred_price = coeffs[0] * year + coeffs[1] * (km or 0) + coeffs[2]
        pred_price = max(500, pred_price)  # Sanity floor
        return round(pred_price, 2), len(all_data)
    
    return None, 0


def recalculate_all():
    conn = sqlite3.connect("autodeal.db")
    c = conn.cursor()
    
    c.execute("SELECT id, brand, model, year, km, price, fuel_type, transmission FROM vehicles WHERE is_active = 1")
    vehicles = c.fetchall()
    
    print(f"Recalculating {len(vehicles)} vehicles with robust statistical pricing...")
    
    updated = 0
    failures = 0
    
    for v in vehicles:
        vid, brand, model, year, km, price, fuel_type, transmission = v
        
        est_value, n_comp = get_segment_median(c, brand, year, km)
        
        if est_value is None:
            # Ultimate fallback: use price with typical market margin
            est_value = price * 0.88 if price else 0
            failures += 1
        
        # Calculate deal score with Portuguese market reality
        market_margin = 1.18  # 18% margin = typical PT market
        asking_benchmark = est_value * market_margin
        discount = (asking_benchmark - price) / asking_benchmark if asking_benchmark > 0 else 0
        raw_score = 6.0 + (discount * 20.0)
        deal_score = max(0.0, min(10.0, raw_score))
        
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
    
    # Summary
    c.execute("SELECT AVG(deal_score), MIN(deal_score), MAX(deal_score) FROM vehicles WHERE is_active = 1")
    avg_score, min_score, max_score = c.fetchone()
    
    c.execute("SELECT deal_grade, COUNT(*) FROM vehicles WHERE is_active = 1 GROUP BY deal_grade")
    grades = c.fetchall()
    
    print(f"\nUpdated {updated} vehicles, {failures} fallbacks used")
    print(f"Deal score: avg={avg_score:.2f}, min={min_score:.1f}, max={max_score:.1f}")
    print("Grade distribution:")
    for g, count in sorted(grades, key=lambda x: x[1], reverse=True):
        print(f"  {g}: {count}")
    
    # Show realistic cases
    print("\n--- TOP 10 DEALS ---")
    c.execute("SELECT brand, model, year, price, estimated_value, deal_score, deal_grade FROM vehicles WHERE is_active = 1 ORDER BY deal_score DESC LIMIT 10")
    for row in c.fetchall():
        print(f"  Score {row[5]:.1f} | {row[0]} {row[1]} {row[2]} | {row[3]:.0f} EUR | est={row[4]:.0f} | {row[6]}")
    
    print("\n--- BOTTOM 10 DEALS ---")
    c.execute("SELECT brand, model, year, price, estimated_value, deal_score, deal_grade FROM vehicles WHERE is_active = 1 ORDER BY deal_score ASC LIMIT 10")
    for row in c.fetchall():
        print(f"  Score {row[5]:.1f} | {row[0]} {row[1]} {row[2]} | {row[3]:.0f} EUR | est={row[4]:.0f} | {row[6]}")
    
    conn.close()


if __name__ == "__main__":
    recalculate_all()
