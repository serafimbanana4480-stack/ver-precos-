"""
Unit test for app services deal service.
"""
import pytest
from app.services.deal_service import DealService


def test_deal_service_init():
    """Test deal service initialization."""
    service = DealService()
    assert service is not None
