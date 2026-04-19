"""
Validação Final — Arquitetura Revolucionária Otimizada
Testa todos os componentes: base, scrapers finais, pipeline
"""
from __future__ import annotations
import asyncio
import logging
import sys
from typing import List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValidationResult:
    """Resultado de um teste de validação"""
    def __init__(self, name: str, passed: bool, details: str = ""):
        self.name = name
        self.passed = passed
        self.details = details
    
    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} | {self.name} | {self.details}"


async def validate_base_scraper() -> ValidationResult:
    """Valida classe base scraper"""
    try:
        from scrapers.base_scraper import BaseScraperV2, get_scraper, clear_scraper
        
        # Test instanciação
        scraper = BaseScraperV2("test")
        assert scraper.source == "test"
        assert scraper.pipeline is not None
        
        # Test singleton
        s1 = get_scraper("test2")
        s2 = get_scraper("test2")
        assert s1 is s2, "Singleton should return same instance"
        
        # Test clear
        clear_scraper("test2")
        s3 = get_scraper("test2")
        assert s1 is not s3, "After clear, should create new instance"
        
        return ValidationResult("BaseScraperV2", True, "Class base + singleton OK")
    except Exception as e:
        return ValidationResult("BaseScraperV2", False, str(e))


async def validate_scrapers_final() -> List[ValidationResult]:
    """Valida scrapers finais otimizados"""
    results = []
    
    scrapers = [
        ("olx", "OLXScraper", "olx_scraper_final"),
        ("standvirtual", "StandvirtualScraper", "standvirtual_scraper_final"),
        ("autosapo", "AutoSapoScraper", "autosapo_scraper_final"),
    ]
    
    for source, class_name, module in scrapers:
        try:
            # Dynamic import
            module_obj = __import__(f"scrapers.{module}", fromlist=[class_name])
            scraper_class = getattr(module_obj, class_name)
            
            # Test instanciação
            scraper = scraper_class()
            assert scraper.source == source
            assert hasattr(scraper, 'pipeline')
            assert hasattr(scraper, 'scrape_listings')
            assert hasattr(scraper, 'save_to_database')
            
            results.append(ValidationResult(f"{class_name}", True, f"Source={source}"))
            
        except Exception as e:
            results.append(ValidationResult(f"{class_name}", False, str(e)))
    
    return results


async def validate_pipeline() -> ValidationResult:
    """Valida pipeline principal"""
    try:
        from scrapers.pipeline import AutoDealPipeline
        
        pipeline = AutoDealPipeline()
        assert hasattr(pipeline, 'run_source')
        assert hasattr(pipeline, '_fetch_via_api')
        assert hasattr(pipeline, '_fetch_via_camoufox')
        assert hasattr(pipeline, '_css_parse')
        assert hasattr(pipeline, '_ai_parse')
        
        return ValidationResult("AutoDealPipeline", True, "All methods present")
    except Exception as e:
        return ValidationResult("AutoDealPipeline", False, str(e))


async def validate_api_clients() -> ValidationResult:
    """Valida API clients"""
    try:
        from scrapers.api_clients import (
            fetch_olx_api, fetch_standvirtual_api, fetch_autosapo_api,
            _parse_price, _parse_int, _extract_price_from_text
        )
        
        # Test parsing
        assert _parse_price("€ 25.500") == 25500.0
        assert _parse_price("15000 EUR") == 15000.0
        assert _parse_int("85.000 km") == 85000
        
        return ValidationResult("API Clients", True, "Parsing functions OK")
    except Exception as e:
        return ValidationResult("API Clients", False, str(e))


async def validate_camoufox_client() -> ValidationResult:
    """Valida Camoufox client (sem iniciar browser)"""
    try:
        from scrapers.camoufox_client import (
            CamoufoxClient, BrowserSession, SESSION_TTL_MINUTES
        )
        
        # Test session
        session = BrowserSession(
            site="test",
            cookies=[],
            user_agent="test",
            created_at=0,
        )
        assert not session.is_valid  # Expired
        
        # Test client
        client = CamoufoxClient(headless=True)
        assert client.headless == True
        assert SESSION_TTL_MINUTES == 25
        
        return ValidationResult("CamoufoxClient", True, f"TTL={SESSION_TTL_MINUTES}min")
    except Exception as e:
        return ValidationResult("CamoufoxClient", False, str(e))


async def validate_ollama_direct() -> ValidationResult:
    """Valida Ollama direct"""
    try:
        from scrapers.ollama_direct import (
            clean_html, build_extraction_prompt, _parse_json_response,
            extract_single_listing, extract_listings_with_ollama
        )
        
        # Test HTML cleaning
        html = "<script>alert(1)</script><h1>Title</h1><p>Text</p>"
        clean = clean_html(html, max_length=100)
        assert "<script>" not in clean
        assert "Title" in clean
        
        # Test JSON parsing
        json_str = '{"titulo": "Test", "preco_eur": 15000}'
        result = _parse_json_response(json_str)
        assert result.get("titulo") == "Test"
        assert result.get("preco_eur") == 15000
        
        return ValidationResult("OllamaDirect", True, "HTML clean + JSON parse OK")
    except Exception as e:
        return ValidationResult("OllamaDirect", False, str(e))


async def validate_managed_client() -> ValidationResult:
    """Valida managed client v2"""
    try:
        from scrapers.managed_client_v2 import (
            ManagedScrapingClient, get_managed_client, clear_managed_client
        )
        
        clear_managed_client()
        
        c1 = get_managed_client()
        c2 = get_managed_client()
        assert c1 is c2, "Should be singleton"
        
        c3 = ManagedScrapingClient()
        assert isinstance(c3, ManagedScrapingClient)
        
        return ValidationResult("ManagedClientV2", True, "Singleton OK")
    except Exception as e:
        return ValidationResult("ManagedClientV2", False, str(e))


async def validate_no_duplicates() -> ValidationResult:
    """Valida que não há duplicações entre arquivos"""
    try:
        import ast
        from pathlib import Path
        
        # Verificar que scrapers finais herdam de BaseScraperV2
        files = [
            "scrapers/olx_scraper_final.py",
            "scrapers/standvirtual_scraper_final.py", 
            "scrapers/autosapo_scraper_final.py",
        ]
        
        for file in files:
            path = Path(f"d:/VER PRECOS/{file}")
            if not path.exists():
                raise FileNotFoundError(f"Missing: {file}")
            
            with open(path) as f:
                content = f.read()
            
            # Verifica herança de BaseScraperV2
            assert "BaseScraperV2" in content, f"{file} should inherit from BaseScraperV2"
            
            # Verifica que não tem métodos duplicados da base
            tree = ast.parse(content)
            methods = [node.name for node in ast.walk(tree) 
                      if isinstance(node, ast.FunctionDef)]
            
            # Não deve ter scrape_listings (herdado da base)
            if "scrape_listings" in methods:
                raise ValueError(f"{file} should not override scrape_listings")
        
        return ValidationResult("No Duplicates", True, "All scrapers use base class")
        
    except Exception as e:
        return ValidationResult("No Duplicates", False, str(e))


async def run_all_validations() -> Tuple[List[ValidationResult], bool]:
    """Executa todas as validações"""
    
    logger.info("=" * 70)
    logger.info("VALIDAÇÃO FINAL — ARQUITETURA OTIMIZADA")
    logger.info("=" * 70)
    
    all_results = []
    
    # Validar componentes principais
    all_results.append(await validate_base_scraper())
    all_results.extend(await validate_scrapers_final())
    all_results.append(await validate_pipeline())
    all_results.append(await validate_api_clients())
    all_results.append(await validate_camoufox_client())
    all_results.append(await validate_ollama_direct())
    all_results.append(await validate_managed_client())
    all_results.append(await validate_no_duplicates())
    
    # Resumo
    logger.info("\n" + "=" * 70)
    logger.info("RESULTADOS")
    logger.info("=" * 70)
    
    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    
    for result in all_results:
        status = "✅" if result.passed else "❌"
        logger.info(f"{status} {result.name:25} {result.details}")
    
    logger.info("=" * 70)
    logger.info(f"Total: {passed}/{total} validações passaram")
    
    if passed == total:
        logger.info("🎉 ARQUITETURA FINAL VALIDADA COM SUCESSO!")
        return all_results, True
    else:
        logger.warning("⚠️ Algumas validações falharam")
        return all_results, False


if __name__ == "__main__":
    results, success = asyncio.run(run_all_validations())
    sys.exit(0 if success else 1)
