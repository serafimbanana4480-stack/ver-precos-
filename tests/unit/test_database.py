"""
Unit tests for database models
"""
import pytest
from datetime import datetime
from database.models import (
    Base, Vehicle, PriceHistory, Watchlist, AIReview, ScrapingLog,
    VehicleType, FuelType, Transmission, Source
)


class TestVehicleModel:
    """Test Vehicle model"""
    
    def test_vehicle_creation(self):
        """Test Vehicle model creation with minimal required fields"""
        vehicle = Vehicle(
            source=Source.OLX,
            source_id="12345",
            url="https://example.com/car/12345",
            vehicle_type=VehicleType.carros,
            brand="Volkswagen",
            model="Golf",
            year=2020,
            price=15000.0,
            title="Volkswagen Golf 2020"
        )
        assert vehicle.source == Source.OLX
        assert vehicle.source_id == "12345"
        assert vehicle.url == "https://example.com/car/12345"
        assert vehicle.vehicle_type == VehicleType.carros
        assert vehicle.brand == "Volkswagen"
        assert vehicle.model == "Golf"
        assert vehicle.year == 2020
        assert vehicle.price == 15000.0
        assert vehicle.title == "Volkswagen Golf 2020"
    
    def test_vehicle_optional_fields(self):
        """Test Vehicle model with optional fields"""
        vehicle = Vehicle(
            source=Source.STANDVIRTUAL,
            source_id="67890",
            url="https://example.com/car/67890",
            vehicle_type=VehicleType.carros,
            brand="Renault",
            model="Clio",
            year=2019,
            price=12000.0,
            title="Renault Clio 2019",
            km=50000,
            horsepower=90,
            engine_size=1500,
            fuel_type=FuelType.DIESEL,
            transmission=Transmission.MANUAL,
            doors=5,
            seats=5,
            color="Blue"
        )
        assert vehicle.km == 50000
        assert vehicle.horsepower == 90
        assert vehicle.engine_size == 1500
        assert vehicle.fuel_type == FuelType.DIESEL
        assert vehicle.transmission == Transmission.MANUAL
        assert vehicle.doors == 5
        assert vehicle.seats == 5
        assert vehicle.color == "Blue"
    
    def test_vehicle_enum_values(self):
        """Test Vehicle model enum values"""
        vehicle = Vehicle(
            source=Source.AUTOSAPO,
            source_id="11111",
            url="https://example.com/car/11111",
            vehicle_type=VehicleType.motos,
            brand="Yamaha",
            model="MT-07",
            year=2021,
            price=8000.0,
            title="Yamaha MT-07 2021",
            fuel_type=FuelType.GASOLINE
        )
        assert vehicle.source == Source.AUTOSAPO
        assert vehicle.vehicle_type == VehicleType.motos
        assert vehicle.fuel_type == FuelType.GASOLINE
    
    def test_vehicle_to_dict(self):
        """Test Vehicle to_dict method"""
        vehicle = Vehicle(
            source=Source.OLX,
            source_id="12345",
            url="https://example.com/car/12345",
            vehicle_type=VehicleType.carros,
            brand="Volkswagen",
            model="Golf",
            year=2020,
            price=15000.0,
            title="Volkswagen Golf 2020"
        )
        vehicle_dict = vehicle.to_dict()
        assert vehicle_dict["source"] == "OLX"  # Source.OLX.value == "OLX"
        assert vehicle_dict["source_id"] == "12345"
        assert vehicle_dict["url"] == "https://example.com/car/12345"
        assert vehicle_dict["vehicle_type"] == "carros"  # VehicleType.carros.value == "carros"
        assert vehicle_dict["brand"] == "Volkswagen"
        assert vehicle_dict["model"] == "Golf"
        assert vehicle_dict["year"] == 2020
        assert vehicle_dict["price"] == 15000.0
    
    def test_vehicle_constraints(self):
        """Test Vehicle model constraints"""
        # SQLAlchemy doesn't enforce nullability in constructor
        # This test is just a placeholder or should be removed if not checking DB constraints
        vehicle = Vehicle(
            source=Source.OLX,
            source_id="12345",
            url="https://example.com/car/12345",
            vehicle_type=VehicleType.carros,
            brand="Volkswagen",
            model="Golf",
            year=2020,
            # price is missing - SQLAlchemy does not enforce nullable in constructor
            title="Volkswagen Golf 2020"
        )
        assert vehicle.price is None


class TestPriceHistory:
    """Test PriceHistory model"""
    
    def test_price_history_creation(self):
        """Test PriceHistory model creation"""
        price_history = PriceHistory(
            vehicle_id=1,
            price=15000.0
        )
        assert price_history.vehicle_id == 1
        assert price_history.price == 15000.0
        # recorded_at is a DB default, not necessarily set on instantiation
    
    def test_price_history_relationship(self):
        """Test PriceHistory relationship with Vehicle"""
        # Note: This test would require a database session
        # For unit test, we just verify the relationship is defined
        assert hasattr(PriceHistory, 'vehicle')


class TestAIReview:
    """Test AIReview model"""
    
    def test_ai_review_creation(self):
        """Test AIReview model creation"""
        ai_review = AIReview(
            vehicle_id=1,
            review_type="description",
            analysis="This vehicle looks good",
            score=8.5,
            approval=True,
            confidence=0.9
        )
        assert ai_review.vehicle_id == 1
        assert ai_review.review_type == "description"
        assert ai_review.analysis == "This vehicle looks good"
        assert ai_review.score == 8.5
        assert ai_review.approval is True
        assert ai_review.confidence == 0.9
    
    def test_ai_review_optional_fields(self):
        """Test AIReview with optional fields"""
        ai_review = AIReview(
            vehicle_id=1,
            review_type="vision",
            analysis="Condition is excellent",
            model_used="gpt-4-vision",
            issues=["scratch on door"],
            positives=["clean interior", "good tires"]
        )
        assert ai_review.model_used == "gpt-4-vision"
        assert ai_review.issues == ["scratch on door"]
        assert ai_review.positives == ["clean interior", "good tires"]


class TestScrapingLog:
    """Test ScrapingLog model"""
    
    def test_scraping_log_creation(self):
        """Test ScrapingLog model creation"""
        scraping_log = ScrapingLog(
            source=Source.OLX,
            status="running",
            listings_found=10,
            listings_added=5
        )
        assert scraping_log.source == Source.OLX
        assert scraping_log.status == "running"
        assert scraping_log.listings_found == 10
        assert scraping_log.listings_added == 5
        # started_at is a DB default
    
    def test_scraping_log_completed(self):
        """Test ScrapingLog with completed status"""
        scraping_log = ScrapingLog(
            source=Source.STANDVIRTUAL,
            status="completed",
            listings_found=20,
            listings_added=15,
            listings_updated=5
        )
        assert scraping_log.status == "completed"
        assert scraping_log.listings_updated == 5


class TestWatchlist:
    """Test Watchlist model"""
    
    def test_watchlist_creation(self):
        """Test Watchlist model creation"""
        watchlist = Watchlist(
            name="Golf under 15k",
            brand="Volkswagen",
            model="Golf",
            max_price=15000.0,
            max_km=100000
        )
        assert watchlist.name == "Golf under 15k"
        assert watchlist.brand == "Volkswagen"
        assert watchlist.model == "Golf"
        assert watchlist.max_price == 15000.0
        assert watchlist.max_km == 100000
        # is_active is a DB default
    
    def test_watchlist_with_criteria(self):
        """Test Watchlist with full criteria"""
        watchlist = Watchlist(
            name="Diesel cars 2018+",
            vehicle_type=VehicleType.carros,
            min_year=2018,
            fuel_type=FuelType.DIESEL,
            min_profit=1000.0
        )
        assert watchlist.vehicle_type == VehicleType.carros
        assert watchlist.min_year == 2018
        assert watchlist.fuel_type == FuelType.DIESEL
        assert watchlist.min_profit == 1000.0
