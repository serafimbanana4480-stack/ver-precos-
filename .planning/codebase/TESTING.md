# Testing Practices - AutoDeal IA Hunter

## Framework
- **Primary:** `pytest`
- **Extensions:** 
  - `pytest-asyncio` for async tests.
  - `pytest-cov` for coverage reporting.
  - `pytest-mock` for dependency mocking.
- **Data Generation:** `factory-boy` for database model factories.

## Test Structure
```text
tests/
├── unit/               # Fast tests for pure logic and models
├── integration/        # Tests for database and multi-service flows
├── conftest.py         # Shared fixtures and setup
└── factories.py        # Model factories for test data
```

## Current State (Status as of 2026-04-15)
- **Overall Coverage:** ~18% (Critical areas like scrapers and AI logic are at 0%).
- **Database Models:** ~100% unit test coverage.
- **Configuration:** ~100% unit test coverage.
- **Failures:** Known failures in database constraint tests (Pending fixes).

## Continuous Integration
- **GitHub Actions:** Configured to run the test suite on push and PR.
- **Grade:** B- (Solid infrastructure, but actual coverage needs significant improvement).

## Strategy
1. **Mocking:** Always mock external API calls (Grok, Ollama, ScraperAPI).
2. **Database:** Use a temporary SQLite database for all integration tests.
3. **Factories:** Use `VehicleFactory` and others in `factories.py` to keep tests DRY.
4. **Coverage Target:** Aim for 70% coverage in core logic and utility modules.
