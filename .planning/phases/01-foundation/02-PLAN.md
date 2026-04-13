# Phase 1.2: Error Handling & Retry

**Wave:** 1
**Depends on:** None
**Files modified:** scrapers/*.py, ai_agent/*.py, database/db.py, requirements.txt
**Autonomous:** true

## Requirements

- ERR-01 - Add tenacity retry decorator with exponential backoff
- ERR-02 - Implement retry logic for transient scraping failures (network timeouts, rate limits)
- ERR-03 - Implement retry logic for transient AI API failures
- ERR-04 - Set max retry attempts (3-5) with jitter
- ERR-05 - Ensure operations are idempotent before adding retry
- ERR-06 - Add deduplication logic for retry operations
- ERR-07 - Retry only on specific error types (transient, not logic errors)
- ERR-08 - Log retry attempts with context and backoff timing

## Tasks

### Task 1: Add tenacity to requirements

<read_first>
requirements.txt
</read_first>

<action>
Add tenacity==8.2.3 to requirements.txt in the dependencies section
</action>

<acceptance_criteria>
requirements.txt contains tenacity==8.2.3
</acceptance_criteria>

### Task 2: Create retry utility module

<read_first>
requirements.txt
</read_first>

<action>
Create a new file utils/retry.py with reusable retry decorators:

1. Import from tenacity: retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
2. Create retry_network decorator for network-related errors (TimeoutError, ConnectionError, HTTPError)
3. Create retry_ai_api decorator for AI API errors (rate limits, timeouts)
4. Create retry_database decorator for database errors (connection failures)
5. Configure each with: max_attempts=3, exponential backoff (min=2s, max=10s), jitter
6. Add before_sleep logging with attempt number and wait time
7. Add exception type filtering (retry only transient errors)
</action>

<acceptance_criteria>
utils/retry.py exists
utils/retry.py contains retry_network decorator
utils/retry.py contains retry_ai_api decorator
utils/retry.py contains retry_database decorator
utils/retry.py uses stop_after_attempt(3)
utils/retry.py uses wait_exponential with min=2, max=10
</acceptance_criteria>

### Task 3: Add retry to scrapers

<read_first>
scrapers/standvirtual_scraper.py
scrapers/olx_scraper.py
scrapers/autosapo_scraper.py
utils/retry.py
</read_first>

<action>
Add retry decorators to scraper network operations:

1. In each scraper, import from utils.retry import retry_network
2. Add @retry_network decorator to:
   - _fetch_page method (network requests)
   - _scroll_to_load method (network-dependent)
   - scrape_listings method (main scraping loop)
3. Ensure idempotency: check if listing already exists before retry
4. Add listing URL deduplication tracking
5. Log retry attempts with listing URL and attempt number
6. Handle final failure: log error, continue to next listing
</action>

<acceptance_criteria>
scrapers/standvirtual_scraper.py imports utils.retry
scrapers/standvirtual_scraper.py uses @retry_network on _fetch_page
scrapers/olx_scraper.py imports utils.retry
scrapers/olx_scraper.py uses @retry_network on network methods
scrapers/autosapo_scraper.py imports utils.retry
scrapers/autosapo_scraper.py uses @retry_network on network methods
</acceptance_criteria>

### Task 4: Add retry to AI agent

<read_first>
ai_agent/llm_review.py
ai_agent/vision_analysis.py
ai_agent/deal_finder.py
utils/retry.py
</read_first>

<action>
Add retry decorators to AI API calls:

1. In ai_agent modules, import from utils.retry import retry_ai_api
2. Add @retry_ai_api decorator to:
   - LLM API call methods (analyze_description, generate_review)
   - Vision analysis methods (analyze_image)
   - Grok/Ollama API client methods
3. Ensure idempotency: cache results by input hash
4. Add request deduplication tracking
5. Log retry attempts with API endpoint and attempt number
6. Handle final failure: log error, return None or use fallback
</action>

<acceptance_criteria>
ai_agent/llm_review.py imports utils.retry
ai_agent/llm_review.py uses @retry_ai_api on API calls
ai_agent/vision_analysis.py imports utils.retry
ai_agent/vision_analysis.py uses @retry_ai_api on API calls
ai_agent/deal_finder.py imports utils.retry
ai_agent/deal_finder.py uses @retry_ai_api on API calls
</acceptance_criteria>

### Task 5: Add retry to database operations

<read_first>
database/db.py
utils/retry.py
</read_first>

<action>
Add retry decorators to database connection operations:

1. In database/db.py, import from utils.retry import retry_database
2. Add @retry_database decorator to:
   - init_db function (initial connection)
   - health_check function (connection validation)
3. Ensure idempotency: check if already initialized
4. Log retry attempts with connection string and attempt number
5. Handle final failure: raise exception to caller
6. Keep session operations within transactions (no retry on transaction errors)
</action>

<acceptance_criteria>
database/db.py imports utils.retry
database/db.py uses @retry_database on init_db
database/db.py uses @retry_database on health_check
</acceptance_criteria>

### Task 6: Add deduplication logic

<read_first>
scrapers/*.py
ai_agent/*.py
database/models.py
</read_first>

<action>
Add deduplication tracking for retry operations:

1. In scrapers, track processed listing URLs in a set
2. Check set before processing: skip if already processed
3. In AI agent, track processed vehicle IDs
4. Check set before AI analysis: skip if already analyzed
5. Add DEDUPLICATION_WINDOW config option (default 1 hour)
6. Use database to persist deduplication state across runs
7. Add Deduplication model or use ScrapingLog for tracking
</action>

<acceptance_criteria>
scrapers track processed listing URLs
scrapers check deduplication before processing
ai_agent tracks processed vehicle IDs
ai_agent checks deduplication before analysis
config.py has DEDUPLICATION_WINDOW setting
</acceptance_criteria>

### Task 7: Configure retry exception types

<read_first>
utils/retry.py
</read_first>

<action>
Configure retry to only retry on transient errors:

1. In retry_network decorator, retry only on:
   - TimeoutError
   - ConnectionError
   - HTTPError with status 429 (rate limit)
   - HTTPError with status 5xx (server errors)
2. Do NOT retry on:
   - HTTPError with status 4xx (client errors, except 429)
   - ValueError (logic errors)
   - KeyError (missing data errors)
3. In retry_ai_api decorator, retry only on:
   - TimeoutError
   - ConnectionError
   - Rate limit errors
4. Add custom exception classes for retry-specific errors
5. Document which errors trigger retry in docstrings
</action>

<acceptance_criteria>
utils/retry.py excludes 4xx client errors from retry
utils/retry.py excludes ValueError from retry
utils/retry.py excludes KeyError from retry
utils/retry.py retries on 429 rate limit errors
utils/retry.py retries on 5xx server errors
</acceptance_criteria>

### Task 8: Add retry logging

<read_first>
utils/logging_config.py
utils/retry.py
</read_first>

<action>
Add comprehensive logging for retry attempts:

1. In utils/retry.py, use before_sleep_log from tenacity
2. Log: attempt number, wait time, exception type, error message
3. Log: operation context (function name, parameters)
4. Log: final failure after max attempts
5. Add retry_success metric (count successful retries)
6. Add retry_failure metric (count failed retries)
7. Add retry_backoff_total metric (total time spent in backoff)
8. In utils/logging_config.py, create retry logger
</action>

<acceptance_criteria>
utils/retry.py uses before_sleep_log
retry logs include attempt number
retry logs include wait time
retry logs include exception type
retry logs include operation context
utils/logging_config.py has retry logger
</acceptance_criteria>

## Verification Criteria

- [ ] tenacity installed and configured
- [ ] Network operations retry on transient failures
- [ ] AI API calls retry on rate limits and timeouts
- [ ] Database connections retry on connection failures
- [ ] Retry limited to 3-5 attempts with exponential backoff
- [ ] Operations are idempotent (deduplication in place)
- [ ] Only transient errors trigger retry (not logic errors)
- [ ] All retry attempts logged with context and timing
- [ ] Existing functionality preserved

## Must Haves

- Transient network failures are automatically retried
- AI API rate limits are handled with backoff
- Database connection failures are retried
- Retry attempts are logged for debugging
- Duplicate operations are prevented
- Logic errors are not retried (fail fast)
- Maximum retry attempts prevent infinite loops
