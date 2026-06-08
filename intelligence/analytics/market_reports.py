"""
Market Reports Module
Generates market intelligence reports and analytics
"""
from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

from database.db import get_db_context
from database.models import Vehicle

logger = logging.getLogger(__name__)


class MarketReports:
    """Generate market intelligence reports"""
    
    def __init__(self):
        pass
    
    def generate_market_report(
        self, 
        brand: Optional[str] = None, 
        model: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate comprehensive market report
        
        Args:
            brand: Vehicle brand filter
            model: Vehicle model filter
            days: Number of days to analyze
            
        Returns:
            Market report with price trends, supply/demand, seasonality, geography
        """
        logger.info(f"Generating market report for {brand} {model} over {days} days")
        
        try:
            with get_db_context() as db:
                # Get vehicles from specified period
                since_date = datetime.utcnow() - timedelta(days=days)
                
                query = db.query(Vehicle).filter(
                    Vehicle.is_active == True,
                    Vehicle.first_seen >= since_date
                )
                
                if brand:
                    query = query.filter(Vehicle.brand.ilike(f"%{brand}%"))
                if model:
                    query = query.filter(Vehicle.model.ilike(f"%{model}%"))
                
                vehicles = query.all()
                
                if not vehicles:
                    return {
                        "error": "No vehicles found for the specified criteria",
                        "brand": brand,
                        "model": model,
                        "days": days
                    }
                
                # Generate report sections
                report = {
                    "brand": brand,
                    "model": model,
                    "days": days,
                    "total_vehicles": len(vehicles),
                    "generated_at": datetime.utcnow().isoformat(),
                    "price_trends": self._analyze_price_trends(vehicles),
                    "supply_demand": self._analyze_supply_demand(vehicles),
                    "seasonality": self._analyze_seasonality(vehicles),
                    "geography": self._analyze_geography(vehicles),
                    "deal_distribution": self._analyze_deal_distribution(vehicles),
                    "price_ranges": self._analyze_price_ranges(vehicles)
                }
                
                return report
                
        except Exception as e:
            logger.error(f"Error generating market report: {e}")
            return {"error": str(e)}
    
    def _analyze_price_trends(self, vehicles: List[Vehicle]) -> Dict[str, Any]:
        """Analyze price trends over time"""
        prices_by_day = defaultdict(list)
        
        for v in vehicles:
            if v.price and v.first_seen:
                day_key = v.first_seen.date().isoformat()
                prices_by_day[day_key].append(v.price)
        
        # Calculate daily averages
        daily_avg = {}
        for day, prices in sorted(prices_by_day.items()):
            daily_avg[day] = statistics.mean(prices)
        
        # Calculate trend
        if len(daily_avg) >= 2:
            first_avg = list(daily_avg.values())[0]
            last_avg = list(daily_avg.values())[-1]
            trend_percent = ((last_avg - first_avg) / first_avg) * 100
        else:
            trend_percent = 0
        
        return {
            "daily_averages": daily_avg,
            "trend_percent": round(trend_percent, 2),
            "trend_direction": "up" if trend_percent > 0 else "down" if trend_percent < 0 else "stable",
            "min_price": min([v.price for v in vehicles if v.price]) if vehicles else 0,
            "max_price": max([v.price for v in vehicles if v.price]) if vehicles else 0,
            "avg_price": statistics.mean([v.price for v in vehicles if v.price]) if vehicles else 0
        }
    
    def _analyze_supply_demand(self, vehicles: List[Vehicle]) -> Dict[str, Any]:
        """Analyze supply and demand indicators"""
        # Supply: number of listings
        supply = len(vehicles)
        
        # Demand indicator: average deal score (higher = higher demand for good deals)
        deal_scores = [v.deal_score for v in vehicles if v.deal_score]
        avg_deal_score = statistics.mean(deal_scores) if deal_scores else 0
        
        # Price compression: ratio of estimated value to asking price
        price_ratios = []
        for v in vehicles:
            if v.estimated_value and v.price and v.price > 0:
                price_ratios.append(v.estimated_value / v.price)
        
        avg_price_ratio = statistics.mean(price_ratios) if price_ratios else 0
        
        return {
            "supply": supply,
            "avg_deal_score": round(avg_deal_score, 2),
            "avg_price_ratio": round(avg_price_ratio, 2),
            "market_health": "balanced",
            "recommendation": self._get_supply_demand_recommendation(supply, avg_deal_score)
        }
    
    def _get_supply_demand_recommendation(self, supply: int, avg_deal_score: float) -> str:
        """Get recommendation based on supply and demand"""
        if supply < 10:
            return "Low supply - good opportunity for sellers"
        elif supply > 100:
            return "High supply - buyers have more options"
        elif avg_deal_score > 7:
            return "Good deals available - recommended for buyers"
        elif avg_deal_score < 5:
            return "Poor deals - consider waiting for better opportunities"
        else:
            return "Market conditions are normal"
    
    def _analyze_seasonality(self, vehicles: List[Vehicle]) -> Dict[str, Any]:
        """Analyze seasonal patterns"""
        # Group by day of week
        by_day_of_week = defaultdict(int)
        for v in vehicles:
            if v.first_seen:
                day_of_week = v.first_seen.strftime("%A")
                by_day_of_week[day_of_week] += 1
        
        # Group by month
        by_month = defaultdict(int)
        for v in vehicles:
            if v.first_seen:
                month = v.first_seen.strftime("%B")
                by_month[month] += 1
        
        return {
            "by_day_of_week": dict(by_day_of_week),
            "by_month": dict(by_month),
            "peak_day": max(by_day_of_week.items(), key=lambda x: x[1])[0] if by_day_of_week else None,
            "peak_month": max(by_month.items(), key=lambda x: x[1])[0] if by_month else None
        }
    
    def _analyze_geography(self, vehicles: List[Vehicle]) -> Dict[str, Any]:
        """Analyze geographic distribution"""
        by_district = defaultdict(list)
        by_location = defaultdict(int)
        
        for v in vehicles:
            if v.district:
                by_district[v.district].append(v.price if v.price else 0)
            if v.location:
                by_location[v.location] += 1
        
        # Calculate average price by district
        avg_price_by_district = {}
        for district, prices in by_district.items():
            if prices:
                avg_price_by_district[district] = statistics.mean(prices)
        
        return {
            "by_district_count": {k: len(v) for k, v in by_district.items()},
            "avg_price_by_district": {k: round(v, 2) for k, v in avg_price_by_district.items()},
            "top_locations": sorted(by_location.items(), key=lambda x: x[1], reverse=True)[:10]
        }
    
    def _analyze_deal_distribution(self, vehicles: List[Vehicle]) -> Dict[str, Any]:
        """Analyze distribution of deal scores"""
        deal_scores = [v.deal_score for v in vehicles if v.deal_score]
        
        if not deal_scores:
            return {"error": "No deal scores available"}
        
        return {
            "avg_score": round(statistics.mean(deal_scores), 2),
            "median_score": round(statistics.median(deal_scores), 2),
            "min_score": round(min(deal_scores), 2),
            "max_score": round(max(deal_scores), 2),
            "std_dev": round(statistics.stdev(deal_scores), 2) if len(deal_scores) > 1 else 0,
            "excellent_deals": len([s for s in deal_scores if s >= 8]),
            "good_deals": len([s for s in deal_scores if 6 <= s < 8]),
            "fair_deals": len([s for s in deal_scores if 4 <= s < 6]),
            "poor_deals": len([s for s in deal_scores if s < 4])
        }
    
    def _analyze_price_ranges(self, vehicles: List[Vehicle]) -> Dict[str, Any]:
        """Analyze price ranges and segments"""
        prices = [v.price for v in vehicles if v.price]
        
        if not prices:
            return {"error": "No prices available"}
        
        # Define price ranges
        ranges = {
            "under_5k": len([p for p in prices if p < 5000]),
            "5k_10k": len([p for p in prices if 5000 <= p < 10000]),
            "10k_20k": len([p for p in prices if 10000 <= p < 20000]),
            "20k_30k": len([p for p in prices if 20000 <= p < 30000]),
            "30k_50k": len([p for p in prices if 30000 <= p < 50000]),
            "over_50k": len([p for p in prices if p >= 50000])
        }
        
        return {
            "ranges": ranges,
            "most_common_range": max(ranges.items(), key=lambda x: x[1])[0] if ranges else None,
            "total_listings": len(prices)
        }


# Singleton instance
market_reports = MarketReports()
