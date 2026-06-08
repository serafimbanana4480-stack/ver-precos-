"""
Listings API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from ..dependencies import get_database, get_cache
from ..schemas import ListingResponse, ListingCreate, ListingUpdate, ListingFilter
from ..services import ListingService

logger = logging.getLogger(__name__)

listings_router = APIRouter(prefix="/listings", tags=["listings"])

@listings_router.get("/", response_model=List[ListingResponse])
async def get_listings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    source: Optional[str] = Query(None),
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_year: Optional[int] = Query(None, ge=1900),
    max_year: Optional[int] = Query(None, le=datetime.now().year + 1),
    location: Optional[str] = Query(None),
    fuel_type: Optional[str] = Query(None),
    transmission: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get car listings with optional filters."""
    
    try:
        # Create cache key
        cache_key = f"listings:{source}:{make}:{model}:{min_price}:{max_price}:{min_year}:{max_year}:{location}:{fuel_type}:{transmission}:{skip}:{limit}"
        
        # Try to get from cache
        cached_listings = cache.get(cache_key)
        if cached_listings:
            logger.info(f"Retrieved {len(cached_listings)} listings from cache")
            return cached_listings
        
        # Get from database
        listing_service = ListingService(db)
        listings = listing_service.get_listings(
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
        cache.set(cache_key, listings, ttl=300)  # 5 minutes
        
        logger.info(f"Retrieved {len(listings)} listings from database")
        return listings
        
    except Exception as e:
        logger.error(f"Error getting listings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: str,
    source: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get a specific listing by ID."""
    
    try:
        # Create cache key
        cache_key = f"listing:{listing_id}:{source}"
        
        # Try to get from cache
        cached_listing = cache.get(cache_key)
        if cached_listing:
            logger.info(f"Retrieved listing {listing_id} from cache")
            return cached_listing
        
        # Get from database
        listing_service = ListingService(db)
        listing = listing_service.get_listing_by_id(listing_id, source)
        
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Cache result
        cache.set(cache_key, listing, ttl=600)  # 10 minutes
        
        logger.info(f"Retrieved listing {listing_id} from database")
        return listing
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting listing {listing_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.post("/", response_model=ListingResponse)
async def create_listing(
    listing: ListingCreate,
    db = Depends(get_database)
):
    """Create a new listing."""
    
    try:
        listing_service = ListingService(db)
        created_listing = listing_service.create_listing(listing.dict())
        
        # Invalidate cache
        cache = get_cache()
        cache.delete_pattern("listings:*")
        
        logger.info(f"Created listing {created_listing['id']}")
        return created_listing
        
    except Exception as e:
        logger.error(f"Error creating listing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.put("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: str,
    listing_update: ListingUpdate,
    db = Depends(get_database)
):
    """Update a listing."""
    
    try:
        listing_service = ListingService(db)
        updated_listing = listing_service.update_listing(listing_id, listing_update.dict(exclude_unset=True))
        
        if not updated_listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Invalidate cache
        cache = get_cache()
        cache.delete_pattern("listings:*")
        cache.delete(f"listing:{listing_id}:*")
        
        logger.info(f"Updated listing {listing_id}")
        return updated_listing
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating listing {listing_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.delete("/{listing_id}")
async def delete_listing(
    listing_id: str,
    source: Optional[str] = Query(None),
    db = Depends(get_database)
):
    """Delete a listing."""
    
    try:
        listing_service = ListingService(db)
        success = listing_service.delete_listing(listing_id, source)
        
        if not success:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Invalidate cache
        cache = get_cache()
        cache.delete_pattern("listings:*")
        cache.delete(f"listing:{listing_id}:*")
        
        logger.info(f"Deleted listing {listing_id}")
        return {"message": "Listing deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting listing {listing_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.get("/{listing_id}/similar", response_model=List[ListingResponse])
async def get_similar_listings(
    listing_id: str,
    limit: int = Query(10, ge=1, le=50),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get similar listings for a specific listing."""
    
    try:
        # Create cache key
        cache_key = f"similar:{listing_id}:{limit}"
        
        # Try to get from cache
        cached_similar = cache.get(cache_key)
        if cached_similar:
            logger.info(f"Retrieved {len(cached_similar)} similar listings for {listing_id} from cache")
            return cached_similar
        
        # Get original listing
        listing_service = ListingService(db)
        original_listing = listing_service.get_listing_by_id(listing_id)
        
        if not original_listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Get similar listings
        similar_listings = listing_service.get_similar_listings(
            make=original_listing.get('make'),
            model=original_listing.get('model'),
            year=original_listing.get('year'),
            price=original_listing.get('price'),
            limit=limit
        )
        
        # Cache result
        cache.set(cache_key, similar_listings, ttl=600)  # 10 minutes
        
        logger.info(f"Found {len(similar_listings)} similar listings for {listing_id}")
        return similar_listings
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting similar listings for {listing_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.get("/featured", response_model=List[ListingResponse])
async def get_featured_listings(
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get featured listings."""
    
    try:
        # Create cache key
        cache_key = f"featured:{limit}"
        
        # Try to get from cache
        cached_featured = cache.get(cache_key)
        if cached_featured:
            logger.info(f"Retrieved {len(cached_featured)} featured listings from cache")
            return cached_featured
        
        # Get from database
        listing_service = ListingService(db)
        featured_listings = listing_service.get_featured_listings(limit)
        
        # Cache result
        cache.set(cache_key, featured_listings, ttl=1800)  # 30 minutes
        
        logger.info(f"Retrieved {len(featured_listings)} featured listings")
        return featured_listings
        
    except Exception as e:
        logger.error(f"Error getting featured listings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.get("/recent", response_model=List[ListingResponse])
async def get_recent_listings(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    limit: int = Query(50, ge=1, le=200),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get recent listings."""
    
    try:
        # Create cache key
        cache_key = f"recent:{hours}:{limit}"
        
        # Try to get from cache
        cached_recent = cache.get(cache_key)
        if cached_recent:
            logger.info(f"Retrieved {len(cached_recent)} recent listings from cache")
            return cached_recent
        
        # Get from database
        listing_service = ListingService(db)
        recent_listings = listing_service.get_recent_listings(hours, limit)
        
        # Cache result
        cache.set(cache_key, recent_listings, ttl=300)  # 5 minutes
        
        logger.info(f"Retrieved {len(recent_listings)} recent listings from last {hours} hours")
        return recent_listings
        
    except Exception as e:
        logger.error(f"Error getting recent listings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.get("/stats", response_model=Dict[str, Any])
async def get_listing_stats(
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get listing statistics."""
    
    try:
        # Create cache key
        cache_key = "listing_stats"
        
        # Try to get from cache
        cached_stats = cache.get(cache_key)
        if cached_stats:
            logger.info("Retrieved listing stats from cache")
            return cached_stats
        
        # Get from database
        listing_service = ListingService(db)
        stats = listing_service.get_statistics()
        
        # Cache result
        cache.set(cache_key, stats, ttl=900)  # 15 minutes
        
        logger.info("Retrieved listing statistics")
        return stats
        
    except Exception as e:
        logger.error(f"Error getting listing stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.post("/bulk", response_model=Dict[str, Any])
async def bulk_create_listings(
    listings: List[ListingCreate],
    db = Depends(get_database)
):
    """Create multiple listings in bulk."""
    
    try:
        if len(listings) > 1000:
            raise HTTPException(status_code=400, detail="Too many listings for bulk creation (max 1000)")
        
        listing_service = ListingService(db)
        result = listing_service.bulk_create_listings([listing.dict() for listing in listings])
        
        # Invalidate cache
        cache = get_cache()
        cache.delete_pattern("listings:*")
        
        logger.info(f"Bulk created {result['created']} listings, {result['errors']} errors")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk creating listings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.delete("/bulk", response_model=Dict[str, Any])
async def bulk_delete_listings(
    listing_ids: List[str],
    db = Depends(get_database)
):
    """Delete multiple listings in bulk."""
    
    try:
        if len(listing_ids) > 1000:
            raise HTTPException(status_code=400, detail="Too many listings for bulk deletion (max 1000)")
        
        listing_service = ListingService(db)
        result = listing_service.bulk_delete_listings(listing_ids)
        
        # Invalidate cache
        cache = get_cache()
        cache.delete_pattern("listings:*")
        for listing_id in listing_ids:
            cache.delete(f"listing:{listing_id}:*")
        
        logger.info(f"Bulk deleted {result['deleted']} listings, {result['errors']} errors")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk deleting listings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@listings_router.get("/search/suggestions", response_model=List[str])
async def get_search_suggestions(
    query: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=20),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get search suggestions for autocomplete."""
    
    try:
        # Create cache key
        cache_key = f"suggestions:{query}:{limit}"
        
        # Try to get from cache
        cached_suggestions = cache.get(cache_key)
        if cached_suggestions:
            logger.info(f"Retrieved {len(cached_suggestions)} search suggestions from cache")
            return cached_suggestions
        
        # Get from database
        listing_service = ListingService(db)
        suggestions = listing_service.get_search_suggestions(query, limit)
        
        # Cache result
        cache.set(cache_key, suggestions, ttl=1800)  # 30 minutes
        
        logger.info(f"Retrieved {len(suggestions)} search suggestions for '{query}'")
        return suggestions
        
    except Exception as e:
        logger.error(f"Error getting search suggestions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
