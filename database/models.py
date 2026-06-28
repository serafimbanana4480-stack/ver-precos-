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
    carros = "carros"
    motos = "motos"


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
    OLX = "OLX"
    STANDVIRTUAL = "STANDVIRTUAL"
    AUTOSAPO = "AUTOSAPO"
    CUSTOJUSTO = "CUSTOJUSTO"
    AUTOPT = "AUTOPT"
    PISCAPISCA = "PISCAPISCA"
    CARPLUS = "CARPLUS"
    AUTOSCOUT24 = "AUTOSCOUT24"
    EBAY_MOTORS = "EBAY_MOTORS"
    VPAUTO = "VPAUTO"
    LEILOSOC = "LEILOSOC"
    MANHEIM = "MANHEIM"
    AUTOROLA = "AUTOROLA"
    BCA = "BCA"
    FACEBOOK = "FACEBOOK"


class Vehicle(Base):
    """Vehicle listing model"""
    __tablename__ = "vehicles"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Source and identification
    source = Column(Enum(Source), nullable=False, index=True)
    source_id = Column(String(100), nullable=False, index=True)  # ID from the source
    url = Column(Text, nullable=False, unique=True)
    
    # Unique constraint moved to consolidated __table_args__ below
    
    # Vehicle details
    vehicle_type = Column(Enum(VehicleType), nullable=False, index=True)
    brand = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)
    version = Column(String(200), nullable=True)
    year = Column(Integer, nullable=True, index=True)
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
    profit_potential = Column(Float, nullable=True, index=True)  # in EUR (buyer_profit)
    profit_percentage = Column(Float, nullable=True)
    
    # Detailed profit analysis
    price_discount_percentage = Column(Float, nullable=True)  # % below market
    estimated_savings = Column(Float, nullable=True)  # EUR savings
    buyer_profit = Column(Float, nullable=True)  # EUR buyer profit
    buyer_profit_margin = Column(Float, nullable=True)  # % buyer profit margin
    buyer_roi = Column(Float, nullable=True)  # % buyer ROI
    repair_costs = Column(Float, nullable=True)  # EUR estimated repair costs
    taxes = Column(Float, nullable=True)  # EUR transfer taxes
    total_additional_costs = Column(Float, nullable=True)  # EUR total additional costs
    deal_grade = Column(String(20), nullable=True)  # exceptional, excellent, good, fair, poor
    profit_recommendation = Column(String(200), nullable=True)  # text recommendation
    
    # Description and media
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    images = Column(JSON, nullable=True)  # List of image URLs
    image_count = Column(Integer, default=0)
    
    # Condition assessment
    condition_score = Column(Float, nullable=True)  # 0-10 from vision analysis
    damages_detected = Column(JSON, nullable=True)  # List of detected issues
    has_accident = Column(Boolean, default=False)

    # Motorcycle-specific fields
    engine_type = Column(String(50), nullable=True)  # single, twin, triple, four-cylinder
    riding_style = Column(String(50), nullable=True)  # sport, touring, adventure, cruiser, naked
    has_abs = Column(Boolean, nullable=True)
    has_traction_control = Column(Boolean, nullable=True)
    aftermarket_mods = Column(JSON, nullable=True)  # List of aftermarket modifications
    seat_height = Column(Integer, nullable=True)  # in mm
    wet_weight = Column(Integer, nullable=True)  # in kg
    license_category = Column(String(10), nullable=True)  # A1, A2, A
    
    # AI analysis
    ai_review = Column(Text, nullable=True)
    ai_approved = Column(Boolean, default=True, index=True)
    ai_confidence = Column(Float, nullable=True)
    ai_review_date = Column(DateTime, nullable=True)
    
    # New AI fields for production architecture
    ai_risk_score = Column(Float, nullable=True)  # 0-10 from LLM analysis
    lifecycle_status = Column(String(50), default="Descoberto", nullable=True)  # Descoberto, Contactado, Proposta Feita, Negociado, Comprado, Perdido
    ai_recommendation = Column(String(20), nullable=True)  # APPROVED/REJECTED/CAUTION
    vision_confidence = Column(Float, nullable=True)  # 0-1 from Vision analysis
    llm_confidence = Column(Float, nullable=True)  # 0-1 from LLM analysis
    
    # Scoring components (multi-dimensional)
    market_deviation_score = Column(Float, nullable=True)  # 0-10
    ai_risk_score_component = Column(Float, nullable=True)  # 0-10 (inverted)
    vision_damage_score = Column(Float, nullable=True)  # 0-10
    price_anomaly_score = Column(Float, nullable=True)  # 0-10
    demand_signal_score = Column(Float, nullable=True)  # 0-10
    
    # Score interpretation
    score_interpretation = Column(String(50), nullable=True)  # e.g., "Exceptional Deal"
    recommended_action = Column(String(50), nullable=True)  # e.g., "Immediate Alert"
    
    # Scraping metadata
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Valuation and Analysis
    valuation_details = Column(JSON, nullable=True)  # Detailed breakdown
    
    scrape_count = Column(Integer, default=1)
    
    # Additional data
    seller_name = Column(String(200), nullable=True)
    seller_type = Column(String(50), nullable=True)  # particular, profissional
    trim_level = Column(String(200), nullable=True)
    has_damage = Column(Boolean, nullable=True, default=False)
    maintenance_history = Column(Boolean, nullable=True, default=False)
    aesthetic_score = Column(Integer, nullable=True)
    extras = Column(JSON, nullable=True)  # List of extras
    features = Column(JSON, nullable=True)  # Additional features
    
    # Market Value Real Factors
    is_national = Column(Boolean, nullable=True)
    num_owners = Column(Integer, nullable=True)
    warranty_months = Column(Integer, nullable=True)
    condition_status = Column(String(50), nullable=True)
    
    # Relationships
    price_history = relationship("PriceHistory", back_populates="vehicle", cascade="all, delete-orphan")
    ai_reviews = relationship("AIReview", back_populates="vehicle", cascade="all, delete-orphan")
    
    # Indexes for common queries + unique constraint
    __table_args__ = (
        Index('idx_source_source_id', 'source', 'source_id', unique=True),
        Index('idx_brand_model_year', 'brand', 'model', 'year'),
        Index('idx_price_km', 'price', 'km'),
        Index('idx_deal_score_active', 'deal_score', 'is_active'),
        Index('idx_source_date', 'source', 'first_seen'),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        def get_val(v):
            if v is None: return None
            return v.value if hasattr(v, 'value') else str(v)
            
        return {
            "id": self.id,
            "source": get_val(self.source),
            "source_id": self.source_id,
            "url": self.url,
            "vehicle_type": get_val(self.vehicle_type),
            "brand": self.brand,
            "model": self.model,
            "version": self.version,
            "year": self.year,
            "km": self.km,
            "horsepower": self.horsepower,
            "engine_size": self.engine_size,
            "fuel_type": get_val(self.fuel_type),
            "transmission": get_val(self.transmission),
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
            "trim_level": self.trim_level,
            "has_damage": self.has_damage,
            "maintenance_history": self.maintenance_history,
            "aesthetic_score": self.aesthetic_score,
            "extras": self.extras,
            "features": self.features,
            "is_national": self.is_national,
            "num_owners": self.num_owners,
            "warranty_months": self.warranty_months,
            "condition_status": self.condition_status,
            "lifecycle_status": self.lifecycle_status,
            "deal_grade": self.deal_grade,
            "price_discount_percentage": self.price_discount_percentage,
            "buyer_profit": self.buyer_profit,
            "buyer_profit_margin": self.buyer_profit_margin,
            "buyer_roi": self.buyer_roi,
            "repair_costs": self.repair_costs,
            "taxes": self.taxes,
            "total_additional_costs": self.total_additional_costs,
            "score_interpretation": self.score_interpretation,
            "recommended_action": self.recommended_action,
            "valuation_details": self.valuation_details,
            "ai_risk_score": self.ai_risk_score,
            "ai_recommendation": self.ai_recommendation,
            "ai_confidence": self.ai_confidence,
            "vision_confidence": self.vision_confidence,
            "llm_confidence": self.llm_confidence,
            "engine_type": self.engine_type,
            "riding_style": self.riding_style,
            "has_abs": self.has_abs,
            "has_traction_control": self.has_traction_control,
            "aftermarket_mods": self.aftermarket_mods,
            "seat_height": self.seat_height,
            "wet_weight": self.wet_weight,
            "license_category": self.license_category,
            "engine_size": self.engine_size,
            "horsepower": self.horsepower,
            "doors": self.doors,
            "seats": self.seats,
            "color": self.color,
            "market_deviation_score": self.market_deviation_score,
            "ai_risk_score_component": self.ai_risk_score_component,
            "vision_damage_score": self.vision_damage_score,
            "price_anomaly_score": self.price_anomaly_score,
            "demand_signal_score": self.demand_signal_score,
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


class AuctionTransaction(Base):
    """Real transaction prices from auctions - used as ground truth for ML training"""
    __tablename__ = "auction_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source identification
    source = Column(Enum(Source), nullable=False, index=True)  # VPauto, Leilosoc, etc.
    source_id = Column(String(100), nullable=False, unique=True)
    url = Column(Text, nullable=False)
    
    # Vehicle details (canonical for matching)
    vehicle_type = Column(Enum(VehicleType), nullable=False, index=True)
    brand = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)
    version = Column(String(200), nullable=True)
    year = Column(Integer, nullable=False, index=True)
    km = Column(Integer, nullable=True, index=True)
    horsepower = Column(Integer, nullable=True)
    engine_size = Column(Integer, nullable=True)
    fuel_type = Column(Enum(FuelType), nullable=True)
    transmission = Column(Enum(Transmission), nullable=True)
    color = Column(String(50), nullable=True)
    
    # Location
    location = Column(String(200), nullable=True)
    district = Column(String(100), nullable=True)
    
    # Auction-specific details
    auction_type = Column(String(50), nullable=True)  # 'judicial', 'dealer', 'renting', 'fleets'
    auction_date = Column(DateTime, nullable=True, index=True)
    lot_number = Column(String(50), nullable=True)
    
    # REAL TRANSACTION PRICES (the ground truth)
    adjudication_price = Column(Float, nullable=False, index=True)  # Preço de adjudicação real
    reserve_price = Column(Float, nullable=True)  # Preço de reserva (mínimo)
    starting_price = Column(Float, nullable=True)  # Preço inicial
    retail_price = Column(Float, nullable=True)  # Preço retail estimado (Standvirtual etc)
    
    # Condition assessment from auction
    condition_grade = Column(String(10), nullable=True)  # A, B, C, D, E
    has_damage = Column(Boolean, default=False)
    damage_notes = Column(Text, nullable=True)
    inspection_report_url = Column(Text, nullable=True)
    
    # Title and description
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    images = Column(JSON, nullable=True)
    
    # Seller info
    seller_type = Column(String(50), nullable=True)  # 'judicial', 'dealer', 'renting_company', 'fleet'
    seller_name = Column(String(200), nullable=True)
    
    # Metadata
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Relationship to vehicle if matched
    matched_vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True, index=True)
    
    __table_args__ = (
        Index('idx_auction_source_id', 'source', 'source_id', unique=True),
        Index('idx_auction_brand_model', 'brand', 'model'),
        Index('idx_auction_year_km', 'year', 'km'),
        Index('idx_auction_price_date', 'adjudication_price', 'auction_date'),
    )
