# Phase 1 Research

**Phase:** 1 - Foundation
**Research Date:** 2026-04-13
**Status:** Complete

## Phase Boundary

Phase 1 establishes core infrastructure for reliability and observability:
- Validation layer with pydantic models
- Error handling & retry logic with tenacity
- Monitoring & code quality improvements (Sentry, structured logging, tool upgrades)
- Test infrastructure setup (pytest-cov, pytest-mock, factory-boy, CI/CD)

## Technical Approach

### Validation Layer (VAL-01 through VAL-08)

**Pydantic Integration Strategy:**
- Use pydantic-settings for config validation (replaces manual Config.validate())
- Create pydantic models for CLI args (wrap argparse outputs)
- Create pydantic models for scraped data (before database insertion)
- Validate LLM response structure before processing

**Implementation Pattern:**
```python
# config.py - Add pydantic-settings
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    database_url: str
    grok_api_key: str = ""
    # ... other fields with type hints and validation
```

**Validation Points:**
1. CLI arguments in main.py after argparse
2. Scraped data in scrapers before db.save()
3. LLM responses in ai_agent before processing
4. Configuration at startup

**Error Handling:**
- Log validation failures with context
- Make validation configurable (strict vs lenient mode)
- Alert on systematic failures (threshold-based)

### Error Handling & Retry (ERR-01 through ERR-08)

**Tenacity Integration Strategy:**
- Add tenacity decorator with exponential backoff
- Retry only on transient errors (network, rate limits)
- Max 3-5 attempts with jitter
- Ensure idempotency before adding retry

**Retry Points:**
1. Scraping network requests (timeouts, 429 errors)
2. AI API calls (Grok, Ollama)
3. Database connection failures
4. File I/O operations

**Implementation Pattern:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    before_sleep=lambda retry_state: logger.warning(f"Retrying... attempt {retry_state.attempt_number}")
)
def scrape_with_retry(url):
    # scraping logic
```

**Idempotency Checks:**
- Add deduplication for retry operations
- Check if data already exists before retry
- Use unique identifiers to prevent duplicates

### Monitoring & Code Quality (MON-01 through MON-10, QUAL-01 through QUAL-08)

**Sentry Integration:**
- Add sentry-sdk to requirements
- Initialize Sentry in main.py or utils/logging_config.py
- Filter sensitive data (API keys, passwords)
- Track scraping success/failure rates
- Track AI API latency and failures

**Structured Logging:**
- Add request IDs or correlation IDs
- Include stack traces in error logs
- Implement log rotation (RotatingFileHandler)
- Filter sensitive data from logs

**Tool Upgrades:**
- Upgrade black 23.12.1 → 24.1.1
- Upgrade flake8 7.0.0 → 7.1.0
- Upgrade mypy 1.8.0 → 1.9.0
- Add type hints to all functions
- Enable mypy strict mode

**Code Quality Improvements:**
- Fix DetachedInstanceError workarounds (proper session management)
- Reduce function complexity (< 50 lines)
- Extract helper functions

### Test Infrastructure (TEST-01 through TEST-03, TEST-10)

**Pytest Integration:**
- Add pytest-cov for coverage reporting
- Add pytest-mock for mocking utilities
- Add factory-boy for test data factories

**Test Structure:**
```
tests/
├── unit/
│   ├── test_scrapers.py
│   ├── test_valuation.py
│   └── test_ai_agent.py
├── integration/
│   ├── test_database.py
│   └── test_scheduler.py
└── conftest.py (fixtures, factories)
```

**CI/CD Integration:**
- Add GitHub Actions workflow for automated tests
- Run tests on push/PR
- Coverage reporting
- Type checking with mypy

## Dependencies

**External Libraries:**
- pydantic-settings 2.1.0
- tenacity 8.2.3
- sentry-sdk 1.40.0
- pytest-cov 4.1.0
- pytest-mock 3.12.0
- factory-boy 3.3.0

**Existing Libraries to Upgrade:**
- black 23.12.1 → 24.1.1
- flake8 7.0.0 → 7.1.0
- mypy 1.8.0 → 1.9.0

## Implementation Order

**Wave 1 (Can run in parallel):**
1. Validation layer (VAL-01 through VAL-08)
2. Error handling & retry (ERR-01 through ERR-08)
3. Monitoring setup (MON-01 through MON-04)
4. Code quality upgrades (QUAL-01 through QUAL-05)

**Wave 2 (Depends on Wave 1):**
5. Test infrastructure (TEST-01 through TEST-03, TEST-10)
6. Monitoring metrics (MON-05 through MON-10)
7. Code quality refactoring (QUAL-06 through QUAL-08)

## Risks & Mitigations

**Validation Risks:**
- Risk: Validation may break existing data flow
- Mitigation: Add validation in non-blocking mode initially, log violations only

**Sentry Risks:**
- Risk: Sentry may expose sensitive data
- Mitigation: Filter sensitive data before sending to Sentry

**Retry Risks:**
- Risk: Infinite retry loops
- Mitigation: Set max retry attempts, use exponential backoff with jitter

**Test Infrastructure Risks:**
- Risk: Test setup complex for Playwright
- Mitigation: Mock Playwright responses, use pytest-playwright if needed

## Known Constraints

- Must follow existing code conventions (snake_case, black formatting)
- Must not break existing functionality
- Must maintain backward compatibility with CLI interface
- Must respect environment variable configuration pattern

## Next Steps

After research complete, proceed to planning:
- Create detailed PLAN.md files for each wave
- Define specific tasks with acceptance criteria
- Set up verification criteria
- Plan CI/CD integration

---
*Research complete: 2026-04-13*
