# Testing Patterns

**Analysis Date:** 2026-04-13 (Updated after Phase 1)

## Test Framework

**Runner:**
- pytest 7.4.3
- pytest-asyncio 0.21.1 for async test support
- pytest-cov 4.1.0 for coverage reporting (added in Phase 1)
- pytest-mock 3.12.0 for mocking utilities (added in Phase 1)
- factory-boy 3.3.0 for test data factories (added in Phase 1)
- Config: mypy.ini with pytest configuration (added in Phase 1)

**Assertion Library:**
- pytest built-in assertions
- Standard assert statements

**Run Commands:**
```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest test_database.py  # Single file
pytest --cov             # Coverage report (if pytest-cov installed)
```

## Test File Organization

**Location:**
- tests/ directory for test infrastructure (added in Phase 1)
- tests/unit/ for unit tests (added in Phase 1)
- tests/integration/ for integration tests (added in Phase 1)
- test_database.py in project root (legacy test file)
- No collocated test files alongside source

**Naming:**
- test_*.py prefix for test files
- No distinction between unit/integration in filename

**Structure:**
```
VER PRECOS/
├── tests/                # Test infrastructure (added in Phase 1)
│   ├── conftest.py       # Shared pytest fixtures
│   ├── factories.py      # Factory Boy test data factories
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── test_database.py      # Database tests (legacy test file)
├── scrapers/
│   ├── olx_scraper.py
│   └── (no test files yet)
├── database/
│   ├── models.py
│   └── (no test files yet)
```

## Test Structure

**Suite Organization:**
```python
import pytest

def test_function_name():
    # arrange
    # act
    # assert
    pass
```

**Patterns:**
- No explicit describe/it pattern (pytest uses function-based organization)
- No explicit arrange/act/assert comments in existing tests
- Fixtures not currently used

## Mocking

**Framework:**
- pytest built-in monkeypatch for mocking
- unittest.mock available but not used in existing tests

**Patterns:**
```python
# Not currently used in codebase
# Example pattern would be:
def test_with_mock(monkeypatch):
    def mock_function():
        return "mocked"
    monkeypatch.setattr("module.function", mock_function)
```

**What to Mock:**
- External APIs (Grok, Ollama)
- Database connections (use in-memory SQLite)
- File system operations
- Playwright browser automation

**What NOT to Mock:**
- Not applicable (no tests yet to establish patterns)

## Fixtures and Factories

**Test Data:**
- Factory Boy factories defined in tests/factories.py (added in Phase 1)
- VehicleFactory, PriceHistoryFactory, AIReviewFactory, ScrapingLogFactory
- Shared fixtures in tests/conftest.py (added in Phase 1)
- Fixtures: temp_dir, db_session, mock_grok, mock_ollama, sample_vehicle_data

**Location:**
- tests/conftest.py - Shared pytest fixtures
- tests/factories.py - Factory Boy test data factories

## Coverage

**Requirements:**
- Coverage target: 70% minimum (configured in mypy.ini, added in Phase 1)
- pytest-cov 4.1.0 installed (added in Phase 1)
- Coverage tracked in GitHub Actions workflow (added in Phase 1)

**Configuration:**
- Configured in mypy.ini pytest section
- Report: term-missing, xml
- Fail on: cov-fail-under=70

**View Coverage:**
```bash
pytest --cov  # Would require pytest-cov installation
```

## Test Types

**Unit Tests:**
- tests/unit/ directory created (added in Phase 1)
- Test individual functions/classes in isolation
- No test files written yet

**Integration Tests:**
- tests/integration/ directory created (added in Phase 1)
- test_database.py exists (minimal, legacy)
- Tests database connection and basic operations

**E2E Tests:**
- Not implemented
- Playwright used for scraping, not for testing

## Common Patterns

**Async Testing:**
```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
```

**Error Testing:**
```python
def test_error_case():
    with pytest.raises(Exception):
        function_that_raises()
```

**Database Testing:**
```python
# From test_database.py
def test_database_connection():
    from database.db import health_check
    assert health_check() == True
```

**Snapshot Testing:**
- Not used in this codebase

---

*Testing analysis: 2026-04-13*
*Update when test patterns change*
