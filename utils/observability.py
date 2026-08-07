"""
Observability Module
Prometheus metrics and structured logging for production monitoring
"""
from __future__ import annotations
import logging
import time
from functools import wraps
from typing import Callable, Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Create custom registry for this application
registry = CollectorRegistry()

# Prometheus Metrics
# Scraping metrics
scrape_requests_total = Counter(
    'scrape_requests_total',
    'Total number of scrape requests',
    ['source', 'status'],
    registry=registry
)

scrape_duration_seconds = Histogram(
    'scrape_duration_seconds',
    'Scrape request duration in seconds',
    ['source'],
    registry=registry
)

# AI metrics
ai_enrichment_requests = Counter(
    'ai_enrichment_requests_total',
    'Total AI enrichment requests',
    ['type', 'status'],
    registry=registry
)

ai_enrichment_duration = Histogram(
    'ai_enrichment_duration_seconds',
    'AI enrichment duration in seconds',
    ['type'],
    registry=registry
)

# Pipeline metrics
pipeline_requests_total = Counter(
    'pipeline_requests_total',
    'Total pipeline processing requests',
    ['status'],
    registry=registry
)

pipeline_duration_seconds = Histogram(
    'pipeline_duration_seconds',
    'Pipeline processing duration in seconds',
    registry=registry
)

# Vehicle metrics
active_vehicles_total = Gauge(
    'active_vehicles_total',
    'Total number of active vehicles in database',
    registry=registry
)

deal_score_distribution = Histogram(
    'deal_score_distribution',
    'Distribution of deal scores',
    buckets=[0, 2, 4, 5, 6, 7, 8, 9, 10],
    registry=registry
)

# Pricing metrics
pricing_requests_total = Counter(
    'pricing_requests_total',
    'Total pricing calculation requests',
    ['method'],  # statistical, comparable, ml, hybrid
    registry=registry
)

pricing_duration_seconds = Histogram(
    'pricing_duration_seconds',
    'Pricing calculation duration in seconds',
    ['method'],
    registry=registry
)

# Database metrics
database_queries_total = Counter(
    'database_queries_total',
    'Total database queries',
    ['operation', 'status'],
    registry=registry
)

database_query_duration = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],
    registry=registry
)

# Error metrics
errors_total = Counter(
    'errors_total',
    'Total errors',
    ['module', 'error_type'],
    registry=registry
)


def track_scrape(source: str):
    """Decorator to track scrape requests"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = 'error'
                errors_total.labels(module='scraping', error_type=type(e).__name__).inc()
                raise
            finally:
                duration = time.time() - start_time
                scrape_requests_total.labels(source=source, status=status).inc()
                scrape_duration_seconds.labels(source=source).observe(duration)
        return wrapper
    return decorator


def track_ai_enrichment(ai_type: str):
    """Decorator to track AI enrichment requests (supports sync and async functions)"""
    import asyncio as _asyncio
    import inspect as _inspect
    def decorator(func: Callable):
        if _inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                status = 'success'
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = 'error'
                    errors_total.labels(module='ai', error_type=type(e).__name__).inc()
                    raise
                finally:
                    duration = time.time() - start_time
                    ai_enrichment_requests.labels(type=ai_type, status=status).inc()
                    ai_enrichment_duration.labels(type=ai_type).observe(duration)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                status = 'success'
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = 'error'
                    errors_total.labels(module='ai', error_type=type(e).__name__).inc()
                    raise
                finally:
                    duration = time.time() - start_time
                    ai_enrichment_requests.labels(type=ai_type, status=status).inc()
                    ai_enrichment_duration.labels(type=ai_type).observe(duration)
            return sync_wrapper
    return decorator


def track_pipeline():
    """Decorator to track pipeline processing"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = 'error'
                errors_total.labels(module='pipeline', error_type=type(e).__name__).inc()
                raise
            finally:
                duration = time.time() - start_time
                pipeline_requests_total.labels(status=status).inc()
                pipeline_duration_seconds.observe(duration)
        return wrapper
    return decorator


def track_database(operation: str):
    """Decorator to track database operations"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = 'error'
                errors_total.labels(module='database', error_type=type(e).__name__).inc()
                raise
            finally:
                duration = time.time() - start_time
                database_queries_total.labels(operation=operation, status=status).inc()
                database_query_duration.labels(operation=operation).observe(duration)
        return wrapper
    return decorator


def track_pricing(method: str):
    """Decorator to track pricing calculations"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                errors_total.labels(module='pricing', error_type=type(e).__name__).inc()
                raise
            finally:
                duration = time.time() - start_time
                pricing_requests_total.labels(method=method).inc()
                pricing_duration_seconds.labels(method=method).observe(duration)
        return wrapper
    return decorator


def update_active_vehicles(count: int):
    """Update the active vehicles gauge"""
    active_vehicles_total.set(count)


def record_deal_score(score: float):
    """Record a deal score"""
    deal_score_distribution.observe(score)


def get_metrics() -> tuple[str, str]:
    """Get Prometheus metrics in the latest format"""
    metrics = generate_latest(registry)
    return metrics, CONTENT_TYPE_LATEST


def setup_structured_logging():
    """Setup structured logging with JSON format"""
    try:
        import structlog
        from structlog.stdlib import LoggerFactory
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        # Override standard logging
        logging.basicConfig(
            format="%(message)s",
            level=logging.INFO,
        )
        
        logger.info("Structured logging configured successfully")
        
    except ImportError:
        logger.warning("structlog not installed, using standard logging")


def setup_sentry():
    """Setup Sentry error tracking"""
    try:
        from core.settings import settings
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        if settings.sentry_dsn:
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                integrations=[
                    LoggingIntegration(
                        level=logging.INFO,  # Capture info and above as breadcrumbs
                        event_level=logging.ERROR  # Send errors as events
                    ),
                ],
                traces_sample_rate=settings.sentry_sample_rate,
                environment=settings.sentry_environment,
                # Filter sensitive data
                before_send_transaction=lambda event, hint: event,
                before_send=lambda event, hint: {
                    **event,
                    # Remove sensitive data from request
                    'request': {
                        **event.get('request', {}),
                        'headers': {k: v for k, v in event.get('request', {}).get('headers', {}).items() 
                                   if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
                    } if event.get('request') else {}
                } if event else None
            )
            logger.info("Sentry configured successfully")
        else:
            logger.info("Sentry DSN not configured, skipping Sentry setup")
            
    except ImportError:
        logger.warning("sentry-sdk not installed, skipping Sentry setup")


class Observability:
    """Legacy compatibility wrapper for observability helpers."""

    def get_metrics(self) -> tuple[str, str]:
        return get_metrics()

    def update_active_vehicles(self, count: int):
        return update_active_vehicles(count)

    def record_deal_score(self, score: float):
        return record_deal_score(score)
