#!/usr/bin/env python3
"""
Script de verificação da organização do projeto
Testa se todas as importações essenciais funcionam após a limpeza
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("VERIFICAÇÃO DA ORGANIZAÇÃO - AutoDeal IA Hunter")
print("=" * 70)
print()

errors = []
warnings = []
success = []

def test_import(name, import_statement):
    """Testa uma importação"""
    try:
        exec(import_statement)
        success.append(f"✅ {name}")
        return True
    except Exception as e:
        errors.append(f"❌ {name}: {e}")
        return False

# 1. Testar configurações
print("[1/6] Testando configurações...")
test_import("Config", "from config import settings")
print()

# 2. Testar database
print("[2/6] Testando database...")
test_import("Database", "from database.db import init_db, get_db_context")
test_import("Models", "from database.models import Vehicle, Source")
print()

# 3. Testar scrapers (apenas os essenciais)
print("[3/6] Testando scrapers (apenas os 6 essenciais)...")
test_import("OLX Scraper", "from scrapers.olx_scraper_final import OLXScraper")
test_import("Standvirtual Scraper", "from scrapers.standvirtual_scraper_final import StandvirtualScraper")
test_import("AutoSapo Scraper", "from scrapers.autosapo_scraper_final import AutoSapoScraper")
print()

# 4. Testar utils essenciais
print("[4/6] Testando utils essenciais...")
test_import("Logging", "from utils.logging_config import setup_logging")
test_import("Health Check", "from utils.health_check import get_system_health")
test_import("Production Safeguards", "from utils.production_safeguards import setup_signal_handlers")
test_import("Retry", "from utils.retry import retry_network")
print()

# 5. Testar valuation
print("[5/6] Testando valuation...")
test_import("Train Model", "from valuation.train_model import train_model")
test_import("Predict", "from valuation.predict import update_vehicle_valuations")
print()

# 6. Testar ai_agent
print("[6/6] Testando ai_agent...")
test_import("Deal Finder", "from ai_agent.deal_finder import DealFinder")
print()

# Resumo
print("=" * 70)
print("RESUMO DA VERIFICAÇÃO")
print("=" * 70)
print()

if success:
    print(f"✅ {len(success)} componentes funcionando:")
    for s in success[:10]:  # Mostrar apenas primeiros 10
        print(f"   {s}")
    if len(success) > 10:
        print(f"   ... e mais {len(success) - 10} componentes")
print()

if warnings:
    print(f"⚠️  {len(warnings)} avisos:")
    for w in warnings:
        print(f"   {w}")
print()

if errors:
    print(f"❌ {len(errors)} erros encontrados:")
    for e in errors:
        print(f"   {e}")
print()

# Status final
if not errors:
    print("=" * 70)
    print("✅ SISTEMA ORGANIZADO E FUNCIONAL!")
    print("=" * 70)
    print()
    print("O projeto está limpo, organizado e pronto para uso.")
    print()
    print("Próximos passos:")
    print("   1. python main.py init")
    print("   2. python main.py scrape --source olx --max-listings 5")
    print("   3. python main.py dashboard")
    sys.exit(0)
else:
    print("=" * 70)
    print("❌ ALGUNS ERROS FORAM ENCONTRADOS")
    print("=" * 70)
    print()
    print("Verifique os erros acima e corrija antes de prosseguir.")
    sys.exit(1)
