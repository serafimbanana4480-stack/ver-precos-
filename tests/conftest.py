"""
Shared test fixtures and configuration
"""
import pytest
from typing import Generator
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Temporary directory fixture"""
    return tmp_path


@pytest.fixture
def db():
    """Database engine fixture (in-memory SQLite for tests)"""
    from database.models import Base
    from sqlalchemy import create_engine
    
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    return test_engine

@pytest.fixture
def session(db):
    """Database session fixture"""
    from sqlalchemy.orm import sessionmaker
    
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db)
    session = TestSessionLocal()
    
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_grok():
    """Mock Grok API fixture"""
    from unittest.mock import MagicMock
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_ollama():
    """Mock Ollama API fixture"""
    from unittest.mock import MagicMock
    mock = MagicMock()
    return mock


@pytest.fixture
def sample_vehicle_data():
    """Sample vehicle data fixture"""
    return {
        "source": "standvirtual",
        "source_id": "test123",
        "url": "https://example.com/test",
        "vehicle_type": "car",
        "brand": "Volkswagen",
        "model": "Golf",
        "year": 2020,
        "km": 50000,
        "price": 15000.0,
        "title": "Volkswagen Golf 2020",
        "location": "Lisbon"
    }


@pytest.fixture(autouse=True)
def setup_logging():
    """Setup logging for tests"""
    from utils.logging_config import setup_logging
    setup_logging()
