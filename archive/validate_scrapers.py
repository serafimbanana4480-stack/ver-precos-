"""
Validação Completa dos Scrapers - AutoDeal IA Hunter
Executa todos os scrapers e verifica funcionamento e qualidade dos dados
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ScraperValidator:
    """Validador completo de scrapers para produção"""
    
    def __init__(self):
        self.results = {
            "olx": {"status": "PENDENTE", "listings": [], "errors": []},
            "standvirtual": {"status": "PENDENTE", "listings": [], "errors": []},
            "autosapo": {"status": "PENDENTE", "listings": [], "errors": []},
            "custojusto": {"status": "PENDENTE", "listings": [], "errors": []}
        }
        self.critical_fields = ["price", "title", "description", "images", "km", "year", "brand", "model"]
        self.required_fields = ["price", "title", "km", "year", "fuel_type", "location"]
    
    async def validate_olx(self) -> Dict[str, Any]:
        """Valida scraper OLX.pt"""
        print("\n" + "="*70)
        print("VALIDANDO OLX.PT")
        print("="*70)
        
        try:
            from scrapers.olx_scraper import OLXScraper
            scraper = OLXScraper()
            
            # Testar scraping com detalhes
            print("Executando scraper OLX (max 5 listagens)...")
            listings = await scraper.scrape_listings("carros", max_listings=5, scrape_details=False)
            
            self.results["olx"]["listings"] = listings
            self.results["olx"]["count"] = len(listings)
            
            if len(listings) == 0:
                self.results["olx"]["status"] = "FALHA"
                self.results["olx"]["errors"].append("Nenhuma listagem retornada")
                print("[FALHA] Nenhuma listagem retornada")
                return self.results["olx"]
            
            print(f"[OK] {len(listings)} listagens retornadas")
            
            # Validar campos
            field_stats = self._validate_fields(listings, "OLX")
            self.results["olx"]["field_stats"] = field_stats
            
            # Verificar campos críticos
            missing_critical = [f for f in self.critical_fields if field_stats[f]["percentage"] < 50]
            if missing_critical:
                self.results["olx"]["status"] = "PARCIAL"
                self.results["olx"]["errors"].append(f"Campos críticos ausentes: {', '.join(missing_critical)}")
                print(f"[PARCIAL] Campos criticos ausentes: {', '.join(missing_critical)}")
            else:
                self.results["olx"]["status"] = "FUNCIONAL"
                print("[FUNCIONAL] Todos os campos criticos presentes")
            
            # Mostrar exemplo
            if listings:
                self._show_example(listings[0], "OLX")
            
        except Exception as e:
            self.results["olx"]["status"] = "ERRO"
            self.results["olx"]["errors"].append(str(e))
            print(f"[ERRO] {str(e)}")
        
        return self.results["olx"]
    
    async def validate_standvirtual(self) -> Dict[str, Any]:
        """Valida scraper Standvirtual"""
        print("\n" + "="*70)
        print("VALIDANDO STANDVIRTUAL")
        print("="*70)
        
        try:
            from scrapers.standvirtual_scraper import StandvirtualScraper
            scraper = StandvirtualScraper()
            
            print("Executando scraper Standvirtual (max 5 listagens)...")
            listings = await scraper.scrape_listings("carros", max_listings=5, scrape_details=True)
            
            self.results["standvirtual"]["listings"] = listings
            self.results["standvirtual"]["count"] = len(listings)
            
            if len(listings) == 0:
                self.results["standvirtual"]["status"] = "FALHA"
                self.results["standvirtual"]["errors"].append("Nenhuma listagem retornada")
                print("[FALHA] Nenhuma listagem retornada")
                return self.results["standvirtual"]
            
            print(f"[OK] {len(listings)} listagens retornadas")
            
            # Validar campos
            field_stats = self._validate_fields(listings, "Standvirtual")
            self.results["standvirtual"]["field_stats"] = field_stats
            
            # Verificar campos críticos
            missing_critical = [f for f in self.critical_fields if field_stats[f]["percentage"] < 50]
            if missing_critical:
                self.results["standvirtual"]["status"] = "PARCIAL"
                self.results["standvirtual"]["errors"].append(f"Campos críticos ausentes: {', '.join(missing_critical)}")
                print(f"[PARCIAL] Campos criticos ausentes: {', '.join(missing_critical)}")
            else:
                self.results["standvirtual"]["status"] = "FUNCIONAL"
                print("[FUNCIONAL] Todos os campos criticos presentes")
            
            # Mostrar exemplo
            if listings:
                self._show_example(listings[0], "Standvirtual")
            
        except Exception as e:
            self.results["standvirtual"]["status"] = "ERRO"
            self.results["standvirtual"]["errors"].append(str(e))
            print(f"[ERRO] {str(e)}")
        
        return self.results["standvirtual"]
    
    async def validate_autosapo(self) -> Dict[str, Any]:
        """Valida scraper AutoSapo"""
        print("\n" + "="*70)
        print("VALIDANDO AUTOSAPO")
        print("="*70)
        
        try:
            from scrapers.autosapo_scraper import AutoSapoScraper
            scraper = AutoSapoScraper()
            
            print("Executando scraper AutoSapo (max 5 listagens)...")
            listings = await scraper.scrape_listings("carros", max_listings=5, scrape_details=True)
            
            self.results["autosapo"]["listings"] = listings
            self.results["autosapo"]["count"] = len(listings)
            
            if len(listings) == 0:
                self.results["autosapo"]["status"] = "FALHA"
                self.results["autosapo"]["errors"].append("Nenhuma listagem retornada")
                print("[FALHA] Nenhuma listagem retornada")
                return self.results["autosapo"]
            
            print(f"[OK] {len(listings)} listagens retornadas")
            
            # Validar campos
            field_stats = self._validate_fields(listings, "AutoSapo")
            self.results["autosapo"]["field_stats"] = field_stats
            
            # Verificar campos críticos
            missing_critical = [f for f in self.critical_fields if field_stats[f]["percentage"] < 50]
            if missing_critical:
                self.results["autosapo"]["status"] = "PARCIAL"
                self.results["autosapo"]["errors"].append(f"Campos críticos ausentes: {', '.join(missing_critical)}")
                print(f"[PARCIAL] Campos criticos ausentes: {', '.join(missing_critical)}")
            else:
                self.results["autosapo"]["status"] = "FUNCIONAL"
                print("[FUNCIONAL] Todos os campos criticos presentes")
            
            # Mostrar exemplo
            if listings:
                self._show_example(listings[0], "AutoSapo")
            
        except Exception as e:
            self.results["autosapo"]["status"] = "ERRO"
            self.results["autosapo"]["errors"].append(str(e))
            print(f"[ERRO] {str(e)}")
        
        return self.results["autosapo"]
    
    async def validate_custojusto(self) -> Dict[str, Any]:
        """Valida scraper CustoJusto"""
        print("\n" + "="*70)
        print("VALIDANDO CUSTOJUSTO")
        print("="*70)
        
        try:
            from scrapers.custojusto_scraper import CustoJustoScraper
            scraper = CustoJustoScraper()
            
            print("Executando scraper CustoJusto (max 5 listagens)...")
            listings = await scraper.scrape_listings("carros", max_listings=5, scrape_details=True)
            
            self.results["custojusto"]["listings"] = listings
            self.results["custojusto"]["count"] = len(listings)
            
            if len(listings) == 0:
                self.results["custojusto"]["status"] = "FALHA"
                self.results["custojusto"]["errors"].append("Nenhuma listagem retornada")
                print("[FALHA] Nenhuma listagem retornada")
                return self.results["custojusto"]
            
            print(f"[OK] {len(listings)} listagens retornadas")
            
            # Validar campos
            field_stats = self._validate_fields(listings, "CustoJusto")
            self.results["custojusto"]["field_stats"] = field_stats
            
            # Verificar campos críticos
            missing_critical = [f for f in self.critical_fields if field_stats[f]["percentage"] < 50]
            if missing_critical:
                self.results["custojusto"]["status"] = "PARCIAL"
                self.results["custojusto"]["errors"].append(f"Campos críticos ausentes: {', '.join(missing_critical)}")
                print(f"[PARCIAL] Campos criticos ausentes: {', '.join(missing_critical)}")
            else:
                self.results["custojusto"]["status"] = "FUNCIONAL"
                print("[FUNCIONAL] Todos os campos criticos presentes")
            
            # Mostrar exemplo
            if listings:
                self._show_example(listings[0], "CustoJusto")
            
        except Exception as e:
            self.results["custojusto"]["status"] = "ERRO"
            self.results["custojusto"]["errors"].append(str(e))
            print(f"[ERRO] {str(e)}")
        
        return self.results["custojusto"]
    
    def _validate_fields(self, listings: List[Dict], source: str) -> Dict[str, Dict]:
        """Valida campos das listagens"""
        stats = {}
        total = len(listings)
        
        all_fields = ["price", "title", "description", "images", "km", "year", 
                     "fuel_type", "location", "brand", "model", "url", "source_id"]
        
        for field in all_fields:
            present = sum(1 for l in listings if self._field_present(l, field))
            percentage = (present / total) * 100 if total > 0 else 0
            stats[field] = {
                "present": present,
                "total": total,
                "percentage": percentage,
                "status": "OK" if percentage >= 80 else "WARN" if percentage >= 50 else "FAIL"
            }
            print(f"  {stats[field]['status']} {field}: {present}/{total} ({percentage:.1f}%)")
        
        return stats
    
    def _field_present(self, listing: Dict, field: str) -> bool:
        """Verifica se campo está presente e válido"""
        value = listing.get(field)
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, list) and len(value) == 0:
            return False
        if isinstance(value, (int, float)) and value == 0:
            return False
        return True
    
    def _show_example(self, listing: Dict, source: str):
        """Mostra exemplo de listagem"""
        print(f"\n  Exemplo de listagem {source}:")
        print(f"    Título: {listing.get('title', 'N/A')[:60]}...")
        print(f"    Preço: {listing.get('price', 'N/A')}")
        print(f"    KM: {listing.get('km', 'N/A')}")
        print(f"    Ano: {listing.get('year', 'N/A')}")
        print(f"    Descrição: {str(listing.get('description', 'N/A'))[:80]}...")
        print(f"    Imagens: {len(listing.get('images', []))} fotos")
        print(f"    URL: {listing.get('url', 'N/A')[:60]}...")
    
    def generate_report(self) -> str:
        """Gera relatório completo"""
        print("\n" + "="*70)
        print("RELATÓRIO DE VALIDAÇÃO DOS SCRAPERS")
        print("="*70)
        
        report_lines = []
        report_lines.append("# RELATÓRIO DE VALIDAÇÃO DOS SCRAPERS")
        report_lines.append(f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Resumo
        report_lines.append("## RESUMO")
        report_lines.append("")
        
        functional = sum(1 for r in self.results.values() if r["status"] == "FUNCIONAL")
        partial = sum(1 for r in self.results.values() if r["status"] == "PARCIAL")
        failed = sum(1 for r in self.results.values() if r["status"] in ["FALHA", "ERRO"])
        
        report_lines.append(f"- **Funcionais:** {functional}/4")
        report_lines.append(f"- **Parciais:** {partial}/4")
        report_lines.append(f"- **Com Falha:** {failed}/4")
        report_lines.append("")
        
        # Status por scraper
        report_lines.append("## STATUS POR SCRAPER")
        report_lines.append("")
        report_lines.append("| Scraper | Status | Listagens | Campos Críticos | Erros |")
        report_lines.append("|---------|--------|-----------|-----------------|-------|")
        
        for source, result in self.results.items():
            status = result["status"]
            count = result.get("count", 0)
            errors = len(result.get("errors", []))
            
            field_stats = result.get("field_stats", {})
            critical_ok = sum(1 for f in self.critical_fields 
                           if field_stats.get(f, {}).get("percentage", 0) >= 80)
            critical_total = len(self.critical_fields)
            
            report_lines.append(f"| {source.capitalize()} | {status} | {count} | {critical_ok}/{critical_total} | {errors} |")
        
        report_lines.append("")
        
        # Detalhes por scraper
        for source, result in self.results.items():
            report_lines.append(f"## {source.upper()}")
            report_lines.append("")
            report_lines.append(f"**Status:** {result['status']}")
            report_lines.append(f"**Listagens:** {result.get('count', 0)}")
            
            if result.get("errors"):
                report_lines.append("")
                report_lines.append("**Erros:**")
                for error in result["errors"]:
                    report_lines.append(f"- {error}")
            
            field_stats = result.get("field_stats", {})
            if field_stats:
                report_lines.append("")
                report_lines.append("**Cobertura de Campos:**")
                report_lines.append("")
                report_lines.append("| Campo | Presente | Total | Percentagem | Status |")
                report_lines.append("|-------|----------|-------|-------------|--------|")
                
                for field, stats in field_stats.items():
                    report_lines.append(f"| {field} | {stats['present']} | {stats['total']} | {stats['percentage']:.1f}% | {stats['status']} |")
            
            report_lines.append("")
        
        # Veredito
        report_lines.append("## VEREDICTO")
        report_lines.append("")
        
        if functional >= 2:
            report_lines.append("[OK] **SISTEMA FUNCIONAL PARA PRODUÇÃO**")
            report_lines.append(f"{functional} scrapers funcionais com dados completos.")
        elif functional >= 1 or partial >= 2:
            report_lines.append("[ATENCAO] **SISTEMA PARCIAL - REQUER CORREÇÕES**")
            report_lines.append("Alguns scrapers funcionam mas necessitam de ajustes.")
        else:
            report_lines.append("[FALHA] **SISTEMA COM FALHAS CRÍTICAS**")
            report_lines.append("Nenhum scraper está funcionando corretamente. Requer intervenção imediata.")
        
        report_lines.append("")
        
        # Recomendações
        report_lines.append("## RECOMENDAÇÕES")
        report_lines.append("")
        
        for source, result in self.results.items():
            if result["status"] != "FUNCIONAL":
                report_lines.append(f"### {source.upper()}")
                report_lines.append("")
                
                if result["status"] == "FALHA":
                    report_lines.append("- Verificar se o site está acessível")
                    report_lines.append("- Verificar se os seletores CSS estão atualizados")
                    report_lines.append("- Verificar se há bloqueios (CAPTCHA, rate limiting)")
                elif result["status"] == "PARCIAL":
                    field_stats = result.get("field_stats", {})
                    missing = [f for f in self.critical_fields 
                              if field_stats.get(f, {}).get("percentage", 0) < 50]
                    if missing:
                        report_lines.append(f"- Corrigir extração dos campos: {', '.join(missing)}")
                    report_lines.append("- Verificar se scrape_details=True está habilitado")
                    report_lines.append("- Verificar seletores para páginas de detalhe")
                elif result["status"] == "ERRO":
                    report_lines.append("- Verificar dependências do scraper")
                    report_lines.append("- Verificar logs de erro detalhados")
                
                report_lines.append("")
        
        return "\n".join(report_lines)


async def main():
    """Executa validação completa"""
    print("\n" + "="*70)
    print("VALIDAÇÃO COMPLETA DOS SCRAPERS - AUTODEAL IA HUNTER")
    print("="*70)
    print(f"Iniciando validação em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    validator = ScraperValidator()
    
    # Validar cada scraper
    await validator.validate_olx()
    await validator.validate_standvirtual()
    await validator.validate_autosapo()
    await validator.validate_custojusto()
    
    # Gerar relatório
    report = validator.generate_report()
    print(report)
    
    # Salvar relatório
    report_path = "d:/VER PRECOS/SCRAPER_VALIDATION_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\nRelatório salvo em: {report_path}")
    
    # Resumo final
    print("\n" + "="*70)
    print("RESUMO FINAL")
    print("="*70)
    
    for source, result in validator.results.items():
        status_icon = "[OK]" if result["status"] == "FUNCIONAL" else "[ATENCAO]" if result["status"] == "PARCIAL" else "[FALHA]"
        print(f"{status_icon} {source.upper()}: {result['status']} ({result.get('count', 0)} listagens)")
    
    functional = sum(1 for r in validator.results.values() if r["status"] == "FUNCIONAL")
    print(f"\nTotal funcionais: {functional}/4")
    
    if functional >= 2:
        print("\n[OK] Sistema pronto para producao!")
    elif functional >= 1:
        print("\n[ATENCAO] Sistema parcial - requer correcoes")
    else:
        print("\n[FALHA] Sistema com falhas criticas!")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
