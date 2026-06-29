"""
AI Pipeline Integration Audit
Verify that AI components are correctly integrated into production pipeline
"""
import sqlite3
import logging
from typing import Dict, List, Any
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIPipelineAuditor:
    """Audits AI pipeline integration in production system"""
    
    def __init__(self, db_path: str = "d:/VER PRECOS/autodeal.db"):
        self.db_path = db_path
        self.results = {
            "total_vehicles": 0,
            "llm_executed": 0,
            "vision_executed": 0,
            "ai_features_stored": 0,
            "pricing_used_ai": 0,
            "deal_scored": 0,
            "breakdown_points": [],
            "missing_integrations": []
        }
    
    def check_database_schema(self) -> Dict[str, Any]:
        """Check if AI-related columns exist in database"""
        print("\n" + "="*60)
        print("DATABASE SCHEMA CHECK")
        print("="*60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute("PRAGMA table_info(vehicles)")
        columns = [row[1] for row in cursor.fetchall()]
        
        ai_columns = {
            "ai_risk_score": False,
            "ai_recommendation": False,
            "vision_confidence": False,
            "llm_confidence": False,
            "detected_damages": False,
            "has_accident_indicators": False,
            "ai_review": False,
            "condition_score": False,
            "market_deviation": False,
            "deal_score": False
        }
        
        for col in ai_columns.keys():
            if col in columns:
                ai_columns[col] = True
                print(f"  ✓ {col} column exists")
            else:
                print(f"  ✗ {col} column MISSING")
        
        conn.close()
        
        return ai_columns
    
    def check_ai_execution_coverage(self) -> Dict[str, Any]:
        """Check AI execution coverage across all vehicles"""
        print("\n" + "="*60)
        print("AI EXECUTION COVERAGE CHECK")
        print("="*60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get total vehicles
        cursor.execute("SELECT COUNT(*) FROM vehicles")
        self.results["total_vehicles"] = cursor.fetchone()[0]
        print(f"Total vehicles in database: {self.results['total_vehicles']}")
        
        # Check LLM execution (ai_review exists and not empty)
        cursor.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE ai_review IS NOT NULL AND length(ai_review) > 10
        """)
        self.results["llm_executed"] = cursor.fetchone()[0]
        llm_coverage = (self.results["llm_executed"] / self.results["total_vehicles"]) * 100 if self.results["total_vehicles"] > 0 else 0
        print(f"LLM analysis executed: {self.results['llm_executed']}/{self.results['total_vehicles']} ({llm_coverage:.1f}%)")
        
        # Check Vision execution (condition_score exists)
        cursor.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE condition_score IS NOT NULL
        """)
        self.results["vision_executed"] = cursor.fetchone()[0]
        vision_coverage = (self.results["vision_executed"] / self.results["total_vehicles"]) * 100 if self.results["total_vehicles"] > 0 else 0
        print(f"Vision analysis executed: {self.results['vision_executed']}/{self.results['total_vehicles']} ({vision_coverage:.1f}%)")
        
        # Check AI features stored (ai_risk_score, ai_recommendation)
        cursor.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE ai_risk_score IS NOT NULL AND ai_recommendation IS NOT NULL
        """)
        self.results["ai_features_stored"] = cursor.fetchone()[0]
        features_coverage = (self.results["ai_features_stored"] / self.results["total_vehicles"]) * 100 if self.results["total_vehicles"] > 0 else 0
        print(f"AI features stored: {self.results['ai_features_stored']}/{self.results['total_vehicles']} ({features_coverage:.1f}%)")
        
        # Check deal scoring (deal_score exists)
        cursor.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE deal_score IS NOT NULL
        """)
        self.results["deal_scored"] = cursor.fetchone()[0]
        scoring_coverage = (self.results["deal_scored"] / self.results["total_vehicles"]) * 100 if self.results["total_vehicles"] > 0 else 0
        print(f"Deal scoring executed: {self.results['deal_scored']}/{self.results['total_vehicles']} ({scoring_coverage:.1f}%)")
        
        conn.close()
        
        return {
            "llm_coverage": llm_coverage,
            "vision_coverage": vision_coverage,
            "features_coverage": features_coverage,
            "scoring_coverage": scoring_coverage
        }
    
    def check_pipeline_architecture(self) -> Dict[str, Any]:
        """Check if AI is integrated into production pipeline"""
        print("\n" + "="*60)
        print("PIPELINE ARCHITECTURE CHECK")
        print("="*60)
        
        # Read the production pipeline file
        try:
            with open("d:/VER PRECOS/processing/pipeline.py", "r") as f:
                pipeline_content = f.read()
            
            # Check if AI enrichment is called
            llm_called = "llm_analyzer" in pipeline_content
            vision_called = "vision_analyzer" in pipeline_content
            
            print(f"LLM analyzer called in pipeline: {'✓' if llm_called else '✗'}")
            print(f"Vision analyzer called in pipeline: {'✓' if vision_called else '✗'}")
            
            # Check if AI is mandatory or optional
            ai_mandatory = "mandatory" in pipeline_content.lower() or "required" in pipeline_content.lower()
            print(f"AI enrichment is mandatory: {'✓' if ai_mandatory else '✗ (may be optional)'}")
            
            return {
                "llm_in_pipeline": llm_called,
                "vision_in_pipeline": vision_called,
                "ai_mandatory": ai_mandatory
            }
        except Exception as e:
            logger.error(f"Error reading pipeline file: {e}")
            return {
                "llm_in_pipeline": False,
                "vision_in_pipeline": False,
                "ai_mandatory": False,
                "error": str(e)
            }
    
    def check_main_integration(self) -> Dict[str, Any]:
        """Check if main.py uses the production pipeline"""
        print("\n" + "="*60)
        print("MAIN.PY INTEGRATION CHECK")
        print("="*60)
        
        try:
            with open("d:/VER PRECOS/main.py", "r") as f:
                main_content = f.read()
            
            # Check if production_pipeline is imported
            production_pipeline_imported = "production_pipeline" in main_content
            print(f"Production pipeline imported: {'✓' if production_pipeline_imported else '✗'}")
            
            # Check if production_pipeline is used in scrape command
            pipeline_used_in_scrape = "production_pipeline" in main_content and "scrape" in main_content
            print(f"Production pipeline used in scrape: {'✓' if pipeline_used_in_scrape else '✗'}")
            
            return {
                "production_pipeline_imported": production_pipeline_imported,
                "pipeline_used_in_scrape": pipeline_used_in_scrape
            }
        except Exception as e:
            logger.error(f"Error reading main.py: {e}")
            return {
                "production_pipeline_imported": False,
                "pipeline_used_in_scrape": False,
                "error": str(e)
            }
    
    def identify_breakdown_points(self) -> List[str]:
        """Identify where the AI pipeline breaks"""
        print("\n" + "="*60)
        print("PIPELINE BREAKDOWN ANALYSIS")
        print("="*60)
        
        breakdown_points = []
        
        # Check if vehicles have descriptions (required for LLM)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE description IS NULL OR length(description) < 10
        """)
        no_description = cursor.fetchone()[0]
        
        if no_description > self.results["total_vehicles"] * 0.8:
            breakdown_points.append(f"80%+ vehicles lack descriptions - LLM cannot function")
            print(f"  [!] 80%+ vehicles lack descriptions - LLM cannot function")
        
        # Check if vehicles have images (required for Vision)
        cursor.execute("""
            SELECT COUNT(*) FROM vehicles 
            WHERE images IS NULL OR json_array_length(images) = 0
        """)
        no_images = cursor.fetchone()[0]
        
        if no_images > self.results["total_vehicles"] * 0.8:
            breakdown_points.append(f"80%+ vehicles lack images - Vision AI cannot function")
            print(f"  [!] 80%+ vehicles lack images - Vision AI cannot function")
        
        # Check if AI execution coverage is low
        if self.results["llm_executed"] < self.results["total_vehicles"] * 0.1:
            breakdown_points.append(f"LLM execution coverage < 10% - AI not integrated in pipeline")
            print(f"  [!] LLM execution coverage < 10% - AI not integrated in pipeline")
        
        if self.results["vision_executed"] < self.results["total_vehicles"] * 0.1:
            breakdown_points.append(f"Vision execution coverage < 10% - AI not integrated in pipeline")
            print(f"  [!] Vision execution coverage < 10% - AI not integrated in pipeline")
        
        conn.close()
        
        if not breakdown_points:
            print("  ✓ No breakdown points identified")
        
        self.results["breakdown_points"] = breakdown_points
        return breakdown_points
    
    def calculate_ai_coverage_score(self) -> int:
        """Calculate overall AI pipeline coverage score (0-100)"""
        if self.results["total_vehicles"] == 0:
            return 0
        
        scores = []
        
        # LLM coverage
        llm_score = (self.results["llm_executed"] / self.results["total_vehicles"]) * 100
        scores.append(llm_score)
        
        # Vision coverage
        vision_score = (self.results["vision_executed"] / self.results["total_vehicles"]) * 100
        scores.append(vision_score)
        
        # AI features stored
        features_score = (self.results["ai_features_stored"] / self.results["total_vehicles"]) * 100
        scores.append(features_score)
        
        # Deal scoring
        scoring_score = (self.results["deal_scored"] / self.results["total_vehicles"]) * 100
        scores.append(scoring_score)
        
        return int(sum(scores) / len(scores))
    
    def generate_report(self) -> str:
        """Generate comprehensive AI pipeline integration report"""
        print("\n" + "="*60)
        print("AI PIPELINE INTEGRATION REPORT")
        print("="*60)
        
        report_lines = []
        
        # Summary
        ai_coverage = self.calculate_ai_coverage_score()
        
        report_lines.append("# AI PIPELINE INTEGRATION AUDIT REPORT")
        report_lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        report_lines.append("## EXECUTIVE SUMMARY")
        report_lines.append("")
        report_lines.append(f"**AI Execution Coverage:** {ai_coverage}%")
        report_lines.append(f"**Total Vehicles:** {self.results['total_vehicles']}")
        report_lines.append(f"**LLM Executed:** {self.results['llm_executed']}")
        report_lines.append(f"**Vision Executed:** {self.results['vision_executed']}")
        report_lines.append(f"**AI Features Stored:** {self.results['ai_features_stored']}")
        report_lines.append(f"**Deal Scored:** {self.results['deal_scored']}")
        report_lines.append("")
        
        # Verdict
        if ai_coverage >= 80:
            report_lines.append("## VERDICT: AI PRODUCT")
            report_lines.append("")
            report_lines.append("The system is an AI product with full pipeline integration.")
        elif ai_coverage >= 50:
            report_lines.append("## VERDICT: PARTIAL AI INTEGRATION")
            report_lines.append("")
            report_lines.append("The system has partial AI integration but needs improvements.")
        else:
            report_lines.append("## VERDICT: DATA TOOL ONLY")
            report_lines.append("")
            report_lines.append("The system is NOT an AI product. AI is not integrated into the production pipeline.")
        
        report_lines.append("")
        
        # Detailed Results
        report_lines.append("## DETAILED RESULTS")
        report_lines.append("")
        
        coverage = self.check_ai_execution_coverage()
        report_lines.append("### AI Execution Coverage")
        report_lines.append("")
        report_lines.append(f"- LLM Analysis: {coverage['llm_coverage']:.1f}%")
        report_lines.append(f"- Vision Analysis: {coverage['vision_coverage']:.1f}%")
        report_lines.append(f"- AI Features Stored: {coverage['features_coverage']:.1f}%")
        report_lines.append(f"- Deal Scoring: {coverage['scoring_coverage']:.1f}%")
        report_lines.append("")
        
        # Pipeline Architecture
        pipeline_check = self.check_pipeline_architecture()
        report_lines.append("### Pipeline Architecture")
        report_lines.append("")
        report_lines.append(f"- LLM Analyzer in Pipeline: {'✓' if pipeline_check.get('llm_in_pipeline') else '✗'}")
        report_lines.append(f"- Vision Analyzer in Pipeline: {'✓' if pipeline_check.get('vision_in_pipeline') else '✗'}")
        report_lines.append(f"- AI Enrichment Mandatory: {'✓' if pipeline_check.get('ai_mandatory') else '✗'}")
        report_lines.append("")
        
        # Main Integration
        main_check = self.check_main_integration()
        report_lines.append("### Main.py Integration")
        report_lines.append("")
        report_lines.append(f"- Production Pipeline Imported: {'✓' if main_check.get('production_pipeline_imported') else '✗'}")
        report_lines.append(f"- Pipeline Used in Scrape: {'✓' if main_check.get('pipeline_used_in_scrape') else '✗'}")
        report_lines.append("")
        
        # Breakdown Points
        if self.results["breakdown_points"]:
            report_lines.append("## PIPELINE BREAKDOWN POINTS")
            report_lines.append("")
            for point in self.results["breakdown_points"]:
                report_lines.append(f"- {point}")
            report_lines.append("")
        
        # Missing Integrations
        missing = []
        if not pipeline_check.get("llm_in_pipeline"):
            missing.append("LLM analyzer not in production pipeline")
        if not pipeline_check.get("vision_in_pipeline"):
            missing.append("Vision analyzer not in production pipeline")
        if not main_check.get("pipeline_used_in_scrape"):
            missing.append("Production pipeline not used in main.py scrape command")
        
        if missing:
            report_lines.append("## MISSING INTEGRATIONS")
            report_lines.append("")
            for item in missing:
                report_lines.append(f"- {item}")
            report_lines.append("")
        
        # Fix Recommendations
        report_lines.append("## FIX RECOMMENDATIONS")
        report_lines.append("")
        
        if self.results["llm_executed"] < self.results["total_vehicles"] * 0.5:
            report_lines.append("### P0: Enable AI in Production Pipeline")
            report_lines.append("")
            report_lines.append("The AI enrichment is not being executed for most vehicles. Fix:")
            report_lines.append("")
            report_lines.append("1. Ensure `scrape_details=True` is enabled in scrapers to extract descriptions and images")
            report_lines.append("2. Verify production_pipeline.process_vehicle() is called for every scraped vehicle")
            report_lines.append("3. Remove any skip/bypass logic for AI enrichment")
            report_lines.append("")
        
        if not main_check.get("pipeline_used_in_scrape"):
            report_lines.append("### P0: Integrate Production Pipeline in main.py")
            report_lines.append("")
            report_lines.append("The production pipeline is not being used in the scrape command. Fix:")
            report_lines.append("")
            report_lines.append("1. Import production_pipeline in main.py")
            report_lines.append("2. Replace direct database saves with production_pipeline.process_batch()")
            report_lines.append("3. Ensure all scraped vehicles pass through the pipeline")
            report_lines.append("")
        
        # Architecture Diagram
        report_lines.append("## CORRECTED ARCHITECTURE")
        report_lines.append("")
        report_lines.append("```")
        report_lines.append("Scraped Vehicle")
        report_lines.append("  ↓")
        report_lines.append("Data Validation")
        report_lines.append("  ↓")
        report_lines.append("AI Enrichment (MANDATORY)")
        report_lines.append("  ├─ LLM Analysis (description → risk_score, recommendation)")
        report_lines.append("  └─ Vision Analysis (images → condition_score, damages)")
        report_lines.append("  ↓")
        report_lines.append("Pricing Engine (uses AI features)")
        report_lines.append("  ↓")
        report_lines.append("Deal Scoring Engine (uses AI features)")
        report_lines.append("  ↓")
        report_lines.append("Database (with AI scores)")
        report_lines.append("```")
        report_lines.append("")
        
        return "\n".join(report_lines)


def main():
    """Run AI pipeline integration audit"""
    print("\n" + "="*60)
    print("AUTODEAL IA HUNTER - AI PIPELINE INTEGRATION AUDIT")
    print("="*60)
    
    auditor = AIPipelineAuditor()
    
    # Run all checks
    auditor.check_database_schema()
    auditor.check_ai_execution_coverage()
    auditor.check_pipeline_architecture()
    auditor.check_main_integration()
    auditor.identify_breakdown_points()
    
    # Generate report
    report = auditor.generate_report()
    print(report)
    
    # Save report
    report_path = "d:/VER PRECOS/AI_PIPELINE_INTEGRATION_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\nReport saved to: {report_path}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
