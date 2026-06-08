"""
Unit test for scrapers managed client.
"""
import pytest
from scrapers.managed_client import ManagedClient


def test_managed_client_init():
    """Test managed client initialization."""
    client = ManagedClient()
    assert client is not None


@pytest.mark.asyncio
async def test_managed_client_get_html_offloads_to_thread(monkeypatch):
    """Test that get_html delegates blocking work to asyncio.to_thread."""
    client = ManagedClient()

    sentinel = object()

    async def fake_to_thread(func, *args, **kwargs):
        assert func == client._get_html_sync
        assert args == ("https://example.com", "olx")
        assert kwargs == {}
        return sentinel

    monkeypatch.setattr("scrapers.managed_client.asyncio.to_thread", fake_to_thread)

    result = await client.get_html("https://example.com", "olx")

    assert result is sentinel
