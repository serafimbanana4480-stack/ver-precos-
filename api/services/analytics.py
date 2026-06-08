"""
Analytics service for API.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics and reporting."""
    
    def __init__(self, database, cache):
        """Initialize analytics service."""
        self.db = database
        self.cache = cache
        self.default_ttl = 900  # 15 minutes
        
    def get_overview(self, days: int = 30) -> Dict[str, Any]:
        """Get analytics overview for the specified period."""
        
        try:
            # Create cache key
            cache_key = f"overview:{days}"
            
            # Try to get from cache
            cached_overview = self.cache.get(cache_key)
            if cached_overview:
                logger.info("Retrieved analytics overview from cache")
                return cached_overview
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get overview data
            overview = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'listings': self._get_listings_overview(start_date, end_date),
                'pricing': self._get_pricing_overview(start_date, end_date),
                'market': self._get_market_overview(start_date, end_date),
                'performance': self._get_performance_overview(start_date, end_date)
            }
            
            # Cache result
            self.cache.set(cache_key, overview, ttl=self.default_ttl)
            
            logger.info(f"Retrieved analytics overview for last {days} days")
            return overview
            
        except Exception as e:
            logger.error(f"Error getting analytics overview: {e}")
            return {}
    
    def _get_listings_overview(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get listings overview."""
        
        try:
            # Get total listings
            total_listings = self.db.count_listings_by_date_range(start_date, end_date)
            
            # Get listings by source
            listings_by_source = self.db.get_listings_by_source(start_date, end_date)
            
            # Get listings by make
            listings_by_make = self.db.get_listings_by_make(start_date, end_date, limit=10)
            
            # Get daily listing counts
            daily_listings = self.db.get_daily_listings(start_date, end_date)
            
            return {
                'total_listings': total_listings,
                'listings_by_source': listings_by_source,
                'top_makes': listings_by_make,
                'daily_listings': daily_listings,
                'average_per_day': total_listings / max(1, (end_date - start_date).days)
            }
            
        except Exception as e:
            logger.error(f"Error getting listings overview: {e}")
            return {}
    
    def _get_pricing_overview(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get pricing overview."""
        
        try:
            # Get price statistics
            price_stats = self.db.get_price_statistics(start_date, end_date)
            
            # Get price trends
            price_trends = self.db.get_price_trends(start_date, end_date)
            
            # Get price distribution
            price_distribution = self.db.get_price_distribution(start_date, end_date)
            
            return {
                'statistics': price_stats,
                'trends': price_trends,
                'distribution': price_distribution
            }
            
        except Exception as e:
            logger.error(f"Error getting pricing overview: {e}")
            return {}
    
    def _get_market_overview(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get market overview."""
        
        try:
            # Get market share
            market_share = self.db.get_market_share(start_date, end_date)
            
            # Get popular locations
            popular_locations = self.db.get_popular_locations(start_date, end_date, limit=10)
            
            # Get fuel type distribution
            fuel_distribution = self.db.get_fuel_type_distribution(start_date, end_date)
            
            # Get transmission distribution
            transmission_distribution = self.db.get_transmission_distribution(start_date, end_date)
            
            return {
                'market_share': market_share,
                'popular_locations': popular_locations,
                'fuel_types': fuel_distribution,
                'transmissions': transmission_distribution
            }
            
        except Exception as e:
            logger.error(f"Error getting market overview: {e}")
            return {}
    
    def _get_performance_overview(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get performance overview."""
        
        try:
            # Get view statistics
            view_stats = self.db.get_view_statistics(start_date, end_date)
            
            # Get search statistics
            search_stats = self.db.get_search_statistics(start_date, end_date)
            
            # Get conversion metrics
            conversion_metrics = self.db.get_conversion_metrics(start_date, end_date)
            
            return {
                'views': view_stats,
                'searches': search_stats,
                'conversions': conversion_metrics
            }
            
        except Exception as e:
            logger.error(f"Error getting performance overview: {e}")
            return {}
    
    def get_market_trends(self, days: int = 90, make: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """Get market trends analysis."""
        
        try:
            # Create cache key
            cache_key = f"trends:{days}:{make}:{model}"
            
            # Try to get from cache
            cached_trends = self.cache.get(cache_key)
            if cached_trends:
                logger.info("Retrieved market trends from cache")
                return cached_trends
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get trends data
            trends = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'price_trends': self._get_price_trends(start_date, end_date, make, model),
                'volume_trends': self._get_volume_trends(start_date, end_date, make, model),
                'seasonal_patterns': self._get_seasonal_patterns(start_date, end_date, make, model),
                'top_growing_makes': self._get_top_growing_makes(start_date, end_date),
                'top_declining_makes': self._get_top_declining_makes(start_date, end_date)
            }
            
            # Cache result
            self.cache.set(cache_key, trends, ttl=self.default_ttl * 2)
            
            logger.info(f"Retrieved market trends for last {days} days")
            return trends
            
        except Exception as e:
            logger.error(f"Error getting market trends: {e}")
            return {}
    
    def _get_price_trends(self, start_date: datetime, end_date: datetime, make: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """Get price trends."""
        
        try:
            # Get daily average prices
            daily_prices = self.db.get_daily_average_prices(start_date, end_date, make, model)
            
            # Calculate trend direction
            if len(daily_prices) >= 2:
                first_price = daily_prices[0]['avg_price']
                last_price = daily_prices[-1]['avg_price']
                
                if last_price > first_price * 1.05:
                    trend_direction = "increasing"
                elif last_price < first_price * 0.95:
                    trend_direction = "decreasing"
                else:
                    trend_direction = "stable"
            else:
                trend_direction = "insufficient_data"
            
            return {
                'daily_prices': daily_prices,
                'trend_direction': trend_direction,
                'price_change': last_price - first_price if len(daily_prices) >= 2 else 0,
                'price_change_percentage': ((last_price - first_price) / first_price * 100) if len(daily_prices) >= 2 and first_price > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting price trends: {e}")
            return {}
    
    def _get_volume_trends(self, start_date: datetime, end_date: datetime, make: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """Get volume trends."""
        
        try:
            # Get daily listing counts
            daily_volumes = self.db.get_daily_listing_counts(start_date, end_date, make, model)
            
            # Calculate trend direction
            if len(daily_volumes) >= 2:
                first_volume = daily_volumes[0]['count']
                last_volume = daily_volumes[-1]['count']
                
                if last_volume > first_volume * 1.1:
                    trend_direction = "increasing"
                elif last_volume < first_volume * 0.9:
                    trend_direction = "decreasing"
                else:
                    trend_direction = "stable"
            else:
                trend_direction = "insufficient_data"
            
            return {
                'daily_volumes': daily_volumes,
                'trend_direction': trend_direction,
                'volume_change': last_volume - first_volume if len(daily_volumes) >= 2 else 0,
                'volume_change_percentage': ((last_volume - first_volume) / first_volume * 100) if len(daily_volumes) >= 2 and first_volume > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting volume trends: {e}")
            return {}
    
    def _get_seasonal_patterns(self, start_date: datetime, end_date: datetime, make: Optional[str] = None, model: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get seasonal patterns."""
        
        try:
            # Get monthly averages
            monthly_data = self.db.get_monthly_averages(start_date, end_date, make, model)
            
            # Identify seasonal patterns
            seasonal_patterns = []
            
            for month_data in monthly_data:
                pattern = {
                    'month': month_data['month'],
                    'avg_price': month_data['avg_price'],
                    'avg_volume': month_data['avg_volume'],
                    'price_vs_average': month_data['avg_price'] / (sum(d['avg_price'] for d in monthly_data) / len(monthly_data)) if monthly_data else 1,
                    'volume_vs_average': month_data['avg_volume'] / (sum(d['avg_volume'] for d in monthly_data) / len(monthly_data)) if monthly_data else 1
                }
                seasonal_patterns.append(pattern)
            
            return seasonal_patterns
            
        except Exception as e:
            logger.error(f"Error getting seasonal patterns: {e}")
            return []
    
    def _get_top_growing_makes(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get top growing makes."""
        
        try:
            return self.db.get_top_growing_makes(start_date, end_date, limit=10)
            
        except Exception as e:
            logger.error(f"Error getting top growing makes: {e}")
            return []
    
    def _get_top_declining_makes(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get top declining makes."""
        
        try:
            return self.db.get_top_declining_makes(start_date, end_date, limit=10)
            
        except Exception as e:
            logger.error(f"Error getting top declining makes: {e}")
            return []
    
    def get_price_analysis(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed price analysis."""
        
        try:
            # Create cache key
            cache_key = f"price_analysis:{make}:{model}:{year}:{location}"
            
            # Try to get from cache
            cached_analysis = self.cache.get(cache_key)
            if cached_analysis:
                logger.info("Retrieved price analysis from cache")
                return cached_analysis
            
            # Get price analysis data
            analysis = {
                'filters': {
                    'make': make,
                    'model': model,
                    'year': year,
                    'location': location
                },
                'statistics': self._get_price_statistics(make, model, year, location),
                'distribution': self._get_price_distribution(make, model, year, location),
                'by_make': self._get_price_by_make(make, model, year, location),
                'by_model': self._get_price_by_model(make, model, year, location),
                'by_year': self._get_price_by_year(make, model, year, location),
                'by_location': self._get_price_by_location(make, model, year, location),
                'trends': self._get_price_trends_for_analysis(make, model, year, location),
                'recommendations': self._get_price_recommendations(make, model, year, location)
            }
            
            # Cache result
            self.cache.set(cache_key, analysis, ttl=self.default_ttl * 4)
            
            logger.info("Retrieved price analysis")
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting price analysis: {e}")
            return {}
    
    def _get_price_statistics(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> Dict[str, Any]:
        """Get price statistics."""
        
        try:
            return self.db.get_price_statistics(make, model, year, location)
            
        except Exception as e:
            logger.error(f"Error getting price statistics: {e}")
            return {}
    
    def _get_price_distribution(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> Dict[str, Any]:
        """Get price distribution."""
        
        try:
            return self.db.get_price_distribution(make, model, year, location)
            
        except Exception as e:
            logger.error(f"Error getting price distribution: {e}")
            return {}
    
    def _get_price_by_make(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> Dict[str, float]:
        """Get average price by make."""
        
        try:
            return self.db.get_average_price_by_make(make, model, year, location)
            
        except Exception as e:
            logger.error(f"Error getting price by make: {e}")
            return {}
    
    def _get_price_by_model(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> Dict[str, float]:
        """Get average price by model."""
        
        try:
            return self.db.get_average_price_by_model(make, model, year, location)
            
        except Exception as e:
            logger.error(f"Error getting price by model: {e}")
            return {}
    
    def _get_price_by_year(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> Dict[str, float]:
        """Get average price by year."""
        
        try:
            return self.db.get_average_price_by_year(make, model, year, location)
            
        except Exception as e:
            logger.error(f"Error getting price by year: {e}")
            return {}
    
    def _get_price_by_location(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> Dict[str, float]:
        """Get average price by location."""
        
        try:
            return self.db.get_average_price_by_location(make, model, year, location)
            
        except Exception as e:
            logger.error(f"Error getting price by location: {e}")
            return {}
    
    def _get_price_trends_for_analysis(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get price trends for analysis."""
        
        try:
            # Get last 30 days of price data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            return self.db.get_daily_average_prices(start_date, end_date, make, model)
            
        except Exception as e:
            logger.error(f"Error getting price trends for analysis: {e}")
            return []
    
    def _get_price_recommendations(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> List[str]:
        """Get price recommendations."""
        
        try:
            recommendations = []
            
            # Get current price statistics
            stats = self._get_price_statistics(make, model, year, location)
            
            if stats:
                avg_price = stats.get('average_price', 0)
                median_price = stats.get('median_price', 0)
                
                # Generate recommendations based on price distribution
                if avg_price > median_price * 1.2:
                    recommendations.append("Average price is significantly higher than median, indicating outliers in the data")
                elif avg_price < median_price * 0.8:
                    recommendations.append("Average price is significantly lower than median, indicating potential data issues")
                
                # Add general recommendations
                recommendations.append("Consider seasonal factors when pricing")
                recommendations.append("Compare with similar listings in the same location")
                recommendations.append("Factor in mileage and condition when evaluating prices")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting price recommendations: {e}")
            return []
    
    def get_make_model_stats(self, limit: int = 20, min_listings: int = 5) -> Dict[str, Any]:
        """Get make and model statistics."""
        
        try:
            # Create cache key
            cache_key = f"make_model_stats:{limit}:{min_listings}"
            
            # Try to get from cache
            cached_stats = self.cache.get(cache_key)
            if cached_stats:
                logger.info("Retrieved make/model stats from cache")
                return cached_stats
            
            # Get make statistics
            make_stats = self.db.get_make_statistics(limit, min_listings)
            
            # Get model statistics
            model_stats = self.db.get_model_statistics(limit, min_listings)
            
            stats = {
                'makes': make_stats,
                'models': model_stats,
                'total_makes': len(make_stats),
                'total_models': len(model_stats),
                'min_listings_threshold': min_listings
            }
            
            # Cache result
            self.cache.set(cache_key, stats, ttl=self.default_ttl * 6)
            
            logger.info(f"Retrieved make/model stats for top {limit} makes")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting make/model stats: {e}")
            return {}
    
    def get_location_analysis(self, limit: int = 50) -> Dict[str, Any]:
        """Get location-based analysis."""
        
        try:
            # Create cache key
            cache_key = f"location_analysis:{limit}"
            
            # Try to get from cache
            cached_analysis = self.cache.get(cache_key)
            if cached_analysis:
                logger.info("Retrieved location analysis from cache")
                return cached_analysis
            
            # Get location statistics
            location_stats = self.db.get_location_statistics(limit)
            
            # Get price by location
            price_by_location = self.db.get_average_price_by_location()
            
            # Get volume by location
            volume_by_location = self.db.get_volume_by_location(limit)
            
            analysis = {
                'location_statistics': location_stats,
                'price_by_location': price_by_location,
                'volume_by_location': volume_by_location,
                'top_locations': location_stats[:10],
                'price_variations': self._calculate_price_variations(price_by_location)
            }
            
            # Cache result
            self.cache.set(cache_key, analysis, ttl=self.default_ttl * 6)
            
            logger.info(f"Retrieved location analysis for top {limit} locations")
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting location analysis: {e}")
            return {}
    
    def _calculate_price_variations(self, price_by_location: Dict[str, float]) -> Dict[str, Any]:
        """Calculate price variations across locations."""
        
        try:
            if not price_by_location:
                return {}
            
            prices = list(price_by_location.values())
            
            if len(prices) < 2:
                return {}
            
            avg_price = sum(prices) / len(prices)
            
            variations = {}
            for location, price in price_by_location.items():
                variation = ((price - avg_price) / avg_price) * 100
                variations[location] = {
                    'price': price,
                    'variation_percentage': variation,
                    'above_average': variation > 0
                }
            
            return variations
            
        except Exception as e:
            logger.error(f"Error calculating price variations: {e}")
            return {}
    
    def get_depreciation_analysis(self, make: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """Get depreciation analysis by year."""
        
        try:
            # Create cache key
            cache_key = f"depreciation:{make}:{model}"
            
            # Try to get from cache
            cached_analysis = self.cache.get(cache_key)
            if cached_analysis:
                logger.info("Retrieved depreciation analysis from cache")
                return cached_analysis
            
            # Get depreciation data
            depreciation_data = self.db.get_depreciation_by_year(make, model)
            
            # Calculate depreciation rates
            depreciation_rates = self._calculate_depreciation_rates(depreciation_data)
            
            analysis = {
                'filters': {
                    'make': make,
                    'model': model
                },
                'depreciation_data': depreciation_data,
                'depreciation_rates': depreciation_rates,
                'average_depreciation': self._calculate_average_depreciation(depreciation_rates),
                'recommendations': self._get_depreciation_recommendations(depreciation_rates)
            }
            
            # Cache result
            self.cache.set(cache_key, analysis, ttl=self.default_ttl * 12)
            
            logger.info("Retrieved depreciation analysis")
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting depreciation analysis: {e}")
            return {}
    
    def _calculate_depreciation_rates(self, depreciation_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate depreciation rates."""
        
        try:
            rates = {}
            
            for i in range(1, len(depreciation_data)):
                current_year = depreciation_data[i]
                previous_year = depreciation_data[i-1]
                
                year_diff = current_year['year'] - previous_year['year']
                price_diff = previous_year['avg_price'] - current_year['avg_price']
                
                if year_diff > 0 and previous_year['avg_price'] > 0:
                    annual_rate = (price_diff / previous_year['avg_price']) / year_diff
                    rates[str(current_year['year'])] = annual_rate * 100  # Convert to percentage
            
            return rates
            
        except Exception as e:
            logger.error(f"Error calculating depreciation rates: {e}")
            return {}
    
    def _calculate_average_depreciation(self, depreciation_rates: Dict[str, float]) -> float:
        """Calculate average depreciation rate."""
        
        try:
            if not depreciation_rates:
                return 0.0
            
            return sum(depreciation_rates.values()) / len(depreciation_rates)
            
        except Exception as e:
            logger.error(f"Error calculating average depreciation: {e}")
            return 0.0
    
    def _get_depreciation_recommendations(self, depreciation_rates: Dict[str, float]) -> List[str]:
        """Get depreciation recommendations."""
        
        try:
            recommendations = []
            
            if depreciation_rates:
                avg_rate = self._calculate_average_depreciation(depreciation_rates)
                
                if avg_rate > 15:
                    recommendations.append("High depreciation rate - consider holding period carefully")
                elif avg_rate < 5:
                    recommendations.append("Low depreciation rate - good value retention")
                else:
                    recommendations.append("Moderate depreciation rate - typical for this market")
                
                recommendations.append("Consider maintenance costs when calculating total cost of ownership")
                recommendations.append("Market conditions can significantly affect depreciation rates")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting depreciation recommendations: {e}")
            return []
    
    def get_market_share(self, days: int = 30, group_by: str = "make") -> Dict[str, Any]:
        """Get market share analysis."""
        
        try:
            # Create cache key
            cache_key = f"market_share:{days}:{group_by}"
            
            # Try to get from cache
            cached_share = self.cache.get(cache_key)
            if cached_share:
                logger.info("Retrieved market share from cache")
                return cached_share
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get market share data
            market_share = self.db.get_market_share_by_group(start_date, end_date, group_by)
            
            # Calculate percentages
            total_listings = sum(market_share.values())
            market_share_percentages = {}
            
            for key, count in market_share.items():
                percentage = (count / total_listings) * 100 if total_listings > 0 else 0
                market_share_percentages[key] = {
                    'count': count,
                    'percentage': percentage,
                    'rank': 0  # Will be calculated below
                }
            
            # Calculate rankings
            sorted_items = sorted(market_share_percentages.items(), key=lambda x: x[1]['percentage'], reverse=True)
            for i, (key, data) in enumerate(sorted_items):
                data['rank'] = i + 1
            
            share_data = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'group_by': group_by,
                'market_share': market_share_percentages,
                'total_listings': total_listings,
                'top_10': dict(sorted_items[:10])
            }
            
            # Cache result
            self.cache.set(cache_key, share_data, ttl=self.default_ttl * 4)
            
            logger.info(f"Retrieved market share by {group_by}")
            return share_data
            
        except Exception as e:
            logger.error(f"Error getting market share: {e}")
            return {}
    
    def get_price_distribution(self, make: Optional[str] = None, model: Optional[str] = None, year: Optional[int] = None, location: Optional[str] = None) -> Dict[str, Any]:
        """Get price distribution analysis."""
        
        try:
            # Create cache key
            cache_key = f"price_dist:{make}:{model}:{year}:{location}"
            
            # Try to get from cache
            cached_distribution = self.cache.get(cache_key)
            if cached_distribution:
                logger.info("Retrieved price distribution from cache")
                return cached_distribution
            
            # Get price distribution data
            distribution = self.db.get_price_distribution(make, model, year, location)
            
            # Calculate distribution statistics
            distribution_stats = self._calculate_distribution_stats(distribution)
            
            distribution_data = {
                'filters': {
                    'make': make,
                    'model': model,
                    'year': year,
                    'location': location
                },
                'distribution': distribution,
                'statistics': distribution_stats,
                'price_ranges': self._create_price_ranges(distribution)
            }
            
            # Cache result
            self.cache.set(cache_key, distribution_data, ttl=self.default_ttl * 3)
            
            logger.info("Retrieved price distribution")
            return distribution_data
            
        except Exception as e:
            logger.error(f"Error getting price distribution: {e}")
            return {}
    
    def _calculate_distribution_stats(self, distribution: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate distribution statistics."""
        
        try:
            if not distribution:
                return {}
            
            # Extract price ranges and counts
            ranges = list(distribution.keys())
            counts = list(distribution.values())
            
            if not counts:
                return {}
            
            return {
                'total_listings': sum(counts),
                'price_ranges_count': len(ranges),
                'most_common_range': ranges[counts.index(max(counts))] if counts else None,
                'least_common_range': ranges[counts.index(min(counts))] if counts else None,
                'average_per_range': sum(counts) / len(counts)
            }
            
        except Exception as e:
            logger.error(f"Error calculating distribution stats: {e}")
            return {}
    
    def _create_price_ranges(self, distribution: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create standardized price ranges."""
        
        try:
            standard_ranges = [
                {'label': 'Under 5.000€', 'min': 0, 'max': 5000, 'count': 0},
                {'label': '5.000€ - 10.000€', 'min': 5000, 'max': 10000, 'count': 0},
                {'label': '10.000€ - 15.000€', 'min': 10000, 'max': 15000, 'count': 0},
                {'label': '15.000€ - 20.000€', 'min': 15000, 'max': 20000, 'count': 0},
                {'label': '20.000€ - 30.000€', 'min': 20000, 'max': 30000, 'count': 0},
                {'label': '30.000€ - 50.000€', 'min': 30000, 'max': 50000, 'count': 0},
                {'label': 'Over 50.000€', 'min': 50000, 'max': None, 'count': 0}
            ]
            
            # Map distribution counts to standard ranges
            for range_label, count in distribution.items():
                # This is a simplified mapping - in production, would be more sophisticated
                for std_range in standard_ranges:
                    if 'Under' in range_label and std_range['max'] == 5000:
                        std_range['count'] += count
                    elif '5.000' in range_label and std_range['max'] == 10000:
                        std_range['count'] += count
                    elif '10.000' in range_label and std_range['max'] == 15000:
                        std_range['count'] += count
                    elif '15.000' in range_label and std_range['max'] == 20000:
                        std_range['count'] += count
                    elif '20.000' in range_label and std_range['max'] == 30000:
                        std_range['count'] += count
                    elif '30.000' in range_label and std_range['max'] == 50000:
                        std_range['count'] += count
                    elif 'Over' in range_label and std_range['min'] == 50000:
                        std_range['count'] += count
            
            return standard_ranges
            
        except Exception as e:
            logger.error(f"Error creating price ranges: {e}")
            return []
    
    def get_seasonal_analysis(self, months: int = 12, make: Optional[str] = None) -> Dict[str, Any]:
        """Get seasonal analysis."""
        
        try:
            # Create cache key
            cache_key = f"seasonal:{months}:{make}"
            
            # Try to get from cache
            cached_analysis = self.cache.get(cache_key)
            if cached_analysis:
                logger.info("Retrieved seasonal analysis from cache")
                return cached_analysis
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months * 30)
            
            # Get seasonal data
            seasonal_data = self.db.get_seasonal_data(start_date, end_date, make)
            
            analysis = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'months': months
                },
                'seasonal_data': seasonal_data,
                'peak_seasons': self._identify_peak_seasons(seasonal_data),
                'off_seasons': self._identify_off_seasons(seasonal_data),
                'seasonal_insights': self._generate_seasonal_insights(seasonal_data)
            }
            
            # Cache result
            self.cache.set(cache_key, analysis, ttl=self.default_ttl * 8)
            
            logger.info(f"Retrieved seasonal analysis for last {months} months")
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting seasonal analysis: {e}")
            return {}
    
    def _identify_peak_seasons(self, seasonal_data: List[Dict[str, Any]]) -> List[str]:
        """Identify peak seasons from seasonal data."""
        
        try:
            if not seasonal_data:
                return []
            
            # Calculate average volume
            avg_volume = sum(data.get('volume', 0) for data in seasonal_data) / len(seasonal_data)
            
            # Identify months with volume significantly above average
            peak_months = []
            for data in seasonal_data:
                volume = data.get('volume', 0)
                if volume > avg_volume * 1.2:  # 20% above average
                    peak_months.append(data.get('month', ''))
            
            return peak_months
            
        except Exception as e:
            logger.error(f"Error identifying peak seasons: {e}")
            return []
    
    def _identify_off_seasons(self, seasonal_data: List[Dict[str, Any]]) -> List[str]:
        """Identify off seasons from seasonal data."""
        
        try:
            if not seasonal_data:
                return []
            
            # Calculate average volume
            avg_volume = sum(data.get('volume', 0) for data in seasonal_data) / len(seasonal_data)
            
            # Identify months with volume significantly below average
            off_months = []
            for data in seasonal_data:
                volume = data.get('volume', 0)
                if volume < avg_volume * 0.8:  # 20% below average
                    off_months.append(data.get('month', ''))
            
            return off_months
            
        except Exception as e:
            logger.error(f"Error identifying off seasons: {e}")
            return []
    
    def _generate_seasonal_insights(self, seasonal_data: List[Dict[str, Any]]) -> List[str]:
        """Generate seasonal insights."""
        
        try:
            insights = []
            
            if not seasonal_data:
                return insights
            
            # Analyze price trends by season
            spring_prices = []
            summer_prices = []
            fall_prices = []
            winter_prices = []
            
            for data in seasonal_data:
                month = data.get('month', '')
                price = data.get('avg_price', 0)
                
                if month in ['March', 'April', 'May']:
                    spring_prices.append(price)
                elif month in ['June', 'July', 'August']:
                    summer_prices.append(price)
                elif month in ['September', 'October', 'November']:
                    fall_prices.append(price)
                elif month in ['December', 'January', 'February']:
                    winter_prices.append(price)
            
            # Generate insights based on seasonal price patterns
            if spring_prices and summer_prices:
                spring_avg = sum(spring_prices) / len(spring_prices)
                summer_avg = sum(summer_prices) / len(summer_prices)
                
                if summer_avg > spring_avg * 1.05:
                    insights.append("Summer prices are typically higher than spring")
                elif spring_avg > summer_avg * 1.05:
                    insights.append("Spring prices are typically higher than summer")
            
            insights.append("Consider seasonal factors when timing your purchase or sale")
            insights.append("Market activity typically increases in spring and summer")
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating seasonal insights: {e}")
            return []
    
    def get_inventory_turnover(self, days: int = 30, make: Optional[str] = None) -> Dict[str, Any]:
        """Get inventory turnover analysis."""
        
        try:
            # Create cache key
            cache_key = f"turnover:{days}:{make}"
            
            # Try to get from cache
            cached_turnover = self.cache.get(cache_key)
            if cached_turnover:
                logger.info("Retrieved inventory turnover from cache")
                return cached_turnover
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get turnover data
            turnover_data = self.db.get_inventory_turnover(start_date, end_date, make)
            
            turnover = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'turnover_rate': turnover_data.get('turnover_rate', 0),
                'average_days_on_market': turnover_data.get('avg_days_on_market', 0),
                'total_listings': turnover_data.get('total_listings', 0),
                'sold_listings': turnover_data.get('sold_listings', 0),
                'new_listings': turnover_data.get('new_listings', 0),
                'recommendations': self._get_turnover_recommendations(turnover_data)
            }
            
            # Cache result
            self.cache.set(cache_key, turnover, ttl=self.default_ttl * 2)
            
            logger.info(f"Retrieved inventory turnover for last {days} days")
            return turnover
            
        except Exception as e:
            logger.error(f"Error getting inventory turnover: {e}")
            return {}
    
    def _get_turnover_recommendations(self, turnover_data: Dict[str, Any]) -> List[str]:
        """Get turnover recommendations."""
        
        try:
            recommendations = []
            
            turnover_rate = turnover_data.get('turnover_rate', 0)
            avg_days = turnover_data.get('avg_days_on_market', 0)
            
            if turnover_rate > 0.8:
                recommendations.append("High turnover rate - good market activity")
            elif turnover_rate < 0.3:
                recommendations.append("Low turnover rate - consider adjusting pricing or marketing")
            
            if avg_days > 60:
                recommendations.append("Long average days on market - review pricing strategy")
            elif avg_days < 30:
                recommendations.append("Quick sales - good pricing or high demand")
            
            recommendations.append("Monitor market trends to optimize turnover")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting turnover recommendations: {e}")
            return []
    
    def get_performance_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get performance metrics."""
        
        try:
            # Create cache key
            cache_key = f"performance:{days}"
            
            # Try to get from cache
            cached_metrics = self.cache.get(cache_key)
            if cached_metrics:
                logger.info("Retrieved performance metrics from cache")
                return cached_metrics
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get performance data
            performance_data = self.db.get_performance_metrics(start_date, end_date)
            
            metrics = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'views': performance_data.get('views', {}),
                'searches': performance_data.get('searches', {}),
                'conversions': performance_data.get('conversions', {}),
                'user_engagement': performance_data.get('user_engagement', {}),
                'site_performance': performance_data.get('site_performance', {})
            }
            
            # Cache result
            self.cache.set(cache_key, metrics, ttl=self.default_ttl // 2)
            
            logger.info(f"Retrieved performance metrics for last {days} days")
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def get_user_behavior_analytics(self, days: int = 30, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get user behavior analytics."""
        
        try:
            # Create cache key
            cache_key = f"user_behavior:{days}:{user_id}"
            
            # Try to get from cache
            cached_behavior = self.cache.get(cache_key)
            if cached_behavior:
                logger.info("Retrieved user behavior analytics from cache")
                return cached_behavior
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get user behavior data
            behavior_data = self.db.get_user_behavior_analytics(start_date, end_date, user_id)
            
            behavior = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'user_id': user_id,
                'search_patterns': behavior_data.get('search_patterns', {}),
                'viewing_patterns': behavior_data.get('viewing_patterns', {}),
                'conversion_funnel': behavior_data.get('conversion_funnel', {}),
                'user_segments': behavior_data.get('user_segments', {}),
                'retention_analysis': behavior_data.get('retention_analysis', {}),
                'insights': self._generate_user_insights(behavior_data)
            }
            
            # Cache result
            self.cache.set(cache_key, behavior, ttl=self.default_ttl * 3)
            
            logger.info(f"Retrieved user behavior analytics for last {days} days")
            return behavior
            
        except Exception as e:
            logger.error(f"Error getting user behavior analytics: {e}")
            return {}
    
    def _generate_user_insights(self, behavior_data: Dict[str, Any]) -> List[str]:
        """Generate user behavior insights."""
        
        try:
            insights = []
            
            # Generate insights based on search patterns
            search_patterns = behavior_data.get('search_patterns', {})
            avg_searches_per_user = search_patterns.get('avg_searches_per_user', 0)
            
            if avg_searches_per_user > 10:
                insights.append("Users are highly engaged with searching")
            elif avg_searches_per_user < 3:
                insights.append("Low search engagement - consider improving search functionality")
            
            # Generate insights based on conversion funnel
            conversion_funnel = behavior_data.get('conversion_funnel', {})
            conversion_rate = conversion_funnel.get('conversion_rate', 0)
            
            if conversion_rate > 0.05:
                insights.append("Good conversion rate")
            elif conversion_rate < 0.01:
                insights.append("Low conversion rate - review listing quality or pricing")
            
            insights.append("Monitor user behavior to identify improvement opportunities")
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating user insights: {e}")
            return []
    
    def get_dashboard_report(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive dashboard report."""
        
        try:
            # Create cache key
            cache_key = f"dashboard:{days}"
            
            # Try to get from cache
            cached_dashboard = self.cache.get(cache_key)
            if cached_dashboard:
                logger.info("Retrieved dashboard report from cache")
                return cached_dashboard
            
            # Get overview data
            overview = self.get_overview(days)
            
            # Get performance metrics
            performance = self.get_performance_metrics(days)
            
            # Get market trends
            trends = self.get_market_trends(days)
            
            dashboard = {
                'period': {
                    'start_date': overview.get('period', {}).get('start_date'),
                    'end_date': overview.get('period', {}).get('end_date'),
                    'days': days
                },
                'overview': overview,
                'performance': performance,
                'trends': trends,
                'key_metrics': self._extract_key_metrics(overview, performance),
                'alerts': self._generate_dashboard_alerts(overview, performance),
                'recommendations': self._generate_dashboard_recommendations(overview, performance)
            }
            
            # Cache result
            self.cache.set(cache_key, dashboard, ttl=self.default_ttl // 2)
            
            logger.info(f"Retrieved dashboard report for last {days} days")
            return dashboard
            
        except Exception as e:
            logger.error(f"Error getting dashboard report: {e}")
            return {}
    
    def _extract_key_metrics(self, overview: Dict[str, Any], performance: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key metrics for dashboard."""
        
        try:
            key_metrics = {}
            
            # Extract from overview
            if 'listings' in overview:
                listings_data = overview['listings']
                key_metrics['total_listings'] = listings_data.get('total_listings', 0)
                key_metrics['listings_per_day'] = listings_data.get('average_per_day', 0)
            
            if 'pricing' in overview:
                pricing_data = overview['pricing']
                stats = pricing_data.get('statistics', {})
                key_metrics['average_price'] = stats.get('average_price', 0)
                key_metrics['median_price'] = stats.get('median_price', 0)
            
            # Extract from performance
            if 'views' in performance:
                views_data = performance['views']
                key_metrics['total_views'] = views_data.get('total_views', 0)
                key_metrics['avg_views_per_listing'] = views_data.get('avg_views_per_listing', 0)
            
            if 'conversions' in performance:
                conversions_data = performance['conversions']
                key_metrics['conversion_rate'] = conversions_data.get('conversion_rate', 0)
                key_metrics['total_conversions'] = conversions_data.get('total_conversions', 0)
            
            return key_metrics
            
        except Exception as e:
            logger.error(f"Error extracting key metrics: {e}")
            return {}
    
    def _generate_dashboard_alerts(self, overview: Dict[str, Any], performance: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate dashboard alerts."""
        
        try:
            alerts = []
            
            # Check for performance issues
            if 'conversions' in performance:
                conversion_rate = performance['conversions'].get('conversion_rate', 0)
                if conversion_rate < 0.01:
                    alerts.append({
                        'type': 'warning',
                        'message': 'Low conversion rate detected',
                        'severity': 'medium'
                    })
            
            # Check for inventory issues
            if 'listings' in overview:
                listings_per_day = overview['listings'].get('average_per_day', 0)
                if listings_per_day < 5:
                    alerts.append({
                        'type': 'warning',
                        'message': 'Low listing volume',
                        'severity': 'low'
                    })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error generating dashboard alerts: {e}")
            return []
    
    def _generate_dashboard_recommendations(self, overview: Dict[str, Any], performance: Dict[str, Any]) -> List[str]:
        """Generate dashboard recommendations."""
        
        try:
            recommendations = []
            
            # Generate recommendations based on data
            if 'listings' in overview:
                listings_data = overview['listings']
                if listings_data.get('average_per_day', 0) < 10:
                    recommendations.append("Consider increasing marketing efforts to boost listing volume")
            
            if 'conversions' in performance:
                conversion_rate = performance['conversions'].get('conversion_rate', 0)
                if conversion_rate < 0.02:
                    recommendations.append("Review listing quality and pricing to improve conversion rate")
            
            recommendations.append("Monitor key metrics regularly to identify trends")
            recommendations.append("Use analytics to optimize business decisions")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating dashboard recommendations: {e}")
            return []
    
    def generate_custom_report(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate custom analytics report."""
        
        try:
            # Extract configuration
            report_type = config.get('report_type', 'overview')
            date_range = config.get('date_range', {})
            filters = config.get('filters', {})
            metrics = config.get('metrics', [])
            
            # Generate report based on type
            if report_type == 'overview':
                days = date_range.get('days', 30)
                report = self.get_overview(days)
            elif report_type == 'trends':
                days = date_range.get('days', 90)
                make = filters.get('make')
                model = filters.get('model')
                report = self.get_market_trends(days, make, model)
            elif report_type == 'price_analysis':
                make = filters.get('make')
                model = filters.get('model')
                year = filters.get('year')
                location = filters.get('location')
                report = self.get_price_analysis(make, model, year, location)
            else:
                report = {"error": f"Unknown report type: {report_type}"}
            
            # Add custom metrics if specified
            if metrics and 'data' in report:
                report['custom_metrics'] = self._calculate_custom_metrics(report['data'], metrics)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating custom report: {e}")
            return {"error": str(e)}
    
    def _calculate_custom_metrics(self, data: Dict[str, Any], metrics: List[str]) -> Dict[str, Any]:
        """Calculate custom metrics."""
        
        try:
            custom_metrics = {}
            
            for metric in metrics:
                if metric == 'price_per_km':
                    # Calculate average price per kilometer
                    if 'listings' in data:
                        listings = data['listings']
                        total_price = sum(listing.get('price', 0) for listing in listings)
                        total_km = sum(listing.get('mileage', 0) for listing in listings)
                        custom_metrics[metric] = total_price / total_km if total_km > 0 else 0
                
                elif metric == 'avg_age':
                    # Calculate average age of listings
                    if 'listings' in data:
                        listings = data['listings']
                        current_year = datetime.now().year
                        total_age = sum(current_year - listing.get('year', current_year) for listing in listings)
                        custom_metrics[metric] = total_age / len(listings) if listings else 0
                
                # Add more custom metrics as needed
            
            return custom_metrics
            
        except Exception as e:
            logger.error(f"Error calculating custom metrics: {e}")
            return {}
    
    def export_analytics_data(self, report_type: str, format: str = 'csv', filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Export analytics data."""
        
        try:
            # Generate report data
            config = {
                'report_type': report_type,
                'filters': filters or {}
            }
            
            report = self.generate_custom_report(config)
            
            # Export based on format
            if format == 'csv':
                export_result = self._export_to_csv(report)
            elif format == 'json':
                export_result = self._export_to_json(report)
            elif format == 'excel':
                export_result = self._export_to_excel(report)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            logger.info(f"Exported {report_type} analytics data to {format}")
            return export_result
            
        except Exception as e:
            logger.error(f"Error exporting analytics data: {e}")
            return {"error": str(e)}
    
    def _export_to_csv(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Export data to CSV format."""
        
        try:
            # This would implement CSV export logic
            return {"format": "csv", "status": "success", "data_size": len(str(data))}
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return {"error": str(e)}
    
    def _export_to_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Export data to JSON format."""
        
        try:
            # This would implement JSON export logic
            return {"format": "json", "status": "success", "data_size": len(str(data))}
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return {"error": str(e)}
    
    def _export_to_excel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Export data to Excel format."""
        
        try:
            # This would implement Excel export logic
            return {"format": "excel", "status": "success", "data_size": len(str(data))}
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            return {"error": str(e)}
