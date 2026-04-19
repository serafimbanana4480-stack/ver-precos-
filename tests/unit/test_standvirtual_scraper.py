import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scrapers.standvirtual_scraper import StandvirtualScraper
from bs4 import BeautifulSoup

@pytest.fixture
def standvirtual_scraper():
    return StandvirtualScraper()

@pytest.fixture
def sample_standvirtual_html():
    return """
    <article data-testid="listing-ad">
        <a href="https://www.standvirtual.com/anuncio/bmw-320.html"></a>
        <h2 class="css-1">BMW 320</h2>
        <span class="css-2">25 000 €</span>
    </article>
    """

@pytest.mark.asyncio
async def test_standvirtual_scrape_listings_resilient_call(standvirtual_scraper):
    """Test that scrape_listings calls the resilient flow"""
    with patch.object(standvirtual_scraper, '_scrape_with_resilient_flow', AsyncMock(return_value=[])) as mock_flow:
        await standvirtual_scraper.scrape_listings(vehicle_type="carros", max_listings=5)
        mock_flow.assert_called_once()

@pytest.mark.asyncio
async def test_standvirtual_parse_soup_to_listings(standvirtual_scraper, sample_standvirtual_html):
    """Test parsing logic from HTML soup"""
    soup = BeautifulSoup(sample_standvirtual_html, 'lxml')
    # Mocking _parse_listing_element
    with patch.object(standvirtual_scraper, '_parse_listing_element', return_value={"title": "BMW"}):
        listings = standvirtual_scraper._parse_soup_to_listings(soup, max_listings=10)
        assert len(listings) == 1
        assert listings[0]["title"] == "BMW"

@pytest.mark.asyncio
async def test_standvirtual_fetch_html_with_playwright_mock(standvirtual_scraper):
    """Test that playwright fetcher is called correctly (mocked)"""
    with patch('playwright.async_api.async_playwright') as mock_p:
        mock_p.return_value.__aenter__.return_value.chromium.launch = AsyncMock()
        browser = mock_p.return_value.__aenter__.return_value.chromium.launch.return_value
        browser.new_context = AsyncMock()
        context = browser.new_context.return_value
        context.new_page = AsyncMock()
        page = context.new_page.return_value
        page.goto = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        browser.close = AsyncMock()
        
        with patch('asyncio.sleep', AsyncMock()):
            html = await standvirtual_scraper._fetch_html_with_playwright("https://example.com")
            assert html == "<html></html>"
            page.goto.assert_called_once()
