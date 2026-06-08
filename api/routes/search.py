"""
Search API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
import logging

from ..dependencies import get_database, get_cache
from ..schemas import SearchRequest, SearchResult, SearchFilter
from ..services import SearchService

logger = logging.getLogger(__name__)

search_router = APIRouter(prefix="/search", tags=["search"])

@search_router.post("/", response_model=SearchResult)
async def search_listings(
    search_request: SearchRequest,
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Search car listings with advanced filters."""
    
    try:
        # Create cache key
        cache_key = f"search:{hash(str(search_request.dict()))}"
        
        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved search results from cache")
            return cached_result
        
        # Perform search
        search_service = SearchService(db)
        result = search_service.search_listings(search_request.dict())
        
        # Cache result
        cache.set(cache_key, result, ttl=300)  # 5 minutes
        
        logger.info(f"Search returned {result['total']} results")
        return result
        
    except Exception as e:
        logger.error(f"Error performing search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.get("/quick", response_model=List[Dict[str, Any]])
async def quick_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Quick search with simple text query."""
    
    try:
        # Create cache key
        cache_key = f"quick:{q}:{limit}"
        
        # Try to get from cache
        cached_results = cache.get(cache_key)
        if cached_results:
            logger.info(f"Retrieved quick search results from cache")
            return cached_results
        
        # Perform quick search
        search_service = SearchService(db)
        results = search_service.quick_search(q, limit)
        
        # Cache result
        cache.set(cache_key, results, ttl=300)  # 5 minutes
        
        logger.info(f"Quick search for '{q}' returned {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"Error performing quick search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.get("/filters", response_model=Dict[str, Any])
async def get_available_filters(
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get available search filters and their options."""
    
    try:
        # Create cache key
        cache_key = "filters"
        
        # Try to get from cache
        cached_filters = cache.get(cache_key)
        if cached_filters:
            logger.info("Retrieved search filters from cache")
            return cached_filters
        
        # Get filters from database
        search_service = SearchService(db)
        filters = search_service.get_available_filters()
        
        # Cache result
        cache.set(cache_key, filters, ttl=3600)  # 1 hour
        
        logger.info("Retrieved available search filters")
        return filters
        
    except Exception as e:
        logger.error(f"Error getting search filters: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.get("/suggestions", response_model=List[str])
async def get_search_suggestions(
    q: str = Query(..., min_length=2),
    field: str = Query("make", pattern="^(make|model|location)$"),
    limit: int = Query(10, ge=1, le=20),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get search suggestions for autocomplete."""
    
    try:
        # Create cache key
        cache_key = f"suggestions:{field}:{q}:{limit}"
        
        # Try to get from cache
        cached_suggestions = cache.get(cache_key)
        if cached_suggestions:
            logger.info(f"Retrieved search suggestions from cache")
            return cached_suggestions
        
        # Get suggestions
        search_service = SearchService(db)
        suggestions = search_service.get_suggestions(q, field, limit)
        
        # Cache result
        cache.set(cache_key, suggestions, ttl=1800)  # 30 minutes
        
        logger.info(f"Retrieved {len(suggestions)} suggestions for field '{field}'")
        return suggestions
        
    except Exception as e:
        logger.error(f"Error getting search suggestions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.get("/popular", response_model=List[Dict[str, Any]])
async def get_popular_searches(
    limit: int = Query(10, ge=1, le=50),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get popular search terms."""
    
    try:
        # Create cache key
        cache_key = f"popular:{limit}"
        
        # Try to get from cache
        cached_popular = cache.get(cache_key)
        if cached_popular:
            logger.info("Retrieved popular searches from cache")
            return cached_popular
        
        # Get popular searches
        search_service = SearchService(db)
        popular_searches = search_service.get_popular_searches(limit)
        
        # Cache result
        cache.set(cache_key, popular_searches, ttl=3600)  # 1 hour
        
        logger.info(f"Retrieved {len(popular_searches)} popular searches")
        return popular_searches
        
    except Exception as e:
        logger.error(f"Error getting popular searches: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.get("/history", response_model=List[Dict[str, Any]])
async def get_search_history(
    user_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get search history for a user or global history."""
    
    try:
        # Create cache key
        cache_key = f"history:{user_id}:{limit}"
        
        # Try to get from cache
        cached_history = cache.get(cache_key)
        if cached_history:
            logger.info("Retrieved search history from cache")
            return cached_history
        
        # Get search history
        search_service = SearchService(db)
        history = search_service.get_search_history(user_id, limit)
        
        # Cache result
        cache.set(cache_key, history, ttl=600)  # 10 minutes
        
        logger.info(f"Retrieved {len(history)} search history entries")
        return history
        
    except Exception as e:
        logger.error(f"Error getting search history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.post("/save", response_model=Dict[str, Any])
async def save_search(
    search_request: SearchRequest,
    user_id: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    db = Depends(get_database)
):
    """Save a search query for later use."""
    
    try:
        search_service = SearchService(db)
        saved_search = search_service.save_search(search_request.dict(), user_id, name)
        
        # Invalidate cache
        cache = get_cache()
        cache.delete_pattern("history:*")
        
        logger.info(f"Saved search with ID {saved_search['id']}")
        return saved_search
        
    except Exception as e:
        logger.error(f"Error saving search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.get("/saved", response_model=List[Dict[str, Any]])
async def get_saved_searches(
    user_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get saved searches for a user or global saved searches."""
    
    try:
        # Create cache key
        cache_key = f"saved:{user_id}:{limit}"
        
        # Try to get from cache
        cached_saved = cache.get(cache_key)
        if cached_saved:
            logger.info("Retrieved saved searches from cache")
            return cached_saved
        
        # Get saved searches
        search_service = SearchService(db)
        saved_searches = search_service.get_saved_searches(user_id, limit)
        
        # Cache result
        cache.set(cache_key, saved_searches, ttl=600)  # 10 minutes
        
        logger.info(f"Retrieved {len(saved_searches)} saved searches")
        return saved_searches
        
    except Exception as e:
        logger.error(f"Error getting saved searches: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.delete("/saved/{search_id}")
async def delete_saved_search(
    search_id: str,
    user_id: Optional[str] = Query(None),
    db = Depends(get_database)
):
    """Delete a saved search."""
    
    try:
        search_service = SearchService(db)
        success = search_service.delete_saved_search(search_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Saved search not found")
        
        # Invalidate cache
        cache = get_cache()
        cache.delete_pattern("saved:*")
        
        logger.info(f"Deleted saved search {search_id}")
        return {"message": "Saved search deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting saved search {search_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.get("/analytics", response_model=Dict[str, Any])
async def get_search_analytics(
    days: int = Query(30, ge=1, le=365),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get search analytics and statistics."""
    
    try:
        # Create cache key
        cache_key = f"analytics:{days}"
        
        # Try to get from cache
        cached_analytics = cache.get(cache_key)
        if cached_analytics:
            logger.info("Retrieved search analytics from cache")
            return cached_analytics
        
        # Get analytics
        search_service = SearchService(db)
        analytics = search_service.get_search_analytics(days)
        
        # Cache result
        cache.set(cache_key, analytics, ttl=1800)  # 30 minutes
        
        logger.info(f"Retrieved search analytics for last {days} days")
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting search analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.post("/compare", response_model=Dict[str, Any])
async def compare_listings(
    listing_ids: List[str],
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Compare multiple listings side by side."""
    
    try:
        if len(listing_ids) < 2 or len(listing_ids) > 10:
            raise HTTPException(status_code=400, detail="Must provide 2-10 listing IDs")
        
        # Create cache key
        cache_key = f"compare:{hash(str(listing_ids))}"
        
        # Try to get from cache
        cached_comparison = cache.get(cache_key)
        if cached_comparison:
            logger.info("Retrieved comparison from cache")
            return cached_comparison
        
        # Get comparison
        search_service = SearchService(db)
        comparison = search_service.compare_listings(listing_ids)
        
        # Cache result
        cache.set(cache_key, comparison, ttl=600)  # 10 minutes
        
        logger.info(f"Compared {len(listing_ids)} listings")
        return comparison
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing listings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.get("/recommendations", response_model=List[Dict[str, Any]])
async def get_recommendations(
    listing_id: str = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get personalized recommendations based on listing or user history."""
    
    try:
        if not listing_id and not user_id:
            raise HTTPException(status_code=400, detail="Must provide either listing_id or user_id")
        
        # Create cache key
        cache_key = f"recommendations:{listing_id}:{user_id}:{limit}"
        
        # Try to get from cache
        cached_recommendations = cache.get(cache_key)
        if cached_recommendations:
            logger.info("Retrieved recommendations from cache")
            return cached_recommendations
        
        # Get recommendations
        search_service = SearchService(db)
        recommendations = search_service.get_recommendations(listing_id, user_id, limit)
        
        # Cache result
        cache.set(cache_key, recommendations, ttl=900)  # 15 minutes
        
        logger.info(f"Retrieved {len(recommendations)} recommendations")
        return recommendations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.get("/trending", response_model=List[Dict[str, Any]])
async def get_trending_searches(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    limit: int = Query(20, ge=1, le=50),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get trending search terms."""
    
    try:
        # Create cache key
        cache_key = f"trending:{hours}:{limit}"
        
        # Try to get from cache
        cached_trending = cache.get(cache_key)
        if cached_trending:
            logger.info("Retrieved trending searches from cache")
            return cached_trending
        
        # Get trending searches
        search_service = SearchService(db)
        trending = search_service.get_trending_searches(hours, limit)
        
        # Cache result
        cache.set(cache_key, trending, ttl=1800)  # 30 minutes
        
        logger.info(f"Retrieved {len(trending)} trending searches")
        return trending
        
    except Exception as e:
        logger.error(f"Error getting trending searches: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@search_router.post("/export", response_model=Dict[str, Any])
async def export_search_results(
    search_request: SearchRequest,
    format: str = Query("csv", pattern="^(csv|json|excel)$"),
    db = Depends(get_database)
):
    """Export search results to file."""
    
    try:
        search_service = SearchService(db)
        export_result = search_service.export_search_results(search_request.dict(), format)
        
        logger.info(f"Exported search results to {format}")
        return export_result
        
    except Exception as e:
        logger.error(f"Error exporting search results: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
