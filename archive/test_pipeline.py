"""
End-to-End Pipeline Test
Tests the new production pipeline with AI enrichment
"""
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from processing.validator import validator
from processing.ai_enrichment.llm_analyzer import llm_analyzer
from processing.ai_enrichment.vision_analyzer import vision_analyzer
from intelligence.pricing.engine import pricing_engine
from intelligence.scoring.engine import scoring_engine
from processing.pipeline import production_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_validation():
    """Test data validation"""
    print("\n" + "="*60)
    print("TEST 1: Data Validation")
    print("="*60)
    
    test_vehicle = {
        "source": "olx",
        "source_id": "test123",
        "url": "https://www.olx.pt/carro/test",
        "title": "BMW 320i 2020",
        "brand": "BMW",
        "model": "320i",
        "year": 2020,
        "price": 15000.0,
        "km": 50000,
        "vehicle_type": "carros",
        "description": "Carro em excelente estado, revisões feitas",
        "images": ["https://example.com/image1.jpg"]
    }
    
    result = validator.validate_vehicle(test_vehicle)
    print(f"Valid: {result.is_valid}")
    print(f"Data Quality Score: {result.data_quality_score:.2f}")
    print(f"Errors: {result.errors}")
    print(f"Warnings: {result.warnings}")
    
    return result.is_valid


def test_llm_analyzer():
    """Test LLM analyzer"""
    print("\n" + "="*60)
    print("TEST 2: LLM Analyzer")
    print("="*60)
    
    test_vehicle = {
        "source": "olx",
        "source_id": "test123",
        "url": "https://www.olx.pt/carro/test",
        "title": "BMW 320i 2020",
        "brand": "BMW",
        "model": "320i",
        "year": 2020,
        "km": 50000,
        "price": 15000.0,
        "vehicle_type": "carros",
        "description": "Carro em excelente estado, revisões feitas na concessionária, único dono, garagem fechada. Sem acidentes.",
        "images": ["https://example.com/image1.jpg"]
    }
    
    try:
        result = llm_analyzer.analyze_vehicle(test_vehicle)
        if result:
            print(f"LLM Risk Score: {result.llm_risk_score}")
            print(f"LLM Recommendation: {result.llm_recommendation}")
            print(f"LLM Confidence: {result.llm_confidence}")
            print(f"Processing Time: {result.processing_time_llm:.2f}s")
            return True
        else:
            print("LLM analyzer returned None")
            return False
    except Exception as e:
        print(f"LLM analyzer error: {e}")
        return False


def test_vision_analyzer():
    """Test Vision analyzer"""
    print("\n" + "="*60)
    print("TEST 3: Vision Analyzer")
    print("="*60)
    
    test_vehicle = {
        "source": "olx",
        "source_id": "test123",
        "url": "https://www.olx.pt/carro/test",
        "title": "BMW 320i 2020",
        "brand": "BMW",
        "model": "320i",
        "year": 2020,
        "km": 50000,
        "price": 15000.0,
        "vehicle_type": "carros",
        "description": "Carro em excelente estado",
        "images": ["https://via.placeholder.com/800x600"]  # Placeholder image
    }
    
    try:
        result = vision_analyzer.analyze_vehicle_images(test_vehicle)
        if result:
            print(f"Vision Condition Score: {result.vision_condition_score}")
            print(f"Vision Confidence: {result.vision_confidence}")
            print(f"Processing Time: {result.processing_time_vision:.2f}s")
            return True
        else:
            print("Vision analyzer returned None")
            return False
    except Exception as e:
        print(f"Vision analyzer error: {e}")
        return False


def test_pricing_engine():
    """Test pricing engine"""
    print("\n" + "="*60)
    print("TEST 4: Pricing Engine")
    print("="*60)
    
    test_vehicle = {
        "brand": "BMW",
        "model": "320i",
        "year": 2020,
        "km": 50000,
        "price": 15000.0,
        "ai_risk_score": 3.0,
        "condition_score": 8.0
    }
    
    try:
        result = pricing_engine.calculate_price(test_vehicle)
        print(f"Final Price: €{result['final_price']:.2f}")
        print(f"Statistical Price: €{result['statistical_price']:.2f}")
        print(f"Comparable Price: €{result['comparable_price']}")
        print(f"AI Adjustment: {result['ai_adjustment']:.2%}")
        print(f"Calculation Method: {result['calculation_method']}")
        return True
    except Exception as e:
        print(f"Pricing engine error: {e}")
        return False


def test_scoring_engine():
    """Test scoring engine"""
    print("\n" + "="*60)
    print("TEST 5: Scoring Engine")
    print("="*60)
    
    test_vehicle = {
        "brand": "BMW",
        "model": "320i",
        "year": 2020,
        "km": 50000,
        "price": 15000.0,
        "estimated_value": 18000.0,
        "ai_risk_score": 3.0,
        "condition_score": 8.0
    }
    
    try:
        result = scoring_engine.calculate_final_score(test_vehicle)
        print(f"Final Score: {result.final_score}/10")
        print(f"Market Deviation Score: {result.market_deviation_score}")
        print(f"AI Risk Score: {result.ai_risk_score}")
        print(f"Vision Damage Score: {result.vision_damage_score}")
        print(f"Score Interpretation: {result.score_interpretation}")
        print(f"Recommended Action: {result.recommended_action}")
        return True
    except Exception as e:
        print(f"Scoring engine error: {e}")
        return False


def test_full_pipeline():
    """Test full production pipeline"""
    print("\n" + "="*60)
    print("TEST 6: Full Production Pipeline")
    print("="*60)
    
    test_vehicle = {
        "source": "olx",
        "source_id": "test123",
        "url": "https://www.olx.pt/carro/test",
        "title": "BMW 320i 2020",
        "brand": "BMW",
        "model": "320i",
        "year": 2020,
        "km": 50000,
        "price": 15000.0,
        "vehicle_type": "carros",
        "description": "Carro em excelente estado, revisões feitas na concessionária, único dono, garagem fechada. Sem acidentes.",
        "images": ["https://via.placeholder.com/800x600"]
    }
    
    try:
        result = production_pipeline.process_vehicle(test_vehicle)
        print(f"Status: {result['status']}")
        if result['status'] == 'success':
            print(f"AI Risk Score: {result['ai_analysis']['llm_risk_score']}")
            print(f"Condition Score: {result['ai_analysis']['vision_condition_score']}")
            print(f"Estimated Value: €{result['pricing']['final_price']:.2f}")
            print(f"Deal Score: {result['scoring']['final_score']}/10")
            print(f"Interpretation: {result['scoring']['score_interpretation']}")
            return True
        else:
            print(f"Error: {result.get('error')}")
            return False
    except Exception as e:
        print(f"Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AUTODEAL IA HUNTER - PIPELINE TEST SUITE")
    print("="*60)
    
    results = {}
    
    # Run tests
    results["Validation"] = test_validation()
    results["LLM Analyzer"] = test_llm_analyzer()
    results["Vision Analyzer"] = test_vision_analyzer()
    results["Pricing Engine"] = test_pricing_engine()
    results["Scoring Engine"] = test_scoring_engine()
    results["Full Pipeline"] = test_full_pipeline()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
