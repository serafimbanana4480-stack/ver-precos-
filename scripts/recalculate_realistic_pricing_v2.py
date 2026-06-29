#!/usr/bin/env python3
"""
Recalculate vehicle valuations using robust regression + segment medians.
Version 2: Adds sanity checks and brand-specific adjustments.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import numpy as np
from datetime import datetime


def build_global_model(c):
    """Build global regression model: price ~ year + km + brand_factor."""
    c.execute("SELECT brand, year, km, price FROM vehicles WHERE is_active = 1 AND price > 0")
    data = c.fetchall()
    
    brands = {}
    years = []
    kms = []
    prices = []
    
    for brand, year, km, price in data:
        if brand not in brands:
            brands[brand] = []
        brands[brand].append(price)
        years.append(year)
        kms.append(km or 0)
        prices.append(price)
    
    # Brand factors (relative to global median)
    global_median = np.median(prices)
    brand_factors = {}
    for brand, brand_prices in brands.items():
        if len(brand_prices) >= 3:
            brand_factors[brand] = np.median(brand_prices) / global_median
        else:
            brand_factors[brand] = 1.0
    
    # Global regression: price = a*year + b*km + c
    X = np.column_stack([np.array(years), np.array(kms), np.ones(len(years))])
    y = np.array(prices)
    coeffs, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)
    
    return coeffs, brand_factors, global_median


def predict_price(c, brand, year, km, coeffs, brand_factors, global_median):
    """Predict price using regression + brand factor + segment median."""
    # 1. Try direct comparables (same brand, year ±1)
    c.execute("""
        SELECT price FROM vehicles 
        WHERE brand = ? AND year BETWEEN ? AND ? AND is_active = 1 AND price > 0
    """, (brand, year - 1, year + 1))
    exact = [r[0] for r in c.fetchall()]
    
    if len(exact) >= 3:
        base = np.median(exact)
    else:
        # 2. Try brand + year ±3
        c.execute("""
            SELECT price FROM vehicles 
            WHERE brand = ? AND year BETWEEN ? AND ? AND is_active = 1 AND price > 0
        """, (brand, year - 3, year + 3))
        brand_year = [r[0] for r in c.fetchall()]
        
        if len(brand_year) >= 3:
            base = np.median(brand_year)
        else:
            # 3. Use regression model
            reg_price = coeffs[0] * year + coeffs[1] * (km or 0) + coeffs[2]
            brand_factor = brand_factors.get(brand, 1.0)
            base = reg_price * brand_factor
    
    # KM adjustment
    if km and km > 0:
        # Typical depreciation: 2% per 10,000km
        km_factor = 1 - ((km / 10000) * 0.02)
        km_factor = max(0.3, min(1.0, km_factor))
    else:
        km_factor = 1.0
    
    # Age adjustment (cars depreciate ~10% per year after year 1)
    age = max(0, datetime.now().year - year)
    age_factor = 0.9 ** max(0, age - 1)
    age_factor = max(0.1, age_factor)
    
    predicted = base * km_factor * age_factor
    
    # Sanity checks
    predicted = max(300, predicted)  # Floor
    predicted = min(150000, predicted)  # Ceiling
    
    return round(predicted, 2)


def recalculate_all():
    conn = sqlite3.connect("autodeal.db")
    c = conn.cursor()
    
    coeffs, brand_factors, global_median = build_global_model(c)
    print(f"Global model: price = {coeffs[0]:.0f}*year + {coeffs[1]:.3f}*km + {coeffs[2]:.0f}")
    print(f"Global median: {global_median:.0f} EUR")
    print(f"Brand factors: {len(brand_factors)} brands")
    
    c.execute("SELECT id, brand, model, year, km, price FROM vehicles WHERE is_active = 1")
    vehicles = c.fetchall()
    
    print(f"\nRecalculating {len(vehicles)} vehicles...")
    
    updated = 0
    
    for v in vehicles:
        vid, brand, model, year, km, price = v
        
        est_value = predict_price(c, brand, year, km, coeffs, brand_factors, global_median)
        
        # Calculate deal score with Portuguese market reality
        # estimated_value = transaction price
        # asking price should be ~15-20% above transaction price
        market_asking = est_value * 1.18
        
        if market_asking > 0 and price > 0:
            discount = (market_asking - price) / market_asking
            raw_score = 6.0 + (discount * 20.0)
            deal_score = max(0.0, min(10.0, raw_score))
        else:
            deal_score = 5.0
        
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
        
        profit = max(0, est_value - price)
        profit_pct = (profit / price * 100) if price > 0 else 0
        
        c.execute("""
            UPDATE vehicles 
            SET estimated_value = ?, deal_score = ?, profit_potential = ?, 
                profit_percentage = ?, deal_grade = ?
            WHERE id = ?
        """, (est_value, round(deal_score, 1), round(profit, 2), 
              round(profit_pct, 2), grade, vid))
        updated += 1
    
    conn.commit()
    
    # Summary
    c.execute("SELECT AVG(deal_score), MIN(deal_score), MAX(deal_score) FROM vehicles WHERE is_active = 1")
    avg_score, min_score, max_score = c.fetchone()
    
    c.execute("SELECT deal_grade, COUNT(*) FROM vehicles WHERE is_active = 1 GROUP BY deal_grade")
    grades = c.fetchall()
    
    print(f"\nUpdated {updated} vehicles")
    print(f"Deal score: avg={avg_score:.2f}, min={min_score:.1f}, max={max_score:.1f}")
    print("Grade distribution:")
    for g, count in sorted(grades, key=lambda x: x[1], reverse=True):
        print(f"  {g}: {count}")
    
    print("\n--- TOP 10 DEALS ---")
    c.execute("SELECT brand, model, year, km, price, estimated_value, deal_score, deal_grade FROM vehicles WHERE is_active = 1 ORDER BY deal_score DESC LIMIT 10")
    for row in c.fetchall():
        print(f"  Score {row[6]:.1f} | {row[0]} {row[1]} {row[2]} | {row[3]} km | {row[4]:.0f} EUR | est={row[5]:.0f} | {row[7]}")
    
    print("\n--- BOTTOM 10 DEALS ---")
    c.execute("SELECT brand, model, year, km, price, estimated_value, deal_score, deal_grade FROM vehicles WHERE is_active = 1 ORDER BY deal_score ASC LIMIT 10")
    for row in c.fetchall():
        print(f"  Score {row[6]:.1f} | {row[0]} {row[1]} {row[2]} | {row[3]} km | {row[4]:.0f} EUR | est={row[5]:.0f} | {row[7]}")
    
    # Check specific problematic cases from before
    print("\n--- CHECKING PREVIOUSLY PROBLEMATIC CASES ---")
    problematic = [
        ("Polestar", "2 Long Range 78 kWh", 2023),
        ("BMW", "420 Gran Coupé d Pack M Auto", 2018),
        ("Mercedes-Benz", "CLA 250 e AMG Line", 2023),
        ("Ford", "Escort Mk5 1100", 1992),
    ]
    for brand, model, year in problematic:
        c.execute("SELECT brand, model, year, price, estimated_value, deal_score FROM vehicles WHERE brand = ? AND model LIKE ? AND year = ?",
                  (brand, f"%{model}%", year))
        row = c.fetchone()
        if row:
            print(f"  {row[0]} {row[1]} {row[2]} | Price={row[3]:.0f} | Est={row[4]:.0f} | Score={row[5]:.1f}")
    
    conn.close()


if __name__ == "__main__":
    recalculate_all()
