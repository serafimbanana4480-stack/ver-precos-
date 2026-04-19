#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
System test script - Verifies all imports and basic functionality
Run with: python test_system.py
"""
import sys
from pathlib import Path

# Add project root to path (parent of tests directory)
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("AutoDeal IA Hunter - System Test")
print("=" * 60)
print()

errors = []
warnings = []

# Test 1: Config import
print("[TEST 1] Testing config import...")
try:
    from config import settings
    print("  [OK] Config imported successfully")
    print(f"  [OK] Database URL: {settings.database_url}")
    print(f"  [OK] Sentry DSN: {'Set' if settings.sentry_dsn else 'Not set (optional)'}")
except Exception as e:
    errors.append(f"Config import failed: {e}")
    print(f"  [FAIL] Config import failed: {e}")

print()

# Test 2: Database import
print("[TEST 2] Testing database import...")
try:
    from database.db import init_db, get_db_context
    from database.models import Vehicle, Source
    print("  [OK] Database module imported successfully")
except Exception as e:
    errors.append(f"Database import failed: {e}")
    print(f"  [FAIL] Database import failed: {e}")

print()

# Test 3: Scraper imports
print("[TEST 3] Testing scraper imports...")
try:
    from scrapers.olx_scraper import OLXScraper
    print("  [OK] OLX scraper imported successfully")
except Exception as e:
    errors.append(f"OLX scraper import failed: {e}")
    print(f"  [FAIL] OLX scraper import failed: {e}")

try:
    from scrapers.standvirtual_scraper import StandvirtualScraper
    print("  [OK] Standvirtual scraper imported successfully")
except Exception as e:
    errors.append(f"Standvirtual scraper import failed: {e}")
    print(f"  [FAIL] Standvirtual scraper import failed: {e}")

try:
    from scrapers.autosapo_scraper import AutoSapoScraper
    print("  [OK] AutoSapo scraper imported successfully")
except Exception as e:
    errors.append(f"AutoSapo scraper import failed: {e}")
    print(f"  [FAIL] AutoSapo scraper import failed: {e}")

print()

# Test 4: Utils imports
print("[TEST 4] Testing utils imports...")
try:
    from utils.production_safeguards import setup_signal_handlers, validate_environment, get_health_check_summary
    print("  [OK] Production safeguards imported successfully")
except Exception as e:
    errors.append(f"Production safeguards import failed: {e}")
    print(f"  [FAIL] Production safeguards import failed: {e}")

try:
    from utils.health_check import get_system_health
    print("  [OK] Health check imported successfully")
except Exception as e:
    errors.append(f"Health check import failed: {e}")
    print(f"  [FAIL] Health check import failed: {e}")

try:
    from utils.logging_config import setup_logging
    print("  [OK] Logging config imported successfully")
except Exception as e:
    errors.append(f"Logging config import failed: {e}")
    print(f"  [FAIL] Logging config import failed: {e}")

print()

# Test 5: Validation imports
print("[TEST 5] Testing validation imports...")
try:
    from validation.cli_models import ScrapeArgs, TrainArgs, FindDealsArgs, ValuateArgs, DashboardArgs
    print("  [OK] CLI models imported successfully")
except Exception as e:
    errors.append(f"CLI models import failed: {e}")
    print(f"  [FAIL] CLI models import failed: {e}")

print()

# Test 6: AI Agent imports
print("[TEST 6] Testing AI agent imports...")
try:
    from ai_agent.deal_finder import DealFinder
    print("  [OK] Deal finder imported successfully")
except Exception as e:
    warnings.append(f"Deal finder import failed: {e}")
    print(f"  [WARN] Deal finder import failed: {e}")

print()

# Test 7: Valuation imports
print("[TEST 7] Testing valuation imports...")
try:
    from valuation.train_model import train_model
    from valuation.predict import update_vehicle_valuations
    print("  [OK] Valuation module imported successfully")
except Exception as e:
    warnings.append(f"Valuation import failed: {e}")
    print(f"  [WARN] Valuation import failed: {e}")

print()

# Summary
print("=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print()

if errors:
    print(f"❌ ERRORS: {len(errors)} critical errors found:")
    for error in errors:
        print(f"   - {error}")
    print()

if warnings:
    print(f"⚠️  WARNINGS: {len(warnings)} non-critical warnings:")
    for warning in warnings:
        print(f"   - {warning}")
    print()

if not errors and not warnings:
    print("✅ ALL TESTS PASSED!")
    print("   The system is ready to run.")
    print()
    print("Next steps:")
    print("   1. Run: python main.py init")
    print("   2. Run: python main.py scrape --source olx --max-listings 5")
    print("   3. Run: python main.py dashboard")
    sys.exit(0)
elif not errors:
    print("✅ SYSTEM READY (with warnings)")
    print("   The core system is functional.")
    print()
    sys.exit(0)
else:
    print("❌ SYSTEM NOT READY")
    print("   Please fix the errors above before running the system.")
    sys.exit(1)
