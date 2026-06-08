"""
Unit test for scheduler daily job.
"""
import pytest
from scheduler.daily_job import DailyJob


def test_daily_job_init():
    """Test daily job initialization."""
    job = DailyJob()
    assert job is not None
