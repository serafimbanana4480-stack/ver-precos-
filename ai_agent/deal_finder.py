"""
AI Agent to find the best deals
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta

from config import settings
from database.models import Vehicle
from database.db import get_db_context
from .llm_review import LLMReviewer
from .vision_analysis import VisionAnalyzer
from utils.retry import retry_ai_api
from utils.deduplication import is_vehicle_processed, mark_vehicle_processed

logger = logging.getLogger(__name__)


class DealFinder:
    """AI Agent to find the best vehicle deals"""
    
    def __init__(self) -> None:
        self.llm_reviewer = LLMReviewer()
        self.vision_analyzer = VisionAnalyzer()
    
    def find_best_deals(
        self,
        vehicle_type: Optional[str] = None,
        min_profit: Optional[float] = None,
        limit: int = settings.top_deals_count
    ) -> List[Dict[str, object]]:
        """
        Find the best deals from the database
        
        Args:
            vehicle_type: Filter by vehicle type ('carros' or 'motos')
            min_profit: Minimum profit potential in EUR
            limit: Maximum number of deals to return
        
        Returns:
            List of best deal dictionaries (to avoid DetachedInstanceError)
        """
        logger.info("Finding best deals")
        
        with get_db_context() as db:
            # Build query
            query = db.query(Vehicle).filter(
                Vehicle.is_active == True,
                Vehicle.deal_score.isnot(None),
                Vehicle.deal_score >= settings.deal_score_threshold,
                ~Vehicle.source_id.like("demo_%"),
                ~Vehicle.url.ilike("%IDE123%"),
                ~Vehicle.url.ilike("%IDE456%"),
                ~Vehicle.url.ilike("%IDE789%"),
            )
            
            if vehicle_type:
                from database.models import VehicleType
                if vehicle_type == "carros":
                    query = query.filter(Vehicle.vehicle_type == VehicleType.carros)
                elif vehicle_type == "motos":
                    query = query.filter(Vehicle.vehicle_type == VehicleType.motos)
            
            if min_profit:
                query = query.filter(Vehicle.profit_potential >= min_profit)
            
            # Order by deal score and profit potential
            query = query.order_by(
                Vehicle.deal_score.desc(),
                Vehicle.profit_potential.desc()
            )
            
            # Get top deals
            deals = query.limit(limit * 2).all()  # Get more to filter
            
            # Filter by recency (last 7 days)
            # Ensure naive vs aware compatibility for SQLite
            recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            
            filtered_deals = []
            for v in deals:
                if v.first_seen:
                    # Handle both naive and aware datetimes
                    first_seen = v.first_seen
                    if first_seen.tzinfo is None:
                        first_seen = first_seen.replace(tzinfo=timezone.utc)
                    if first_seen >= recent_cutoff:
                        filtered_deals.append(v)
            
            deals = filtered_deals
            
            # Sort and limit
            deals.sort(key=lambda x: (x.deal_score or 0, x.profit_potential or 0), reverse=True)
            deals = deals[:limit]
            
            # Convert to dictionaries within session context
            deal_dicts = []
            for deal in deals:
                try:
                    deal_dict = deal.to_dict()
                    if deal_dict.get("ai_review"):
                        deal_dict["ai_review"] = deal_dict["ai_review"][:500]
                    deal_dicts.append(deal_dict)
                except Exception as e:
                    logger.error(f"Error converting deal to dict: {e}")
                    continue
            
            logger.info(f"Found {len(deal_dicts)} best deals")
            return deal_dicts
    
    def perform_second_review(self, vehicles: List[Dict[str, object]]) -> List[Dict[str, object]]:
        """
        Perform second AI review on top deals

        Args:
            vehicles: List of vehicle dictionaries to review

        Returns:
            List of vehicle dictionaries that passed second review
        """
        logger.info(f"Performing second review on {len(vehicles)} vehicles")

        approved_vehicles = []

        for vehicle_dict in vehicles:
            try:
                vehicle_id = vehicle_dict.get("id")
                if not vehicle_id:
                    continue

                # Check deduplication
                vid = int(vehicle_id) if isinstance(vehicle_id, (int, str)) else 0
                if is_vehicle_processed(vid):
                    logger.debug(f"Skipping already processed vehicle: {vehicle_id}")
                    continue

                # Get vehicle from database for AI review
                with get_db_context() as db:
                    from database.models import Vehicle
                    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
                    if not vehicle:
                        continue

                    # LLM review
                    llm_review = self.llm_reviewer.review_vehicle(vehicle)

                    # Vision analysis (if images available)
                    if vehicle.images and len(vehicle.images) > 0:
                        vision_review = self.vision_analyzer.analyze_vehicle_images(vehicle)

                    # Check if approved
                    db.refresh(vehicle)
                    if vehicle.ai_approved:
                        approved_vehicles.append(vehicle.to_dict())
                        mark_vehicle_processed(vid)

            except Exception as e:
                logger.warning(f"Error in second review for vehicle: {e}")
                continue

        logger.info(f"Second review: {len(approved_vehicles)} approved out of {len(vehicles)}")
        return approved_vehicles
    
    def run_daily_analysis(self) -> List[Dict[str, object]]:
        """
        Run complete daily analysis pipeline
        1. Find top deals based on deal score
        2. Perform second AI review
        3. Return final approved deals
        """
        logger.info("Starting daily analysis")

        # Find top deals
        top_deals = self.find_best_deals(limit=settings.ai_review_count)
        
        if not top_deals:
            logger.warning("No deals found for analysis")
            return []
        
        # Perform second review
        approved_deals = self.perform_second_review(top_deals)
        
        # Sort by combined score
        approved_deals.sort(
            key=lambda x: (x.get("deal_score") or 0, x.get("profit_potential") or 0),
            reverse=True
        )
        
        # Return top deals
        final_deals = approved_deals[:settings.top_deals_count]
        
        logger.info(f"Daily analysis complete: {len(final_deals)} final deals")
        return final_deals
    
    def get_deal_summary(self, vehicle: Vehicle) -> Dict[str, object]:
        """
        Get summary of a deal
        
        Args:
            vehicle: Vehicle to summarize
        
        Returns:
            Dictionary with deal summary
        """
        # Use to_dict() to avoid DetachedInstanceError
        try:
            summary = vehicle.to_dict()
            # Truncate ai_review if exists
            if summary.get("ai_review"):
                summary["ai_review"] = summary["ai_review"][:500]
            return summary
        except Exception as e:
            logger.error(f"Error getting deal summary: {e}")
            return {
                "id": None,
                "brand": "Unknown",
                "model": "Unknown",
                "year": None,
                "km": None,
                "price": None,
                "estimated_value": None,
                "deal_score": None,
                "profit_potential": None,
                "profit_percentage": None,
                "condition_score": None,
                "url": None,
                "source": None,
                "location": None,
                "ai_approved": None,
                "ai_review": None,
            }
    
    def export_deals_report(self, vehicles: List[Vehicle], format: str = "dict") -> List[Dict[str, object]] | str:
        """
        Export deals as report
        
        Args:
            vehicles: List of vehicles
            format: Export format ('dict', 'json')
        
        Returns:
            List of deal summaries
        """
        summaries = [self.get_deal_summary(v) for v in vehicles]
        
        if format == "json":
            import json
            return json.dumps(summaries, indent=2, default=str)
        
        return summaries
    
    def calculate_combined_score(self, vehicle: Vehicle) -> float:
        """
        Calculate combined score considering deal score, condition, and AI approval

        Args:
            vehicle: Vehicle to score

        Returns:
            Combined score (0-10)
        """
        base_score = float(vehicle.deal_score) if vehicle.deal_score else 5.0

        # Adjust for condition
        if vehicle.condition_score:
            condition_weight = 0.3
            base_score = base_score * (1 - condition_weight) + float(vehicle.condition_score) * condition_weight

        # Adjust for AI approval
        if vehicle.ai_approved is False:
            base_score *= 0.5  # Heavy penalty for AI rejection

        # Adjust for AI confidence
        if vehicle.ai_confidence:
            confidence_factor = 0.5 + (float(vehicle.ai_confidence) * 0.5)
            base_score *= confidence_factor

        return max(0.0, min(10.0, base_score))


if __name__ == "__main__":
    # Test deal finder
    finder = DealFinder()

    # Run daily analysis
    deals = finder.run_daily_analysis()

    print(f"Found {len(deals)} top deals:")
    for deal in deals:
        print(f"- {deal.get('brand')} {deal.get('model')} ({deal.get('year')}): "
              f"€{deal.get('price')}, Score: {deal.get('deal_score')}, "
              f"Profit: €{deal.get('profit_potential')}")
