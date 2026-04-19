# Testing Practices - AutoDeal IA Hunter

## Test Framework

- **pytest**: Primary testing framework
- **pytest-asyncio**: Async test support
- **pytest-cov**: Code coverage
- **pytest-mock**: Mocking utilities
- **factory-boy**: Test data generation

## Test Structure

```
tests/
├── conftest.py           # Pytest configuration and fixtures
├── factories.py          # Test data factories
├── unit/                 # Unit tests
│   ├── test_olx_scraper.py
│   ├── test_standvirtual_scraper.py
│   ├── test_autosapo_scraper.py
│   ├── test_managed_client.py
│   ├── test_database.py
│   ├── test_config.py
│   └── test_selector_manager.py
├── integration/          # Integration tests
│   ├── test_deal_scorer.py
│   └── test_database.py
└── test_circuit_breaker.py  # Circuit breaker tests
```

## Unit Tests

### Scraper Tests
- Test individual scraper methods (async)
- Mock HTTP responses with aioresponses
- Test CSS selector logic
- Test data parsing
- Test error handling
- Test circuit breaker integration

### Database Tests
- Test model creation
- Test query operations
- Test validation (Pydantic + custom)
- Test relationships
- Test context manager pattern
- Test retry decorator
- Use in-memory SQLite for speed

### Utility Tests
- Test retry decorators (tenacity)
- Test circuit breakers (separate per scraper)
- Test data validators
- Test deduplication (Redis + in-memory fallback)
- Test selector manager fallback
- Test consistent hash encoding

### AI/ML Tests
- Test price prediction
- Test deal scoring
- Test feature encoding
- Mock LLM responses
- Mock vision analysis

## Integration Tests

### Database Integration
- Test with PostgreSQL
- Test migrations (Alembic)
- Test real queries
- Test transaction handling
- Test N+1 query issues

### Scraper Integration
- Test with real websites (carefully)
- Test fallback chains
- Test circuit breakers
- Test AI extraction
- Test event loop management

### Service Integration
- Test deal finding pipeline
- Test AI analysis
- Test notification sending
- Test scheduler jobs

### Redis Integration
- Test Redis deduplication
- Test fallback to in-memory
- Test TTL expiration
- Test distributed scenarios

## Fixtures

### Database Fixture
```python
@pytest.fixture
def db_session():
    with get_db_context() as db:
        yield db
```

### Scraper Fixture
```python
@pytest.fixture
def olx_scraper():
    return OLXScraper()
```

### Mock HTTP Fixture
```python
@pytest.fixture
def mock_http_response():
    with aioresponses() as m:
        m.get(url, payload=response_data)
        yield
```

### Circuit Breaker Fixture
```python
@pytest.fixture
def circuit_breaker():
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
    return breaker
```

## Coverage

### Target Coverage
- Aim for 80%+ overall coverage
- Critical paths: 90%+ (database, validation)
- Scraper logic: 85%+
- Utility functions: 90%+
- Circuit breakers: 95%+

### Running Coverage
```bash
pytest --cov=. --cov-report=html
```

### Coverage Report
- HTML report in htmlcov/
- Line coverage by module
- Branch coverage where applicable
- Identify untested paths

## Test Data

### Factories
- Use factory-boy for test data
- Define realistic defaults
- Allow customization
- Keep data consistent
- Include new Vehicle fields (trim_level, has_damage, maintenance_history, aesthetic_score)

### Mock Data
- Use realistic mock data
- Match real data structure
- Include edge cases (year 1980, invalid URLs)
- Test error conditions
- Test validation boundaries

## Running Tests

### All Tests
```bash
pytest
```

### Unit Tests Only
```bash
pytest tests/unit/
```

### Integration Tests Only
```bash
pytest tests/integration/
```

### Specific Test
```bash
pytest tests/unit/test_olx_scraper.py::test_scrape_listings
```

### With Coverage
```bash
pytest --cov=. --cov-report=html
```

### Async Tests Only
```bash
pytest -m asyncio
```

## Async Testing

### Async Tests
- Use @pytest.mark.asyncio
- Use pytest-asyncio fixture
- Mock async operations
- Test error handling
- Test event loop scenarios

### Example
```python
@pytest.mark.asyncio
async def test_async_scraper():
    scraper = OLXScraper()
    listings = await scraper.scrape_listings("carros", max_listings=10)
    assert len(listings) >= 0  # May be empty if mocked
```

### Event Loop Testing
- Test closed loop scenarios
- Test nested async contexts
- Test Parsera integration
- Test asyncio.run() edge cases

## Testing Gaps

### Current Gaps
- No integration tests for Redis deduplication
- No tests for event loop management in AI scraper
- No tests for consistent hash encoding
- No tests for new Vehicle fields
- No performance tests for N+1 queries

### Recommended Additions
- Add Redis integration tests
- Add circuit breaker state transition tests
- Add async event loop scenario tests
- Add ML model prediction tests
- Add scheduler job tests
