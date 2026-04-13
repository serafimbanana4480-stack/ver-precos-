# Testing Patterns

**Analysis Date:** 2026-04-13

## Test Framework

**Runner:**
- pytest 7.4.3
- pytest-asyncio 0.21.1 for async test support
- Config: pytest.ini or pytest configuration in setup.cfg (not present, using defaults)

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
- test_*.py in project root (currently only test_database.py exists)
- No separate tests/ directory
- No collocated test files alongside source

**Naming:**
- test_*.py prefix for test files
- No distinction between unit/integration in filename

**Structure:**
```
VER PRECOS/
├── test_database.py      # Database tests (only test file)
├── scrapers/
│   ├── olx_scraper.py
│   └── (no test files)
├── database/
│   ├── models.py
│   └── (no test files)
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
- No factory functions defined
- No shared fixtures directory
- Test data inline in test files (if tests existed)

**Location:**
- Not applicable (no test infrastructure yet)

## Coverage

**Requirements:**
- No enforced coverage target
- Coverage not currently tracked
- pytest-cov not installed (available but not in requirements.txt)

**Configuration:**
- No coverage configuration

**View Coverage:**
```bash
pytest --cov  # Would require pytest-cov installation
```

## Test Types

**Unit Tests:**
- Not currently implemented
- Would test individual functions/classes in isolation

**Integration Tests:**
- test_database.py exists (minimal)
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
