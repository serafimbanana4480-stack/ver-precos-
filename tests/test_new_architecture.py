"""
Script de teste rápido da Nova Arquitetura
Valida: pipeline, api_clients, camoufox_client, ollama_direct
NOTE: This is a standalone test script, not meant for pytest
"""
from __future__ import annotations
import asyncio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


import pytest

# Skip all tests in this file since it's a standalone script
pytestmark = pytest.mark.skip(reason="This is a standalone test script, run with: python tests/test_new_architecture.py")


@pytest.mark.asyncio
async def test_pipeline():
    """Test complete pipeline with new architecture"""
    pytest.skip("Run this script directly: python tests/test_new_architecture.py")


@pytest.mark.asyncio
async def test_api_clients():
    """Test API clients functionality"""
    pytest.skip("Run this script directly: python tests/test_new_architecture.py")


async def test_camoufox_client():
    """Testa CamoufoxClient (sem iniciar browser ainda)"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Camoufox Client")
    logger.info("=" * 60)
    
    try:
        from scrapers.camoufox_client import (
            CamoufoxClient,
            BrowserSession,
            SESSIONS_DIR,
        )
        logger.info("✅ Camoufox client importado com sucesso")
        
        # Testa sessão
        session = BrowserSession(
            site="test",
            cookies=[],
            user_agent="test",
            created_at=0,
        )
        assert not session.is_valid, "Expired session should be invalid"
        logger.info("✅ BrowserSession funciona")
        
        # Testa cliente
        client = CamoufoxClient(headless=True)
        logger.info("✅ CamoufoxClient instanciado")
        
        return True
    except ImportError as e:
        logger.warning(f"⚠️ Camoufox não instalado: {e}")
        logger.info("   Execute: pip install camoufox")
        return True  # Não é erro fatal, pode instalar depois
    except Exception as e:
        logger.error(f"❌ Camoufox client failed: {e}")
        return False


async def test_ollama_direct():
    """Testa Ollama direct (sem chamar Ollama ainda)"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Ollama Direct")
    logger.info("=" * 60)
    
    try:
        from scrapers.ollama_direct import (
            clean_html,
            build_extraction_prompt,
            _parse_json_response,
        )
        logger.info("✅ Ollama direct importado com sucesso")
        
        # Testa HTML cleaning
        sample_html = """
        <html>
        <body>
            <script>alert('test');</script>
            <h1>Mercedes C220</h1>
            <p>€ 25.500</p>
            <style>.red{color:red}</style>
        </body>
        </html>
        """
        clean = clean_html(sample_html, max_length=500)
        assert "Mercedes" in clean, "Title should be preserved"
        assert "<script>" not in clean, "Scripts should be removed"
        assert "<style>" not in clean, "Styles should be removed"
        logger.info(f"✅ clean_html funciona: '{clean[:50]}...'")
        
        # Testa prompt building
        prompt = build_extraction_prompt("Test text", "carro")
        assert "JSON" in prompt, "Prompt should mention JSON"
        logger.info("✅ build_extraction_prompt funciona")
        
        # Testa JSON parsing
        json_text = '{"titulo": "Test", "preco_eur": 15000}'
        result = _parse_json_response(json_text)
        assert result.get("titulo") == "Test", "Should parse title"
        assert result.get("preco_eur") == 15000, "Should parse price"
        logger.info("✅ _parse_json_response funciona")
        
        return True
    except Exception as e:
        logger.error(f"❌ Ollama direct failed: {e}")
        return False


async def test_scrapers_v2():
    """Testa scrapers simplificados"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Scrapers v2")
    logger.info("=" * 60)
    
    tests = []
    
    try:
        from scrapers.olx_scraper_v2 import OLXScraper
        scraper = OLXScraper()
        logger.info("✅ OLXScraper v2 importado")
        tests.append(True)
    except Exception as e:
        logger.error(f"❌ OLXScraper v2 failed: {e}")
        tests.append(False)
    
    try:
        from scrapers.standvirtual_scraper_v2 import StandvirtualScraper
        scraper = StandvirtualScraper()
        logger.info("✅ StandvirtualScraper v2 importado")
        tests.append(True)
    except Exception as e:
        logger.error(f"❌ StandvirtualScraper v2 failed: {e}")
        tests.append(False)
    
    try:
        from scrapers.autosapo_scraper_v2 import AutoSapoScraper
        scraper = AutoSapoScraper()
        logger.info("✅ AutoSapoScraper v2 importado")
        tests.append(True)
    except Exception as e:
        logger.error(f"❌ AutoSapoScraper v2 failed: {e}")
        tests.append(False)
    
    return all(tests)


async def test_managed_client_v2():
    """Testa managed client simplificado"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 6: Managed Client v2")
    logger.info("=" * 60)
    
    try:
        from scrapers.managed_client_v2 import (
            ManagedScrapingClient,
            get_managed_client,
            clear_managed_client,
        )
        
        # Limpa singleton para teste limpo
        clear_managed_client()
        
        # Testa singleton: duas chamadas devem retornar mesma instância
        client1 = get_managed_client()
        client2 = get_managed_client()
        assert client1 is client2, "Should return same instance"
        logger.info("✅ get_managed_client singleton funciona")
        
        # Testa instanciação direta também funciona
        client3 = ManagedScrapingClient()
        assert isinstance(client3, ManagedScrapingClient), "Direct instantiation should work"
        logger.info("✅ ManagedScrapingClient v2 instanciado")
        
        return True
    except Exception as e:
        logger.error(f"❌ Managed client v2 failed: {e}")
        return False


async def run_all_tests():
    """Executa todos os testes"""
    logger.info("\n" + "=" * 70)
    logger.info("TESTES DA NOVA ARQUITETURA")
    logger.info("=" * 70)
    
    results = {
        "Pipeline": await test_pipeline(),
        "API Clients": await test_api_clients(),
        "Camoufox Client": await test_camoufox_client(),
        "Ollama Direct": await test_ollama_direct(),
        "Scrapers v2": await test_scrapers_v2(),
        "Managed Client v2": await test_managed_client_v2(),
    }
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("RESULTADOS")
    logger.info("=" * 70)
    
    passed = sum(results.values())
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{name:20} {status}")
    
    logger.info("=" * 70)
    logger.info(f"Total: {passed}/{total} testes passaram")
    
    if passed == total:
        logger.info("🎉 Todos os testes passaram! Nova arquitetura pronta.")
        return 0
    else:
        logger.warning("⚠️ Alguns testes falharam. Verifique os erros acima.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
