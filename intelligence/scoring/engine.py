"""
Multi-Dimensional Deal Scoring Engine
Production-grade scoring with market deviation, AI risk, vision damage, anomaly detection, demand signal
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from validation.schemas import DealScore
import sqlite3
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


class DealScoringEngine:
    """
    Multi-dimensional deal scoring engine
    
    Final Score = 35% Market Deviation + 25% AI Risk + 20% Vision Damage + 10% Price Anomaly + 10% Demand Signal
    """
    
    def __init__(self, db_path: Optional[str] = None):
        # Use config.settings if not provided
        if db_path is None:
            if settings.use_sqlite:
                db_url = settings.database_url
                if db_url.startswith("sqlite:///"):
                    db_path = db_url.replace("sqlite:///", "")
                elif db_url.startswith("sqlite://"):
                    db_path = db_url.replace("sqlite://", "")
                else:
                    db_path = "autodeal.db"
            else:
                db_path = settings.database_url
        
        self.db_path = db_path
    
    def calculate_final_score(self, vehicle: Dict[str, Any]) -> DealScore:
        """
        Calculate final deal score (0-10) from multiple dimensions
        
        Args:
            vehicle: Vehicle dictionary with pricing and AI analysis
            
        Returns:
            DealScore with component scores and final score
        """
        try:
            # 1. Market Deviation Score (0-10)
            market_score = self._calculate_market_score(vehicle)
            
            # 2. AI Risk Score (0-10) - inverted: high risk = low score
            ai_risk_score = self._calculate_ai_risk_score(vehicle)
            
            # 3. Vision Damage Score (0-10)
            vision_score = self._calculate_vision_score(vehicle)
            
            # 4. Price Anomaly Detection (0-10)
            anomaly_score = self._detect_price_anomaly(vehicle)
            
            # 5. Demand Trend Signal (0-10)
            demand_score = self._calculate_demand_signal(vehicle)
            
            # Weighted combination
            final_score = (
                market_score * 0.35 +      # 35% - most important
                ai_risk_score * 0.25 +      # 25% - AI intelligence
                vision_score * 0.20 +       # 20% - visual condition
                anomaly_score * 0.10 +      # 10% - anomaly detection
                demand_score * 0.10         # 10% - market demand
            )
            
            # Normalize to 0-10
            final_score = max(0.0, min(10.0, final_score))
            
            # Determine interpretation and action
            interpretation, action = self._interpret_score(final_score)
            
            return DealScore(
                market_deviation_score=round(market_score, 1),
                ai_risk_score=round(ai_risk_score, 1),
                vision_damage_score=round(vision_score, 1),
                price_anomaly_score=round(anomaly_score, 1),
                demand_signal_score=round(demand_score, 1),
                final_score=round(final_score, 1),
                score_interpretation=interpretation,
                recommended_action=action,
                calculated_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error calculating deal score: {e}")
            # Return neutral score on error
            return DealScore(
                market_deviation_score=5.0,
                ai_risk_score=5.0,
                vision_damage_score=5.0,
                price_anomaly_score=5.0,
                demand_signal_score=5.0,
                final_score=5.0,
                score_interpretation="Fair Deal",
                recommended_action="No Action",
                calculated_at=datetime.utcnow()
            )
    
    def _calculate_market_score(self, vehicle: Dict[str, Any]) -> float:
        """
        Calculate market deviation score aligned with robust pricing v6.
        
        Uses estimated_value * 1.10 as market asking benchmark,
        then computes discount vs actual price.
        Score 5.0 = neutral (price = market asking)
        """
        price = vehicle.get('price', 0) or 0
        estimated_value = vehicle.get('estimated_value')
        if estimated_value is None or estimated_value <= 0 or price <= 0:
            return 5.0  # Neutral if insufficient pricing data
        
        market_asking = estimated_value * 1.10
        discount = (market_asking - price) / market_asking
        raw_score = 5.0 + (discount * 15.0)
        return max(0.0, min(10.0, raw_score))
    
    def _calculate_ai_risk_score(self, vehicle: Dict[str, Any]) -> float:
        """
        Calculate AI risk score (inverted: high risk = low score)
        """
        # Get AI risk score from LLM analysis
        ai_risk = vehicle.get('ai_risk_score', 5.0)
        
        # Invert: high risk (9-10) = low score (1-2)
        ai_risk_score = 10 - ai_risk
        
        return max(0.0, min(10.0, ai_risk_score))
    
    def _calculate_vision_score(self, vehicle: Dict[str, Any]) -> float:
        """
        Calculate vision damage score (from Vision analysis)
        """
        # Get condition score from Vision analysis
        condition_score = vehicle.get('condition_score', 6.0)
        
        return max(0.0, min(10.0, condition_score))
    
    def _detect_price_anomaly(self, vehicle: Dict[str, Any]) -> float:
        """
        Detect if price is anomalous (too low = scam, too high = bad deal)
        """
        price = vehicle.get('price', 0) or 0
        brand = vehicle.get('brand', '')
        model = vehicle.get('model', '')
        year = vehicle.get('year') or 2020
        
        # Calculate expected price range for this vehicle
        expected_range = self._get_price_range(brand, model, year)
        
        if not expected_range:
            return 5.0  # Neutral if no data
        
        min_price = expected_range['min']
        max_price = expected_range['max']
        
        if price < min_price * 0.5:
            return 2.0  # Suspiciously low
        elif price < min_price:
            return 5.0  # Below minimum but not suspicious
        elif price > max_price:
            return 3.0  # Above maximum
        else:
            return 8.0  # Within expected range
    
    def _get_price_range(self, brand: str, model: str, year: int) -> Optional[Dict[str, float]]:
        """
        Get expected price range for similar vehicles from database
        """
        from database.db import get_db_context
        from sqlalchemy import text
        try:
            with get_db_context() as db:
                query = text("""
                    SELECT MIN(price) as min_price, MAX(price) as max_price, AVG(price) as avg_price
                    FROM vehicles
                    WHERE brand LIKE :brand_pattern
                    AND year BETWEEN :y_start AND :y_end
                    AND price > 0
                    AND is_active = 1
                """)
                result = db.execute(query, {
                    "brand_pattern": f"%{brand}%",
                    "y_start": year - 2,
                    "y_end": year + 2
                })
                row = result.fetchone()
            if row and row[0]:
                return {
                    'min': row[0],
                    'max': row[1],
                    'avg': row[2]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting price range: {e}")
            return None
    
    def _calculate_demand_signal(self, vehicle: Dict[str, Any]) -> float:
        """
        Calculate demand signal based on market data
        """
        brand = vehicle.get('brand', '')
        model = vehicle.get('model', '')
        year = vehicle.get('year') or 2020
        
        # Count similar vehicles in database (proxy for supply)
        similar_count = self._count_similar_vehicles(brand, model, year)
        
        # Calculate days on market (if available)
        # days_on_market = self._get_avg_days_on_market(brand, model) # Not used currently but could be
        
        # High demand = low supply OR fast sales
        if similar_count < 10:
            return 9.0  # Low supply = high demand
        elif similar_count < 30:
            return 7.0
        elif similar_count < 50:
            return 5.0
        else:
            return 3.0  # High supply = low demand
    
    def _count_similar_vehicles(self, brand: str, model: str, year: int) -> int:
        """Count similar vehicles in database"""
        from database.db import get_db_context
        from sqlalchemy import text
        try:
            with get_db_context() as db:
                query = text("""
                    SELECT COUNT(*)
                    FROM vehicles
                    WHERE brand LIKE :brand_pattern
                    AND year BETWEEN :y_start AND :y_end
                    AND is_active = 1
                """)
                result = db.execute(query, {
                    "brand_pattern": f"%{brand}%",
                    "y_start": year - 2,
                    "y_end": year + 2
                })
                count = result.fetchone()[0]
            return count
        except Exception as e:
            logger.error(f"Error counting similar vehicles: {e}")
            return 0
    
    def _get_avg_days_on_market(self, brand: str, model: str) -> Optional[float]:
        """
        Calculate average days on market for similar vehicles
        """
        from database.db import get_db_context
        from sqlalchemy import text
        try:
            with get_db_context() as db:
                query = text("""
                    SELECT AVG(julianday('now') - julianday(first_seen))
                    FROM vehicles
                    WHERE brand LIKE :brand_pattern
                    AND is_active = 1
                """)
                result = db.execute(query, {"brand_pattern": f"%{brand}%"})
                row = result.fetchone()
            if row and row[0]:
                return row[0] * 24
            return None
        except Exception as e:
            logger.error(f"Error calculating days on market: {e}")
            return None
    
    def _interpret_score(self, score: float) -> tuple[str, str]:
        """
        Interpret score and recommend action.
        Thresholds aligned with robust pricing v6.
        """
        if score >= 8.5:
            return "Exceptional Deal", "Immediate Alert"
        elif score >= 7.5:
            return "Excellent Deal", "Alert"
        elif score >= 6.0:
            return "Good Deal", "Monitor"
        elif score >= 4.5:
            return "Fair Deal", "No Action"
        else:
            return "Poor Deal/Risk", "Ignore"


# Singleton instance - uses config.settings
scoring_engine = DealScoringEngine(db_path=None)
