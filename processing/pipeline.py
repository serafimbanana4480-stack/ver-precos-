"""
Production Pipeline
Orchestrates the entire data processing flow
"""
from __future__ import annotations
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from config import settings
from processing.validator import validator
from processing.ai_enrichment.llm_analyzer import llm_analyzer
from processing.ai_enrichment.vision_analyzer import vision_analyzer
from intelligence.pricing.engine import pricing_engine
from intelligence.scoring.engine import scoring_engine
from intelligence.profit.deal_profit_calculator import deal_profit_calculator
from utils.observability import track_scrape, track_ai_enrichment, track_pricing, track_pipeline, track_database

logger = logging.getLogger(__name__)


class ProductionPipeline:
    """
    Production pipeline with mandatory AI enrichment
    
    Pipeline stages:
    1. Data Validation
    2. AI Enrichment (LLM + Vision) - MANDATORY
    3. Hybrid Pricing
    4. Multi-dimensional Scoring
    5. Database Update
    """
    
    def __init__(self, db_path: Optional[str] = None):
        # Use config.settings.database_url if db_path not provided
        if db_path is None:
            if settings.use_sqlite:
                # Extract SQLite path from database_url
                db_url = settings.database_url
                if db_url.startswith("sqlite:///"):
                    db_path = db_url.replace("sqlite:///", "")
                elif db_url.startswith("sqlite://"):
                    db_path = db_url.replace("sqlite://", "")
                else:
                    db_path = "autodeal.db"
            else:
                # For PostgreSQL, we'll use SQLAlchemy connection string
                db_path = settings.database_url
        
        self.db_path = db_path
        self.ollama_available = settings.check_ollama_available()
        logger.info(f"Pipeline initialized with db_path: {self.db_path}")
        logger.info(f"Ollama available: {self.ollama_available}")
    
    @track_pipeline()
    def process_vehicle(self, vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single vehicle through the full pipeline
        
        Args:
            vehicle_data: Raw scraped vehicle data
            
        Returns:
            Processed vehicle with AI analysis, pricing, and scoring
        """
        try:
            logger.info(f"Processing vehicle {vehicle_data.get('source_id')}")
            
            # Pre-validation: normalize/extract year if missing
            if vehicle_data.get('year') is None:
                import re
                title = str(vehicle_data.get('title', ''))
                year_match = re.search(r'\b(19|20)\d{2}\b', title)
                if year_match:
                    extracted_year = int(year_match.group(0))
                    vehicle_data['year'] = extracted_year
                    logger.info(f"Extracted year={extracted_year} from title for vehicle {vehicle_data.get('source_id')}")
                else:
                    # Use current year as last resort fallback
                    from datetime import datetime
                    vehicle_data['year'] = datetime.now().year
                    logger.warning(f"No year found for vehicle {vehicle_data.get('source_id')}, using current year as fallback")
            
            # Stage 1: Data Validation
            validation = validator.validate_vehicle(vehicle_data)
            if not validation.is_valid:
                logger.warning(f"Vehicle {vehicle_data.get('source_id')} failed validation: {validation.errors}")
                # Skip vehicles with critical validation errors (missing required fields like year)
                critical_errors = [e for e in validation.errors if 'year' in e.lower() or 'price' in e.lower() or 'required field' in e.lower()]
                if critical_errors:
                    logger.error(f"Vehicle {vehicle_data.get('source_id')} skipped due to critical errors: {critical_errors}")
                    return {
                        'vehicle_id': vehicle_data.get('source_id'),
                        'status': 'error',
                        'error': f"Critical validation errors: {critical_errors}"
                    }
            
            # Stage 2: AI Enrichment (MANDATORY)
            ai_analysis = self._run_ai_enrichment(vehicle_data)
            
            # Merge AI analysis into vehicle data
            vehicle_data.update({
                'ai_risk_score': ai_analysis.llm_risk_score,
                'condition_score': ai_analysis.vision_condition_score,
                'ai_recommendation': ai_analysis.llm_recommendation,
                'detected_damages': ai_analysis.vision_exterior_damage,
                'has_accident_indicators': len(ai_analysis.vision_accident_indicators) > 0
            })
            
            # Stage 3: Hybrid Pricing
            pricing = pricing_engine.calculate_price(vehicle_data)
            if pricing.get('insufficient_data') or pricing.get('final_price') is None:
                vehicle_data['estimated_value'] = None
                vehicle_data['pricing_confidence'] = pricing.get('pricing_confidence', 'insufficient')
            else:
                vehicle_data['estimated_value'] = pricing['final_price']
                vehicle_data['pricing_confidence'] = pricing.get('pricing_confidence', 'medium')
            
            # Stage 4: Multi-dimensional Scoring
            scoring = scoring_engine.calculate_final_score(vehicle_data)
            vehicle_data['deal_score'] = scoring.final_score
            
            # Stage 4.5: Deal Profit Analysis
            profit_analysis = deal_profit_calculator.calculate_deal_profit(vehicle_data)
            vehicle_data.update({
                'price_discount_percentage': profit_analysis.price_discount_percentage,
                'estimated_savings': profit_analysis.estimated_savings,
                'buyer_profit': profit_analysis.buyer_profit,
                'buyer_profit_margin': profit_analysis.buyer_profit_margin,
                'buyer_roi': profit_analysis.buyer_roi,
                'repair_costs': profit_analysis.repair_costs,
                'taxes': profit_analysis.taxes,
                'total_additional_costs': profit_analysis.total_additional_costs,
                'deal_grade': profit_analysis.deal_grade,
                'profit_recommendation': profit_analysis.recommendation
            })
            
            # Stage 5: Database Update
            self._save_to_database(vehicle_data, validation, ai_analysis, pricing, scoring, profit_analysis)
            
            logger.info(f"Vehicle {vehicle_data.get('source_id')} processed successfully - Score: {scoring.final_score}")
            
            return {
                'vehicle_id': vehicle_data.get('source_id'),
                'validation': validation.dict(),
                'ai_analysis': ai_analysis.dict(),
                'pricing': pricing,
                'scoring': scoring.dict(),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Error processing vehicle {vehicle_data.get('source_id')}: {e}")
            return {
                'vehicle_id': vehicle_data.get('source_id'),
                'status': 'error',
                'error': str(e)
            }
    
    @track_ai_enrichment(ai_type='combined')
    def _run_ai_enrichment(self, vehicle_data: Dict[str, Any]):
        """
        Run AI enrichment (LLM + Vision) - MANDATORY with graceful fallback
        
        This is the critical change - AI is now INLINE in the pipeline
        If Ollama is not available, uses neutral fallback values
        """
        source_id = vehicle_data.get('source_id', 'unknown')

        if getattr(settings, 'fast_scrape_mode', False):
            logger.info(f"Fast scrape mode: skipping AI for {source_id}")
            return self._get_neutral_ai_fallback()
        
        if not self.ollama_available:
            logger.warning(f"Ollama not available, using neutral AI fallback for vehicle {source_id}")
            return self._get_neutral_ai_fallback()

        run_llm = getattr(settings, 'enable_pipeline_llm', True)
        run_vision = getattr(settings, 'enable_pipeline_vision', True)
        if not run_llm and not run_vision:
            return self._get_neutral_ai_fallback()
        
        logger.info(f"Running AI enrichment for vehicle {source_id}")
        
        try:
            llm_result = llm_analyzer.analyze_vehicle(vehicle_data) if run_llm else None
            
            vision_result = None
            if run_vision and vehicle_data.get('images'):
                try:
                    vision_result = vision_analyzer.analyze_vehicle_images(vehicle_data)
                except Exception as vision_err:
                    logger.warning(f"Vision skipped for {source_id}: {vision_err}")
            
            # Merge results
            # Vision result will have placeholder LLM fields, LLM result will have placeholder Vision fields
            # We need to merge them properly
            
            if not llm_result and not vision_result:
                return self._get_neutral_ai_fallback()

            merged = llm_result.dict() if llm_result else self._get_neutral_ai_fallback().dict()
            
            if vision_result:
                vision_dict = vision_result.dict()
                # Overwrite Vision-specific fields
                merged.update({
                    'vision_exterior_damage': vision_dict.get('vision_exterior_damage', []),
                    'vision_accident_indicators': vision_dict.get('vision_accident_indicators', []),
                    'vision_tire_condition': vision_dict.get('vision_tire_condition', 'fair'),
                    'vision_interior_condition': vision_dict.get('vision_interior_condition', 'fair'),
                    'vision_condition_score': vision_dict.get('vision_condition_score', 6.0),
                    'vision_major_concerns': vision_dict.get('vision_major_concerns', []),
                    'vision_confidence': vision_dict.get('vision_confidence', 0.0),
                    'processing_time_vision': vision_dict.get('processing_time_vision', 0.0)
                })
            
            # Convert back to AIAnalysisResult
            from validation.schemas import AIAnalysisResult
            return AIAnalysisResult(**merged)
            
        except Exception as e:
            logger.error(f"AI enrichment failed for vehicle {source_id}: {e}, using fallback")
            return self._get_neutral_ai_fallback()
    
    def _get_neutral_ai_fallback(self):
        """
        Return neutral AI values when Ollama is not available
        This allows the pipeline to continue without AI
        """
        from validation.schemas import AIAnalysisResult
        return AIAnalysisResult(
            llm_risk_score=5.0,
            llm_market_position="fair",
            llm_recommendation="CAUTION",
            llm_reasoning="AI analysis not available - Ollama service not running",
            llm_confidence=0.0,
            vision_exterior_damage=[],
            vision_accident_indicators=[],
            vision_tire_condition="fair",
            vision_interior_condition="fair",
            vision_condition_score=6.0,
            vision_major_concerns=[],
            vision_confidence=0.0,
            processing_time_llm=0.0,
            processing_time_vision=0.0
        )
    
    @track_database(operation='insert_update')
    def _save_to_database(self, vehicle: Dict[str, Any], validation, ai_analysis, pricing, scoring, profit_analysis):
        """Save processed vehicle to database and track price history"""
        from utils.source_normalize import normalize_source
        from database.db import get_db_context
        from database.models import Vehicle, PriceHistory

        vehicle['source'] = normalize_source(vehicle.get('source'))
        
        # Normalize fuel_type, transmission, and seller_type before DB save
        from validation.normalizers import normalize_fuel_type, normalize_transmission
        from database.models import FuelType as DBFuelType, Transmission as DBTransmission
        
        raw_fuel = vehicle.get('fuel_type')
        normalized_fuel = normalize_fuel_type(raw_fuel)
        if normalized_fuel:
            try:
                vehicle['fuel_type'] = DBFuelType(normalized_fuel)
            except ValueError:
                vehicle['fuel_type'] = None
        else:
            vehicle['fuel_type'] = None
        
        raw_trans = vehicle.get('transmission')
        normalized_trans = normalize_transmission(raw_trans)
        if normalized_trans:
            try:
                vehicle['transmission'] = DBTransmission(normalized_trans)
            except ValueError:
                vehicle['transmission'] = None
        else:
            vehicle['transmission'] = None
        
        # Normalize seller_type to valid values or None
        seller_type = vehicle.get('seller_type')
        if seller_type:
            seller_lower = str(seller_type).lower().strip()
            if seller_lower in ('particular', 'individual', 'private'):
                vehicle['seller_type'] = 'particular'
            elif seller_lower in ('profissional', 'dealer', 'stand'):
                vehicle['seller_type'] = 'profissional'
            else:
                vehicle['seller_type'] = None
        else:
            vehicle['seller_type'] = None
        
        try:
            with get_db_context() as db:
                # Check if vehicle already exists
                existing = db.query(Vehicle).filter(
                    Vehicle.source == vehicle.get('source'),
                    Vehicle.source_id == vehicle.get('source_id')
                ).first()

                if existing:
                    old_price = existing.price

                    # Update fields
                    existing.estimated_value = vehicle.get('estimated_value')
                    existing.deal_score = vehicle.get('deal_score')
                    existing.ai_risk_score = ai_analysis.llm_risk_score
                    existing.condition_score = ai_analysis.vision_condition_score
                    existing.ai_recommendation = ai_analysis.llm_recommendation
                    existing.damages_detected = ai_analysis.vision_exterior_damage
                    existing.has_accident = len(ai_analysis.vision_accident_indicators) > 0
                    existing.ai_review = ai_analysis.llm_reasoning[:500]
                    existing.profit_potential = vehicle.get('buyer_profit')
                    existing.price_discount_percentage = vehicle.get('price_discount_percentage')
                    existing.estimated_savings = vehicle.get('estimated_savings')
                    existing.buyer_profit = vehicle.get('buyer_profit')
                    existing.buyer_profit_margin = vehicle.get('buyer_profit_margin')
                    existing.buyer_roi = vehicle.get('buyer_roi')
                    existing.repair_costs = vehicle.get('repair_costs')
                    existing.taxes = vehicle.get('taxes')
                    existing.total_additional_costs = vehicle.get('total_additional_costs')
                    existing.deal_grade = vehicle.get('deal_grade')
                    existing.profit_recommendation = vehicle.get('profit_recommendation')
                    existing.last_seen = datetime.now(timezone.utc)

                    # Update price and core fields that may change on re-scrape
                    existing.price = vehicle.get('price')
                    existing.km = vehicle.get('km')
                    existing.title = vehicle.get('title')
                    existing.description = vehicle.get('description', '')
                    existing.location = vehicle.get('location', '')
                    existing.district = vehicle.get('district', '')
                    existing.url = str(vehicle.get('url'))
                    existing.scrape_count = (existing.scrape_count or 1) + 1

                    # Record price history if price changed
                    if old_price != existing.price:
                        price_history = PriceHistory(
                            vehicle_id=existing.id,
                            price=existing.price,
                            recorded_at=datetime.now(timezone.utc)
                        )
                        db.add(price_history)
                else:
                    # Create new vehicle
                    new_vehicle = Vehicle(
                        source=vehicle.get('source'),
                        source_id=vehicle.get('source_id'),
                        url=str(vehicle.get('url')),
                        title=vehicle.get('title'),
                        brand=vehicle.get('brand'),
                        model=vehicle.get('model'),
                        year=vehicle.get('year'),
                        km=vehicle.get('km'),
                        price=vehicle.get('price'),
                        vehicle_type=vehicle.get('vehicle_type') or 'carros',
                        description=vehicle.get('description', ''),
                        images=vehicle.get('images', []),
                        location=vehicle.get('location', ''),
                        district=vehicle.get('district', ''),
                        fuel_type=vehicle.get('fuel_type') or None,
                        transmission=vehicle.get('transmission') or None,
                        estimated_value=vehicle.get('estimated_value'),
                        deal_score=vehicle.get('deal_score'),
                        ai_risk_score=ai_analysis.llm_risk_score,
                        condition_score=ai_analysis.vision_condition_score,
                        ai_recommendation=ai_analysis.llm_recommendation,
                        damages_detected=ai_analysis.vision_exterior_damage,
                        has_accident=len(ai_analysis.vision_accident_indicators) > 0,
                        ai_review=ai_analysis.llm_reasoning[:500],
                        profit_potential=vehicle.get('buyer_profit'),
                        price_discount_percentage=vehicle.get('price_discount_percentage'),
                        estimated_savings=vehicle.get('estimated_savings'),
                        buyer_profit=vehicle.get('buyer_profit'),
                        buyer_profit_margin=vehicle.get('buyer_profit_margin'),
                        buyer_roi=vehicle.get('buyer_roi'),
                        repair_costs=vehicle.get('repair_costs'),
                        taxes=vehicle.get('taxes'),
                        total_additional_costs=vehicle.get('total_additional_costs'),
                        deal_grade=vehicle.get('deal_grade'),
                        profit_recommendation=vehicle.get('profit_recommendation'),
                        first_seen=datetime.now(timezone.utc),
                        last_seen=datetime.now(timezone.utc),
                        is_active=True
                    )
                    db.add(new_vehicle)
                    db.flush()  # Get the assigned ID

                    # Create initial price history snapshot
                    price_history = PriceHistory(
                        vehicle_id=new_vehicle.id,
                        price=new_vehicle.price,
                        recorded_at=datetime.now(timezone.utc)
                    )
                    db.add(price_history)
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            raise
    
    def process_batch(self, vehicles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a batch of vehicles
        
        Args:
            vehicles: List of vehicle data dictionaries
            
        Returns:
            Summary of processing results
        """
        results = {
            'total': len(vehicles),
            'success': 0,
            'error': 0,
            'avg_score': 0.0,
            'processing_time': 0.0
        }
        
        start_time = datetime.utcnow()
        total_score = 0.0
        
        for vehicle in vehicles:
            result = self.process_vehicle(vehicle)
            
            if result['status'] == 'success':
                results['success'] += 1
                total_score += result['scoring']['final_score']
            else:
                results['error'] += 1
        
        results['processing_time'] = (datetime.utcnow() - start_time).total_seconds()
        
        if results['success'] > 0:
            results['avg_score'] = total_score / results['success']
        
        return results


# Singleton instance - uses config.settings.database_url
production_pipeline = ProductionPipeline(db_path=None)


# Legacy compatibility alias.
Pipeline = ProductionPipeline
