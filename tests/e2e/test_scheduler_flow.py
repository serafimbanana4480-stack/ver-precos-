"""
E2E test for scheduler flow.
"""
import pytest
from scheduler.daily_job import DailyJob


@pytest.mark.e2e
async def test_scheduler_flow():
    """Test complete scheduler flow."""
    job = DailyJob()
    result = await job.run()
    assert result is not None
