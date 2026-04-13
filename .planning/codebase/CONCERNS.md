# Codebase Concerns

**Analysis Date:** 2026-04-13 (Updated after Phase 1)

## Tech Debt

**DetachedInstanceError workarounds:**
- Issue: Code converts SQLAlchemy objects to dictionaries before session ends to avoid DetachedInstanceError
- Files: `ai_agent/deal_finder.py` (lines 79-88), `database/models.py` (to_dict method)
- Why: SQLAlchemy session management complexity, objects accessed after session close
- Impact: Extra code complexity, potential performance overhead from serialization
- Fix approach: Implement proper session lifecycle management, use lazy loading correctly, or use session-per-request pattern consistently

**Alembic not configured:**
- Issue: Alembic installed but migrations not set up
- File: `requirements.txt` (alembic==1.13.1)
- Why: Project likely started with SQLite, migrations not prioritized
- Impact: Database schema changes cannot be versioned, no rollback capability, production deployments risky
- Fix approach: Initialize Alembic, create initial migration from existing models, configure migration workflow

**No input validation:**
- Issue: Minimal validation on user inputs (CLI arguments, scraped data)
- Files: `main.py` (argparse without custom validators), scrapers accept scraped data without validation
- Why: Rapid development, assumed trusted sources
- Impact: Invalid data can enter database, potential crashes, security risk
- Fix approach: Add pydantic models for validation, validate scraped data before database insertion
- **RESOLVED in Phase 1:** Added pydantic models for CLI arguments, scraped data, and AI responses in validation/ directory

## Known Bugs

**None documented:**
- No known bugs currently tracked
- Code is in early development stage

## Security Considerations

**Environment variables in .env file:**
- Risk: API keys and secrets stored in plain text .env file
- File: `.env.example` shows required secrets (GROK_API_KEY, DATABASE_URL, etc.)
- Current mitigation: .env in .gitignore, .env.example provided
- Recommendations: Use secret management service (HashiCorp Vault, AWS Secrets Manager) in production, rotate keys regularly

**No authentication/authorization:**
- Risk: No user authentication system, dashboard publicly accessible
- Files: `dashboard/app.py` (Streamlit app without auth)
- Current mitigation: None
- Recommendations: Add Streamlit authentication, or move dashboard behind reverse proxy with auth

**SQL injection risk:**
- Risk: SQLAlchemy ORM used correctly, but raw SQL possible
- File: `database/db.py` (line 87: `conn.execute("SELECT 1")`)
- Current mitigation: Using SQLAlchemy ORM for most queries, raw SQL minimal
- Recommendations: Avoid raw SQL entirely, use SQLAlchemy query builder

**Web scraping without rate limiting:**
- Risk: Scrapers may be blocked by target sites
- Files: `scrapers/standvirtual_scraper.py`, `scrapers/olx_scraper.py`
- Current mitigation: REQUEST_DELAY_SECONDS (default 2s), random user agents
- Recommendations: Implement adaptive rate limiting, respect robots.txt, add proxy rotation

## Performance Bottlenecks

**Playwright browser overhead:**
- Problem: Each scrape launches full browser instance
- Files: `scrapers/standvirtual_scraper.py` (lines 60-93)
- Measurement: ~2-5 seconds per page load, browser startup overhead
- Cause: Full browser automation required for JavaScript-heavy sites
- Improvement path: Use API endpoints if available, cache browser instances, consider headless API-only scrapers

**Database N+1 queries:**
- Problem: Potential N+1 query pattern in deal finder
- File: `ai_agent/deal_finder.py` (lines 43-68)
- Measurement: Not measured, but pattern suggests possible issue
- Cause: Querying vehicles then accessing relationships without eager loading
- Improvement path: Use SQLAlchemy joinedload or selectinload for relationships

**No caching:**
- Problem: No caching layer for repeated queries
- Files: All database queries hit database directly
- Measurement: Every request queries database
- Cause: Redis optional (USE_REDIS=false by default)
- Improvement path: Enable Redis, cache frequent queries (vehicle listings, model predictions)

## Fragile Areas

**Web scrapers (HTML structure dependencies):**
- Files: `scrapers/standvirtual_scraper.py` (lines 153-248), `scrapers/olx_scraper.py`
- Why fragile: Scrapers depend on specific HTML structure, CSS classes, DOM hierarchy
- Common failures: Target site redesigns, class name changes, layout updates
- Safe modification: Add robust error handling, multiple selector strategies, fallback parsing
- Test coverage: No tests for scrapers (high priority gap)

**Brand/model parsing:**
- File: `scrapers/standvirtual_scraper.py` (lines 486-506)
- Why fragile: Hardcoded brand list, simple string splitting
- Common failures: New brands not recognized, non-standard title formats
- Safe modification: Use external vehicle database API, fuzzy matching, ML-based classification
- Test coverage: No tests

**ML model training data quality:**
- File: `valuation/train_model.py` (lines 47-78)
- Why fragile: Depends on scraped data quality, missing values handled with median
- Common failures: Insufficient training data, biased data, outliers skew model
- Safe modification: Add data validation, outlier detection, cross-validation
- Test coverage: No tests for model training

## Scaling Limits

**SQLite for production:**
- Current capacity: SQLite suitable for development, limited concurrency
- Limit: Single write operation at a time, no horizontal scaling
- Symptoms at limit: Database locks, slow writes under concurrent load
- Scaling path: Migrate to PostgreSQL, implement connection pooling

**Playwright browser instances:**
- Current capacity: One browser per scraper, sequential scraping
- Limit: Memory intensive, cannot scale horizontally
- Symptoms at limit: OOM errors, slow scraping with many sources
- Scaling path: Use Playwright in distributed mode, implement queue system, use serverless browsers

**Grok API rate limits:**
- Current capacity: Dependent on xAI API tier
- Limit: API rate limits not documented in code
- Symptoms at limit: 429 errors, failed AI reviews
- Scaling path: Implement request queuing, exponential backoff, fallback to Ollama

## Dependencies at Risk

**Playwright:**
- Risk: Browser automation requires regular updates as browsers change
- Impact: Scrapers may break on browser updates
- Migration plan: Keep Playwright updated, monitor for breaking changes, test scrapers regularly

**OpenAI SDK (for Grok compatibility):**
- Risk: Using OpenAI SDK for Grok API (compatibility layer)
- Files: `requirements.txt` (openai==1.6.1)
- Impact: Grok API changes may break compatibility
- Migration plan: Use official xAI SDK when available, or direct HTTP client

**XGBoost:**
- Risk: Model format may change between versions
- Files: `requirements.txt` (xgboost==2.0.3)
- Impact: Trained models may not load with new XGBoost version
- Migration plan: Version pin model artifacts, retrain on major version changes

## Missing Critical Features

**No backup/restore:**
- Problem: No automated database backups
- Current workaround: Manual database dumps
- Blocks: Cannot recover from data loss, no point-in-time recovery
- Implementation complexity: Low (PostgreSQL pg_dump, SQLite file copy)

**No monitoring/alerting:**
- Problem: No external monitoring, scraping failures silent
- Current workaround: Check logs manually
- Blocks: Cannot detect failures proactively, no alerting on critical issues
- Implementation complexity: Medium (Prometheus + Grafana, or Sentry)
- **RESOLVED in Phase 1:** Added Sentry SDK for error tracking with sensitive data filtering, validation failure tracking and alerting

**No retry mechanism:**
- Problem: Scrapers fail on transient errors without retry
- Files: `scrapers/standvirtual_scraper.py` (MAX_RETRIES=3 but not implemented)
- Current workaround: Manual re-run
- Blocks: Scraping failures require manual intervention
- Implementation complexity: Low (implement retry logic with exponential backoff)
- **RESOLVED in Phase 1:** Added tenacity retry decorators for network, AI API, and database operations in utils/retry.py

**No data validation pipeline:**
- Problem: No validation of scraped data before database insertion
- Current workaround: Trust scraper output
- Blocks: Invalid data enters database, model training on bad data
- Implementation complexity: Medium (pydantic models, validation rules)
- **RESOLVED in Phase 1:** Added pydantic validation models for scraped data, configurable validation rules, and validation failure tracking

## Test Coverage Gaps

**Scrapers:**
- What's not tested: All scraping logic (OLX, Standvirtual, AutoSapo)
- Risk: Scrapers break silently on site changes, data quality degrades
- Priority: High
- Difficulty to test: Medium (need mock HTML responses, Playwright mocking)

**ML model training:**
- What's not tested: Model training pipeline, prediction accuracy
- Risk: Model training fails silently, poor predictions
- Priority: High
- Difficulty to test: High (need test dataset, mock database)

**AI agent:**
- What's not tested: Deal finding logic, LLM integration, vision analysis
- Risk: AI analysis fails, incorrect deal scores
- Priority: High
- Difficulty to test: High (need mock LLM responses, test images)

**Database models:**
- What's not tested: ORM relationships, constraints, migrations
- Risk: Database schema errors, data integrity issues
- Priority: Medium
- Difficulty to test: Low (use in-memory SQLite for tests)

**Scheduler:**
- What's not tested: Daily job execution, trigger logic
- Risk: Scheduler fails silently, jobs don't run
- Priority: Medium
- Difficulty to test: Medium (need time mocking)

**Dashboard:**
- What's not tested: Streamlit app, data visualization
- Risk: Dashboard crashes, incorrect displays
- Priority: Low (user-facing, not critical)
- Difficulty to test: High (Streamlit testing framework immature)

---

*Concerns audit: 2026-04-13*
*Update as issues are fixed or new ones discovered*
