"""
Unit test for ingestion scheduler scheduler.
"""
import pytest
from ingestion.scheduler.scheduler import Scheduler


def test_scheduler_init():
    """Test scheduler initialization."""
    scheduler = Scheduler()
    assert scheduler is not None
