#!/usr/bin/env python3
"""
Recalculate vehicle valuations using a robust, quality-aware approach.
V6: Stricter model matching (>=3 comparables + IQR check) to avoid
    mixing different trim levels (e.g., CLA 220 vs CLA 45 AMG).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
import numpy as np

# Premium brands/models
PREMIUM_BRANDS = {"BMW", "Mercedes-Benz", "Audi", "Porsche", "Lexus", "Jaguar", "Land Rover", "Volvo"}
PREMIUM_MODELS = {"AMG", "M3", "M4", "M5", "RS", "S3", "S4", "S5", "GT", "Cayenne", "Panamera",
                  "CLA 45", "CLA45", "A 45", "A45", "C 63", "C63", "E 63", "E63"}


def is_premium(brand, model):
    if brand in PREMIUM_BRANDS:
        return True
    model_upper = (model or "").upper()
    for p in PREMIUM_MODELS:
        if p.upper() in model_upper:
            return True
    return False


def is_bike(vehicle_type):
    return vehicle_type and vehicle_type.lower() in ["moto", "scooter", "quad"]


def price_in_iqr(price, prices):
    """Check if price is within a reasonable range of comparable prices.
    Avoids mixing base models with high-performance variants."""
    if len(prices) < 3:
        return True
    q1 = np.percentile(prices, 25)
    q3 = np.percentile(prices, 75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return lower <= price <= upper


def get_comparable_median(c, brand, model, year, price, vehicle_type):
    """Get median price from comparable vehicles in same segment.
    Uses stricter matching to avoid mixing trim levels."""
    
    bike_clause = "AND vehicle_type IN ('moto', 'scooter', 'quad')" if is_bike(vehicle_type) else \
                  "AND (vehicle_type IS NULL OR vehicle_type NOT IN ('moto', 'scooter', 'quad'))"
    
    # Level 1: Same brand + model word + year ±2, same type (bike/car)
    model_word = model.split()[0] if model else ''
    c.execute(f"""
        SELECT price, km FROM vehicles 
        WHERE brand = ? AND model LIKE ? AND year BETWEEN ? AND ? 
        AND is_active = 1 AND price > 0 {bike_clause}
    """, (brand, f"{model_word}%", year - 2, year + 2))
    rows = c.fetchall()
    
    prices = [r[0] for r in rows]
    # Require >= 3 comparables AND price must be within IQR of comparables
    if len(rows) >= 3 and price_in_iqr(price, prices):
        return np.median(prices), len(rows), "model_year"
    
    # Level 2: Same brand + year ±3, same type
    c.execute(f"""
        SELECT price, km FROM vehicles 
        WHERE brand = ? AND year BETWEEN ? AND ? 
        AND is_active = 1 AND price > 0 {bike_clause}
    """, (brand, year - 3, year + 3))
    rows = c.fetchall()
    
    if len(rows) >= 3:
        prices = [r[0] for r in rows]
        return np.median(prices), len(rows), "brand_year"
    
    # Level 3: Same brand (any year), same type
    c.execute(f"""
        SELECT price, km FROM vehicles 
        WHERE brand = ? AND is_active = 1 AND price > 0 {bike_clause}
    """, (brand,))
    rows = c.fetchall()
    
    if len(rows) >= 3:
        prices = [r[0] for r in rows]
        return np.median(prices), len(rows), "brand"
    
    return None, 0, "none"


def recalculate_all():
    conn = sqlite3.connect("autodeal.db")
    c = conn.cursor()
    
    c.execute("SELECT id, brand, model, year, km, price, vehicle_type FROM vehicles WHERE is_active = 1")
    vehicles = c.fetchall()
    
    print(f"Recalculating {len(vehicles)} vehicles with robust v6 pricing...")
    
    updated = 0
    level_counts = {"model_year": 0, "brand_year": 0, "brand": 0, "price_anchor": 0}
    
    for v in vehicles:
        vid, brand, model, year, km, price, vehicle_type = v
        
        premium = is_premium(brand, model)
        
        median_price, n_comp, level = get_comparable_median(
            c, brand, model, year, price, vehicle_type
        )
        
        if median_price is not None and price > 0:
            # Adjust median for KM difference
            adjusted_median = median_price
            if km and km > 0:
                c.execute("""
                    SELECT km FROM vehicles 
                    WHERE brand = ? AND year BETWEEN ? AND ? AND is_active = 1 AND price > 0 AND km > 0
                """, (brand, year - 3, year + 3))
                comp_kms = [r[0] for r in c.fetchall()]
                if comp_kms:
                    comp_median_km = np.median(comp_kms)
                    km_diff_pct = (km - comp_median_km) / max(comp_median_km, 1)
                    km_adjustment = max(-0.10, min(0.10, km_diff_pct * -0.20))
                    adjusted_median = median_price * (1 + km_adjustment)
            
            # Quality-aware blending strategy
            if level == "model_year":
                # High confidence: comparables are very similar and price-consistent
                # Blend 70% external median, 30% own price
                est_value = adjusted_median * 0.70 + price * 0.30
                
            elif level == "brand_year":
                # Medium confidence: same brand + similar year
                # Small adjustment from own price toward median (max 6%)
                ratio = adjusted_median / price
                if ratio > 1.06:
                    ratio = 1.06
                elif ratio < 0.94:
                    ratio = 0.94
                est_value = price * ratio
                
            else:  # brand only
                # Low confidence: only same brand
                # Very small adjustment from own price (max 4%)
                ratio = adjusted_median / price
                if ratio > 1.04:
                    ratio = 1.04
                elif ratio < 0.96:
                    ratio = 0.96
                est_value = price * ratio
            
            level_counts[level] += 1
        else:
            # No comparables at all — use vehicle's own price as neutral estimate
            est_value = price * 0.98 if price else 0
            level_counts["price_anchor"] += 1
        
        # Final sanity clamp
        if price > 0:
            if price >= 50000:
                low_mult, high_mult = 0.60, 1.30
            elif price >= 30000:
                low_mult, high_mult = 0.55, 1.25
            elif price >= 15000:
                low_mult, high_mult = 0.50, 1.20
            else:
                low_mult, high_mult = 0.45, 1.15
            est_value = max(price * low_mult, min(price * high_mult, est_value))
        
        # Calculate deal score
        # Benchmark = estimated_value * 1.12 (consistent with HybridValuator)
        # Portuguese market: asking prices ~10-15% above real transaction
        market_asking = est_value * 1.12
        
        if market_asking > 0 and price > 0:
            discount = (market_asking - price) / market_asking
            # Score 5.0 = neutral (at benchmark)
            # Score 8.0 = ~20% below benchmark
            # Score 10.0 = 33%+ below benchmark
            raw_score = 5.0 + (discount * 15.0)
            deal_score = max(0.0, min(10.0, raw_score))
        else:
            deal_score = 5.0
        
        # Grade thresholds
        if deal_score >= 8.5:
            grade = "exceptional"
        elif deal_score >= 7.5:
            grade = "excellent"
        elif deal_score >= 6.0:
            grade = "good"
        elif deal_score >= 4.5:
            grade = "fair"
        else:
            grade = "poor"
        
        # Gross profit (before Portugal transfer taxes & repairs)
        profit = max(0, est_value - price) if price else 0
        profit_pct = (profit / price * 100) if price else 0
        # Note: net profit = profit - taxes(~15.5% of price) - repair_costs
        
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
        ("Honda", "Civic"),
        ("Honda", "CBR"),
        ("Renault", "Kadjar"),
        ("Mercedes-Benz", "CLA 45"),
        ("Mercedes-Benz", "CLA 220"),
    ]
    for brand, model in cases:
        c.execute("SELECT brand, model, year, price, estimated_value, deal_score, deal_grade FROM vehicles WHERE brand = ? AND model LIKE ?",
                  (brand, f"%{model}%"))
        for row in c.fetchall():
            print(f"  {row[0]} {row[1]} {row[2]} | Price={row[3]:.0f} | Est={row[4]:.0f} | Score={row[5]:.1f} ({row[6]})")
    
    conn.close()


if __name__ == "__main__":
    recalculate_all()
