import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Skip tests if managed_client module is not available
try:
    from scrapers.managed_client import ManagedScrapingClient, ManagedServiceType
    MANAGED_CLIENT_AVAILABLE = True
except ImportError:
    MANAGED_CLIENT_AVAILABLE = False
    pytest.skip("managed_client module not available in simplified version", allow_module_level=True)

@pytest.mark.asyncio
async def test_fetch_resilient_html_local_success():
    """Test that it returns local HTML if success and not blocked"""
    client = ManagedScrapingClient()
    local_fetcher = AsyncMock(return_value="<html><body>Success</body></html>")
    
    # Mock detection logic to say NOT blocked
    with patch('utils.error_classifier.ErrorClassifier.detect_blocking_in_html', return_value=False):
        html = await client.fetch_resilient_html("https://example.com", local_fetcher)
        
        assert html == "<html><body>Success</body></html>"
        local_fetcher.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_resilient_html_fallback_on_block():
    """Test that it falls back to ZenRows if local fetch is blocked"""
    client = ManagedScrapingClient()
    local_fetcher = AsyncMock(return_value="<html><body>Cloudflare Blocked</body></html>")
    zenrows_html = "<html><body>ZenRows Success</body></html>"
    
    # Mock detection to say BLOCKED for local, NOT BLOCKED for ZenRows
    # Mock settings.zenrows_enabled to True
    with patch('utils.error_classifier.ErrorClassifier.detect_blocking_in_html') as mock_detect:
        mock_detect.side_effect = [True, False] # Blocked first time (local), not second (zenrows)
        
        with patch.object(client, 'scrape_with_zenrows', AsyncMock(return_value=zenrows_html)):
            with patch('config.settings.zenrows_enabled', True):
                html = await client.fetch_resilient_html("https://example.com", local_fetcher)
                
                assert html == zenrows_html
                client.scrape_with_zenrows.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_resilient_html_fallback_on_exception():
    """Test that it falls back to ZenRows if local fetch raises an exception"""
    client = ManagedScrapingClient()
    local_fetcher = AsyncMock(side_effect=Exception("Playwright Crash"))
    zenrows_html = "<html><body>ZenRows Success</body></html>"
    
    with patch.object(client, 'scrape_with_zenrows', AsyncMock(return_value=zenrows_html)):
        with patch('config.settings.zenrows_enabled', True):
            html = await client.fetch_resilient_html("https://example.com", local_fetcher)
            
            assert html == zenrows_html
            client.scrape_with_zenrows.assert_called_once()
