"""
Scraping Engine Reality Check - Verify each source's real extraction success
"""
import sqlite3
from pathlib import Path

print("=" * 80)
print("SCRAPING ENGINE REALITY CHECK")
print("=" * 80)

db_path = Path("d:/VER PRECOS/autodeal.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Check scraping logs for each source
print("\n[1] Scraping Logs Analysis")
print("-" * 80)

cursor.execute("""
    SELECT source, 
           COUNT(*) as total_runs,
           SUM(listings_found) as total_found,
           SUM(listings_added) as total_added,
           AVG(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success_rate
    FROM scraping_logs
    GROUP BY source
""")

sources_stats = cursor.fetchall()
if sources_stats:
    print("Source Performance:")
    for source, runs, found, added, success_rate in sources_stats:
        print(f"  {source}:")
        print(f"    Runs: {runs}")
        print(f"    Total found: {found}")
        print(f"    Total added: {added}")
        print(f"    Success rate: {success_rate*100:.1f}%")
        print(f"    Addition rate: {added/found*100 if found > 0 else 0:.1f}% of found")
else:
    print("❌ No scraping logs found")

# 2. Check data quality by source
print("\n[2] Data Quality by Source")
print("-" * 80)

cursor.execute("""
    SELECT source, 
           COUNT(*) as total,
           COUNT(CASE WHEN brand IS NOT NULL AND brand != '' THEN 1 END) as has_brand,
           COUNT(CASE WHEN model IS NOT NULL AND model != '' THEN 1 END) as has_model,
           COUNT(CASE WHEN year IS NOT NULL THEN 1 END) as has_year,
           COUNT(CASE WHEN km IS NOT NULL THEN 1 END) as has_km,
           COUNT(CASE WHEN price IS NOT NULL AND price > 0 THEN 1 END) as has_price,
           COUNT(CASE WHEN description IS NOT NULL AND description != '' THEN 1 END) as has_description,
           COUNT(CASE WHEN images IS NOT NULL AND json_array_length(images) > 0 THEN 1 END) as has_images
    FROM vehicles
    GROUP BY source
""")

for row in cursor.fetchall():
    source, total, has_brand, has_model, has_year, has_km, has_price, has_desc, has_images = row
    print(f"\n{source}:")
    print(f"  Total vehicles: {total}")
    print(f"  Has brand: {has_brand}/{total} ({has_brand/total*100:.1f}%)")
    print(f"  Has model: {has_model}/{total} ({has_model/total*100:.1f}%)")
    print(f"  Has year: {has_year}/{total} ({has_year/total*100:.1f}%)")
    print(f"  Has km: {has_km}/{total} ({has_km/total*100:.1f}%)")
    print(f"  Has valid price: {has_price}/{total} ({has_price/total*100:.1f}%)")
    print(f"  Has description: {has_desc}/{total} ({has_desc/total*100:.1f}%)")
    print(f"  Has images: {has_images}/{total} ({has_images/total*100:.1f}%)")

# 3. Check for duplicate URLs (indicates scraping issues)
print("\n[3] Duplicate Detection")
print("-" * 80)

cursor.execute("""
    SELECT url, COUNT(*) as count
    FROM vehicles
    GROUP BY url
    HAVING COUNT(*) > 1
    LIMIT 10
""")

duplicates = cursor.fetchall()
if duplicates:
    print(f"⚠️  Found {len(duplicates)} duplicate URLs (sample):")
    for url, count in duplicates:
        print(f"  {url[:80]}... ({count} copies)")
else:
    print("✓ No duplicate URLs found")

# 4. Check URL validity
print("\n[4] URL Validity Check")
print("-" * 80)

cursor.execute("""
    SELECT source, COUNT(*)
    FROM vehicles
    WHERE url NOT LIKE 'http%'
    GROUP BY source
""")

invalid_urls = cursor.fetchall()
if invalid_urls:
    print(f"❌ Invalid URLs found:")
    for source, count in invalid_urls:
        print(f"  {source}: {count} invalid URLs")
else:
    print("✓ All URLs are valid HTTP/HTTPS")

# 5. Check recent scraping activity
print("\n[5] Recent Scraping Activity")
print("-" * 80)

cursor.execute("""
    SELECT source, started_at, finished_at, status, listings_found, listings_added
    FROM scraping_logs
    ORDER BY started_at DESC
    LIMIT 20
""")

recent_scrapes = cursor.fetchall()
if recent_scrapes:
    print("Last 20 scraping operations:")
    for source, started, finished, status, found, added in recent_scrapes:
        print(f"  {source} | {started} | {status} | Found: {found} | Added: {added}")
else:
    print("❌ No recent scraping activity")

# 6. Check which sources are actually contributing
print("\n[6] Source Contribution Analysis")
print("-" * 80)

cursor.execute("""
    SELECT source, 
           COUNT(*) as total,
           MIN(first_seen) as first_seen,
           MAX(first_seen) as last_seen,
           COUNT(CASE WHEN datetime(first_seen) > datetime('now', '-7 days') THEN 1 END) as last_7_days
    FROM vehicles
    GROUP BY source
""")

for row in cursor.fetchall():
    source, total, first, last, recent = row
    print(f"{source}:")
    print(f"  Total: {total}")
    print(f"  First seen: {first}")
    print(f"  Last seen: {last}")
    print(f"  Last 7 days: {recent}")

# 7. Check for missing sources (AutoSapo, CustoJusto)
print("\n[7] Missing Sources Check")
print("-" * 80)

expected_sources = ['OLX', 'STANDVIRTUAL', 'AUTOSAPO', 'CUSTOJUSTO']
cursor.execute("SELECT DISTINCT source FROM vehicles")
actual_sources = [row[0] for row in cursor.fetchall()]

for source in expected_sources:
    if source in actual_sources:
        print(f"✓ {source} - Active")
    else:
        print(f"❌ {source} - NOT SCRAPING")

conn.close()

print("\n" + "=" * 80)
