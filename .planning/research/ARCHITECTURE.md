# Architecture Research

**Analysis Date:** 2026-04-13

## Current Architecture (from codebase map)

**Pattern:** Monolithic CLI Application with Scheduled Jobs

**Layers:**
- CLI Layer (main.py) - Entry point, command routing
- Scraper Layer (scrapers/*.py) - Web scraping
- Database Layer (database/*.py) - Data persistence
- Valuation Layer (valuation/*.py) - ML model
- AI Agent Layer (ai_agent/*.py) - AI analysis
- Scheduler Layer (scheduler/*.py) - Job automation
- Dashboard Layer (dashboard/*.py) - Web UI
- Utility Layer (utils/*.py) - Shared helpers

## Architectural Improvements for Technical Debt

### Component Boundaries

**Validation Layer (New):**
- Purpose: Validate all inputs before processing
- Contains: Pydantic models, validators
- Location: validation/ or models/validators.py
- Depends on: pydantic, existing data structures
- Used by: CLI layer, scraper layer, AI agent layer

**Testing Layer (New):**
- Purpose: Test infrastructure and fixtures
- Contains: Test factories, fixtures, mocks
- Location: tests/ (with subdirectories: unit/, integration/, e2e/)
- Depends on: pytest, pytest-mock, factory-boy
- Used by: Development workflow

**Monitoring Layer (New):**
- Purpose: Error tracking and observability
- Contains: Sentry integration, metrics collectors
- Location: monitoring/ or utils/monitoring.py
- Depends on: sentry-sdk, logging infrastructure
- Used by: All layers (cross-cutting)

**Migration Layer (New):**
- Purpose: Database schema versioning
- Contains: Alembic migrations
- Location: migrations/ (Alembic standard)
- Depends on: Alembic, SQLAlchemy models
- Used by: Database layer (initialization)

### Data Flow Enhancements

**Current Flow:** Scrape → Save → Train → Valuate → Find Deals → Notify

**Enhanced Flow with Validation:**
Scrape → Validate → Save → Train → Valuate → Find Deals → Validate Output → Notify

**Enhanced Flow with Retry:**
Scrape → [Retry on failure] → Validate → Save → Train → [Retry on insufficient data] → Valuate → Find Deals → Validate Output → Notify

**Enhanced Flow with Caching:**
Check Cache → [Hit] → Return → [Miss] → Scrape → Validate → Save → Update Cache

### Build Order for Improvements

**Phase 1 (Foundation - No Breaking Changes):**
1. Add validation layer (doesn't affect existing flow)
2. Add monitoring layer (cross-cutting, non-blocking)
3. Add retry decorators (wraps existing functions)
4. Add test infrastructure (parallel to production code)

**Phase 2 (Database - Requires Care):**
1. Configure Alembic (initial setup)
2. Create initial migration from existing schema
3. Test migration on copy of database
4. Deploy migration to production

**Phase 3 (Performance - Optimizations):**
1. Enable Redis (configuration change)
2. Add caching decorators (wraps queries)
3. Optimize database queries (eager loading)
4. Benchmark and validate improvements

### Integration Points

**Validation Integration:**
- CLI: Validate argparse arguments with pydantic
- Scrapers: Validate scraped data before database save
- Database: Validate model data before commit
- AI Agent: Validate LLM responses before use

**Monitoring Integration:**
- All layers: Structured logging with context
- Scrapers: Track scraping success/failure rates
- Database: Track query performance
- AI Agent: Track API call latency and failures
- Scheduler: Track job execution times

**Testing Integration:**
- Scrapers: Mock Playwright and HTML responses
- Database: Use in-memory SQLite for tests
- AI Agent: Mock LLM responses
- Scheduler: Mock time for job triggers

**Migration Integration:**
- Database: Alembic hooks into SQLAlchemy
- Models: No changes needed, Alembic reads models
- Deployment: Migration step in Docker startup

### Component Communication

**Current:** Direct function calls between layers

**Enhanced:** Add interfaces where beneficial:
- Validation: Decorator pattern (@validate_input)
- Retry: Decorator pattern (@retry)
- Caching: Decorator pattern (@cache)
- Monitoring: Context manager pattern (with monitor())

### Data Flow Direction

**Current:** Linear flow through layers

**Enhanced:** Add feedback loops:
- Validation failures → Log and skip (don't break flow)
- Retry failures → Exponential backoff, then fail
- Cache misses → Fetch and populate cache
- Monitoring alerts → Trigger notifications

### Architectural Patterns to Apply

**Dependency Injection:**
- Pass database session to functions (already done with context manager)
- Pass AI client to functions (currently global in config)
- Pass logger to functions (currently global)

**Repository Pattern (Optional):**
- Encapsulate database queries in repository classes
- Benefits: Easier testing, cleaner separation
- Trade-off: More boilerplate code

**Factory Pattern (For Testing):**
- Factory-boy for test data creation
- Reduces test setup code
- Makes tests more maintainable

**Strategy Pattern (For Scrapers):**
- Already implemented (different scraper classes)
- Good pattern, keep as-is

**Observer Pattern (For Monitoring):**
- Event-based logging
- Decouples monitoring from business logic
- Consider for complex monitoring needs

### Anti-Patterns to Avoid

**God Objects:**
- Avoid putting everything in one class
- Keep layers focused on single responsibility

**Circular Dependencies:**
- Watch for import cycles when adding new layers
- Use dependency injection to break cycles

**Tight Coupling:**
- Avoid hard-coding external service URLs
- Use configuration for all external dependencies

**Global State:**
- Reduce reliance on global variables
- Pass dependencies explicitly where possible

### Scalability Considerations

**Current Scaling Limits:**
- SQLite: Single writer, no horizontal scaling
- Playwright: One browser per scraper, memory intensive
- Grok API: Rate limits
- No caching: Every query hits database

**Scaling Path:**
1. PostgreSQL for database (already supported)
2. Redis for caching (already supported)
3. Distributed scraping (queue system)
4. API rate limiting (request queuing)
5. Horizontal scaling (container orchestration)

### Migration Strategy

**Zero-Downtime Migrations:**
- Use Alembic's transactional migrations
- Test migrations on staging first
- Have rollback plan ready
- Monitor for errors post-deployment

**Backward Compatibility:**
- Keep old fields during migration
- Migrate data in separate step
- Drop old fields after validation
- Version API responses if needed
