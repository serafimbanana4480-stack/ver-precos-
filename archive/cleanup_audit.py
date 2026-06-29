"""
Production Cleanup Audit
Sanitize AutoDeal IA Hunter system from fake data, simulated outputs, and inconsistencies
"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import json
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CleanupAuditor:
    """Production cleanup auditor with verification-first approach"""
    
    def __init__(self, db_path: str = "d:/VER PRECOS/autodeal.db"):
        self.db_path = db_path
        self.findings = {
            "fake_data": [],
            "duplicates": [],
            "test_data": [],
            "dead_code": [],
            "inconsistencies": []
        }
        self.files_to_delete = []
        self.files_to_refactor = []
    
    def scan_database_for_fake_data(self) -> Dict[str, Any]:
        """Scan database for fake/synthetic vehicle listings"""
        print("\n" + "="*60)
        print("DATABASE FAKE DATA SCAN")
        print("="*60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        results = {
            "total_vehicles": 0,
            "fake_indicators": [],
            "suspicious_patterns": []
        }
        
        try:
            # Get total vehicles
            cursor.execute("SELECT COUNT(*) FROM vehicles")
            results["total_vehicles"] = cursor.fetchone()[0]
            print(f"Total vehicles: {results['total_vehicles']}")
            
            # Check for test IDs
            cursor.execute("""
                SELECT source_id, title, url 
                FROM vehicles 
                WHERE source_id LIKE '%test%' OR source_id LIKE '%qa%'
                LIMIT 10
            """)
            test_ids = cursor.fetchall()
            if test_ids:
                results["fake_indicators"].append(f"Found {len(test_ids)} test/QA vehicle IDs")
                self.findings["test_data"].extend([row[0] for row in test_ids])
                print(f"  [!] Found {len(test_ids)} test/QA vehicle IDs")
                for row in test_ids[:3]:
                    print(f"      - {row[0]}: {row[1][:50]}")
            
            # Check for placeholder titles
            cursor.execute("""
                SELECT source_id, title 
                FROM vehicles 
                WHERE title LIKE '%test%' OR title LIKE '%placeholder%' OR title LIKE '%sample%'
                LIMIT 10
            """)
            placeholder_titles = cursor.fetchall()
            if placeholder_titles:
                results["fake_indicators"].append(f"Found {len(placeholder_titles)} placeholder titles")
                self.findings["fake_data"].extend([row[0] for row in placeholder_titles])
                print(f"  [!] Found {len(placeholder_titles)} placeholder titles")
            
            # Check for suspicious price patterns (all multiples of 1000)
            cursor.execute("""
                SELECT source_id, price 
                FROM vehicles 
                WHERE price % 1000 = 0
                LIMIT 20
            """)
            round_prices = cursor.fetchall()
            if len(round_prices) > results["total_vehicles"] * 0.8:
                results["suspicious_patterns"].append(f"{len(round_prices)}/{results['total_vehicles']} vehicles have prices multiples of 1000")
                print(f"  [!] Suspicious: {len(round_prices)}/{results['total_vehicles']} vehicles have round prices (multiples of 1000)")
            
            # Check for duplicate descriptions
            cursor.execute("""
                SELECT description, COUNT(*) as count 
                FROM vehicles 
                WHERE description IS NOT NULL AND length(description) > 50
                GROUP BY description 
                HAVING count > 1
                LIMIT 10
            """)
            dup_descriptions = cursor.fetchall()
            if dup_descriptions:
                results["fake_indicators"].append(f"Found {len(dup_descriptions)} duplicate descriptions")
                print(f"  [!] Found {len(dup_descriptions)} duplicate descriptions")
            
            # Check for vehicles with no images
            cursor.execute("""
                SELECT COUNT(*) FROM vehicles 
                WHERE images IS NULL OR json_array_length(images) = 0
            """)
            no_images = cursor.fetchone()[0]
            if no_images > 0:
                print(f"  [!] {no_images} vehicles have no images")
            
            # Check for vehicles with no description
            cursor.execute("""
                SELECT COUNT(*) FROM vehicles 
                WHERE description IS NULL OR length(description) < 10
            """)
            no_description = cursor.fetchone()[0]
            if no_description > 0:
                print(f"  [!] {no_description} vehicles have no description")
            
            # Check for vehicles with no KM (required for cars)
            cursor.execute("""
                SELECT COUNT(*) FROM vehicles 
                WHERE vehicle_type = 'carros' AND (km IS NULL OR km = 0)
            """)
            no_km = cursor.fetchone()[0]
            if no_km > 0:
                print(f"  [!] {no_km} vehicles have no KM")
            
        except Exception as e:
            logger.error(f"Database scan failed: {e}")
        finally:
            conn.close()
        
        return results
    
    def scan_for_duplicates(self) -> Dict[str, Any]:
        """Scan for duplicate vehicle entries"""
        print("\n" + "="*60)
        print("DUPLICATE SCAN")
        print("="*60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        results = {
            "duplicate_urls": [],
            "duplicate_source_ids": []
        }
        
        try:
            # Check duplicate URLs
            cursor.execute("""
                SELECT url, COUNT(*) as count, GROUP_CONCAT(source_id)
                FROM vehicles
                GROUP BY url
                HAVING count > 1
                LIMIT 20
            """)
            dup_urls = cursor.fetchall()
            if dup_urls:
                results["duplicate_urls"] = dup_urls
                self.findings["duplicates"].extend([row[0] for row in dup_urls])
                print(f"  [!] Found {len(dup_urls)} duplicate URLs")
                for row in dup_urls[:5]:
                    print(f"      {row[0]} ({row[1]} copies)")
            
            # Check duplicate source_ids
            cursor.execute("""
                SELECT source, source_id, COUNT(*) as count
                FROM vehicles
                GROUP BY source, source_id
                HAVING count > 1
                LIMIT 20
            """)
            dup_source_ids = cursor.fetchall()
            if dup_source_ids:
                results["duplicate_source_ids"] = dup_source_ids
                print(f"  [!] Found {len(dup_source_ids)} duplicate source_ids")
                for row in dup_source_ids[:5]:
                    print(f"      {row[0]}/{row[1]} ({row[2]} copies)")
            
        except Exception as e:
            logger.error(f"Duplicate scan failed: {e}")
        finally:
            conn.close()
        
        return results
    
    def scan_for_test_data(self) -> Dict[str, Any]:
        """Scan for test/sample data"""
        print("\n" + "="*60)
        print("TEST DATA SCAN")
        print("="*60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        results = {
            "test_vehicles": [],
            "sample_data": []
        }
        
        try:
            # Check for test vehicles by various indicators
            cursor.execute("""
                SELECT source_id, title, url, created_at
                FROM vehicles
                WHERE source_id LIKE '%test%' 
                   OR source_id LIKE '%qa%'
                   OR source_id LIKE '%sample%'
                   OR source_id LIKE '%demo%'
                   OR title LIKE '%test%'
                   OR title LIKE '%sample%'
                   OR title LIKE '%demo%'
                   OR url LIKE '%test%'
                LIMIT 50
            """)
            test_vehicles = cursor.fetchall()
            if test_vehicles:
                results["test_vehicles"] = test_vehicles
                self.findings["test_data"].extend([row[0] for row in test_vehicles])
                print(f"  [!] Found {len(test_vehicles)} test/sample vehicles")
                for row in test_vehicles[:10]:
                    print(f"      {row[0]}: {row[1][:50]}")
            
        except Exception as e:
            logger.error(f"Test data scan failed: {e}")
        finally:
            conn.close()
        
        return results
    
    def audit_scraping_engines(self) -> Dict[str, Any]:
        """Audit scraping engines for fake logs and cached responses"""
        print("\n" + "="*60)
        print("SCRAPING ENGINE AUDIT")
        print("="*60)
        
        results = {
            "fake_logs": [],
            "cached_responses": [],
            "broken_selectors": []
        }
        
        # Check for cached HTML files
        cache_dirs = [
            Path("d:/VER PRECOS/cache"),
            Path("d:/VER PRECOS/scrapers/cache"),
            Path("d:/VER PRECOS/.cache")
        ]
        
        for cache_dir in cache_dirs:
            if cache_dir.exists():
                cache_files = list(cache_dir.rglob("*.html"))
                if cache_files:
                    results["cached_responses"].extend([str(f) for f in cache_files])
                    print(f"  [!] Found {len(cache_files)} cached HTML files in {cache_dir}")
        
        # Check for fake log patterns in scrapers
        scraper_files = [
            Path("d:/VER PRECOS/scrapers/olx_scraper.py"),
            Path("d:/VER PRECOS/scrapers/standvirtual_scraper.py"),
            Path("d:/VER PRECOS/scrapers/autosapo_scraper.py"),
            Path("d:/VER PRECOS/scrapers/custojusto_scraper.py")
        ]
        
        for scraper_file in scraper_files:
            if scraper_file.exists():
                content = scraper_file.read_text()
                if "FAKE" in content or "MOCK" in content or "PLACEHOLDER" in content:
                    results["fake_logs"].append(str(scraper_file))
                    print(f"  [!] Found fake/mock patterns in {scraper_file.name}")
        
        return results
    
    def audit_ai_pipeline(self) -> Dict[str, Any]:
        """Audit AI pipeline for template-based analysis or bypasses"""
        print("\n" + "="*60)
        print("AI PIPELINE AUDIT")
        print("="*60)
        
        results = {
            "template_responses": [],
            "bypasses": [],
            "fake_inference": []
        }
        
        # Check AI enrichment files for template responses
        ai_files = [
            Path("d:/VER PRECOS/processing/ai_enrichment/llm_analyzer.py"),
            Path("d:/VER PRECOS/processing/ai_enrichment/vision_analyzer.py")
        ]
        
        for ai_file in ai_files:
            if ai_file.exists():
                content = ai_file.read_text()
                if "template" in content.lower() or "hardcoded" in content.lower():
                    results["template_responses"].append(str(ai_file))
                    print(f"  [!] Found template/hardcoded patterns in {ai_file.name}")
                
                if "bypass" in content.lower() or "skip" in content.lower():
                    results["bypasses"].append(str(ai_file))
                    print(f"  [!] Found bypass/skip patterns in {ai_file.name}")
        
        return results
    
    def scan_for_dead_code(self) -> Dict[str, Any]:
        """Identify dead code and duplicate logic"""
        print("\n" + "="*60)
        print("DEAD CODE SCAN")
        print("="*60)
        
        results = {
            "unused_files": [],
            "duplicate_functions": []
        }
        
        # Check for unused model files (ML model was deleted, check for remnants)
        model_dir = Path("d:/VER PRECOS/models")
        if model_dir.exists():
            model_files = list(model_dir.glob("*"))
            for model_file in model_files:
                if model_file.name not in ["model_metrics.json", "feature_names.json"]:
                    results["unused_files"].append(str(model_file))
                    print(f"  [!] Unused model file: {model_file.name}")
        
        # Check for duplicate pipeline files
        pipeline_files = [
            Path("d:/VER PRECOS/processing/pipeline.py"),
            Path("d:/VER PRECOS/valuation/predict.py"),
            Path("d:/VER PRECOS/deal_finder.py")
        ]
        
        existing_pipelines = [f for f in pipeline_files if f.exists()]
        if len(existing_pipelines) > 1:
            print(f"  [!] Multiple pipeline files found (potential duplicates):")
            for f in existing_pipelines:
                print(f"      - {f.name}")
        
        return results
    
    def generate_cleanup_report(self) -> str:
        """Generate final cleanup report"""
        print("\n" + "="*60)
        print("CLEANUP AUDIT REPORT")
        print("="*60)
        
        report_lines = []
        
        # Summary
        report_lines.append("## CLEANUP AUDIT SUMMARY")
        report_lines.append("")
        report_lines.append(f"Fake Data Indicators: {len(self.findings['fake_data'])}")
        report_lines.append(f"Duplicate Entries: {len(self.findings['duplicates'])}")
        report_lines.append(f"Test Data Entries: {len(self.findings['test_data'])}")
        report_lines.append(f"Dead Code Files: {len(self.findings['dead_code'])}")
        report_lines.append("")
        
        # Files to delete
        if self.files_to_delete:
            report_lines.append("## FILES TO DELETE")
            for file in self.files_to_delete:
                report_lines.append(f"- {file}")
            report_lines.append("")
        
        # Files to refactor
        if self.files_to_refactor:
            report_lines.append("## FILES TO REFACTOR")
            for file in self.files_to_refactor:
                report_lines.append(f"- {file}")
            report_lines.append("")
        
        # Risk zones
        report_lines.append("## RISK ZONES")
        if self.findings["fake_data"]:
            report_lines.append("- Database contains fake/synthetic data")
        if self.findings["duplicates"]:
            report_lines.append("- Database contains duplicate entries")
        if self.findings["test_data"]:
            report_lines.append("- Database contains test/sample data")
        if self.files_to_delete:
            report_lines.append("- Dead code files present")
        report_lines.append("")
        
        # Production-ready structure
        report_lines.append("## PRODUCTION-READY STRUCTURE")
        report_lines.append("```")
        report_lines.append("d:/VER PRECOS/")
        report_lines.append("|-- core/              # Configuration management")
        report_lines.append("|-- database/          # Database models and connection")
        report_lines.append("|-- ingestion/         # Scraping orchestrator")
        report_lines.append("|-- intelligence/      # Pricing and scoring engines")
        report_lines.append("|-- observability/     # Logging and metrics")
        report_lines.append("|-- processing/        # Data validation and AI enrichment")
        report_lines.append("|-- scrapers/          # Scraping engines")
        report_lines.append("|-- validation/        # Pydantic schemas")
        report_lines.append("|-- main.py            # Main entry point")
        report_lines.append("|-- autodeal.db        # SQLite database")
        report_lines.append("```")
        report_lines.append("")
        
        return "\n".join(report_lines)


def main():
    """Run cleanup audit"""
    print("\n" + "="*60)
    print("AUTODEAL IA HUNTER - PRODUCTION CLEANUP AUDIT")
    print("="*60)
    
    auditor = CleanupAuditor()
    
    # Run all scans
    auditor.scan_database_for_fake_data()
    auditor.scan_for_duplicates()
    auditor.scan_for_test_data()
    auditor.audit_scraping_engines()
    auditor.audit_ai_pipeline()
    auditor.scan_for_dead_code()
    
    # Generate report
    report = auditor.generate_cleanup_report()
    print(report)
    
    # Save report
    report_path = Path("d:/VER PRECOS/CLEANUP_AUDIT_REPORT.md")
    with open(report_path, "w") as f:
        f.write(report)
    
    print(f"\nReport saved to: {report_path}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
