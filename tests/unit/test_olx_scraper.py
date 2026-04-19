import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scrapers.olx_scraper import OLXScraper
from bs4 import BeautifulSoup

@pytest.fixture
def olx_scraper():
    return OLXScraper()

@pytest.fixture
def sample_olx_html():
    return """
    <div data-cy="l-card">
        <a href="https://www.olx.pt/anuncio/carro-123.html"></a>
        <h6 class="css-1wba192">Volkswagen Golf</h6>
        <p class="css-18h94m8">15 000 €</p>
        <span class="css-19v0v0">Lisboa, Benfica</span>
    </div>
    """

@pytest.mark.asyncio
async def test_olx_scrape_listings_resilient_call(olx_scraper):
    """Test that scrape_listings calls the resilient flow"""
    with patch.object(olx_scraper, '_scrape_with_resilient_flow', AsyncMock(return_value=[])) as mock_flow:
        await olx_scraper.scrape_listings(vehicle_type="carros", max_listings=5)
        mock_flow.assert_called_once()

@pytest.mark.asyncio
async def test_olx_parse_soup_to_listings(olx_scraper, sample_olx_html):
    """Test parsing logic from HTML soup"""
    soup = BeautifulSoup(sample_olx_html, 'lxml')
    # Mocking _parse_olx_element because it relies on selector_manager
    with patch.object(olx_scraper, '_parse_olx_element', return_value={"title": "Golf"}):
        listings = olx_scraper._parse_soup_to_listings(soup, max_listings=10)
        assert len(listings) == 1
        assert listings[0]["title"] == "Golf"

@pytest.mark.asyncio
async def test_olx_fetch_html_with_playwright_mock(olx_scraper):
    """Test that playwright fetcher is called correctly (mocked playwright)"""
    with patch('playwright.async_api.async_playwright') as mock_p:
        # Complex mocking of async playwright context manager
        mock_p.return_value.__aenter__.return_value.chromium.launch = AsyncMock()
        browser = mock_p.return_value.__aenter__.return_value.chromium.launch.return_value
        browser.new_context = AsyncMock()
        context = browser.new_context.return_value
        context.new_page = AsyncMock()
        page = context.new_page.return_value
        page.goto = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        browser.close = AsyncMock()
        
        # We need to use a shorter settle time for tests or mock asyncio.sleep
        with patch('asyncio.sleep', AsyncMock()):
            html = await olx_scraper._fetch_html_with_playwright("https://example.com")
            assert html == "<html></html>"
            page.goto.assert_called_once_with("https://example.com", timeout=olx_scraper.timeout, wait_until='networkidle')
