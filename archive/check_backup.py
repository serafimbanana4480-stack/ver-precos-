"""
Check backup database for data
"""
import sqlite3
from pathlib import Path

backup_db = Path("autodeal_backup_2026-04-20.db")

if backup_db.exists():
    print(f"Checking backup database: {backup_db}")
    print("=" * 60)
    
    conn = sqlite3.connect(backup_db)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"\nTables found: {[t[0] for t in tables]}")
    
    # Count vehicles
    cursor.execute("SELECT COUNT(*) FROM vehicles;")
    total = cursor.fetchone()[0]
    print(f"\nTotal vehicles in backup: {total}")
    
    # Count active vehicles
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE is_active = 1;")
    active = cursor.fetchone()[0]
    print(f"Active vehicles in backup: {active}")
    
    # Check by source
    cursor.execute("SELECT source, COUNT(*) FROM vehicles GROUP BY source;")
    sources = cursor.fetchall()
    print(f"\nVehicles by source:")
    for source, count in sources:
        print(f"  {source}: {count}")
    
    # Sample data
    cursor.execute("SELECT * FROM vehicles LIMIT 3;")
    columns = [description[0] for description in cursor.description]
    print(f"\nSample vehicle data (columns: {len(columns)}):")
    print(f"Columns: {columns[:10]}...")  # Show first 10 columns
    
    rows = cursor.fetchall()
    for i, row in enumerate(rows, 1):
        print(f"\nVehicle {i}:")
        for j, (col, val) in enumerate(zip(columns, row)):
            if j < 10:  # Show first 10 columns
                print(f"  {col}: {val}")
    
    conn.close()
else:
    print(f"Backup database not found: {backup_db}")
