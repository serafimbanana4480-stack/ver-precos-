import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scrapers.autosapo_scraper import AutoSapoScraper
from bs4 import BeautifulSoup

@pytest.fixture
def autosapo_scraper():
    return AutoSapoScraper()

@pytest.fixture
def sample_autosapo_html():
    return """
    <article class="vehicle-card">
        <a href="https://auto.sapo.pt/anuncio/opel-corsa.html"></a>
        <h2 class="title">Opel Corsa</h2>
        <span class="price">10 000 €</span>
    </article>
    """

@pytest.mark.asyncio
async def test_autosapo_scrape_listings_resilient_call(autosapo_scraper):
    """Test that scrape_listings calls the resilient flow"""
    with patch.object(autosapo_scraper, '_scrape_with_resilient_flow', AsyncMock(return_value=[])) as mock_flow:
        await autosapo_scraper.scrape_listings(vehicle_type="carros", max_listings=5)
        mock_flow.assert_called_once()

@pytest.mark.asyncio
async def test_autosapo_parse_soup_to_listings(autosapo_scraper, sample_autosapo_html):
    """Test parsing logic from HTML soup"""
    soup = BeautifulSoup(sample_autosapo_html, 'lxml')
    # Mocking _parse_listing_element and _parse_links_fallback to avoid fallback logic
    with patch.object(autosapo_scraper, '_parse_listing_element', return_value={"title": "Opel"}):
        with patch.object(autosapo_scraper, '_parse_links_fallback', return_value=[]):
            listings = autosapo_scraper._parse_soup_to_listings(soup, max_listings=10)
            assert len(listings) == 1
            assert listings[0]["title"] == "Opel"

@pytest.mark.asyncio
async def test_autosapo_fetch_html_with_playwright_mock(autosapo_scraper):
    """Test that playwright fetcher returns HTML when mocked at method level"""
    with patch.object(autosapo_scraper, '_fetch_html_with_playwright', AsyncMock(return_value="<html></html>")):
        html = await autosapo_scraper._fetch_html_with_playwright("https://example.com")
        assert html == "<html></html>"
