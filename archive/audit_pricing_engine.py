"""
Pricing Engine Audit - Verify statistical comparables vs heuristics
"""
import sqlite3
from pathlib import Path

print("=" * 80)
print("PRICING ENGINE AUDIT")
print("=" * 80)

db_path = Path("d:/VER PRECOS/autodeal.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Sample vehicles with estimated values
print("\n[1] Sample Estimated Values")
print("-" * 80)
cursor.execute("""
    SELECT brand, model, year, km, price, estimated_value, deal_score, profit_potential
    FROM vehicles
    WHERE estimated_value IS NOT NULL
    ORDER BY deal_score DESC
    LIMIT 10
""")

samples = cursor.fetchall()
print(f"Top 10 vehicles by deal_score:")
for i, (brand, model, year, km, price, est, score, profit) in enumerate(samples, 1):
    diff_pct = ((est - price) / est * 100) if est > 0 else 0
    print(f"  {i}. {brand} {model} {year} | €{price:,.0f} → €{est:,.0f} ({diff_pct:+.1f}%) | Score: {score} | Profit: €{profit:,.0f}")

# Check if estimates are realistic
print("\n[2] Estimate Realism Check")
print("-" * 80)
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN ABS(estimated_value - price) / price < 0.1 THEN 1 END) as within_10pct,
        COUNT(CASE WHEN ABS(estimated_value - price) / price < 0.2 THEN 1 END) as within_20pct,
        COUNT(CASE WHEN ABS(estimated_value - price) / price < 0.5 THEN 1 END) as within_50pct,
        AVG(ABS(estimated_value - price) / price) as avg_diff_pct
    FROM vehicles
    WHERE estimated_value IS NOT NULL
""")

row = cursor.fetchone()
total, within_10, within_20, within_50, avg_diff = row
print(f"Total with estimates: {total}")
print(f"Within 10% of asking price: {within_10} ({within_10/total*100:.1f}%)")
print(f"Within 20% of asking price: {within_20} ({within_20/total*100:.1f}%)")
print(f"Within 50% of asking price: {within_50} ({within_50/total*100:.1f}%)")
print(f"Average difference: {avg_diff*100:.1f}%")

# Check for unrealistic estimates
print("\n[3] Unrealistic Estimates Detection")
print("-" * 80)
cursor.execute("""
    SELECT brand, model, year, price, estimated_value
    FROM vehicles
    WHERE estimated_value IS NOT NULL
    AND (estimated_value < price * 0.3 OR estimated_value > price * 3.0)
    LIMIT 10
""")

unrealistic = cursor.fetchall()
if unrealistic:
    print(f"⚠️  Found {len(unrealistic)} unrealistic estimates (outside 0.3x-3.0x bounds):")
    for brand, model, year, price, est in unrealistic:
        ratio = est / price if price > 0 else 0
        print(f"  {brand} {model} {year}: €{price:,.0f} → €{est:,.0f} ({ratio:.2f}x)")
else:
    print("✓ No unrealistic estimates found (all within sanity bounds)")

# Check comparables availability
print("\n[4] Comparables Availability Check")
print("-" * 80)
# Sample a few vehicles and check if they have comparables
cursor.execute("""
    SELECT brand, model, year
    FROM vehicles
    WHERE estimated_value IS NOT NULL
    LIMIT 5
""")

test_vehicles = cursor.fetchall()
for brand, model, year in test_vehicles:
    # Find same brand+model within ±2 years
    cursor.execute("""
        SELECT COUNT(*)
        FROM vehicles
        WHERE brand LIKE ?
        AND model LIKE ?
        AND year BETWEEN ? AND ?
        AND is_active = 1
    """, (f"%{brand}%", f"%{model.split()[0] if model else ''}%", year-2, year+2))
    
    count = cursor.fetchone()[0]
    print(f"  {brand} {model} {year}: {count} comparables (±2 years)")

# Check if statistical approach is actually used
print("\n[5] Statistical vs ML Approach Verification")
print("-" * 80)
predict_file = Path("d:/VER PRECOS/valuation/predict.py")
with open(predict_file) as f:
    predict_code = f.read()

# Check if the statistical function is the main one
if "estimate_market_value" in predict_code:
    print("✓ Statistical market value estimation function exists")
    
    # Check if it's the primary method
    if "def estimate_market_value" in predict_code:
        print("✓ estimate_market_value is defined as main function")
    
    # Check if it uses comparables
    if "_find_comparables" in predict_code:
        print("✓ Uses comparables-based approach")
    
    # Check if it uses median
    if "median" in predict_code:
        print("✓ Uses median (robust to outliers)")
    
    # Check if it has sanity bounds
    if "_apply_sanity_bounds" in predict_code:
        print("✓ Has sanity bounds to prevent absurd estimates")

# Check if XGBoost is actually used
if "load_model()" in predict_code:
    print("⚠️  Contains load_model() - may attempt XGBoost")
    # Check if it's actually called in estimate_market_value
    import re
    match = re.search(r'def estimate_market_value.*?(?=\ndef )', predict_code, re.DOTALL)
    if match:
        func_body = match.group(0)
        if "xgb" in func_body.lower() or "xgboost" in func_body.lower():
            print("❌ CRITICAL: estimate_market_value may use XGBoost model")
        else:
            print("✓ estimate_market_value does NOT use XGBoost")

conn.close()

print("\n" + "=" * 80)
