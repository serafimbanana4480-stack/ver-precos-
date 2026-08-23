from scrapers.resilience import scrape_with_resilience
from utils.production_safeguards import CircuitBreaker


def test_empty_scrape_is_not_recorded_as_success():
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=300)

    rows, success = scrape_with_resilience("empty", lambda: [], breaker)

    assert rows == []
    assert success is False
    assert breaker.state == "open"


def test_non_empty_scrape_is_recorded_as_success():
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=300)

    rows, success = scrape_with_resilience("healthy", lambda: [{"url": "https://example.test/1"}], breaker)

    assert rows == [{"url": "https://example.test/1"}]
    assert success is True
    assert breaker.state == "closed"
