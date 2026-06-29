"""
Production Validation Script - Audit AutoDeal IA Hunter
Checks for real data vs fake/simulated components
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("PRODUCTION VALIDATION AUDIT - AutoDeal IA Hunter")
print("=" * 80)

# 1. DATABASE VALIDATION
print("\n[1] DATABASE VALIDATION")
print("-" * 80)

db_path = Path("d:/VER PRECOS/autodeal.db")
if not db_path.exists():
    print("❌ CRITICAL: Database file does not exist!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Total vehicles
cursor.execute("SELECT COUNT(*) FROM vehicles")
total_vehicles = cursor.fetchone()[0]
print(f"Total vehicles in database: {total_vehicles}")

if total_vehicles == 0:
    print("❌ CRITICAL: No vehicles in database - NO REAL DATA")
else:
    print(f"✓ Database contains {total_vehicles} vehicles")

# By source
cursor.execute("SELECT source, COUNT(*) FROM vehicles GROUP BY source")
sources = cursor.fetchall()
print("\nVehicles by source:")
for source, count in sources:
    status = "✓" if count > 0 else "❌"
    print(f"  {status} {source}: {count}")

# Check for estimated values
cursor.execute("SELECT COUNT(*) FROM vehicles WHERE estimated_value IS NOT NULL")
with_estimated = cursor.fetchone()[0]
print(f"\nVehicles with estimated_value: {with_estimated}/{total_vehicles} ({with_estimated/total_vehicles*100:.1f}%)")

# Check for deal scores
cursor.execute("SELECT COUNT(*) FROM vehicles WHERE deal_score IS NOT NULL")
with_score = cursor.fetchone()[0]
print(f"Vehicles with deal_score: {with_score}/{total_vehicles} ({with_score/total_vehicles*100:.1f}%)")

# Check for AI reviews
cursor.execute("SELECT COUNT(*) FROM vehicles WHERE ai_review IS NOT NULL")
with_ai = cursor.fetchone()[0]
print(f"Vehicles with AI review: {with_ai}/{total_vehicles} ({with_ai/total_vehicles*100:.1f}%)")

# Check for condition scores (vision analysis)
cursor.execute("SELECT COUNT(*) FROM vehicles WHERE condition_score IS NOT NULL")
with_vision = cursor.fetchone()[0]
print(f"Vehicles with condition_score (vision): {with_vision}/{total_vehicles} ({with_vision/total_vehicles*100:.1f}%)")

# Sample real data
cursor.execute("SELECT brand, model, year, price, km, source, url FROM vehicles LIMIT 5")
samples = cursor.fetchall()
print(f"\nSample of {len(samples)} real listings:")
for i, (brand, model, year, price, km, source, url) in enumerate(samples, 1):
    print(f"  {i}. {brand} {model} {year} - €{price} - {km}km - {source}")
    print(f"     URL: {url[:80]}..." if len(url) > 80 else f"     URL: {url}")

# Check for fake data patterns
cursor.execute("SELECT COUNT(*) FROM vehicles WHERE url LIKE '%example%' OR url LIKE '%test%'")
fake_urls = cursor.fetchone()[0]
if fake_urls > 0:
    print(f"⚠️  WARNING: {fake_urls} vehicles with example/test URLs detected")

cursor.execute("SELECT COUNT(*) FROM vehicles WHERE price = 0 OR price IS NULL")
zero_prices = cursor.fetchone()[0]
if zero_prices > 0:
    print(f"⚠️  WARNING: {zero_prices} vehicles with zero/null prices")

conn.close()

# 2. ML MODEL VALIDATION
print("\n[2] ML MODEL VALIDATION")
print("-" * 80)

models_dir = Path("d:/VER PRECOS/models")
model_files = list(models_dir.glob("*.json")) + list(models_dir.glob("*.joblib"))

if not model_files:
    print("❌ CRITICAL: No ML model files found")
else:
    print(f"Model files found: {len(model_files)}")
    for f in model_files:
        print(f"  ✓ {f.name}: {f.stat().st_size:,} bytes")

metrics_file = models_dir / "model_metrics.json"
if metrics_file.exists():
    with open(metrics_file) as f:
        metrics = json.load(f)
    print(f"\nModel metrics:")
    print(f"  Training date: {metrics.get('training_date', 'N/A')}")
    print(f"  Samples: {metrics.get('n_samples', 'N/A')}")
    print(f"  MAE: €{metrics.get('mae', 'N/A'):.2f}")
    print(f"  RMSE: €{metrics.get('rmse', 'N/A'):.2f}")
    print(f"  R²: {metrics.get('r2', 'N/A'):.4f}")
    
    if metrics.get('rejected'):
        print(f"  ❌ MODEL REJECTED: {metrics.get('reason', 'Unknown')}")
    else:
        print(f"  ✓ Model accepted for production")
else:
    print("❌ No model_metrics.json - model may not be trained")

# 3. LOG VALIDATION
print("\n[3] LOG VALIDATION")
print("-" * 80)

logs_dir = Path("d:/VER PRECOS/logs")
if logs_dir.exists():
    log_files = list(logs_dir.glob("*.log")) + list(logs_dir.glob("*.txt"))
    print(f"Log files found: {len(log_files)}")
    for f in log_files:
        print(f"  {f.name}: {f.stat().st_size:,} bytes")
    
    # Check recent activity
    autodeal_log = logs_dir / "autodeal.log"
    if autodeal_log.exists():
        with open(autodeal_log, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        print(f"\nLast 10 log entries:")
        for line in lines[-10:]:
            print(f"  {line.strip()}")
else:
    print("❌ No logs directory found")

# 4. SCRAPING LOGS VALIDATION
print("\n[4] SCRAPING LOGS VALIDATION")
print("-" * 80)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT source, started_at, finished_at, status, listings_found, listings_added FROM scraping_logs ORDER BY started_at DESC LIMIT 10")
scrape_logs = cursor.fetchall()

if scrape_logs:
    print(f"Recent scraping operations:")
    for source, started, finished, status, found, added in scrape_logs:
        print(f"  {source} | {started} | {status} | Found: {found} | Added: {added}")
else:
    print("❌ No scraping logs found - may indicate no real scraping executed")

conn.close()

# 5. AI REVIEWS VALIDATION
print("\n[5] AI REVIEWS VALIDATION")
print("-" * 80)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM ai_reviews")
ai_reviews_count = cursor.fetchone()[0]
print(f"Total AI reviews in database: {ai_reviews_count}")

if ai_reviews_count > 0:
    cursor.execute("SELECT review_type, model_used, approval, score FROM ai_reviews LIMIT 5")
    reviews = cursor.fetchall()
    print(f"\nSample AI reviews:")
    for review_type, model, approval, score in reviews:
        print(f"  Type: {review_type} | Model: {model} | Approved: {approval} | Score: {score}")
else:
    print("❌ No AI reviews found - AI analysis may not be running")

conn.close()

# 6. SUMMARY
print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

critical_failures = []
warnings = []

if total_vehicles == 0:
    critical_failures.append("No vehicles in database - NO REAL DATA")
if with_estimated == 0:
    critical_failures.append("No estimated values - pricing engine not working")
if with_score == 0:
    warnings.append("No deal scores calculated")
if with_ai == 0:
    warnings.append("No AI reviews performed")
if with_vision == 0:
    warnings.append("No vision analysis performed")
if not model_files:
    critical_failures.append("No ML model files - ML system not operational")
if not scrape_logs:
    critical_failures.append("No scraping logs - scraping may never have run")

print(f"\nCritical Failures: {len(critical_failures)}")
for failure in critical_failures:
    print(f"  ❌ {failure}")

print(f"\nWarnings: {len(warnings)}")
for warning in warnings:
    print(f"  ⚠️  {warning}")

print("\n" + "=" * 80)
