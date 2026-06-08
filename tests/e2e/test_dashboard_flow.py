"""
E2E test for dashboard flow.
"""
import pytest
from dashboard.app import DashboardApp


@pytest.mark.e2e
async def test_dashboard_flow():
    """Test complete dashboard flow."""
    dashboard = DashboardApp()
    result = await dashboard.get_overview()
    assert result is not None
