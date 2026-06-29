"""
Production Scraper Audit
Comprehensive audit of all scrapers for AI pipeline compatibility
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScraperAuditor:
    """Production-grade scraper auditor with AI pipeline compatibility checks"""
    
    def __init__(self):
        self.results = {
            "olx": {},
            "standvirtual": {},
            "autosapo": {},
            "custojusto": {}
        }
        self.required_fields = {
            "price": "required",
            "title": "required",
            "description": "critical for LLM",
            "images": "critical for Vision AI",
            "km": "critical for pricing",
            "year": "required",
            "fuel_type": "important",
            "location": "important",
            "brand": "required",
            "model": "required"
        }
    
    async def test_olx_scraper(self) -> Dict[str, Any]:
        """Test OLX.pt scraper with field validation"""
        print("\n" + "="*60)
        print("TESTING OLX.PT SCRAPER")
        print("="*60)
        
        result = {
            "status": "UNKNOWN",
            "listings_tested": 0,
            "field_coverage": {},
            "missing_fields": [],
            "ai_compatibility": {},
            "root_cause": ""
        }
        
        try:
            from scrapers.olx_scraper import OLXScraper
            
            scraper = OLXScraper()
            listings = await scraper.scrape_listings("carros", max_listings=10)
            
            result["listings_tested"] = len(listings)
            print(f"Scraped {len(listings)} listings")
            
            if len(listings) == 0:
                result["status"] = "FAIL"
                result["root_cause"] = "No listings returned - scraper completely non-functional"
                return result
            
            # Validate fields
            field_stats = {}
            for field in self.required_fields.keys():
                present = sum(1 for l in listings if l.get(field) and l.get(field) not in [None, "", [], 0])
                field_stats[field] = {
                    "present": present,
                    "total": len(listings),
                    "percentage": (present / len(listings)) * 100 if len(listings) > 0 else 0
                }
            
            result["field_coverage"] = field_stats
            
            # Identify missing fields
            missing_critical = []
            missing_required = []
            
            for field, importance in self.required_fields.items():
                if field_stats[field]["percentage"] < 50:
                    if importance in ["critical for LLM", "critical for Vision AI", "critical for pricing"]:
                        missing_critical.append(field)
                    elif importance == "required":
                        missing_required.append(field)
            
            result["missing_fields"] = {
                "critical": missing_critical,
                "required": missing_required
            }
            
            # AI compatibility check
            ai_compatibility = {
                "llm_compatible": field_stats.get("description", {}).get("percentage", 0) > 80,
                "vision_compatible": field_stats.get("images", {}).get("percentage", 0) > 80,
                "pricing_compatible": field_stats.get("km", {}).get("percentage", 0) > 80 and field_stats.get("year", {}).get("percentage", 0) > 80
            }
            result["ai_compatibility"] = ai_compatibility
            
            # Determine status
            if missing_critical:
                result["status"] = "AI-INCOMPATIBLE"
                result["root_cause"] = f"Missing critical fields: {', '.join(missing_critical)}"
            elif missing_required:
                result["status"] = "PARTIAL"
                result["root_cause"] = f"Missing required fields: {', '.join(missing_required)}"
            else:
                result["status"] = "FULLY_FUNCTIONAL"
                result["root_cause"] = "All required fields present"
            
            # Print results
            print(f"\nField Coverage:")
            for field, stats in field_stats.items():
                status = "✓" if stats["percentage"] > 80 else "⚠" if stats["percentage"] > 50 else "✗"
                print(f"  {status} {field}: {stats['present']}/{stats['total']} ({stats['percentage']:.1f}%)")
            
            print(f"\nAI Compatibility:")
            print(f"  LLM: {'✓' if ai_compatibility['llm_compatible'] else '✗'}")
            print(f"  Vision: {'✓' if ai_compatibility['vision_compatible'] else '✗'}")
            print(f"  Pricing: {'✓' if ai_compatibility['pricing_compatible'] else '✗'}")
            
            print(f"\nStatus: {result['status']}")
            print(f"Root Cause: {result['root_cause']}")
            
        except Exception as e:
            result["status"] = "ERROR"
            result["root_cause"] = f"Exception during scraping: {str(e)}"
            logger.error(f"OLX scraper test failed: {e}")
        
        return result
    
    async def test_standvirtual_scraper(self) -> Dict[str, Any]:
        """Test Standvirtual scraper with field validation"""
        print("\n" + "="*60)
        print("TESTING STANDVIRTUAL SCRAPER")
        print("="*60)
        
        result = {
            "status": "UNKNOWN",
            "listings_tested": 0,
            "field_coverage": {},
            "missing_fields": [],
            "ai_compatibility": {},
            "root_cause": ""
        }
        
        try:
            from scrapers.standvirtual_scraper import StandvirtualScraper
            
            scraper = StandvirtualScraper()
            listings = await scraper.scrape_listings("carros", max_listings=10)
            
            result["listings_tested"] = len(listings)
            print(f"Scraped {len(listings)} listings")
            
            if len(listings) == 0:
                result["status"] = "FAIL"
                result["root_cause"] = "No listings returned - scraper completely non-functional"
                return result
            
            # Validate fields
            field_stats = {}
            for field in self.required_fields.keys():
                present = sum(1 for l in listings if l.get(field) and l.get(field) not in [None, "", [], 0])
                field_stats[field] = {
                    "present": present,
                    "total": len(listings),
                    "percentage": (present / len(listings)) * 100 if len(listings) > 0 else 0
                }
            
            result["field_coverage"] = field_stats
            
            # Identify missing fields
            missing_critical = []
            missing_required = []
            
            for field, importance in self.required_fields.items():
                if field_stats[field]["percentage"] < 50:
                    if importance in ["critical for LLM", "critical for Vision AI", "critical for pricing"]:
                        missing_critical.append(field)
                    elif importance == "required":
                        missing_required.append(field)
            
            result["missing_fields"] = {
                "critical": missing_critical,
                "required": missing_required
            }
            
            # AI compatibility check
            ai_compatibility = {
                "llm_compatible": field_stats.get("description", {}).get("percentage", 0) > 80,
                "vision_compatible": field_stats.get("images", {}).get("percentage", 0) > 80,
                "pricing_compatible": field_stats.get("km", {}).get("percentage", 0) > 80 and field_stats.get("year", {}).get("percentage", 0) > 80
            }
            result["ai_compatibility"] = ai_compatibility
            
            # Determine status
            if missing_critical:
                result["status"] = "AI-INCOMPATIBLE"
                result["root_cause"] = f"Missing critical fields: {', '.join(missing_critical)}"
            elif missing_required:
                result["status"] = "PARTIAL"
                result["root_cause"] = f"Missing required fields: {', '.join(missing_required)}"
            else:
                result["status"] = "FULLY_FUNCTIONAL"
                result["root_cause"] = "All required fields present"
            
            # Print results
            print(f"\nField Coverage:")
            for field, stats in field_stats.items():
                status = "✓" if stats["percentage"] > 80 else "⚠" if stats["percentage"] > 50 else "✗"
                print(f"  {status} {field}: {stats['present']}/{stats['total']} ({stats['percentage']:.1f}%)")
            
            print(f"\nAI Compatibility:")
            print(f"  LLM: {'✓' if ai_compatibility['llm_compatible'] else '✗'}")
            print(f"  Vision: {'✓' if ai_compatibility['vision_compatible'] else '✗'}")
            print(f"  Pricing: {'✓' if ai_compatibility['pricing_compatible'] else '✗'}")
            
            print(f"\nStatus: {result['status']}")
            print(f"Root Cause: {result['root_cause']}")
            
        except Exception as e:
            result["status"] = "ERROR"
            result["root_cause"] = f"Exception during scraping: {str(e)}"
            logger.error(f"Standvirtual scraper test failed: {e}")
        
        return result
    
    async def test_autosapo_scraper(self) -> Dict[str, Any]:
        """Test AutoSapo scraper with field validation"""
        print("\n" + "="*60)
        print("TESTING AUTOSAPO SCRAPER")
        print("="*60)
        
        result = {
            "status": "UNKNOWN",
            "listings_tested": 0,
            "field_coverage": {},
            "missing_fields": [],
            "ai_compatibility": {},
            "root_cause": ""
        }
        
        try:
            from scrapers.autosapo_scraper import AutoSapoScraper
            
            scraper = AutoSapoScraper()
            listings = await scraper.scrape_listings("carros", max_listings=10)
            
            result["listings_tested"] = len(listings)
            print(f"Scraped {len(listings)} listings")
            
            if len(listings) == 0:
                result["status"] = "FAIL"
                result["root_cause"] = "No listings returned - scraper completely non-functional"
                return result
            
            # Validate fields
            field_stats = {}
            for field in self.required_fields.keys():
                present = sum(1 for l in listings if l.get(field) and l.get(field) not in [None, "", [], 0])
                field_stats[field] = {
                    "present": present,
                    "total": len(listings),
                    "percentage": (present / len(listings)) * 100 if len(listings) > 0 else 0
                }
            
            result["field_coverage"] = field_stats
            
            # Identify missing fields
            missing_critical = []
            missing_required = []
            
            for field, importance in self.required_fields.items():
                if field_stats[field]["percentage"] < 50:
                    if importance in ["critical for LLM", "critical for Vision AI", "critical for pricing"]:
                        missing_critical.append(field)
                    elif importance == "required":
                        missing_required.append(field)
            
            result["missing_fields"] = {
                "critical": missing_critical,
                "required": missing_required
            }
            
            # AI compatibility check
            ai_compatibility = {
                "llm_compatible": field_stats.get("description", {}).get("percentage", 0) > 80,
                "vision_compatible": field_stats.get("images", {}).get("percentage", 0) > 80,
                "pricing_compatible": field_stats.get("km", {}).get("percentage", 0) > 80 and field_stats.get("year", {}).get("percentage", 0) > 80
            }
            result["ai_compatibility"] = ai_compatibility
            
            # Determine status
            if missing_critical:
                result["status"] = "AI-INCOMPATIBLE"
                result["root_cause"] = f"Missing critical fields: {', '.join(missing_critical)}"
            elif missing_required:
                result["status"] = "PARTIAL"
                result["root_cause"] = f"Missing required fields: {', '.join(missing_required)}"
            else:
                result["status"] = "FULLY_FUNCTIONAL"
                result["root_cause"] = "All required fields present"
            
            # Print results
            print(f"\nField Coverage:")
            for field, stats in field_stats.items():
                status = "✓" if stats["percentage"] > 80 else "⚠" if stats["percentage"] > 50 else "✗"
                print(f"  {status} {field}: {stats['present']}/{stats['total']} ({stats['percentage']:.1f}%)")
            
            print(f"\nAI Compatibility:")
            print(f"  LLM: {'✓' if ai_compatibility['llm_compatible'] else '✗'}")
            print(f"  Vision: {'✓' if ai_compatibility['vision_compatible'] else '✗'}")
            print(f"  Pricing: {'✓' if ai_compatibility['pricing_compatible'] else '✗'}")
            
            print(f"\nStatus: {result['status']}")
            print(f"Root Cause: {result['root_cause']}")
            
        except Exception as e:
            result["status"] = "ERROR"
            result["root_cause"] = f"Exception during scraping: {str(e)}"
            logger.error(f"AutoSapo scraper test failed: {e}")
        
        return result
    
    async def test_custojusto_scraper(self) -> Dict[str, Any]:
        """Test CustoJusto scraper with field validation"""
        print("\n" + "="*60)
        print("TESTING CUSTOJUSTO SCRAPER")
        print("="*60)
        
        result = {
            "status": "UNKNOWN",
            "listings_tested": 0,
            "field_coverage": {},
            "missing_fields": [],
            "ai_compatibility": {},
            "root_cause": ""
        }
        
        try:
            from scrapers.custojusto_scraper import CustoJustoScraper
            
            scraper = CustoJustoScraper()
            listings = await scraper.scrape_listings("carros", max_listings=10)
            
            result["listings_tested"] = len(listings)
            print(f"Scraped {len(listings)} listings")
            
            if len(listings) == 0:
                result["status"] = "FAIL"
                result["root_cause"] = "Scraper not implemented - completely non-functional"
                return result
            
            # Validate fields
            field_stats = {}
            for field in self.required_fields.keys():
                present = sum(1 for l in listings if l.get(field) and l.get(field) not in [None, "", [], 0])
                field_stats[field] = {
                    "present": present,
                    "total": len(listings),
                    "percentage": (present / len(listings)) * 100 if len(listings) > 0 else 0
                }
            
            result["field_coverage"] = field_stats
            
            # Identify missing fields
            missing_critical = []
            missing_required = []
            
            for field, importance in self.required_fields.items():
                if field_stats[field]["percentage"] < 50:
                    if importance in ["critical for LLM", "critical for Vision AI", "critical for pricing"]:
                        missing_critical.append(field)
                    elif importance == "required":
                        missing_required.append(field)
            
            result["missing_fields"] = {
                "critical": missing_critical,
                "required": missing_required
            }
            
            # AI compatibility check
            ai_compatibility = {
                "llm_compatible": field_stats.get("description", {}).get("percentage", 0) > 80,
                "vision_compatible": field_stats.get("images", {}).get("percentage", 0) > 80,
                "pricing_compatible": field_stats.get("km", {}).get("percentage", 0) > 80 and field_stats.get("year", {}).get("percentage", 0) > 80
            }
            result["ai_compatibility"] = ai_compatibility
            
            # Determine status
            if missing_critical:
                result["status"] = "AI-INCOMPATIBLE"
                result["root_cause"] = f"Missing critical fields: {', '.join(missing_critical)}"
            elif missing_required:
                result["status"] = "PARTIAL"
                result["root_cause"] = f"Missing required fields: {', '.join(missing_required)}"
            else:
                result["status"] = "FULLY_FUNCTIONAL"
                result["root_cause"] = "All required fields present"
            
            # Print results
            print(f"\nField Coverage:")
            for field, stats in field_stats.items():
                status = "✓" if stats["percentage"] > 80 else "⚠" if stats["percentage"] > 50 else "✗"
                print(f"  {status} {field}: {stats['present']}/{stats['total']} ({stats['percentage']:.1f}%)")
            
            print(f"\nAI Compatibility:")
            print(f"  LLM: {'✓' if ai_compatibility['llm_compatible'] else '✗'}")
            print(f"  Vision: {'✓' if ai_compatibility['vision_compatible'] else '✗'}")
            print(f"  Pricing: {'✓' if ai_compatibility['pricing_compatible'] else '✗'}")
            
            print(f"\nStatus: {result['status']}")
            print(f"Root Cause: {result['root_cause']}")
            
        except Exception as e:
            result["status"] = "ERROR"
            result["root_cause"] = f"Exception during scraping: {str(e)}"
            logger.error(f"CustoJusto scraper test failed: {e}")
        
        return result
    
    def calculate_ai_compatibility_score(self, result: Dict[str, Any]) -> int:
        """Calculate AI compatibility score (0-10)"""
        score = 10
        ai_compat = result.get("ai_compatibility", {})
        
        if not ai_compat.get("llm_compatible"):
            score -= 4  # Critical for LLM
        if not ai_compat.get("vision_compatible"):
            score -= 3  # Critical for Vision
        if not ai_compat.get("pricing_compatible"):
            score -= 3  # Critical for pricing
        
        return max(0, score)
    
    def generate_fix_recommendations(self, source: str, result: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate fix recommendations based on audit results"""
        recommendations = []
        
        missing_fields = result.get("missing_fields", {})
        if isinstance(missing_fields, list):
            # Handle case where missing_fields is a list
            missing_critical = missing_fields
            missing_required = []
        else:
            missing_critical = missing_fields.get("critical", [])
            missing_required = missing_fields.get("required", [])
        
        for field in missing_critical:
            if field == "description":
                recommendations.append({
                    "field": "description",
                    "priority": "P0",
                    "fix": "Enable detail page scraping (scrape_details=True) to extract descriptions from individual listing pages",
                    "file": f"scrapers/{source}_scraper.py"
                })
            elif field == "images":
                recommendations.append({
                    "field": "images",
                    "priority": "P0",
                    "fix": "Fix image extraction selector or use AI-based image detection from listing page",
                    "file": f"scrapers/{source}_scraper.py"
                })
            elif field == "km":
                recommendations.append({
                    "field": "km",
                    "priority": "P0",
                    "fix": "Fix KM extraction selector or add fallback extraction from title/description",
                    "file": f"scrapers/{source}_scraper.py"
                })
        
        for field in missing_required:
            recommendations.append({
                "field": field,
                "priority": "P1",
                "fix": f"Fix {field} extraction selector or add fallback extraction logic",
                "file": f"scrapers/{source}_scraper.py"
            })
        
        return recommendations
    
    def generate_report(self) -> str:
        """Generate comprehensive audit report"""
        print("\n" + "="*60)
        print("SCRAPER AUDIT REPORT")
        print("="*60)
        
        report_lines = []
        
        # Summary
        report_lines.append("# PRODUCTION SCRAPER AUDIT REPORT")
        report_lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Scraper Health Matrix
        report_lines.append("## SCRAPER HEALTH MATRIX")
        report_lines.append("")
        report_lines.append("| Source | Status | Listings Tested | AI Score (0-10) | LLM | Vision | Pricing |")
        report_lines.append("|--------|--------|----------------|-----------------|-----|--------|---------|")
        
        for source, result in self.results.items():
            status = result.get("status", "UNKNOWN")
            listings = result.get("listings_tested", 0)
            ai_score = self.calculate_ai_compatibility_score(result)
            ai_compat = result.get("ai_compatibility", {})
            
            llm = "✓" if ai_compat.get("llm_compatible") else "✗"
            vision = "✓" if ai_compat.get("vision_compatible") else "✗"
            pricing = "✓" if ai_compat.get("pricing_compatible") else "✗"
            
            report_lines.append(f"| {source.capitalize()} | {status} | {listings} | {ai_score}/10 | {llm} | {vision} | {pricing} |")
        
        report_lines.append("")
        
        # Detailed Analysis per Source
        for source, result in self.results.items():
            report_lines.append(f"## {source.capitalize()} Scraper")
            report_lines.append("")
            report_lines.append(f"**Status:** {result.get('status', 'UNKNOWN')}")
            report_lines.append(f"**Root Cause:** {result.get('root_cause', 'N/A')}")
            report_lines.append(f"**Listings Tested:** {result.get('listings_tested', 0)}")
            report_lines.append("")
            
            # Field Coverage
            report_lines.append("### Field Coverage")
            report_lines.append("")
            report_lines.append("| Field | Present | Total | Percentage | Status |")
            report_lines.append("|-------|---------|-------|------------|--------|")
            
            field_coverage = result.get("field_coverage", {})
            for field, stats in field_coverage.items():
                percentage = stats.get("percentage", 0)
                status = "✓" if percentage > 80 else "⚠" if percentage > 50 else "✗"
                report_lines.append(f"| {field} | {stats.get('present', 0)} | {stats.get('total', 0)} | {percentage:.1f}% | {status} |")
            
            report_lines.append("")
            
            # Missing Fields
            missing_fields = result.get("missing_fields", {})
            if isinstance(missing_fields, dict) and missing_fields.get("critical"):
                report_lines.append("### Missing Critical Fields")
                report_lines.append("")
                for field in missing_fields["critical"]:
                    report_lines.append(f"- **{field}**: {self.required_fields[field]}")
                report_lines.append("")
            
            if isinstance(missing_fields, dict) and missing_fields.get("required"):
                report_lines.append("### Missing Required Fields")
                report_lines.append("")
                for field in missing_fields["required"]:
                    report_lines.append(f"- **{field}**: {self.required_fields[field]}")
                report_lines.append("")
            
            # Fix Recommendations
            recommendations = self.generate_fix_recommendations(source, result)
            if recommendations:
                report_lines.append("### Fix Recommendations")
                report_lines.append("")
                for rec in recommendations:
                    report_lines.append(f"- **[{rec['priority']}] {rec['field']}**")
                    report_lines.append(f"  - Fix: {rec['fix']}")
                    report_lines.append(f"  - File: {rec['file']}")
                report_lines.append("")
        
        # Priority Summary
        report_lines.append("## FIX PRIORITY SUMMARY")
        report_lines.append("")
        
        p0_fixes = []
        p1_fixes = []
        p2_fixes = []
        
        for source, result in self.results.items():
            recommendations = self.generate_fix_recommendations(source, result)
            for rec in recommendations:
                if rec["priority"] == "P0":
                    p0_fixes.append(f"{source}: {rec['field']}")
                elif rec["priority"] == "P1":
                    p1_fixes.append(f"{source}: {rec['field']}")
                else:
                    p2_fixes.append(f"{source}: {rec['field']}")
        
        if p0_fixes:
            report_lines.append("### P0 (Critical - Block AI Pipeline)")
            for fix in p0_fixes:
                report_lines.append(f"- {fix}")
            report_lines.append("")
        
        if p1_fixes:
            report_lines.append("### P1 (High - Affect Data Quality)")
            for fix in p1_fixes:
                report_lines.append(f"- {fix}")
            report_lines.append("")
        
        if p2_fixes:
            report_lines.append("### P2 (Medium - Nice to Have)")
            for fix in p2_fixes:
                report_lines.append(f"- {fix}")
            report_lines.append("")
        
        # Production Readiness Assessment
        report_lines.append("## PRODUCTION READINESS ASSESSMENT")
        report_lines.append("")
        
        ai_compatible_scrapers = 0
        for source, result in self.results.items():
            ai_score = self.calculate_ai_compatibility_score(result)
            if ai_score >= 8:
                ai_compatible_scrapers += 1
        
        if ai_compatible_scrapers >= 2:
            report_lines.append("**Status:** PRODUCTION READY FOR AI PIPELINE")
            report_lines.append(f"**AI-Compatible Scrapers:** {ai_compatible_scrapers}/4")
            report_lines.append("")
            report_lines.append("The system has enough functional scrapers to run the AI pipeline with real data.")
        else:
            report_lines.append("**Status:** NOT PRODUCTION READY FOR AI PIPELINE")
            report_lines.append(f"**AI-Compatible Scrapers:** {ai_compatible_scrapers}/4")
            report_lines.append("")
            report_lines.append("The system does not have enough functional scrapers to reliably feed the AI pipeline.")
            report_lines.append("Please implement P0 fixes before deploying to production.")
        
        return "\n".join(report_lines)


async def main():
    """Run comprehensive scraper audit"""
    print("\n" + "="*60)
    print("AUTODEAL IA HUNTER - PRODUCTION SCRAPER AUDIT")
    print("="*60)
    
    auditor = ScraperAuditor()
    
    # Test all scrapers
    auditor.results["olx"] = await auditor.test_olx_scraper()
    auditor.results["standvirtual"] = await auditor.test_standvirtual_scraper()
    auditor.results["autosapo"] = await auditor.test_autosapo_scraper()
    auditor.results["custojusto"] = await auditor.test_custojusto_scraper()
    
    # Generate report
    report = auditor.generate_report()
    print(report)
    
    # Save report
    report_path = "d:/VER PRECOS/SCRAPER_AUDIT_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\nReport saved to: {report_path}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
