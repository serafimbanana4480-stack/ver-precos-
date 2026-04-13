# Stack Research

**Analysis Date:** 2026-04-13

## Current Stack Assessment

**Existing Stack (from codebase map):**
- Python 3.12+ - Primary language
- SQLAlchemy 2.0.25 - ORM
- Playwright 1.40.0 - Browser automation
- XGBoost 2.0.3 - ML model
- pytest 7.4.3 - Testing framework
- APScheduler 3.10.4 - Job scheduling
- Streamlit 1.29.0 - Dashboard
- black 23.12.1 - Formatting
- flake8 7.0.0 - Linting
- mypy 1.8.0 - Type checking

## Recommended Additions for Technical Debt Resolution

### Testing & Quality

**pytest-asyncio 0.21.1** - Already in requirements, good for async testing
**pytest-cov 4.1.0** - Coverage reporting (currently missing)
**pytest-mock 3.12.0** - Mocking utilities (currently missing)
**factory-boy 3.3.0** - Test data factories (recommended for database testing)

### Validation

**pydantic 2.5.0** - Already in requirements, should be used for input validation
**pydantic-settings 2.1.0** - Settings validation (add for config.py)

### Database

**alembic 1.13.1** - Already in requirements, needs configuration
**psycopg2-binary 2.9.9** - PostgreSQL adapter (already in requirements, commented)

### Caching

**redis 5.0.1** - Already in requirements, should be enabled
**hiredis 2.2.3** - Redis C parser for performance (add)

### Monitoring

**sentry-sdk 1.40.0** - Error tracking (add for production)
**prometheus-client 0.19.0** - Metrics collection (optional add)

### Retry Logic

**tenacity 8.2.3** - Retry decorator (add for scraping failures)
**backoff 2.2.1** - Alternative retry with exponential backoff

## Version Recommendations

**Keep Current (Stable):**
- Python 3.12+ - Latest stable
- SQLAlchemy 2.0.25 - Latest 2.x
- Playwright 1.40.0 - Latest stable
- XGBoost 2.0.3 - Latest stable
- pytest 7.4.3 - Latest stable

**Upgrade Recommended:**
- black 23.12.1 → 24.1.1 (latest)
- flake8 7.0.0 → 7.1.0 (latest)
- mypy 1.8.0 → 1.9.0 (latest)

**Add New:**
- pytest-cov 4.1.0 - Coverage reporting
- pytest-mock 3.12.0 - Mocking
- factory-boy 3.3.0 - Test factories
- pydantic-settings 2.1.0 - Config validation
- hiredis 2.2.3 - Redis performance
- sentry-sdk 1.40.0 - Error tracking
- tenacity 8.2.3 - Retry logic

## Dependencies to Remove

**None** - All current dependencies are in use.

## Rationale

**pytest-cov**: Essential for measuring test coverage, especially when building out test suite from minimal coverage.

**pytest-mock**: Simplifies mocking in tests, reduces boilerplate code for mocking external services (Grok API, scraping targets).

**factory-boy**: Makes test data creation easier for database models, reduces test setup code.

**pydantic-settings**: Extends pydantic for settings validation, ensures configuration is correct at startup.

**hiredis**: Redis C parser improves performance for caching operations, minimal integration effort.

**sentry-sdk**: Production error tracking is critical for autonomous systems, provides visibility into failures.

**tenacity**: Provides clean retry decorators with exponential backoff, better than manual retry logic.

## Confidence Levels

- **High**: pytest-cov, pytest-mock, factory-boy (standard testing stack)
- **High**: pydantic-settings (natural extension of existing pydantic)
- **Medium**: hiredis (performance optimization, not critical)
- **High**: sentry-sdk (production best practice)
- **High**: tenacity (well-established library, solves documented gap)

## What NOT to Use

- **unittest**: pytest is already in use, don't mix frameworks
- **mock (stdlib)**: pytest-mock provides better integration
- **SQLAlchemy-migrate**: Alembic is the standard choice
- **requests**: aiohttp is already used for async operations
- **celery**: APScheduler is sufficient for current needs
- **dramatiq**: Not needed for simple job queue
