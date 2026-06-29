"""
Database Cleanup Script — Reset corrupt valuation data and re-run statistical valuation.

This script:
1. Resets ALL estimated_value, deal_score, profit_potential, profit_percentage to NULL
2. Flags suspicious listings (deposit prices, data errors)
3. Re-runs the new statistical valuation engine
4. Prints a before/after summary
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import sqlite3
from datetime import datetime

DB_PATH = "autodeal.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print("=" * 60)
    print("AutoDeal Database Cleanup")
    print("=" * 60)
    
    # --- Step 1: Show current state ---
    print("\n📊 BEFORE CLEANUP:")
    c.execute("SELECT COUNT(*) FROM vehicles")
    total = c.fetchone()[0]
    print(f"  Total vehicles: {total}")
    
    c.execute("SELECT COUNT(*) FROM vehicles WHERE estimated_value IS NOT NULL")
    with_est = c.fetchone()[0]
    print(f"  With estimates: {with_est}")
    
    c.execute("""
        SELECT COUNT(*) FROM vehicles 
        WHERE estimated_value IS NOT NULL 
        AND (estimated_value > price * 3 OR estimated_value < price * 0.3)
    """)
    absurd = c.fetchone()[0]
    print(f"  With ABSURD estimates (>3x or <0.3x price): {absurd}")
    
    c.execute("""
        SELECT brand, model, year, price, estimated_value, deal_score 
        FROM vehicles 
        WHERE estimated_value IS NOT NULL 
        ORDER BY ABS(estimated_value - price) DESC 
        LIMIT 5
    """)
    rows = c.fetchall()
    if rows:
        print("\n  Worst offenders:")
        for r in rows:
            est = r[4] if r[4] else 0
            price = r[3] if r[3] else 1
            ratio = est / price if price > 0 else 0
            print(f"    {r[0]} {r[1]} ({r[2]}): price=€{price:.0f}, "
                  f"est=€{est:.0f} ({ratio:.1f}x), score={r[5]}")
    
    # --- Step 2: Reset all valuation data ---
    print("\n🧹 RESETTING all valuation data...")
    c.execute("""
        UPDATE vehicles SET 
            estimated_value = NULL,
            deal_score = NULL,
            profit_potential = NULL,
            profit_percentage = NULL
    """)
    reset_count = c.rowcount
    print(f"  Reset {reset_count} vehicles")
    
    # --- Step 3: Flag suspicious prices ---
    print("\n🚩 FLAGGING suspicious listings...")
    
    # Deactivate cars under €500 (likely deposits)
    c.execute("""
        UPDATE vehicles SET is_active = 0 
        WHERE vehicle_type = 'carros' AND price < 500 AND price > 0
    """)
    flagged_cheap_cars = c.rowcount
    print(f"  Deactivated {flagged_cheap_cars} cars under €500")
    
    # Deactivate motos under €200
    c.execute("""
        UPDATE vehicles SET is_active = 0 
        WHERE vehicle_type = 'motos' AND price < 200 AND price > 0
    """)
    flagged_cheap_motos = c.rowcount
    print(f"  Deactivated {flagged_cheap_motos} motos under €200")
    
    # Deactivate premium brands with suspiciously low prices (< €2000)
    premium_brands = ["Porsche", "Ferrari", "Lamborghini", "Maserati", "Bentley",
                       "Rolls-Royce", "Aston Martin", "McLaren"]
    for brand in premium_brands:
        c.execute("""
            UPDATE vehicles SET is_active = 0 
            WHERE LOWER(brand) = LOWER(?) AND price < 2000 AND price > 0
        """, (brand,))
        if c.rowcount > 0:
            print(f"  Deactivated {c.rowcount} suspicious {brand} listings (< €2000)")
    
    # Deactivate vehicles with no price
    c.execute("UPDATE vehicles SET is_active = 0 WHERE price IS NULL OR price <= 0")
    flagged_no_price = c.rowcount
    if flagged_no_price > 0:
        print(f"  Deactivated {flagged_no_price} vehicles with no/zero price")
    
    conn.commit()
    
    # --- Step 4: Show clean state ---
    print("\n📊 AFTER CLEANUP:")
    c.execute("SELECT COUNT(*) FROM vehicles WHERE is_active = 1")
    active = c.fetchone()[0]
    print(f"  Active vehicles: {active}")
    
    c.execute("SELECT COUNT(*) FROM vehicles WHERE is_active = 0")
    inactive = c.fetchone()[0]
    print(f"  Deactivated: {inactive}")
    
    c.execute("""
        SELECT source, COUNT(*) 
        FROM vehicles 
        WHERE is_active = 1 
        GROUP BY source
    """)
    by_source = c.fetchall()
    for src, cnt in by_source:
        print(f"  {src}: {cnt} active")
    
    conn.close()
    
    # --- Step 5: Re-run valuation with new engine ---
    print("\n🔄 RE-RUNNING statistical valuation...")
    try:
        from valuation.predict import update_vehicle_valuations
        update_vehicle_valuations(batch_size=1000)
        print("  ✅ Valuation complete!")
    except Exception as e:
        print(f"  ❌ Valuation error: {e}")
        import traceback
        traceback.print_exc()
    
    # --- Step 6: Verify results ---
    print("\n📊 VERIFICATION:")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM vehicles WHERE estimated_value IS NOT NULL AND is_active = 1")
    new_est = c.fetchone()[0]
    print(f"  Vehicles with new estimates: {new_est}")
    
    c.execute("""
        SELECT AVG(estimated_value), MIN(estimated_value), MAX(estimated_value) 
        FROM vehicles 
        WHERE estimated_value IS NOT NULL AND is_active = 1
    """)
    stats = c.fetchone()
    if stats[0]:
        print(f"  Estimate range: €{stats[1]:.0f} – €{stats[2]:.0f} (avg: €{stats[0]:.0f})")
    
    c.execute("""
        SELECT COUNT(*) FROM vehicles 
        WHERE estimated_value IS NOT NULL AND is_active = 1
        AND (estimated_value > price * 3 OR estimated_value < price * 0.3)
    """)
    still_absurd = c.fetchone()[0]
    print(f"  Absurd estimates remaining: {still_absurd}")
    
    c.execute("""
        SELECT brand, model, year, price, estimated_value, deal_score, profit_potential
        FROM vehicles 
        WHERE estimated_value IS NOT NULL AND is_active = 1
        ORDER BY deal_score DESC
        LIMIT 10
    """)
    top = c.fetchall()
    if top:
        print("\n  🏆 Top 10 deals (new valuation):")
        print(f"  {'Brand':15} {'Model':25} {'Year':>5} {'Price':>10} {'Est.Value':>10} {'Score':>6} {'Profit':>10}")
        print(f"  {'-'*15} {'-'*25} {'-'*5} {'-'*10} {'-'*10} {'-'*6} {'-'*10}")
        for r in top:
            est = r[4] if r[4] else 0
            score = r[5] if r[5] else 0
            profit = r[6] if r[6] else 0
            print(f"  {r[0] or '':15} {r[1] or '':25} {r[2] or '':>5} "
                  f"€{r[3]:>9,.0f} €{est:>9,.0f} {score:>5.1f} €{profit:>9,.0f}")
    
    conn.close()
    print("\n✅ Cleanup complete!")


if __name__ == "__main__":
    main()
