"""
Check backup data quality
"""
import sqlite3
from pathlib import Path

backup_db = Path("autodeal_backup_2026-04-20.db")

if backup_db.exists():
    print(f"Checking backup data quality: {backup_db}")
    print("=" * 60)
    
    conn = sqlite3.connect(backup_db)
    cursor = conn.cursor()
    
    # Data quality checks
    print("\n1. MISSING DATA CHECKS")
    print("-" * 60)
    
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE brand IS NULL OR brand = '';")
    missing_brand = cursor.fetchone()[0]
    print(f"Missing brand: {missing_brand} ({missing_brand/982*100:.1f}%)")
    
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE model IS NULL OR model = '';")
    missing_model = cursor.fetchone()[0]
    print(f"Missing model: {missing_model} ({missing_model/982*100:.1f}%)")
    
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE title IS NULL OR title = '';")
    missing_title = cursor.fetchone()[0]
    print(f"Missing title: {missing_title} ({missing_title/982*100:.1f}%)")
    
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE km IS NULL;")
    missing_km = cursor.fetchone()[0]
    print(f"Missing KM: {missing_km} ({missing_km/982*100:.1f}%)")
    
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE url IS NULL OR url = '';")
    missing_url = cursor.fetchone()[0]
    print(f"Missing URL: {missing_url} ({missing_url/982*100:.1f}%)")
    
    # 2. Price validation
    print("\n2. PRICE VALIDATION")
    print("-" * 60)
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE price < 100;")
    too_low = cursor.fetchone()[0]
    print(f"Price < €100: {too_low}")
    
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE price > 1000000;")
    too_high = cursor.fetchone()[0]
    print(f"Price > €1M: {too_high}")
    
    cursor.execute("SELECT COUNT(*) FROM vehicles WHERE price IS NULL;")
    null_price = cursor.fetchone()[0]
    print(f"Null price: {null_price}")
    
    # 3. Source/URL mismatch
    print("\n3. SOURCE/URL MISMATCH")
    print("-" * 60)
    cursor.execute("SELECT source, url FROM vehicles WHERE url IS NOT NULL;")
    rows = cursor.fetchall()
    
    mismatches = []
    for source, url in rows:
        if source == "OLX" and "standvirtual.com" in url.lower():
            mismatches.append((source, url))
        elif source == "STANDVIRTUAL" and "olx.pt" in url.lower():
            mismatches.append((source, url))
    
    print(f"Source/URL mismatches: {len(mismatches)}")
    if len(mismatches) > 0:
        print("Sample mismatches:")
        for source, url in mismatches[:3]:
            print(f"  {source}: {url[:80]}...")
    
    # 4. Duplicate detection
    print("\n4. DUPLICATE DETECTION")
    print("-" * 60)
    cursor.execute("SELECT url, COUNT(*) FROM vehicles GROUP BY url HAVING COUNT(*) > 1;")
    duplicates = cursor.fetchall()
    print(f"Duplicate URLs: {len(duplicates)}")
    
    cursor.execute("SELECT source_id, COUNT(*) FROM vehicles GROUP BY source_id HAVING COUNT(*) > 1;")
    dup_source_id = cursor.fetchall()
    print(f"Duplicate source_ids: {len(dup_source_id)}")
    
    # 5. Sample complete records
    print("\n5. SAMPLE COMPLETE RECORDS")
    print("-" * 60)
    cursor.execute("SELECT * FROM vehicles WHERE brand IS NOT NULL AND brand != '' AND model IS NOT NULL AND model != '' LIMIT 3;")
    complete = cursor.fetchall()
    print(f"Complete records (brand+model): {len(complete)}")
    
    if len(complete) > 0:
        columns = [description[0] for description in cursor.description]
        for i, row in enumerate(complete, 1):
            print(f"\nComplete Vehicle {i}:")
            for col, val in zip(columns[:15], row[:15]):
                print(f"  {col}: {val}")
    
    # 6. Scraping logs
    print("\n6. SCRAPING LOGS")
    print("-" * 60)
    cursor.execute("SELECT source, status, listings_found, finished_at FROM scraping_logs ORDER BY finished_at DESC LIMIT 5;")
    logs = cursor.fetchall()
    print(f"Recent scraping logs:")
    for source, status, listings, finished in logs:
        print(f"  {source}: {status} - {listings} listings at {finished}")
    
    conn.close()
else:
    print(f"Backup database not found: {backup_db}")
