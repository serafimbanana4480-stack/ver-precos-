#!/usr/bin/env python3
"""
Data analysis script to check for real vs fake data
"""
import sqlite3
import sys
from pathlib import Path

def analyze_vehicle_data():
    """Analyze vehicle data for authenticity"""
    db_path = Path("autodeal.db")
    
    if not db_path.exists():
        print("Database file does not exist")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        print("=" * 50)
        print("VEHICLE DATA ANALYSIS")
        print("=" * 50)
        
        # Total vehicles
        cursor.execute("SELECT COUNT(*) FROM vehicles")
        total_count = cursor.fetchone()[0]
        print(f"Total vehicles: {total_count}")
        
        # Brands distribution
        cursor.execute("SELECT brand, COUNT(*) FROM vehicles WHERE brand != '' GROUP BY brand ORDER BY COUNT(*) DESC LIMIT 10")
        brands = cursor.fetchall()
        print(f"\nTop brands: {brands}")
        
        # Price ranges
        cursor.execute("SELECT MIN(price), MAX(price), AVG(price) FROM vehicles")
        price_stats = cursor.fetchone()
        print(f"\nPrice range: {price_stats[0]:.0f} - {price_stats[1]:.0f} (avg: {price_stats[2]:.0f})")
        
        # Year distribution
        cursor.execute("SELECT MIN(year), MAX(year), AVG(year) FROM vehicles")
        year_stats = cursor.fetchone()
        print(f"\nYear range: {year_stats[0]} - {year_stats[1]} (avg: {year_stats[1]:.0f})")
        
        # Sample real data
        cursor.execute("SELECT brand, model, year, km, price, location FROM vehicles WHERE brand != '' AND model != '' LIMIT 5")
        sample_data = cursor.fetchall()
        print(f"\nSample real data:")
        for i, vehicle in enumerate(sample_data, 1):
            print(f"  {i}. {vehicle[0]} {vehicle[1]}, {vehicle[2]}, {vehicle[3]}km, {vehicle[4]:.0f} EUR, {vehicle[5]}")
        
        # Check for suspicious patterns
        cursor.execute("SELECT COUNT(*) FROM vehicles WHERE brand = '' OR model = ''")
        empty_brand_model = cursor.fetchone()[0]
        print(f"\nVehicles with empty brand/model: {empty_brand_model}")
        
        cursor.execute("SELECT COUNT(*) FROM vehicles WHERE price < 1000 OR price > 100000")
        suspicious_prices = cursor.fetchone()[0]
        print(f"Vehicles with suspicious prices (<1k or >100k): {suspicious_prices}")
        
        # Source distribution
        cursor.execute("SELECT source, COUNT(*) FROM vehicles GROUP BY source")
        sources = cursor.fetchall()
        print(f"\nData sources: {sources}")
        
        conn.close()
        
        # Assessment
        print("\n" + "=" * 50)
        print("DATA AUTHENTICITY ASSESSMENT")
        print("=" * 50)
        
        if total_count > 0:
            authenticity_score = 0
            
            # Check for real brands
            real_brands = ['Volkswagen', 'BMW', 'Mercedes', 'Renault', 'Peugeot', 'Opel', 'Ford', 'Toyota']
            real_brand_count = sum(1 for brand in brands if brand[0] in real_brands)
            if real_brand_count > 0:
                authenticity_score += 25
                print(f"  [+25] Found {real_brand_count} real car brands")
            
            # Check reasonable price ranges
            if 1000 <= price_stats[0] <= 50000 and price_stats[1] <= 100000:
                authenticity_score += 25
                print(f"  [+25] Reasonable price ranges")
            
            # Check year ranges
            if 1990 <= year_stats[0] <= 2024:
                authenticity_score += 25
                print(f"  [+25] Realistic year ranges")
            
            # Check data completeness
            completeness = (total_count - empty_brand_model) / total_count * 100
            if completeness > 50:
                authenticity_score += 25
                print(f"  [+25] Good data completeness ({completeness:.1f}%)")
            
            print(f"\nAUTHENTICITY SCORE: {authenticity_score}/100")
            
            if authenticity_score >= 75:
                print("  Assessment: REAL DATA - Contains authentic vehicle listings")
            elif authenticity_score >= 50:
                print("  Assessment: MIXED - Some real data, some test/fake data")
            else:
                print("  Assessment: FAKE DATA - Mostly test or fabricated data")
        
        return True
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return False

if __name__ == "__main__":
    analyze_vehicle_data()
