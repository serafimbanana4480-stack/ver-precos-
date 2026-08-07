"""
Tests for multi-auction scrapers: Manheim, Autorola, BCA.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class DummyTransaction:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture(autouse=True)
def _patch_database_and_models():
    with patch.dict(
        "sys.modules",
        {
            "database": MagicMock(),
            "database.models": MagicMock(),
            "database.db": MagicMock(),
        },
    ), patch("config.settings", MagicMock()):
        yield


def _import_scrapers_module():
    with patch("config.settings", MagicMock()), \
         patch.dict(
             "sys.modules",
             {
                 "database": MagicMock(),
                 "database.models": MagicMock(),
                 "database.db": MagicMock(),
             },
         ):
         from scrapers import auction_multi_scraper as module
    return module


class TestScraperInstantiation:
    def test_manheim_scraper_instantiation(self):
        module = _import_scrapers_module()
        scraper = module.ManheimScraper()
        assert scraper is not None

    def test_autorola_scraper_instantiation(self):
        module = _import_scrapers_module()
        scraper = module.AutorolaScraper()
        assert scraper is not None

    def test_bca_scraper_instantiation(self):
        module = _import_scrapers_module()
        scraper = module.BCAScraper()
        assert scraper is not None


class TestScrapeListings:
    @pytest.mark.asyncio
    async def test_manheim_scrape_listings_returns_list(self):
        module = _import_scrapers_module()
        scraper = module.ManheimScraper()
        result = await scraper.scrape_listings()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_autorola_scrape_listings_returns_list(self):
        module = _import_scrapers_module()
        scraper = module.AutorolaScraper()
        result = await scraper.scrape_listings()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_bca_scrape_listings_returns_list(self):
        module = _import_scrapers_module()
        scraper = module.BCAScraper()
        result = await scraper.scrape_listings()
        assert isinstance(result, list)


class TestCircuitBreakerBlocksAtThreshold:
    def test_circuit_breaker_opens_on_threshold(self, tmp_path):
        from utils.production_safeguards import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == "open"
        assert breaker.can_attempt() is False

    def test_circuit_breaker_closes_after_recovery_timeout(self):
        from utils.production_safeguards import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == "open"
        import time
        time.sleep(1.1)
        assert breaker.can_attempt() is True


class TestHttpResponses:
    @pytest.mark.asyncio
    async def test_manheim_handles_blocked_response(self):
        module = _import_scrapers_module()
        scraper = module.ManheimScraper()

        mock_response = MagicMock()
        mock_response.status = 403
        mock_response.text = MagicMock()

        with patch.object(scraper, "_playwright_fetch", new=AsyncMock(return_value=None)), \
             patch.object(scraper, "_fetch_text", new=AsyncMock(return_value=None)):
            result = await scraper.scrape_listings()
        assert result == []
