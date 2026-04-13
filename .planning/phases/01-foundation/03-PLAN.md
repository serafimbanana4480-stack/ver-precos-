# Phase 1.3: Monitoring & Code Quality

**Wave:** 1
**Depends on:** None
**Files modified:** requirements.txt, config.py, utils/logging_config.py, main.py, scrapers/*.py, ai_agent/*.py
**Autonomous:** true

## Requirements

- MON-01 - Add sentry-sdk for error tracking and monitoring
- MON-02 - Implement structured logging with context (request IDs, stack traces)
- MON-03 - Add log rotation to prevent uncontrolled log growth
- MON-04 - Filter sensitive data from logs (API keys, passwords)
- MON-05 - Add health check endpoint for monitoring system status
- MON-06 - Alert only on actionable issues with severity levels
- MON-07 - Aggregate related alerts to prevent alert fatigue
- MON-08 - Track scraping success/failure rates
- MON-09 - Track AI API call latency and failures
- MON-10 - Track scheduler job execution times
- QUAL-01 - Upgrade black from 23.12.1 to 24.1.1
- QUAL-02 - Upgrade flake8 from 7.0.0 to 7.1.0
- QUAL-03 - Upgrade mypy from 1.8.0 to 1.9.0
- QUAL-04 - Add type hints to all functions
- QUAL-05 - Enable mypy strict mode for type checking

## Tasks

### Task 1: Add sentry-sdk to requirements

<read_first>
requirements.txt
</read_first>

<action>
Add sentry-sdk==1.40.0 to requirements.txt in the dependencies section
</action>

<acceptance_criteria>
requirements.txt contains sentry-sdk==1.40.0
</acceptance_criteria>

### Task 2: Initialize Sentry in main.py

<read_first>
main.py
config.py
</read_first>

<action>
Add Sentry initialization in main.py:

1. Import sentry_sdk
2. After config import, initialize Sentry:
   - Get SENTRY_DSN from config or environment
   - Set environment (development/production)
   - Set release version (from git tag or hardcoded)
   - Configure sample rate (1.0 for production, 0.1 for development)
   - Filter sensitive data (API keys, passwords)
3. Add before_send callback to filter sensitive data
4. Add user context when available
5. Add breadcrumbs for important operations
</action>

<acceptance_criteria>
main.py imports sentry_sdk
main.py calls sentry_sdk.init()
config.py has SENTRY_DSN setting
main.py filters sensitive data from Sentry
</acceptance_criteria>

### Task 3: Implement structured logging

<read_first>
utils/logging_config.py
main.py
</read_first>

<action>
Refactor logging to use structured format:

1. In utils/logging_config.py, add JSON formatter option
2. Add request ID generation and context
3. Add correlation ID support (pass through context)
4. Add stack trace inclusion for ERROR and CRITICAL levels
5. Add custom fields: function, line, module
6. Update log format to include structured fields
7. Add LOG_FORMAT config option (text vs json)
8. In main.py, set request ID at entry point
</action>

<acceptance_criteria>
utils/logging_config.py has JSON formatter option
utils/logging_config.py generates request IDs
utils/logging_config.py includes stack traces for errors
config.py has LOG_FORMAT setting
main.py sets request ID at startup
</acceptance_criteria>

### Task 4: Add log rotation

<read_first>
utils/logging_config.py
config.py
</read_first>

<action>
Implement log rotation to prevent uncontrolled growth:

1. In utils/logging_config.py, use RotatingFileHandler
2. Configure rotation: maxBytes=10MB, backupCount=5
3. Add LOG_MAX_BYTES config option (default 10485760)
4. Add LOG_BACKUP_COUNT config option (default 5)
5. Add timestamp to backup filenames
6. Compress old log files if possible
7. Add log cleanup on startup (delete logs older than 30 days)
</action>

<acceptance_criteria>
utils/logging_config.py uses RotatingFileHandler
utils/logging_config.py has maxBytes=10485760
utils/logging_config.py has backupCount=5
config.py has LOG_MAX_BYTES setting
config.py has LOG_BACKUP_COUNT setting
</acceptance_criteria>

### Task 5: Filter sensitive data from logs

<read_first>
utils/logging_config.py
config.py
</read_first>

<action>
Add sensitive data filtering from logs:

1. In utils/logging_config.py, create sensitive data filter
2. Filter patterns: API keys, passwords, tokens, secrets
3. Use regex to replace with ***REDACTED***
4. Add SENSITIVE_PATTERNS config option (list of regex patterns)
5. Apply filter to all log messages
6. Apply filter to Sentry events
7. Test filtering with sample data
</action>

<acceptance_criteria>
utils/logging_config.py has sensitive data filter
utils/logging_config.py replaces API keys with ***REDACTED***
config.py has SENSITIVE_PATTERNS setting
</acceptance_criteria>

### Task 6: Add health check endpoint

<read_first>
main.py
database/db.py
</read_first>

<action>
Add health check CLI command and endpoint:

1. In main.py, add health-check subcommand
2. Health check checks:
   - Database connection (call db.health_check())
   - Configuration validity (call settings.validate())
   - Log file writability
   - AI API availability (optional, with timeout)
3. Return status code 0 if healthy, 1 if unhealthy
4. Output JSON with status and component details
5. Add HEALTH_CHECK_TIMEOUT config option (default 5s)
</action>

<acceptance_criteria>
main.py has health-check subcommand
main.py health-check calls db.health_check()
main.py health-check calls settings.validate()
main.py health-check outputs JSON status
config.py has HEALTH_CHECK_TIMEOUT setting
</acceptance_criteria>

### Task 7: Configure alert severity levels

<read_first>
utils/logging_config.py
config.py
</read_first>

<action>
Implement severity-based alerting:

1. In utils/logging_config.py, add alert handler
2. Map log levels to alert severity:
   - CRITICAL -> high
   - ERROR -> medium
   - WARNING -> low
3. Add ALERT_MIN_LEVEL config option (default ERROR)
4. Only send alerts for levels >= ALERT_MIN_LEVEL
5. Add alert deduplication (same alert once per hour)
6. Add ALERT_ENABLED config option (default true)
</action>

<acceptance_criteria>
utils/logging_config.py has alert handler
utils/logging_config.py maps CRITICAL to high severity
utils/logging_config.py maps ERROR to medium severity
config.py has ALERT_MIN_LEVEL setting
config.py has ALERT_ENABLED setting
</acceptance_criteria>

### Task 8: Aggregate related alerts

<read_first>
utils/logging_config.py
</read_first>

<action>
Implement alert aggregation to prevent fatigue:

1. In utils/logging_config.py, add alert aggregator
2. Group alerts by: error type, source location, context
3. Send aggregated alert every 5 minutes (configurable)
4. Include count of occurrences in aggregated alert
5. Add ALERT_AGGREGATION_WINDOW config option (default 300s)
6. Add ALERT_AGGREGATION_ENABLED config option (default true)
7. Reset aggregation after sending
</action>

<acceptance_criteria>
utils/logging_config.py has alert aggregator
utils/logging_config.py groups alerts by error type
utils/logging_config.py sends aggregated alerts
config.py has ALERT_AGGREGATION_WINDOW setting
config.py has ALERT_AGGREGATION_ENABLED setting
</acceptance_criteria>

### Task 9: Track scraping metrics

<read_first>
scrapers/*.py
database/models.py
</read_first>

<action>
Add scraping success/failure rate tracking:

1. In scrapers, track: listings attempted, succeeded, failed
2. Log metrics after each scrape operation
3. Add to ScrapingLog: success_count, failure_count, success_rate
4. Calculate success_rate = success_count / (success_count + failure_count)
5. Add SCRAPING_METRICS_ENABLED config option (default true)
6. Log success_rate below threshold as WARNING
7. Add SCRAPING_SUCCESS_THRESHOLD config option (default 0.8)
</action>

<acceptance_criteria>
scrapers track listings attempted, succeeded, failed
scrapers log success_rate after scrape
database/models.py has success_count in ScrapingLog
database/models.py has failure_count in ScrapingLog
database/models.py has success_rate in ScrapingLog
config.py has SCRAPING_METRICS_ENABLED setting
config.py has SCRAPING_SUCCESS_THRESHOLD setting
</acceptance_criteria>

### Task 10: Track AI API metrics

<read_first>
ai_agent/*.py
</read_first>

<action>
Add AI API latency and failure tracking:

1. In ai_agent modules, track: API call duration, success, failure
2. Log metrics after each API call
3. Add to AIReview: api_latency_ms, api_success
4. Calculate average latency per API type
5. Log API calls exceeding latency threshold
6. Add AI_METRICS_ENABLED config option (default true)
7. Add AI_LATENCY_THRESHOLD_MS config option (default 5000)
8. Add AI_FAILURE_ALERT_THRESHOLD config option (default 0.2)
</action>

<acceptance_criteria>
ai_agent tracks API call duration
ai_agent logs API latency
ai_agent tracks API success/failure
database/models.py has api_latency_ms in AIReview
database/models.py has api_success in AIReview
config.py has AI_METRICS_ENABLED setting
config.py has AI_LATENCY_THRESHOLD_MS setting
</acceptance_criteria>

### Task 11: Track scheduler metrics

<read_first>
scheduler/daily_job.py
</read_first>

<action>
Add scheduler job execution time tracking:

1. In scheduler, track: job start time, end time, duration
2. Log metrics after each job execution
3. Add to ScrapingLog: job_duration_seconds
4. Calculate average job duration
5. Log jobs exceeding duration threshold
6. Add SCHEDULER_METRICS_ENABLED config option (default true)
7. Add SCHEDULER_DURATION_THRESHOLD_SECONDS config option (default 3600)
</action>

<acceptance_criteria>
scheduler tracks job start and end time
scheduler logs job duration
database/models.py has job_duration_seconds in ScrapingLog
config.py has SCHEDULER_METRICS_ENABLED setting
config.py has SCHEDULER_DURATION_THRESHOLD_SECONDS setting
</acceptance_criteria>

### Task 12: Upgrade code quality tools

<read_first>
requirements.txt
</read_first>

<action>
Upgrade code quality tools to latest versions:

1. Update black from 23.12.1 to 24.1.1 in requirements.txt
2. Update flake8 from 7.0.0 to 7.1.0 in requirements.txt
3. Update mypy from 1.8.0 to 1.9.0 in requirements.txt
4. Run pip install -r requirements.txt to install upgrades
5. Test black on codebase: black --check .
6. Test flake8 on codebase: flake8 .
7. Test mypy on codebase: mypy .
</action>

<acceptance_criteria>
requirements.txt has black==24.1.1
requirements.txt has flake8==7.1.0
requirements.txt has mypy==1.9.0
black --check passes
flake8 passes
mypy passes
</acceptance_criteria>

### Task 13: Add type hints to functions

<read_first>
scrapers/*.py
ai_agent/*.py
valuation/*.py
database/*.py
</read_first>

<action>
Add type hints to all functions:

1. Add type hints to function parameters
2. Add return type hints to all functions
3. Use typing module for complex types (List, Dict, Optional, Union)
4. Add type hints to class methods
5. Add type hints to module-level functions
6. Run mypy to verify type hints
7. Fix any type errors
8. Add from __future__ import annotations to all files (Python 3.12)
</action>

<acceptance_criteria>
scrapers/*.py have type hints on all functions
ai_agent/*.py have type hints on all functions
valuation/*.py have type hints on all functions
database/*.py have type hints on all functions
mypy passes without errors
</acceptance_criteria>

### Task 14: Enable mypy strict mode

<read_first>
mypy.ini or pyproject.toml or setup.cfg
</read_first>

<action>
Enable mypy strict mode for type checking:

1. Create or update mypy.ini configuration file
2. Set strict = true in [mypy] section
3. Add ignore_missing_imports = true for third-party packages
4. Add exclude directives for tests if needed
5. Add warn_return_any = true
6. Add warn_unused_configs = true
7. Run mypy to verify strict mode
8. Fix any new type errors
9. Add mypy to CI/CD pipeline
</action>

<acceptance_criteria>
mypy.ini exists
mypy.ini has strict = true
mypy.ini has ignore_missing_imports = true
mypy passes in strict mode
</acceptance_criteria>

## Verification Criteria

- [ ] Sentry initialized and sending error reports
- [ ] Structured logging with context implemented
- [ ] Log rotation prevents uncontrolled growth
- [ ] Sensitive data filtered from logs
- [ ] Health check endpoint functional
- [ ] Alerts use severity levels
- [ ] Related alerts aggregated
- [ ] Scraping success/failure rates tracked
- [ ] AI API latency and failures tracked
- [ ] Scheduler execution times tracked
- [ ] Code quality tools upgraded
- [ ] Type hints added to all functions
- [ ] mypy strict mode enabled
- [ ] Existing functionality preserved

## Must Haves

- Sentry captures and reports errors
- Logs are structured and include context
- Log files rotate and don't grow unbounded
- Sensitive data never appears in logs
- Health check can verify system status
- Alerts are actionable and not overwhelming
- Metrics provide visibility into system health
- Code quality tools are up-to-date
- Type checking is strict and enforced
