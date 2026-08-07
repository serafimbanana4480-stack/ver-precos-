"""
FastAPI Application for AutoDeal IA Hunter
REST API for vehicle valuation, deal finding, and market intelligence
"""
from __future__ import annotations
import logging
from typing import List, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn

from config import settings
from app.api.schemas.vehicle import VehicleRequest, VehicleResponse, VehicleFilter, ProcessVehicleRequest
from app.api.schemas.deal import DealResponse, DealScoreBreakdown
from app.api.schemas.valuation import ValuationRequest, ValuationResponse
from utils.observability import get_metrics
from app.api.websockets import stream_vehicle_updates
from app.api.auth import (
    UserCreate, UserLogin, Token, 
    create_user, authenticate_user, 
    get_current_active_user, get_current_admin_user,
    create_access_token
)
from intelligence.analytics.market_reports import market_reports

# Import production components
from processing.pipeline import production_pipeline
from intelligence.pricing.engine import pricing_engine
from intelligence.scoring.engine import scoring_engine
from database.db import get_db_context
from database.models import Vehicle

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    from utils.observability import setup_structured_logging
    setup_structured_logging()
    logger.info("Starting AutoDeal API...")
    # Check Ollama availability
    if settings.check_ollama_available():
        logger.info("✅ Ollama is available")
    else:
        logger.warning("⚠️ Ollama not available - AI features will use fallback")
    yield
    logger.info("Shutting down AutoDeal API...")


# Create FastAPI app
app = FastAPI(
    title="AutoDeal IA Hunter API",
    description="AI-powered vehicle valuation and deal finding platform for Portugal",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Backward-compatible alias used by legacy tests.
API = FastAPI

# CORS: explicit origins only (never "*" with credentials)
_cors_origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Health check endpoint
@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "connected",
            "ai": "available" if settings.check_ollama_available() else "unavailable",
            "scrapers": "ready"
        }
    }


# Metrics endpoint for Prometheus
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    metrics_data, content_type = get_metrics()
    return Response(content=metrics_data, media_type=content_type)


# WebSocket endpoint for real-time vehicle updates
@app.websocket("/api/v1/ws/vehicles")
async def websocket_vehicle_updates(
    websocket: WebSocket,
    client_id: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    WebSocket endpoint for real-time vehicle updates
    
    Streams new vehicles as they are added to the database
    """
    await stream_vehicle_updates(websocket, client_id, poll_interval=5)


# Valuation endpoint
@app.post("/api/v1/vehicles/valuate", response_model=ValuationResponse)
async def valuate_vehicle(
    request: ValuationRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Valuate a vehicle using hybrid pricing engine
    
    Combines statistical, comparable clustering, ML, and AI reasoning
    """
    try:
        # Convert request to vehicle dict
        vehicle_data = request.dict()
        
        # Calculate hybrid price
        pricing = pricing_engine.calculate_price(vehicle_data)
        
        return ValuationResponse(**pricing)
        
    except Exception as e:
        logger.error(f"Error valuating vehicle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Get vehicles endpoint
@app.get("/api/v1/vehicles", response_model=List[VehicleResponse])
async def get_vehicles(
    current_user: User = Depends(get_current_active_user),
    brand: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    year_min: Optional[int] = Query(None),
    year_max: Optional[int] = Query(None),
    price_min: Optional[float] = Query(None),
    price_max: Optional[float] = Query(None),
    deal_score_min: Optional[float] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get vehicles with optional filtering
    """
    try:
        with get_db_context() as db:
            query = db.query(Vehicle).filter(Vehicle.is_active == True)
            
            # Apply filters
            if brand:
                query = query.filter(Vehicle.brand.ilike(f"%{brand}%"))
            if model:
                query = query.filter(Vehicle.model.ilike(f"%{model}%"))
            if year_min:
                query = query.filter(Vehicle.year >= year_min)
            if year_max:
                query = query.filter(Vehicle.year <= year_max)
            if price_min:
                query = query.filter(Vehicle.price >= price_min)
            if price_max:
                query = query.filter(Vehicle.price <= price_max)
            if deal_score_min:
                query = query.filter(Vehicle.deal_score >= deal_score_min)
            if source:
                query = query.filter(Vehicle.source == source)
            
            # Apply pagination
            vehicles = query.order_by(Vehicle.deal_score.desc()).offset(offset).limit(limit).all()
            
            return [VehicleResponse.from_orm(v) for v in vehicles]
            
    except Exception as e:
        logger.error(f"Error getting vehicles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Get top deals endpoint
@app.get("/api/v1/deals", response_model=List[DealResponse])
async def get_top_deals(
    current_user: User = Depends(get_current_active_user),
    limit: int = Query(20, ge=1, le=100),
    min_score: float = Query(7.0, ge=0, le=10)
):
    """
    Get top deals with high deal scores
    """
    try:
        with get_db_context() as db:
            vehicles = db.query(Vehicle).filter(
                Vehicle.is_active == True,
                Vehicle.profit_is_publishable == True,
                Vehicle.credible_profit.isnot(None),
                Vehicle.credible_profit > 0,
                Vehicle.deal_score >= min_score
            ).order_by(Vehicle.deal_score.desc()).limit(limit).all()
            
            deals = []
            for v in vehicles:
                deal = DealResponse.from_orm(v)
                # Calculate savings
                if v.estimated_value and v.price:
                    # Savings on the reliability-adjusted value when available;
                    # the raw estimate still contains model noise (winner's curse).
                    base = v.adjusted_estimated_value or v.estimated_value
                    deal.price_savings = base - v.price
                    deal.price_savings_percent = ((base - v.price) / base) * 100
                deals.append(deal)
            
            return deals
            
    except Exception as e:
        logger.error(f"Error getting top deals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Get vehicle by ID endpoint
@app.get("/api/v1/vehicles/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(vehicle_id: int):
    """
    Get a specific vehicle by ID
    """
    try:
        with get_db_context() as db:
            vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
            
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
            
            return VehicleResponse.from_orm(vehicle)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vehicle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Process vehicle through pipeline endpoint
@app.post("/api/v1/vehicles/process", response_model=dict)
async def process_vehicle(
    vehicle_data: ProcessVehicleRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Process a vehicle through the full pipeline (validation, AI enrichment, pricing, scoring)
    """
    try:
        result = production_pipeline.process_vehicle(vehicle_data.dict())
        return result
        
    except Exception as e:
        logger.error(f"Error processing vehicle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "AutoDeal IA Hunter API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/v1/health"
    }


# Authentication endpoints
@app.post("/api/v1/auth/register", response_model=Token)
async def register(user: UserCreate):
    """Register a new user"""
    try:
        created_user = create_user(user)
        
        # Create access token
        access_token = create_access_token(
            data={"sub": created_user.email, "user_id": created_user.id, "username": created_user.username}
        )
        
        return Token(access_token=access_token, token_type="bearer", user=created_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/auth/login", response_model=Token)
async def login(user: UserLogin):
    """Login and get access token"""
    try:
        authenticated_user = authenticate_user(user.email, user.password)
        
        if not authenticated_user:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        
        # Create access token
        access_token = create_access_token(
            data={"sub": authenticated_user.email, "user_id": authenticated_user.id, "username": authenticated_user.username}
        )
        
        return Token(access_token=access_token, token_type="bearer", user=authenticated_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/auth/me")
async def get_me(current_user = Depends(get_current_active_user)):
    """Get current user info"""
    return current_user


# Analytics endpoints
@app.get("/api/v1/analytics/market-report")
async def get_market_report(
    current_user: User = Depends(get_current_active_user),
    brand: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365)
):
    """
    Generate market intelligence report
    
    Includes price trends, supply/demand analysis, seasonality, and geographic distribution
    """
    try:
        report = market_reports.generate_market_report(
            brand=brand,
            model=model,
            days=days
        )
        return report
    except Exception as e:
        logger.error(f"Error generating market report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def run_api():
    """Run the FastAPI application"""
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload to avoid multiprocessing issues
        log_level="info"
    )


if __name__ == "__main__":
    run_api()
