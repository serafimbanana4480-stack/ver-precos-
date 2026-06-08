"""
Integration tests for database operations
"""
import pytest

pytestmark = pytest.mark.integration
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from database.models import Base, Vehicle, PriceHistory, AIReview, Source, VehicleType


class TestDatabaseConnection:
    """Test database connection and initialization"""
    
    def test_create_tables(self, db):
        """Test that tables can be created"""
        # Tables are created in the db fixture
        assert True
    
    def test_session_creation(self, session):
        """Test that session can be created"""
        assert isinstance(session, Session)
        assert session.is_active is True


class TestVehicleCRUD:
    """Test Vehicle CRUD operations"""
    
    def test_create_vehicle(self, session):
        """Test creating a vehicle in database"""
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
        session.add(vehicle)
        session.commit()
        
        retrieved = session.query(Vehicle).filter_by(source_id="12345").first()
        assert retrieved is not None
        assert retrieved.brand == "Volkswagen"
        assert retrieved.model == "Golf"
    
    def test_read_vehicle(self, session):
        """Test reading a vehicle from database"""
        vehicle = Vehicle(
            source=Source.STANDVIRTUAL,
            source_id="67890",
            url="https://example.com/car/67890",
            vehicle_type=VehicleType.carros,
            brand="Renault",
            model="Clio",
            year=2019,
            price=12000.0,
            title="Renault Clio 2019"
        )
        session.add(vehicle)
        session.commit()
        
        retrieved = session.query(Vehicle).filter_by(source_id="67890").first()
        assert retrieved is not None
        assert retrieved.source == Source.STANDVIRTUAL
        assert retrieved.price == 12000.0
    
    def test_update_vehicle(self, session):
        """Test updating a vehicle in database"""
        vehicle = Vehicle(
            source=Source.AUTOSAPO,
            source_id="11111",
            url="https://example.com/car/11111",
            vehicle_type=VehicleType.carros,
            brand="Peugeot",
            model="308",
            year=2021,
            price=18000.0,
            title="Peugeot 308 2021"
        )
        session.add(vehicle)
        session.commit()
        
        retrieved = session.query(Vehicle).filter_by(source_id="11111").first()
        retrieved.price = 17500.0
        session.commit()
        
        updated = session.query(Vehicle).filter_by(source_id="11111").first()
        assert updated.price == 17500.0
    
    def test_delete_vehicle(self, session):
        """Test deleting a vehicle from database"""
        vehicle = Vehicle(
            source=Source.OLX,
            source_id="22222",
            url="https://example.com/car/22222",
            vehicle_type=VehicleType.carros,
            brand="Toyota",
            model="Corolla",
            year=2020,
            price=20000.0,
            title="Toyota Corolla 2020"
        )
        session.add(vehicle)
        session.commit()
        
        retrieved = session.query(Vehicle).filter_by(source_id="22222").first()
        session.delete(retrieved)
        session.commit()
        
        deleted = session.query(Vehicle).filter_by(source_id="22222").first()
        assert deleted is None


class TestVehicleRelationships:
    """Test Vehicle relationships"""
    
    def test_vehicle_price_history_relationship(self, session):
        """Test Vehicle-PriceHistory relationship"""
        vehicle = Vehicle(
            source=Source.OLX,
            source_id="33333",
            url="https://example.com/car/33333",
            vehicle_type=VehicleType.carros,
            brand="BMW",
            model="320",
            year=2019,
            price=25000.0,
            title="BMW 320 2019"
        )
        session.add(vehicle)
        session.commit()
        
        price_history = PriceHistory(
            vehicle_id=vehicle.id,
            price=26000.0
        )
        session.add(price_history)
        session.commit()
        
        retrieved_vehicle = session.query(Vehicle).filter_by(source_id="33333").first()
        assert len(retrieved_vehicle.price_history) == 1
        assert retrieved_vehicle.price_history[0].price == 26000.0
    
    def test_vehicle_ai_review_relationship(self, session):
        """Test Vehicle-AIReview relationship"""
        vehicle = Vehicle(
            source=Source.STANDVIRTUAL,
            source_id="44444",
            url="https://example.com/car/44444",
            vehicle_type=VehicleType.carros,
            brand="Mercedes",
            model="C-Class",
            year=2020,
            price=35000.0,
            title="Mercedes C-Class 2020"
        )
        session.add(vehicle)
        session.commit()
        
        ai_review = AIReview(
            vehicle_id=vehicle.id,
            review_type="description",
            analysis="Excellent condition",
            score=9.0,
            approval=True
        )
        session.add(ai_review)
        session.commit()
        
        retrieved_vehicle = session.query(Vehicle).filter_by(source_id="44444").first()
        assert len(retrieved_vehicle.ai_reviews) == 1
        assert retrieved_vehicle.ai_reviews[0].review_type == "description"


class TestDatabaseConstraints:
    """Test database constraints"""
    
    def test_unique_url_constraint(self, session):
        """Test that URL is unique"""
        vehicle1 = Vehicle(
            source=Source.OLX,
            source_id="55555",
            url="https://example.com/car/55555",
            vehicle_type=VehicleType.carros,
            brand="Audi",
            model="A4",
            year=2019,
            price=28000.0,
            title="Audi A4 2019"
        )
        session.add(vehicle1)
        session.commit()
        
        vehicle2 = Vehicle(
            source=Source.STANDVIRTUAL,
            source_id="66666",
            url="https://example.com/car/55555",  # Same URL
            vehicle_type=VehicleType.carros,
            brand="Audi",
            model="A4",
            year=2019,
            price=27000.0,
            title="Audi A4 2019"
        )
        session.add(vehicle2)
        
        # This should raise an integrity error due to unique constraint
        with pytest.raises(Exception):  # SQLAlchemy raises IntegrityError
            session.commit()


class TestSessionLifecycle:
    """Test session lifecycle and context manager"""
    
    def test_session_rollback_on_error(self, session):
        """Test that session rolls back on error"""
        vehicle = Vehicle(
            source=Source.OLX,
            source_id="77777",
            url="https://example.com/car/77777",
            vehicle_type=VehicleType.carros,
            brand="Honda",
            model="Civic",
            year=2020,
            price=18000.0,
            title="Honda Civic 2020"
        )
        session.add(vehicle)
        session.rollback()
        
        # Vehicle should not be in database after rollback
        retrieved = session.query(Vehicle).filter_by(source_id="77777").first()
        assert retrieved is None
