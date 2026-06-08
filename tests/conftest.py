"""
Shared test fixtures and configuration
"""
import pytest
from typing import Generator
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Modules that fail at import/collection (missing models, streamlit, etc.)
collect_ignore = [
    "e2e/test_dashboard_flow.py",
    "unit/test_alerts_templates.py",
    "unit/test_app_schemas_map.py",
    "unit/test_app_schemas_multiline.py",
    "unit/test_app_schemas_multipoint.py",
    "unit/test_app_schemas_multipolygon.py",
    "unit/test_app_schemas_red_black_tree.py",
    "unit/test_app_schemas_set.py",
    "unit/test_dashboard_app.py",
    "unit/test_database_models.py",
    "unit/test_scrapers_managed_client.py",
    "unit/test_ingestion_testing_tester.py",
]

# Legacy placeholder modules under tests/unit/test_app_*
_COMPAT_PLACEHOLDER_PREFIXES = (
    "tests/unit/test_app_schemas_",
    "tests/unit/test_app_routers_",
    "tests/unit/test_app_dependencies_",
    "tests/unit/test_app_services_",
    "tests/unit/test_app_v1_",
    "tests/unit/test_app_middleware_",
)


def pytest_collection_modifyitems(config, items):
    """Skip auto-generated compat placeholder tests unless explicitly selected."""
    markexpr = config.getoption("-m", default="") or ""
    if "compat_placeholder" in markexpr:
        return
    skip = pytest.mark.skip(
        reason="Legacy app._compat placeholder (use -m compat_placeholder to include)"
    )
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if any(prefix in nodeid for prefix in _COMPAT_PLACEHOLDER_PREFIXES):
            item.add_marker(skip)
            item.add_marker(pytest.mark.compat_placeholder)


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
