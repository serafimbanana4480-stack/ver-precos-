"""
Listing service for API.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ListingService:
    """Service for managing car listings."""
    
    def __init__(self, database, cache):
        """Initialize listing service."""
        self.db = database
        self.cache = cache
        self.default_ttl = 300  # 5 minutes
        
    def get_listings(self, 
                    skip: int = 0,
                    limit: int = 100,
                    source: Optional[str] = None,
                    make: Optional[str] = None,
                    model: Optional[str] = None,
                    min_price: Optional[float] = None,
                    max_price: Optional[float] = None,
                    min_year: Optional[int] = None,
                    max_year: Optional[int] = None,
                    location: Optional[str] = None,
                    fuel_type: Optional[str] = None,
                    transmission: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get listings with optional filters."""
        
        try:
            # Create cache key
            cache_key = f"listings:{skip}:{limit}:{source}:{make}:{model}:{min_price}:{max_price}:{min_year}:{max_year}:{location}:{fuel_type}:{transmission}"
            
            # Try to get from cache
            cached_listings = self.cache.get(cache_key)
            if cached_listings:
                logger.info(f"Retrieved {len(cached_listings)} listings from cache")
                return cached_listings
            
            # Get from database
            listings = self.db.get_listings(
                skip=skip,
                limit=limit,
                source=source,
                make=make,
                model=model,
                min_price=min_price,
                max_price=max_price,
                min_year=min_year,
                max_year=max_year,
                location=location,
                fuel_type=fuel_type,
                transmission=transmission
            )
            
            # Cache results
            self.cache.set(cache_key, listings, ttl=self.default_ttl)
            
            logger.info(f"Retrieved {len(listings)} listings from database")
            return listings
            
        except Exception as e:
            logger.error(f"Error getting listings: {e}")
            return []
    
    def get_listing_by_id(self, listing_id: str, source: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a specific listing by ID."""
        
        try:
            # Create cache key
            cache_key = f"listing:{listing_id}:{source}"
            
            # Try to get from cache
            cached_listing = self.cache.get(cache_key)
            if cached_listing:
                logger.info(f"Retrieved listing {listing_id} from cache")
                return cached_listing
            
            # Get from database
            listing = self.db.get_listing_by_id(listing_id, source)
            
            if listing:
                # Cache result
                self.cache.set(cache_key, listing, ttl=self.default_ttl * 2)
                logger.info(f"Retrieved listing {listing_id} from database")
            
            return listing
            
        except Exception as e:
            logger.error(f"Error getting listing {listing_id}: {e}")
            return None
    
    def create_listing(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new listing."""
        
        try:
            # Add timestamps
            listing_data['created_at'] = datetime.now().isoformat()
            listing_data['updated_at'] = datetime.now().isoformat()
            
            # Save to database
            created_listing = self.db.save_listing(listing_data)
            
            if created_listing:
                # Invalidate cache
                self.cache.delete_pattern("listings:*")
                
                logger.info(f"Created listing {created_listing.get('id')}")
                return created_listing
            
            return {}
            
        except Exception as e:
            logger.error(f"Error creating listing: {e}")
            return {}
    
    def update_listing(self, listing_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a listing."""
        
        try:
            # Add update timestamp
            update_data['updated_at'] = datetime.now().isoformat()
            
            # Update in database
            updated_listing = self.db.update_listing(listing_id, update_data)
            
            if updated_listing:
                # Invalidate cache
                self.cache.delete_pattern("listings:*")
                self.cache.delete(f"listing:{listing_id}:*")
                
                logger.info(f"Updated listing {listing_id}")
                return updated_listing
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating listing {listing_id}: {e}")
            return None
    
    def delete_listing(self, listing_id: str, source: Optional[str] = None) -> bool:
        """Delete a listing."""
        
        try:
            # Delete from database
            success = self.db.delete_listing(listing_id, source)
            
            if success:
                # Invalidate cache
                self.cache.delete_pattern("listings:*")
                self.cache.delete(f"listing:{listing_id}:*")
                
                logger.info(f"Deleted listing {listing_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting listing {listing_id}: {e}")
            return False
    
    def get_similar_listings(self, 
                           make: Optional[str] = None,
                           model: Optional[str] = None,
                           year: Optional[int] = None,
                           price: Optional[float] = None,
                           limit: int = 10) -> List[Dict[str, Any]]:
        """Get similar listings."""
        
        try:
            # Create cache key
            cache_key = f"similar:{make}:{model}:{year}:{price}:{limit}"
            
            # Try to get from cache
            cached_similar = self.cache.get(cache_key)
            if cached_similar:
                logger.info(f"Retrieved {len(cached_similar)} similar listings from cache")
                return cached_similar
            
            # Get from database
            similar_listings = self.db.get_similar_listings(
                make=make,
                model=model,
                year=year,
                price=price,
                limit=limit
            )
            
            # Cache result
            self.cache.set(cache_key, similar_listings, ttl=self.default_ttl * 2)
            
            logger.info(f"Found {len(similar_listings)} similar listings")
            return similar_listings
            
        except Exception as e:
            logger.error(f"Error getting similar listings: {e}")
            return []
    
    def get_featured_listings(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get featured listings."""
        
        try:
            # Create cache key
            cache_key = f"featured:{limit}"
            
            # Try to get from cache
            cached_featured = self.cache.get(cache_key)
            if cached_featured:
                logger.info(f"Retrieved {len(cached_featured)} featured listings from cache")
                return cached_featured
            
            # Get from database
            featured_listings = self.db.get_featured_listings(limit)
            
            # Cache result
            self.cache.set(cache_key, featured_listings, ttl=self.default_ttl * 3)
            
            logger.info(f"Retrieved {len(featured_listings)} featured listings")
            return featured_listings
            
        except Exception as e:
            logger.error(f"Error getting featured listings: {e}")
            return []
    
    def get_recent_listings(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent listings."""
        
        try:
            # Create cache key
            cache_key = f"recent:{hours}:{limit}"
            
            # Try to get from cache
            cached_recent = self.cache.get(cache_key)
            if cached_recent:
                logger.info(f"Retrieved {len(cached_recent)} recent listings from cache")
                return cached_recent
            
            # Get from database
            recent_listings = self.db.get_recent_listings(hours, limit)
            
            # Cache result
            self.cache.set(cache_key, recent_listings, ttl=self.default_ttl // 2)
            
            logger.info(f"Retrieved {len(recent_listings)} recent listings from last {hours} hours")
            return recent_listings
            
        except Exception as e:
            logger.error(f"Error getting recent listings: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get listing statistics."""
        
        try:
            # Create cache key
            cache_key = "listing_stats"
            
            # Try to get from cache
            cached_stats = self.cache.get(cache_key)
            if cached_stats:
                logger.info("Retrieved listing stats from cache")
                return cached_stats
            
            # Get from database
            stats = self.db.get_statistics()
            
            # Cache result
            self.cache.set(cache_key, stats, ttl=self.default_ttl * 6)
            
            logger.info("Retrieved listing statistics")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting listing stats: {e}")
            return {}
    
    def bulk_create_listings(self, listings_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create multiple listings in bulk."""
        
        try:
            if len(listings_data) > 1000:
                raise ValueError("Too many listings for bulk creation (max 1000)")
            
            # Add timestamps to all listings
            current_time = datetime.now().isoformat()
            for listing in listings_data:
                listing['created_at'] = current_time
                listing['updated_at'] = current_time
            
            # Save to database
            result = self.db.bulk_save_listings(listings_data)
            
            # Invalidate cache
            self.cache.delete_pattern("listings:*")
            
            logger.info(f"Bulk created {result.get('created', 0)} listings")
            return result
            
        except Exception as e:
            logger.error(f"Error bulk creating listings: {e}")
            return {"created": 0, "errors": [str(e)]}
    
    def bulk_delete_listings(self, listing_ids: List[str]) -> Dict[str, Any]:
        """Delete multiple listings in bulk."""
        
        try:
            if len(listing_ids) > 1000:
                raise ValueError("Too many listings for bulk deletion (max 1000)")
            
            # Delete from database
            result = self.db.bulk_delete_listings(listing_ids)
            
            # Invalidate cache
            self.cache.delete_pattern("listings:*")
            for listing_id in listing_ids:
                self.cache.delete(f"listing:{listing_id}:*")
            
            logger.info(f"Bulk deleted {result.get('deleted', 0)} listings")
            return result
            
        except Exception as e:
            logger.error(f"Error bulk deleting listings: {e}")
            return {"deleted": 0, "errors": [str(e)]}
    
    def get_search_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get search suggestions for autocomplete."""
        
        try:
            # Create cache key
            cache_key = f"suggestions:{query}:{limit}"
            
            # Try to get from cache
            cached_suggestions = self.cache.get(cache_key)
            if cached_suggestions:
                logger.info(f"Retrieved {len(cached_suggestions)} search suggestions from cache")
                return cached_suggestions
            
            # Get from database
            suggestions = self.db.get_search_suggestions(query, limit)
            
            # Cache result
            self.cache.set(cache_key, suggestions, ttl=self.default_ttl * 3)
            
            logger.info(f"Retrieved {len(suggestions)} search suggestions for '{query}'")
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting search suggestions: {e}")
            return []
    
    def get_listings_by_make(self, make: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get listings by make."""
        
        try:
            # Create cache key
            cache_key = f"make:{make}:{limit}"
            
            # Try to get from cache
            cached_listings = self.cache.get(cache_key)
            if cached_listings:
                logger.info(f"Retrieved {len(cached_listings)} listings for make {make} from cache")
                return cached_listings
            
            # Get from database
            listings = self.db.get_listings_by_make(make, limit)
            
            # Cache result
            self.cache.set(cache_key, listings, ttl=self.default_ttl * 2)
            
            logger.info(f"Retrieved {len(listings)} listings for make {make}")
            return listings
            
        except Exception as e:
            logger.error(f"Error getting listings by make {make}: {e}")
            return []
    
    def get_listings_by_model(self, make: str, model: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get listings by make and model."""
        
        try:
            # Create cache key
            cache_key = f"model:{make}:{model}:{limit}"
            
            # Try to get from cache
            cached_listings = self.cache.get(cache_key)
            if cached_listings:
                logger.info(f"Retrieved {len(cached_listings)} listings for model {make} {model} from cache")
                return cached_listings
            
            # Get from database
            listings = self.db.get_listings_by_model(make, model, limit)
            
            # Cache result
            self.cache.set(cache_key, listings, ttl=self.default_ttl * 2)
            
            logger.info(f"Retrieved {len(listings)} listings for model {make} {model}")
            return listings
            
        except Exception as e:
            logger.error(f"Error getting listings by model {make} {model}: {e}")
            return []
    
    def get_price_analysis(self, make: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """Get price analysis for listings."""
        
        try:
            # Create cache key
            cache_key = f"price_analysis:{make}:{model}"
            
            # Try to get from cache
            cached_analysis = self.cache.get(cache_key)
            if cached_analysis:
                logger.info(f"Retrieved price analysis for {make} {model} from cache")
                return cached_analysis
            
            # Get from database
            analysis = self.db.get_price_analysis(make, model)
            
            # Cache result
            self.cache.set(cache_key, analysis, ttl=self.default_ttl * 4)
            
            logger.info(f"Retrieved price analysis for {make} {model}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting price analysis: {e}")
            return {}
    
    def get_makes_and_models(self) -> Dict[str, List[str]]:
        """Get all makes and their models."""
        
        try:
            # Create cache key
            cache_key = "makes_models"
            
            # Try to get from cache
            cached_data = self.cache.get(cache_key)
            if cached_data:
                logger.info("Retrieved makes and models from cache")
                return cached_data
            
            # Get from database
            makes_models = self.db.get_makes_and_models()
            
            # Cache result
            self.cache.set(cache_key, makes_models, ttl=self.default_ttl * 12)
            
            logger.info("Retrieved makes and models")
            return makes_models
            
        except Exception as e:
            logger.error(f"Error getting makes and models: {e}")
            return {}
    
    def validate_listing_data(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate listing data."""
        
        try:
            errors = []
            warnings = []
            
            # Required fields
            required_fields = ['title', 'make', 'model', 'year', 'price']
            for field in required_fields:
                if field not in listing_data or listing_data[field] is None:
                    errors.append(f"Missing required field: {field}")
            
            # Validate year
            if 'year' in listing_data:
                year = listing_data['year']
                if not isinstance(year, int) or year < 1900 or year > datetime.now().year + 1:
                    errors.append(f"Invalid year: {year}")
            
            # Validate price
            if 'price' in listing_data:
                price = listing_data['price']
                if not isinstance(price, (int, float)) or price <= 0 or price > 1000000:
                    errors.append(f"Invalid price: {price}")
            
            # Validate mileage
            if 'mileage' in listing_data:
                mileage = listing_data['mileage']
                if mileage is not None and (not isinstance(mileage, int) or mileage < 0 or mileage > 500000):
                    warnings.append(f"Unusual mileage: {mileage}")
            
            # Validate make and model
            if 'make' in listing_data and 'model' in listing_data:
                make = listing_data['make']
                model = listing_data['model']
                
                # Check if make exists in database
                makes_models = self.get_makes_and_models()
                if make not in makes_models:
                    warnings.append(f"Unknown make: {make}")
                elif model not in makes_models[make]:
                    warnings.append(f"Unknown model: {model} for make {make}")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Error validating listing data: {e}")
            return {"valid": False, "errors": [str(e)], "warnings": []}
    
    def enrich_listing(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich listing with additional data."""
        
        try:
            enriched_data = listing_data.copy()
            
            # Add price per km if mileage is available
            if 'price' in enriched_data and 'mileage' in enriched_data:
                price = enriched_data['price']
                mileage = enriched_data['mileage']
                
                if mileage and mileage > 0:
                    enriched_data['price_per_km'] = price / mileage
            
            # Add age in years
            if 'year' in enriched_data:
                year = enriched_data['year']
                current_year = datetime.now().year
                enriched_data['age_years'] = current_year - year
            
            # Add price category
            if 'price' in enriched_data:
                price = enriched_data['price']
                
                if price < 5000:
                    enriched_data['price_category'] = 'budget'
                elif price < 15000:
                    enriched_data['price_category'] = 'economy'
                elif price < 30000:
                    enriched_data['price_category'] = 'standard'
                elif price < 50000:
                    enriched_data['price_category'] = 'premium'
                else:
                    enriched_data['price_category'] = 'luxury'
            
            # Add fuel efficiency estimate (simplified)
            if 'fuel_type' in enriched_data and 'engine_size' in enriched_data:
                fuel_type = enriched_data['fuel_type']
                engine_size = enriched_data['engine_size']
                
                if fuel_type == 'Electric':
                    enriched_data['fuel_efficiency'] = 'N/A (Electric)'
                elif fuel_type in ['Gasoline', 'Hybrid'] and engine_size:
                    if engine_size < 1.5:
                        enriched_data['fuel_efficiency'] = 'High'
                    elif engine_size < 2.0:
                        enriched_data['fuel_efficiency'] = 'Medium'
                    else:
                        enriched_data['fuel_efficiency'] = 'Low'
            
            return enriched_data
            
        except Exception as e:
            logger.error(f"Error enriching listing: {e}")
            return listing_data
    
    def get_listing_quality_score(self, listing_data: Dict[str, Any]) -> float:
        """Calculate quality score for a listing."""
        
        try:
            score = 0.0
            max_score = 10.0
            
            # Title quality (2 points)
            if 'title' in listing_data and listing_data['title']:
                title = listing_data['title']
                if len(title) >= 10 and len(title) <= 100:
                    score += 2.0
                elif len(title) >= 5:
                    score += 1.0
            
            # Description quality (2 points)
            if 'description' in listing_data and listing_data['description']:
                description = listing_data['description']
                if len(description) >= 50:
                    score += 2.0
                elif len(description) >= 20:
                    score += 1.0
            
            # Image presence (1 point)
            if 'image_url' in listing_data and listing_data['image_url']:
                score += 1.0
            
            # Complete data (2 points)
            required_fields = ['make', 'model', 'year', 'price', 'mileage', 'fuel_type', 'transmission']
            complete_fields = sum(1 for field in required_fields if field in listing_data and listing_data[field])
            score += (complete_fields / len(required_fields)) * 2.0
            
            # Price reasonableness (2 points)
            if 'price' in listing_data and 'year' in listing_data:
                price = listing_data['price']
                year = listing_data['year']
                age = datetime.now().year - year
                
                # Simple price reasonableness check
                if age <= 1 and 10000 <= price <= 50000:
                    score += 2.0
                elif age <= 5 and 5000 <= price <= 30000:
                    score += 2.0
                elif age <= 10 and 2000 <= price <= 20000:
                    score += 2.0
                elif age > 10 and 1000 <= price <= 10000:
                    score += 2.0
                else:
                    score += 0.5
            
            # Location specificity (1 point)
            if 'location' in listing_data and listing_data['location']:
                location = listing_data['location']
                if len(location) >= 5:
                    score += 1.0
            
            return min(score, max_score)
            
        except Exception as e:
            logger.error(f"Error calculating listing quality score: {e}")
            return 0.0
