"""
Search service for API.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SearchService:
    """Service for managing search functionality."""
    
    def __init__(self, database, cache):
        """Initialize search service."""
        self.db = database
        self.cache = cache
        self.default_ttl = 300  # 5 minutes
        
    def search_listings(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Search car listings with advanced filters."""
        
        try:
            # Create cache key
            cache_key = f"search:{hash(str(search_params))}"
            
            # Try to get from cache
            cached_result = self.cache.get(cache_key)
            if cached_result:
                logger.info(f"Retrieved search results from cache")
                return cached_result
            
            # Perform search
            result = self._perform_search(search_params)
            
            # Cache result
            self.cache.set(cache_key, result, ttl=self.default_ttl)
            
            logger.info(f"Search returned {result.get('total', 0)} results")
            return result
            
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            return {"listings": [], "total": 0, "facets": {}}
    
    def _perform_search(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual search."""
        
        # Extract search parameters
        query = search_params.get('query')
        filters = search_params.get('filters', {})
        sort_by = search_params.get('sort_by', 'scraped_at')
        sort_order = search_params.get('sort_order', 'desc')
        limit = search_params.get('limit', 20)
        offset = search_params.get('offset', 0)
        include_facets = search_params.get('include_facets', False)
        
        # Build search query
        search_query = self._build_search_query(query, filters)
        
        # Get listings from database
        listings = self.db.search_listings(
            query=search_query,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )
        
        # Get total count
        total = self.db.count_listings(query=search_query, filters=filters)
        
        # Get facets if requested
        facets = {}
        if include_facets:
            facets = self._get_search_facets(search_query, filters)
        
        return {
            "listings": listings,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(listings) < total,
            "facets": facets
        }
    
    def _build_search_query(self, query: Optional[str], filters: Dict[str, Any]) -> str:
        """Build search query string."""
        
        if not query:
            return ""
        
        # Simple query building - in production, this would be more sophisticated
        search_terms = query.split()
        
        # Add wildcards for partial matching
        query_parts = []
        for term in search_terms:
            query_parts.append(f"*{term}*")
        
        return " AND ".join(query_parts)
    
    def _get_search_facets(self, query: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get search facets for filtering."""
        
        try:
            facets = {}
            
            # Make facet
            make_facet = self.db.get_make_facet(query=query, filters=filters)
            if make_facet:
                facets['makes'] = make_facet
            
            # Model facet
            model_facet = self.db.get_model_facet(query=query, filters=filters)
            if model_facet:
                facets['models'] = model_facet
            
            # Price range facet
            price_facet = self.db.get_price_facet(query=query, filters=filters)
            if price_facet:
                facets['price_ranges'] = price_facet
            
            # Year facet
            year_facet = self.db.get_year_facet(query=query, filters=filters)
            if year_facet:
                facets['years'] = year_facet
            
            # Location facet
            location_facet = self.db.get_location_facet(query=query, filters=filters)
            if location_facet:
                facets['locations'] = location_facet
            
            # Fuel type facet
            fuel_facet = self.db.get_fuel_type_facet(query=query, filters=filters)
            if fuel_facet:
                facets['fuel_types'] = fuel_facet
            
            return facets
            
        except Exception as e:
            logger.error(f"Error getting search facets: {e}")
            return {}
    
    def quick_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Quick search with simple text query."""
        
        try:
            # Create cache key
            cache_key = f"quick:{query}:{limit}"
            
            # Try to get from cache
            cached_results = self.cache.get(cache_key)
            if cached_results:
                logger.info(f"Retrieved quick search results from cache")
                return cached_results
            
            # Perform quick search
            search_params = {
                'query': query,
                'limit': limit,
                'sort_by': 'relevance'
            }
            
            result = self.search_listings(search_params)
            
            # Cache result
            self.cache.set(cache_key, result['listings'], ttl=self.default_ttl)
            
            logger.info(f"Quick search for '{query}' returned {len(result['listings'])} results")
            return result['listings']
            
        except Exception as e:
            logger.error(f"Error performing quick search: {e}")
            return []
    
    def get_available_filters(self) -> Dict[str, Any]:
        """Get available search filters and their options."""
        
        try:
            # Create cache key
            cache_key = "available_filters"
            
            # Try to get from cache
            cached_filters = self.cache.get(cache_key)
            if cached_filters:
                logger.info("Retrieved available filters from cache")
                return cached_filters
            
            # Get filters from database
            filters = {
                'makes': self.db.get_all_makes(),
                'models': self.db.get_all_models(),
                'fuel_types': self.db.get_all_fuel_types(),
                'transmissions': self.db.get_all_transmissions(),
                'conditions': self.db.get_all_conditions(),
                'locations': self.db.get_all_locations(),
                'price_ranges': [
                    {'label': 'Under 5.000€', 'min': 0, 'max': 5000},
                    {'label': '5.000€ - 10.000€', 'min': 5000, 'max': 10000},
                    {'label': '10.000€ - 15.000€', 'min': 10000, 'max': 15000},
                    {'label': '15.000€ - 20.000€', 'min': 15000, 'max': 20000},
                    {'label': '20.000€ - 30.000€', 'min': 20000, 'max': 30000},
                    {'label': '30.000€ - 50.000€', 'min': 30000, 'max': 50000},
                    {'label': 'Over 50.000€', 'min': 50000, 'max': None}
                ],
                'year_ranges': [
                    {'label': 'Last 2 years', 'min': datetime.now().year - 2, 'max': datetime.now().year + 1},
                    {'label': 'Last 5 years', 'min': datetime.now().year - 5, 'max': datetime.now().year + 1},
                    {'label': 'Last 10 years', 'min': datetime.now().year - 10, 'max': datetime.now().year + 1},
                    {'label': 'Older than 10 years', 'min': 0, 'max': datetime.now().year - 10}
                ],
                'mileage_ranges': [
                    {'label': 'Under 50.000 km', 'min': 0, 'max': 50000},
                    {'label': '50.000 - 100.000 km', 'min': 50000, 'max': 100000},
                    {'label': '100.000 - 150.000 km', 'min': 100000, 'max': 150000},
                    {'label': '150.000 - 200.000 km', 'min': 150000, 'max': 200000},
                    {'label': 'Over 200.000 km', 'min': 200000, 'max': None}
                ]
            }
            
            # Cache result
            self.cache.set(cache_key, filters, ttl=self.default_ttl * 12)
            
            logger.info("Retrieved available search filters")
            return filters
            
        except Exception as e:
            logger.error(f"Error getting available filters: {e}")
            return {}
    
    def get_suggestions(self, query: str, field: str, limit: int = 10) -> List[str]:
        """Get search suggestions for autocomplete."""
        
        try:
            # Create cache key
            cache_key = f"suggestions:{field}:{query}:{limit}"
            
            # Try to get from cache
            cached_suggestions = self.cache.get(cache_key)
            if cached_suggestions:
                logger.info(f"Retrieved search suggestions from cache")
                return cached_suggestions
            
            # Get suggestions from database
            suggestions = self.db.get_suggestions(query, field, limit)
            
            # Cache result
            self.cache.set(cache_key, suggestions, ttl=self.default_ttl * 6)
            
            logger.info(f"Retrieved {len(suggestions)} suggestions for field '{field}'")
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")
            return []
    
    def get_popular_searches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get popular search terms."""
        
        try:
            # Create cache key
            cache_key = f"popular:{limit}"
            
            # Try to get from cache
            cached_popular = self.cache.get(cache_key)
            if cached_popular:
                logger.info("Retrieved popular searches from cache")
                return cached_popular
            
            # Get popular searches from database
            popular_searches = self.db.get_popular_searches(limit)
            
            # Cache result
            self.cache.set(cache_key, popular_searches, ttl=self.default_ttl * 24)
            
            logger.info(f"Retrieved {len(popular_searches)} popular searches")
            return popular_searches
            
        except Exception as e:
            logger.error(f"Error getting popular searches: {e}")
            return []
    
    def get_search_history(self, user_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get search history for a user or global history."""
        
        try:
            # Create cache key
            cache_key = f"history:{user_id}:{limit}"
            
            # Try to get from cache
            cached_history = self.cache.get(cache_key)
            if cached_history:
                logger.info("Retrieved search history from cache")
                return cached_history
            
            # Get search history from database
            history = self.db.get_search_history(user_id, limit)
            
            # Cache result
            self.cache.set(cache_key, history, ttl=self.default_ttl * 2)
            
            logger.info(f"Retrieved {len(history)} search history entries")
            return history
            
        except Exception as e:
            logger.error(f"Error getting search history: {e}")
            return []
    
    def save_search(self, search_params: Dict[str, Any], user_id: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
        """Save a search query for later use."""
        
        try:
            # Create search record
            search_record = {
                'query': search_params.get('query', ''),
                'filters': search_params.get('filters', {}),
                'user_id': user_id,
                'name': name,
                'created_at': datetime.now().isoformat()
            }
            
            # Save to database
            saved_search = self.db.save_search(search_record)
            
            # Invalidate cache
            self.cache.delete_pattern("history:*")
            
            logger.info(f"Saved search with ID {saved_search.get('id')}")
            return saved_search
            
        except Exception as e:
            logger.error(f"Error saving search: {e}")
            return {}
    
    def get_saved_searches(self, user_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get saved searches for a user or global saved searches."""
        
        try:
            # Create cache key
            cache_key = f"saved:{user_id}:{limit}"
            
            # Try to get from cache
            cached_saved = self.cache.get(cache_key)
            if cached_saved:
                logger.info("Retrieved saved searches from cache")
                return cached_saved
            
            # Get saved searches from database
            saved_searches = self.db.get_saved_searches(user_id, limit)
            
            # Cache result
            self.cache.set(cache_key, saved_searches, ttl=self.default_ttl * 6)
            
            logger.info(f"Retrieved {len(saved_searches)} saved searches")
            return saved_searches
            
        except Exception as e:
            logger.error(f"Error getting saved searches: {e}")
            return []
    
    def delete_saved_search(self, search_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a saved search."""
        
        try:
            # Delete from database
            success = self.db.delete_saved_search(search_id, user_id)
            
            if success:
                # Invalidate cache
                self.cache.delete_pattern("saved:*")
                logger.info(f"Deleted saved search {search_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting saved search {search_id}: {e}")
            return False
    
    def get_search_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get search analytics and statistics."""
        
        try:
            # Create cache key
            cache_key = f"analytics:{days}"
            
            # Try to get from cache
            cached_analytics = self.cache.get(cache_key)
            if cached_analytics:
                logger.info("Retrieved search analytics from cache")
                return cached_analytics
            
            # Get analytics from database
            analytics = self.db.get_search_analytics(days)
            
            # Cache result
            self.cache.set(cache_key, analytics, ttl=self.default_ttl * 12)
            
            logger.info(f"Retrieved search analytics for last {days} days")
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting search analytics: {e}")
            return {}
    
    def compare_listings(self, listing_ids: List[str]) -> Dict[str, Any]:
        """Compare multiple listings side by side."""
        
        try:
            if len(listing_ids) < 2 or len(listing_ids) > 10:
                raise ValueError("Must provide 2-10 listing IDs for comparison")
            
            # Create cache key
            cache_key = f"compare:{hash(str(listing_ids))}"
            
            # Try to get from cache
            cached_comparison = self.cache.get(cache_key)
            if cached_comparison:
                logger.info("Retrieved comparison from cache")
                return cached_comparison
            
            # Get listings from database
            listings = []
            for listing_id in listing_ids:
                listing = self.db.get_listing_by_id(listing_id)
                if listing:
                    listings.append(listing)
            
            if len(listings) < 2:
                return {"error": "Not enough valid listings found for comparison"}
            
            # Create comparison data
            comparison = self._create_comparison_data(listings)
            
            # Cache result
            self.cache.set(cache_key, comparison, ttl=self.default_ttl * 3)
            
            logger.info(f"Compared {len(listings)} listings")
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing listings: {e}")
            return {"error": str(e)}
    
    def _create_comparison_data(self, listings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create comparison data from listings."""
        
        # Define comparison fields
        comparison_fields = [
            'title', 'make', 'model', 'year', 'price', 'mileage',
            'fuel_type', 'transmission', 'engine_size', 'location',
            'condition', 'seller_name', 'seller_type'
        ]
        
        comparison = {
            'listings': listings,
            'comparison_table': {},
            'price_analysis': {},
            'specifications_comparison': {}
        }
        
        # Build comparison table
        for field in comparison_fields:
            comparison['comparison_table'][field] = []
            for listing in listings:
                value = listing.get(field, 'N/A')
                comparison['comparison_table'][field].append(value)
        
        # Price analysis
        prices = [listing.get('price', 0) for listing in listings if listing.get('price')]
        if prices:
            comparison['price_analysis'] = {
                'min_price': min(prices),
                'max_price': max(prices),
                'avg_price': sum(prices) / len(prices),
                'price_range': max(prices) - min(prices)
            }
        
        # Specifications comparison
        specs = ['year', 'mileage', 'engine_size']
        for spec in specs:
            values = [listing.get(spec) for listing in listings if listing.get(spec) is not None]
            if values:
                comparison['specifications_comparison'][spec] = {
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'range': max(values) - min(values)
                }
        
        return comparison
    
    def get_recommendations(self, listing_id: Optional[str] = None, user_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get personalized recommendations based on listing or user history."""
        
        try:
            if not listing_id and not user_id:
                raise ValueError("Must provide either listing_id or user_id")
            
            # Create cache key
            cache_key = f"recommendations:{listing_id}:{user_id}:{limit}"
            
            # Try to get from cache
            cached_recommendations = self.cache.get(cache_key)
            if cached_recommendations:
                logger.info("Retrieved recommendations from cache")
                return cached_recommendations
            
            # Get recommendations
            recommendations = []
            
            if listing_id:
                # Get similar listings
                listing = self.db.get_listing_by_id(listing_id)
                if listing:
                    recommendations = self.db.get_similar_listings(
                        make=listing.get('make'),
                        model=listing.get('model'),
                        year=listing.get('year'),
                        price=listing.get('price'),
                        limit=limit
                    )
            
            elif user_id:
                # Get recommendations based on user history
                user_searches = self.db.get_search_history(user_id, limit=10)
                if user_searches:
                    # Extract preferences from search history
                    preferences = self._extract_user_preferences(user_searches)
                    recommendations = self.db.get_recommendations_by_preferences(preferences, limit)
            
            # Cache result
            self.cache.set(cache_key, recommendations, ttl=self.default_ttl * 4)
            
            logger.info(f"Retrieved {len(recommendations)} recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []
    
    def _extract_user_preferences(self, user_searches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract user preferences from search history."""
        
        preferences = {
            'preferred_makes': {},
            'preferred_models': {},
            'price_range': {'min': None, 'max': None},
            'preferred_years': {},
            'preferred_locations': {}
        }
        
        for search in user_searches:
            filters = search.get('filters', {})
            
            # Count make preferences
            if 'make' in filters:
                make = filters['make']
                preferences['preferred_makes'][make] = preferences['preferred_makes'].get(make, 0) + 1
            
            # Count model preferences
            if 'model' in filters:
                model = filters['model']
                preferences['preferred_models'][model] = preferences['preferred_models'].get(model, 0) + 1
            
            # Update price range
            if 'min_price' in filters:
                min_price = filters['min_price']
                if preferences['price_range']['min'] is None or min_price < preferences['price_range']['min']:
                    preferences['price_range']['min'] = min_price
            
            if 'max_price' in filters:
                max_price = filters['max_price']
                if preferences['price_range']['max'] is None or max_price > preferences['price_range']['max']:
                    preferences['price_range']['max'] = max_price
            
            # Count year preferences
            if 'year' in filters:
                year = filters['year']
                preferences['preferred_years'][year] = preferences['preferred_years'].get(year, 0) + 1
            
            # Count location preferences
            if 'location' in filters:
                location = filters['location']
                preferences['preferred_locations'][location] = preferences['preferred_locations'].get(location, 0) + 1
        
        return preferences
    
    def get_trending_searches(self, hours: int = 24, limit: int = 20) -> List[Dict[str, Any]]:
        """Get trending search terms."""
        
        try:
            # Create cache key
            cache_key = f"trending:{hours}:{limit}"
            
            # Try to get from cache
            cached_trending = self.cache.get(cache_key)
            if cached_trending:
                logger.info("Retrieved trending searches from cache")
                return cached_trending
            
            # Get trending searches from database
            trending = self.db.get_trending_searches(hours, limit)
            
            # Cache result
            self.cache.set(cache_key, trending, ttl=self.default_ttl * 2)
            
            logger.info(f"Retrieved {len(trending)} trending searches")
            return trending
            
        except Exception as e:
            logger.error(f"Error getting trending searches: {e}")
            return []
    
    def export_search_results(self, search_params: Dict[str, Any], format: str = 'csv') -> Dict[str, Any]:
        """Export search results to file."""
        
        try:
            # Perform search
            result = self.search_listings(search_params)
            
            # Export based on format
            if format == 'csv':
                export_result = self.db.export_to_csv(result['listings'])
            elif format == 'json':
                export_result = self.db.export_to_json(result['listings'])
            elif format == 'excel':
                export_result = self.db.export_to_excel(result['listings'])
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            logger.info(f"Exported search results to {format}")
            return export_result
            
        except Exception as e:
            logger.error(f"Error exporting search results: {e}")
            return {"error": str(e)}
    
    def get_search_performance_metrics(self) -> Dict[str, Any]:
        """Get search performance metrics."""
        
        try:
            # Create cache key
            cache_key = "search_performance"
            
            # Try to get from cache
            cached_metrics = self.cache.get(cache_key)
            if cached_metrics:
                logger.info("Retrieved search performance metrics from cache")
                return cached_metrics
            
            # Get metrics from database
            metrics = self.db.get_search_performance_metrics()
            
            # Cache result
            self.cache.set(cache_key, metrics, ttl=self.default_ttl * 6)
            
            logger.info("Retrieved search performance metrics")
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting search performance metrics: {e}")
            return {}
    
    def optimize_search_index(self) -> bool:
        """Optimize search index for better performance."""
        
        try:
            # This would typically involve rebuilding search indexes
            # For this implementation, we'll just clear cache and rebuild
            self.cache.delete_pattern("search:*")
            self.cache.delete_pattern("suggestions:*")
            
            logger.info("Search index optimization completed")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing search index: {e}")
            return False
    
    def validate_search_query(self, query: str) -> Dict[str, Any]:
        """Validate search query for potential issues."""
        
        try:
            validation_result = {
                'is_valid': True,
                'errors': [],
                'warnings': [],
                'suggestions': []
            }
            
            # Check query length
            if len(query) < 2:
                validation_result['errors'].append("Query too short (minimum 2 characters)")
                validation_result['is_valid'] = False
            elif len(query) > 100:
                validation_result['warnings'].append("Query is very long, may return too many results")
            
            # Check for special characters
            special_chars = ['<', '>', '|', '&', '^', '(', ')', '[', ']', '{', '}']
            for char in special_chars:
                if char in query:
                    validation_result['warnings'].append(f"Special character '{char}' may affect search results")
            
            # Check for common spelling mistakes
            common_mistakes = {
                'mercedes': 'Mercedes',
                'volkswagen': 'Volkswagen',
                'toyota': 'Toyota',
                'honda': 'Honda',
                'ford': 'Ford'
            }
            
            for mistake, correction in common_mistakes.items():
                if mistake.lower() in query.lower():
                    validation_result['suggestions'].append(f"Did you mean '{correction}'?")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating search query: {e}")
            return {'is_valid': False, 'errors': [str(e)], 'warnings': [], 'suggestions': []}
