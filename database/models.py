"""
SQLAlchemy ORM models for AutoDeal IA Hunter
"""
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, 
    Text, ForeignKey, JSON, Enum, Index
)
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


class VehicleType(str, enum.Enum):
    CAR = "car"
    MOTO = "moto"


class FuelType(str, enum.Enum):
    GASOLINE = "gasolina"
    DIESEL = "diesel"
    ELECTRIC = "eletrico"
    HYBRID = "hibrido"
    GPL = "gpl"
    GAS = "gas natural"


class Transmission(str, enum.Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatico"
    SEMI_AUTOMATIC = "semi-automatico"


class Source(str, enum.Enum):
    OLX = "olx"
    STANDVIRTUAL = "standvirtual"
    AUTOSAPO = "autosapo"


class Vehicle(Base):
    """Vehicle listing model"""
    __tablename__ = "vehicles"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Source and identification
    source = Column(Enum(Source), nullable=False, index=True)
    source_id = Column(String(100), nullable=False, index=True)  # ID from the source
    url = Column(Text, nullable=False, unique=True)
    
    # Vehicle details
    vehicle_type = Column(Enum(VehicleType), nullable=False, index=True)
    brand = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)
    version = Column(String(200), nullable=True)
    year = Column(Integer, nullable=False, index=True)
    km = Column(Integer, nullable=True, index=True)
    horsepower = Column(Integer, nullable=True)
    engine_size = Column(Integer, nullable=True)  # in cc
    fuel_type = Column(Enum(FuelType), nullable=True)
    transmission = Column(Enum(Transmission), nullable=True)
    doors = Column(Integer, nullable=True)
    seats = Column(Integer, nullable=True)
    color = Column(String(50), nullable=True)
    
    # Location
    location = Column(String(200), nullable=True, index=True)
    district = Column(String(100), nullable=True, index=True)
    
    # Price and valuation
    price = Column(Float, nullable=False, index=True)
    estimated_value = Column(Float, nullable=True)
    deal_score = Column(Float, nullable=True, index=True)  # 0-10 scale
    profit_potential = Column(Float, nullable=True, index=True)  # in EUR
    profit_percentage = Column(Float, nullable=True)
    
    # Description and media
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    images = Column(JSON, nullable=True)  # List of image URLs
    image_count = Column(Integer, default=0)
    
    # Condition assessment
    condition_score = Column(Float, nullable=True)  # 0-10 from vision analysis
    damages_detected = Column(JSON, nullable=True)  # List of detected issues
    has_accident = Column(Boolean, default=False)
    
    # AI analysis
    ai_review = Column(Text, nullable=True)
    ai_approved = Column(Boolean, default=True, index=True)
    ai_confidence = Column(Float, nullable=True)
    ai_review_date = Column(DateTime, nullable=True)
    
    # Scraping metadata
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Valuation and Analysis
    deal_score = Column(Float, nullable=True, index=True)  # 0-100 score
    valuation_details = Column(JSON, nullable=True)  # Detailed breakdown
    
    scrape_count = Column(Integer, default=1)
    
    # Additional data
    seller_name = Column(String(200), nullable=True)
    seller_type = Column(String(50), nullable=True)  # particular, profissional
    extras = Column(JSON, nullable=True)  # List of extras
    features = Column(JSON, nullable=True)  # Additional features
    
    # Relationships
    price_history = relationship("PriceHistory", back_populates="vehicle", cascade="all, delete-orphan")
    ai_reviews = relationship("AIReview", back_populates="vehicle", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_brand_model_year', 'brand', 'model', 'year'),
        Index('idx_price_km', 'price', 'km'),
        Index('idx_deal_score_active', 'deal_score', 'is_active'),
        Index('idx_source_date', 'source', 'first_seen'),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "source": self.source.value if self.source else None,
            "source_id": self.source_id,
            "url": self.url,
            "vehicle_type": self.vehicle_type.value if self.vehicle_type else None,
            "brand": self.brand,
            "model": self.model,
            "version": self.version,
            "year": self.year,
            "km": self.km,
            "horsepower": self.horsepower,
            "engine_size": self.engine_size,
            "fuel_type": self.fuel_type.value if self.fuel_type else None,
            "transmission": self.transmission.value if self.transmission else None,
            "doors": self.doors,
            "seats": self.seats,
            "color": self.color,
            "location": self.location,
            "district": self.district,
            "price": self.price,
            "estimated_value": self.estimated_value,
            "deal_score": self.deal_score,
            "profit_potential": self.profit_potential,
            "profit_percentage": self.profit_percentage,
            "title": self.title,
            "description": self.description,
            "images": self.images,
            "image_count": self.image_count,
            "condition_score": self.condition_score,
            "damages_detected": self.damages_detected,
            "has_accident": self.has_accident,
            "ai_review": self.ai_review,
            "ai_approved": self.ai_approved,
            "ai_confidence": self.ai_confidence,
            "ai_review_date": self.ai_review_date.isoformat() if self.ai_review_date else None,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_active": self.is_active,
            "scrape_count": self.scrape_count,
            "seller_name": self.seller_name,
            "seller_type": self.seller_type,
            "extras": self.extras,
            "features": self.features,
        }


class PriceHistory(Base):
    """Price change history for vehicles"""
    __tablename__ = "price_history"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    price = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    vehicle = relationship("Vehicle", back_populates="price_history")
    
    __table_args__ = (
        Index('idx_vehicle_price_date', 'vehicle_id', 'recorded_at'),
    )


class Watchlist(Base):
    """User watchlist for specific vehicle criteria"""
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    
    # Criteria
    brand = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    vehicle_type = Column(Enum(VehicleType), nullable=True)
    min_year = Column(Integer, nullable=True)
    max_year = Column(Integer, nullable=True)
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    max_km = Column(Integer, nullable=True)
    min_profit = Column(Float, nullable=True)
    fuel_type = Column(Enum(FuelType), nullable=True)
    
    # Notifications
    notify_on_match = Column(Boolean, default=True)
    last_notified = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_watchlist_active', 'is_active'),
    )


class AIReview(Base):
    """Detailed AI review history"""
    __tablename__ = "ai_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    
    # Review details
    review_type = Column(String(50), nullable=False)  # 'description', 'vision', 'comprehensive'
    model_used = Column(String(100), nullable=True)
    prompt_used = Column(Text, nullable=True)
    
    # Results
    analysis = Column(Text, nullable=False)
    score = Column(Float, nullable=True)  # 0-10
    approval = Column(Boolean, nullable=True)
    confidence = Column(Float, nullable=True)
    
    # Detected issues
    issues = Column(JSON, nullable=True)
    positives = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    processing_time = Column(Float, nullable=True)  # seconds
    
    vehicle = relationship("Vehicle", back_populates="ai_reviews")
    
    __table_args__ = (
        Index('idx_ai_review_vehicle_date', 'vehicle_id', 'created_at'),
    )


class ScrapingLog(Base):
    """Scraping operation logs"""
    __tablename__ = "scraping_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(Enum(Source), nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False)  # 'running', 'completed', 'failed'
    listings_found = Column(Integer, default=0)
    listings_added = Column(Integer, default=0)
    listings_updated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    __table_args__ = (
        Index('idx_scraping_log_date', 'started_at'),
    )
