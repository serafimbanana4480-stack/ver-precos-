#!/usr/bin/env python3
"""
Fix valuation issues in the database
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def fix_valuation_issues():
    """Fix impossible profit percentages and deal scores"""
    db_path = Path("autodeal.db")
    
    if not db_path.exists():
        print("Database file does not exist")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get vehicles with problematic valuations
        cursor.execute("""
            SELECT id, brand, model, year, km, price, estimated_value, 
                   deal_score, profit_potential, profit_percentage
            FROM vehicles 
            WHERE profit_percentage > 100 OR deal_score > 9.5
            ORDER BY profit_percentage DESC
        """)
        
        vehicles = cursor.fetchall()
        print(f"Found {len(vehicles)} vehicles with problematic valuations")
        
        for vehicle in vehicles:
            vehicle_id, brand, model, year, km, price, est_value, deal_score, profit_pot, profit_pct = vehicle
            
            print(f"\nFixing: {brand} {model} ({year})")
            print(f"  Current Price: €{price:,.2f}")
            print(f"  Est. Value: €{est_value:,.2f}")
            print(f"  Current Profit %: {profit_pct:.1f}%")
            print(f"  Current Deal Score: {deal_score}")
            
            # Recalculate realistic values
            if est_value and est_value > 0:
                # Calculate realistic profit (max 50% margin)
                max_realistic_profit_pct = 50.0
                price_diff_pct = (est_value - price) / est_value * 100
                
                # Cap the price difference
                realistic_price_diff_pct = min(price_diff_pct, max_realistic_profit_pct)
                
                # Calculate realistic resale price
                realistic_resale_price = est_value * 0.85  # 15% margin
                realistic_profit = realistic_resale_price - price
                realistic_profit_pct = (realistic_profit / price) * 100 if price > 0 else 0
                
                # Calculate realistic deal score
                if realistic_price_diff_pct <= 0:
                    realistic_deal_score = 0.0
                elif realistic_price_diff_pct < 5:
                    realistic_deal_score = 3.0
                elif realistic_price_diff_pct < 10:
                    realistic_deal_score = 5.0
                elif realistic_price_diff_pct < 15:
                    realistic_deal_score = 7.0
                elif realistic_price_diff_pct < 20:
                    realistic_deal_score = 8.0
                else:
                    realistic_deal_score = 9.0
                
                # Apply KM and year adjustments
                if km and km < 50000:
                    realistic_deal_score += 0.3
                elif km and km < 100000:
                    realistic_deal_score += 0.1
                
                if year and (2024 - year) < 3:
                    realistic_deal_score += 0.2
                
                # Cap at 10
                realistic_deal_score = min(10.0, realistic_deal_score)
                
                print(f"  New Profit %: {realistic_profit_pct:.1f}%")
                print(f"  New Deal Score: {realistic_deal_score:.1f}")
                
                # Update database
                cursor.execute("""
                    UPDATE vehicles 
                    SET estimated_value = ?, 
                        deal_score = ?, 
                        profit_potential = ?, 
                        profit_percentage = ?,
                        ai_approved = CASE WHEN ? > 5.0 THEN 1 ELSE 0 END
                    WHERE id = ?
                """, (
                    est_value,
                    realistic_deal_score,
                    realistic_profit,
                    realistic_profit_pct,
                    realistic_deal_score,
                    vehicle_id
                ))
                
                print(f"  ✅ Updated vehicle {vehicle_id}")
        
        conn.commit()
        print(f"\n✅ Fixed {len(vehicles)} vehicles")
        
        # Verify fixes
        cursor.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE profit_percentage > 100 OR deal_score > 9.5
        """)
        remaining_issues = cursor.fetchone()[0]
        
        if remaining_issues == 0:
            print("✅ All valuation issues fixed!")
        else:
            print(f"⚠️ {remaining_issues} vehicles still have issues")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    fix_valuation_issues()
