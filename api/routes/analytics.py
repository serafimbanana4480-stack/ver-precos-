"""
Analytics API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from ..dependencies import get_database, get_cache
from ..services import AnalyticsService

logger = logging.getLogger(__name__)

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])

@analytics_router.get("/overview", response_model=Dict[str, Any])
async def get_analytics_overview(
    days: int = Query(30, ge=1, le=365),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get analytics overview for the specified period."""
    
    try:
        # Create cache key
        cache_key = f"overview:{days}"
        
        # Try to get from cache
        cached_overview = cache.get(cache_key)
        if cached_overview:
            logger.info("Retrieved analytics overview from cache")
            return cached_overview
        
        # Get overview
        analytics_service = AnalyticsService(db)
        overview = analytics_service.get_overview(days)
        
        # Cache result
        cache.set(cache_key, overview, ttl=1800)  # 30 minutes
        
        logger.info(f"Retrieved analytics overview for last {days} days")
        return overview
        
    except Exception as e:
        logger.error(f"Error getting analytics overview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/market-trends", response_model=Dict[str, Any])
async def get_market_trends(
    days: int = Query(90, ge=7, le=365),
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get market trends analysis."""
    
    try:
        # Create cache key
        cache_key = f"trends:{days}:{make}:{model}"
        
        # Try to get from cache
        cached_trends = cache.get(cache_key)
        if cached_trends:
            logger.info("Retrieved market trends from cache")
            return cached_trends
        
        # Get trends
        analytics_service = AnalyticsService(db)
        trends = analytics_service.get_market_trends(days, make, model)
        
        # Cache result
        cache.set(cache_key, trends, ttl=3600)  # 1 hour
        
        logger.info(f"Retrieved market trends for last {days} days")
        return trends
        
    except Exception as e:
        logger.error(f"Error getting market trends: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/price-analysis", response_model=Dict[str, Any])
async def get_price_analysis(
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    location: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get detailed price analysis."""
    
    try:
        # Create cache key
        cache_key = f"price_analysis:{make}:{model}:{year}:{location}"
        
        # Try to get from cache
        cached_analysis = cache.get(cache_key)
        if cached_analysis:
            logger.info("Retrieved price analysis from cache")
            return cached_analysis
        
        # Get analysis
        analytics_service = AnalyticsService(db)
        analysis = analytics_service.get_price_analysis(make, model, year, location)
        
        # Cache result
        cache.set(cache_key, analysis, ttl=1800)  # 30 minutes
        
        logger.info("Retrieved price analysis")
        return analysis
        
    except Exception as e:
        logger.error(f"Error getting price analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/make-model-stats", response_model=Dict[str, Any])
async def get_make_model_stats(
    limit: int = Query(20, ge=1, le=100),
    min_listings: int = Query(5, ge=1),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get make and model statistics."""
    
    try:
        # Create cache key
        cache_key = f"make_model_stats:{limit}:{min_listings}"
        
        # Try to get from cache
        cached_stats = cache.get(cache_key)
        if cached_stats:
            logger.info("Retrieved make/model stats from cache")
            return cached_stats
        
        # Get stats
        analytics_service = AnalyticsService(db)
        stats = analytics_service.get_make_model_stats(limit, min_listings)
        
        # Cache result
        cache.set(cache_key, stats, ttl=3600)  # 1 hour
        
        logger.info(f"Retrieved make/model stats for top {limit} makes")
        return stats
        
    except Exception as e:
        logger.error(f"Error getting make/model stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/location-analysis", response_model=Dict[str, Any])
async def get_location_analysis(
    limit: int = Query(50, ge=1, le=200),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get location-based analysis."""
    
    try:
        # Create cache key
        cache_key = f"location_analysis:{limit}"
        
        # Try to get from cache
        cached_analysis = cache.get(cache_key)
        if cached_analysis:
            logger.info("Retrieved location analysis from cache")
            return cached_analysis
        
        # Get analysis
        analytics_service = AnalyticsService(db)
        analysis = analytics_service.get_location_analysis(limit)
        
        # Cache result
        cache.set(cache_key, analysis, ttl=3600)  # 1 hour
        
        logger.info(f"Retrieved location analysis for top {limit} locations")
        return analysis
        
    except Exception as e:
        logger.error(f"Error getting location analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/depreciation-analysis", response_model=Dict[str, Any])
async def get_depreciation_analysis(
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get depreciation analysis by year."""
    
    try:
        # Create cache key
        cache_key = f"depreciation:{make}:{model}"
        
        # Try to get from cache
        cached_analysis = cache.get(cache_key)
        if cached_analysis:
            logger.info("Retrieved depreciation analysis from cache")
            return cached_analysis
        
        # Get analysis
        analytics_service = AnalyticsService(db)
        analysis = analytics_service.get_depreciation_analysis(make, model)
        
        # Cache result
        cache.set(cache_key, analysis, ttl=3600)  # 1 hour
        
        logger.info("Retrieved depreciation analysis")
        return analysis
        
    except Exception as e:
        logger.error(f"Error getting depreciation analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/market-share", response_model=Dict[str, Any])
async def get_market_share(
    days: int = Query(30, ge=1, le=365),
    group_by: str = Query("make", pattern="^(make|model|location|fuel_type)$"),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get market share analysis."""
    
    try:
        # Create cache key
        cache_key = f"market_share:{days}:{group_by}"
        
        # Try to get from cache
        cached_share = cache.get(cache_key)
        if cached_share:
            logger.info("Retrieved market share from cache")
            return cached_share
        
        # Get market share
        analytics_service = AnalyticsService(db)
        share = analytics_service.get_market_share(days, group_by)
        
        # Cache result
        cache.set(cache_key, share, ttl=1800)  # 30 minutes
        
        logger.info(f"Retrieved market share by {group_by}")
        return share
        
    except Exception as e:
        logger.error(f"Error getting market share: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/price-distribution", response_model=Dict[str, Any])
async def get_price_distribution(
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    location: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get price distribution analysis."""
    
    try:
        # Create cache key
        cache_key = f"price_dist:{make}:{model}:{year}:{location}"
        
        # Try to get from cache
        cached_distribution = cache.get(cache_key)
        if cached_distribution:
            logger.info("Retrieved price distribution from cache")
            return cached_distribution
        
        # Get distribution
        analytics_service = AnalyticsService(db)
        distribution = analytics_service.get_price_distribution(make, model, year, location)
        
        # Cache result
        cache.set(cache_key, distribution, ttl=1800)  # 30 minutes
        
        logger.info("Retrieved price distribution")
        return distribution
        
    except Exception as e:
        logger.error(f"Error getting price distribution: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/seasonal-analysis", response_model=Dict[str, Any])
async def get_seasonal_analysis(
    months: int = Query(12, ge=3, le=24),
    make: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get seasonal analysis."""
    
    try:
        # Create cache key
        cache_key = f"seasonal:{months}:{make}"
        
        # Try to get from cache
        cached_analysis = cache.get(cache_key)
        if cached_analysis:
            logger.info("Retrieved seasonal analysis from cache")
            return cached_analysis
        
        # Get analysis
        analytics_service = AnalyticsService(db)
        analysis = analytics_service.get_seasonal_analysis(months, make)
        
        # Cache result
        cache.set(cache_key, analysis, ttl=7200)  # 2 hours
        
        logger.info(f"Retrieved seasonal analysis for last {months} months")
        return analysis
        
    except Exception as e:
        logger.error(f"Error getting seasonal analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/inventory-turnover", response_model=Dict[str, Any])
async def get_inventory_turnover(
    days: int = Query(30, ge=7, le=90),
    make: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get inventory turnover analysis."""
    
    try:
        # Create cache key
        cache_key = f"turnover:{days}:{make}"
        
        # Try to get from cache
        cached_turnover = cache.get(cache_key)
        if cached_turnover:
            logger.info("Retrieved inventory turnover from cache")
            return cached_turnover
        
        # Get turnover
        analytics_service = AnalyticsService(db)
        turnover = analytics_service.get_inventory_turnover(days, make)
        
        # Cache result
        cache.set(cache_key, turnover, ttl=1800)  # 30 minutes
        
        logger.info(f"Retrieved inventory turnover for last {days} days")
        return turnover
        
    except Exception as e:
        logger.error(f"Error getting inventory turnover: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/performance-metrics", response_model=Dict[str, Any])
async def get_performance_metrics(
    days: int = Query(30, ge=1, le=365),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get performance metrics."""
    
    try:
        # Create cache key
        cache_key = f"performance:{days}"
        
        # Try to get from cache
        cached_metrics = cache.get(cache_key)
        if cached_metrics:
            logger.info("Retrieved performance metrics from cache")
            return cached_metrics
        
        # Get metrics
        analytics_service = AnalyticsService(db)
        metrics = analytics_service.get_performance_metrics(days)
        
        # Cache result
        cache.set(cache_key, metrics, ttl=900)  # 15 minutes
        
        logger.info(f"Retrieved performance metrics for last {days} days")
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/user-behavior", response_model=Dict[str, Any])
async def get_user_behavior_analytics(
    days: int = Query(30, ge=1, le=365),
    user_id: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get user behavior analytics."""
    
    try:
        # Create cache key
        cache_key = f"user_behavior:{days}:{user_id}"
        
        # Try to get from cache
        cached_behavior = cache.get(cache_key)
        if cached_behavior:
            logger.info("Retrieved user behavior analytics from cache")
            return cached_behavior
        
        # Get behavior analytics
        analytics_service = AnalyticsService(db)
        behavior = analytics_service.get_user_behavior_analytics(days, user_id)
        
        # Cache result
        cache.set(cache_key, behavior, ttl=1800)  # 30 minutes
        
        logger.info(f"Retrieved user behavior analytics for last {days} days")
        return behavior
        
    except Exception as e:
        logger.error(f"Error getting user behavior analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/reports/dashboard", response_model=Dict[str, Any])
async def get_dashboard_report(
    days: int = Query(30, ge=1, le=365),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get comprehensive dashboard report."""
    
    try:
        # Create cache key
        cache_key = f"dashboard:{days}"
        
        # Try to get from cache
        cached_dashboard = cache.get(cache_key)
        if cached_dashboard:
            logger.info("Retrieved dashboard report from cache")
            return cached_dashboard
        
        # Get dashboard report
        analytics_service = AnalyticsService(db)
        dashboard = analytics_service.get_dashboard_report(days)
        
        # Cache result
        cache.set(cache_key, dashboard, ttl=900)  # 15 minutes
        
        logger.info(f"Retrieved dashboard report for last {days} days")
        return dashboard
        
    except Exception as e:
        logger.error(f"Error getting dashboard report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.post("/reports/custom", response_model=Dict[str, Any])
async def generate_custom_report(
    report_config: Dict[str, Any],
    db = Depends(get_database)
):
    """Generate custom analytics report."""
    
    try:
        analytics_service = AnalyticsService(db)
        report = analytics_service.generate_custom_report(report_config)
        
        logger.info(f"Generated custom report: {report.get('name', 'unnamed')}")
        return report
        
    except Exception as e:
        logger.error(f"Error generating custom report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_analytics_alerts(
    severity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    limit: int = Query(50, ge=1, le=200),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get analytics alerts."""
    
    try:
        # Create cache key
        cache_key = f"alerts:{severity}:{limit}"
        
        # Try to get from cache
        cached_alerts = cache.get(cache_key)
        if cached_alerts:
            logger.info("Retrieved analytics alerts from cache")
            return cached_alerts
        
        # Get alerts
        analytics_service = AnalyticsService(db)
        alerts = analytics_service.get_analytics_alerts(severity, limit)
        
        # Cache result
        cache.set(cache_key, alerts, ttl=300)  # 5 minutes
        
        logger.info(f"Retrieved {len(alerts)} analytics alerts")
        return alerts
        
    except Exception as e:
        logger.error(f"Error getting analytics alerts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.post("/export", response_model=Dict[str, Any])
async def export_analytics_data(
    report_type: str = Query(..., pattern="^(overview|trends|price_analysis|market_share)$"),
    format: str = Query("csv", pattern="^(csv|json|excel)$"),
    filters: Optional[Dict[str, Any]] = None,
    db = Depends(get_database)
):
    """Export analytics data."""
    
    try:
        analytics_service = AnalyticsService(db)
        export_result = analytics_service.export_analytics_data(report_type, format, filters)
        
        logger.info(f"Exported {report_type} analytics data to {format}")
        return export_result
        
    except Exception as e:
        logger.error(f"Error exporting analytics data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/insights", response_model=List[Dict[str, Any]])
async def get_market_insights(
    category: str = Query("general", pattern="^(general|pricing|inventory|trends)$"),
    limit: int = Query(10, ge=1, le=20),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get AI-powered market insights."""
    
    try:
        # Create cache key
        cache_key = f"insights:{category}:{limit}"
        
        # Try to get from cache
        cached_insights = cache.get(cache_key)
        if cached_insights:
            logger.info("Retrieved market insights from cache")
            return cached_insights
        
        # Get insights
        analytics_service = AnalyticsService(db)
        insights = analytics_service.get_market_insights(category, limit)
        
        # Cache result
        cache.set(cache_key, insights, ttl=3600)  # 1 hour
        
        logger.info(f"Retrieved {len(insights)} market insights")
        return insights
        
    except Exception as e:
        logger.error(f"Error getting market insights: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@analytics_router.get("/forecast", response_model=Dict[str, Any])
async def get_market_forecast(
    forecast_type: str = Query("price", pattern="^(price|demand|inventory)$"),
    days: int = Query(30, ge=7, le=180),
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    db = Depends(get_database),
    cache = Depends(get_cache)
):
    """Get market forecast predictions."""
    
    try:
        # Create cache key
        cache_key = f"forecast:{forecast_type}:{days}:{make}:{model}"
        
        # Try to get from cache
        cached_forecast = cache.get(cache_key)
        if cached_forecast:
            logger.info("Retrieved market forecast from cache")
            return cached_forecast
        
        # Get forecast
        analytics_service = AnalyticsService(db)
        forecast = analytics_service.get_market_forecast(forecast_type, days, make, model)
        
        # Cache result
        cache.set(cache_key, forecast, ttl=7200)  # 2 hours
        
        logger.info(f"Retrieved {forecast_type} forecast for next {days} days")
        return forecast
        
    except Exception as e:
        logger.error(f"Error getting market forecast: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
