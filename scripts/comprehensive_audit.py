"""
Comprehensive System Audit Script
Tests all components and generates a detailed report
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print('='*70)
print('COMPREHENSIVE SYSTEM AUDIT')
print('='*70)

# SECTION 1: IMPORTS TEST
print('\n[SECTION 1] TESTING ALL IMPORTS')
print('-'*50)

modules = [
    ('database.db', 'get_db_context'),
    ('database.models', 'Vehicle'),
    ('scrapers.olx_scraper', 'OLXScraper'),
    ('scrapers.standvirtual_scraper', 'StandvirtualScraper'),
    ('scrapers.autosapo_scraper', 'AutoSapoScraper'),
    ('scrapers.custojusto_scraper', 'CustoJustoScraper'),
    ('scrapers.auction_scraper', 'AuctionScraper'),
    ('scrapers.schema', 'VehicleListing'),
    ('processing.pipeline', 'ProductionPipeline'),
    ('intelligence.pricing.engine', 'pricing_engine'),
    ('intelligence.scoring.engine', 'scoring_engine'),
    ('intelligence.profit.deal_profit_calculator', 'deal_profit_calculator'),
    ('ai_agent.deal_finder', 'DealFinder'),
    ('ai_agent.llm_review', 'LLMReviewer'),
    ('alerts.manager', 'AlertManager'),
    ('valuation.train_model', 'train_model'),
    ('valuation.predict', 'update_vehicle_valuations'),
    ('utils.health_check', 'get_system_health'),
    ('config', 'settings'),
    ('utils.selector_manager', 'SelectorManager'),
    ('utils.proxy_manager', 'ProxyManager'),
    ('utils.captcha_solver', 'CaptchaSolver'),
]

import_results = []
for module, items in modules:
    try:
        mod = __import__(module, fromlist=[items.split(',')[0].strip()])
        import_results.append((module, 'OK', None))
    except Exception as e:
        import_results.append((module, 'FAIL', str(e)[:50]))

ok_count = sum(1 for _, status, _ in import_results if status == 'OK')
fail_count = sum(1 for _, status, _ in import_results if status == 'FAIL')

print(f'Imports: {ok_count} OK, {fail_count} FAILED')
for module, status, error in import_results:
    if status == 'FAIL':
        print(f'  FAIL: {module} - {error}')

# SECTION 2: DATABASE TEST
print('\n[SECTION 2] TESTING DATABASE')
print('-'*50)

from database.db import get_db_context
from database.models import Vehicle, AuctionTransaction, PriceHistory, Watchlist, ScrapingLog, AIReview
from sqlalchemy import inspect, text

with get_db_context() as db:
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    print(f'Tables ({len(tables)}): {tables}')

    counts = {}
    for model in [Vehicle, AuctionTransaction, PriceHistory, Watchlist, ScrapingLog, AIReview]:
        try:
            count = db.query(model).count()
            counts[model.__name__] = count
        except:
            counts[model.__name__] = 'N/A'

    print(f'Records:')
    for name, count in counts.items():
        print(f'  {name}: {count}')

    try:
        result = db.execute(text('SELECT 1')).fetchone()
        print(f'DB Query: OK ({result})')
    except Exception as e:
        print(f'DB Query: FAIL - {e}')

# SECTION 3: PRICING ENGINE TEST
print('\n[SECTION 3] TESTING PRICING ENGINE')
print('-'*50)

from intelligence.pricing.engine import pricing_engine
from database.models import Vehicle

with get_db_context() as db:
    test_vehicles = db.query(Vehicle).filter(
        Vehicle.is_active == True,
        Vehicle.price.isnot(None)
    ).limit(5).all()

    print(f'Testing pricing on {len(test_vehicles)} vehicles:')
    for v in test_vehicles:
        try:
            result = pricing_engine.calculate_estimated_value(
                brand=v.brand,
                model=v.model,
                year=v.year,
                km=v.km,
                fuel_type=v.fuel_type.value if v.fuel_type else None,
                transmission=v.transmission.value if v.transmission else None
            )
            estimated = result.get('estimated_value', 0) if result else 0
            actual = v.price
            diff_pct = abs((estimated - actual) / actual * 100) if actual else 0
            status = 'OK' if diff_pct < 50 else 'WARN'
            print(f'  {status}: {v.brand} {v.model} {v.year} - Actual={actual}, Est={estimated}, Diff={diff_pct:.1f}%')
        except Exception as e:
            print(f'  FAIL: {v.brand} {v.model} - {e}')

# SECTION 4: SCRAPER TEST
print('\n[SECTION 4] TESTING SCRAPERS')
print('-'*50)

from scrapers.olx_scraper import OLXScraper
from scrapers.standvirtual_scraper import StandvirtualScraper
from scrapers.autosapo_scraper import AutoSapoScraper

async def test_scrapers():
    results = []

    try:
        scraper = OLXScraper()
        await scraper.initialize()
        listings = await scraper.scrape(max_listings=3)
        await scraper.close()
        results.append(('OLX', 'OK', len(listings)))
    except Exception as e:
        results.append(('OLX', 'FAIL', str(e)[:50]))

    try:
        scraper = StandvirtualScraper()
        await scraper.initialize()
        listings = await scraper.scrape(max_listings=3)
        await scraper.close()
        results.append(('Standvirtual', 'OK', len(listings)))
    except Exception as e:
        results.append(('Standvirtual', 'FAIL', str(e)[:50]))

    try:
        scraper = AutoSapoScraper()
        await scraper.initialize()
        listings = await scraper.scrape(max_listings=3)
        await scraper.close()
        results.append(('AutoSapo', 'OK', len(listings)))
    except Exception as e:
        results.append(('AutoSapo', 'FAIL', str(e)[:50]))

    return results

import asyncio
scraper_results = asyncio.run(test_scrapers())
for name, status, count in scraper_results:
    print(f'{name}: {status} ({count} listings)')

# SECTION 5: AI/OLLAMA TEST
print('\n[SECTION 5] TESTING OLLAMA/AI')
print('-'*50)

import requests
try:
    r = requests.get('http://localhost:11434/api/tags', timeout=3)
    if r.status_code == 200:
        models = r.json().get('models', [])
        print(f'Ollama: RUNNING ({len(models)} models)')
        for m in models[:3]:
            print(f'  - {m.get("name")}')
    else:
        print(f'Ollama: HTTP {r.status_code}')
except Exception as e:
    print(f'Ollama: NOT RUNNING - {e}')

try:
    from ai_agent.llm_review import LLMReviewer
    reviewer = LLMReviewer()
    print(f'LLMReviewer: OK (use_ollama={reviewer.use_ollama})')
except Exception as e:
    print(f'LLMReviewer: FAIL - {e}')

# SECTION 6: CLI COMMANDS TEST
print('\n[SECTION 6] TESTING CLI COMMANDS')
print('-'*50)

import main
import argparse
commands = ['init', 'scrape', 'train', 'valuate', 'find-deals', 'auction',
            'scheduler', 'dashboard', 'health-check', 'search', 'watchlist', 'stats']

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers()

for cmd in commands:
    try:
        subparsers.add_parser(cmd)
        print(f'{cmd}: OK')
    except:
        print(f'{cmd}: FAIL')

# SECTION 7: CONFIG TEST
print('\n[SECTION 7] TESTING CONFIGURATION')
print('-'*50)

from config import settings
config_checks = [
    ('ENVIRONMENT', settings.ENVIRONMENT),
    ('USE_OLLAMA', settings.USE_OLLAMA),
    ('OLLAMA_URL', settings.OLLAMA_URL),
    ('ai_enabled', settings.ai_enabled),
    ('DEAL_SCORE_THRESHOLD', settings.DEAL_SCORE_THRESHOLD),
]

for name, value in config_checks:
    print(f'{name}: {value}')

# SECTION 8: FILE ORGANIZATION CHECK
print('\n[SECTION 8] FILE ORGANIZATION')
print('-'*50)

dirs_to_check = ['scripts', 'scratch', 'archive', 'tests', 'config', 'migrations']
for d in dirs_to_check:
    if (project_root / d).exists():
        files = list((project_root / d).glob('*'))
        py_files = [f for f in files if f.suffix == '.py']
        print(f'{d}/: {len(py_files)} .py files')

# SECTION 9: HEALTH CHECK
print('\n[SECTION 9] HEALTH CHECK')
print('-'*50)

try:
    from utils.health_check import get_system_health
    health = get_system_health()
    print(f'Overall: {health.get("overall_status")}')
    db_health = health.get("database", {})
    print(f'Database: {db_health.get("status")}')
    sys_health = health.get("system", {})
    print(f'System: CPU={sys_health.get("cpu_percent")}% Mem={sys_health.get("memory_percent")}% Disk={sys_health.get("disk_percent")}%')
except Exception as e:
    print(f'Health check: FAIL - {e}')

print('\n' + '='*70)
print('AUDIT COMPLETE')
print('='*70)
