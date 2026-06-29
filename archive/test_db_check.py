#!/usr/bin/env python3
"""
Quick database verification script
"""
import sqlite3
import sys
from pathlib import Path

def check_database():
    """Check database tables and sample data"""
    db_path = Path("autodeal.db")
    
    if not db_path.exists():
        print("Database file does not exist")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables found: {tables}")
        
        # Check vehicles table if exists
        if any('vehicles' in table[0] for table in tables):
            cursor.execute("SELECT COUNT(*) FROM vehicles")
            vehicle_count = cursor.fetchone()[0]
            print(f"Vehicles in database: {vehicle_count}")
            
            if vehicle_count > 0:
                cursor.execute("SELECT source, brand, model, year, price FROM vehicles LIMIT 3")
                sample_vehicles = cursor.fetchall()
                print("Sample vehicles:")
                for vehicle in sample_vehicles:
                    print(f"  {vehicle}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Database error: {e}")
        return False

if __name__ == "__main__":
    check_database()
