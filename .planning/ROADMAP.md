# Roadmap

**Project:** AutoDeal IA Hunter
**Milestone:** v2.0 Quality & Observability
**Created:** 2026-04-14

## Overview

This roadmap addresses quality and observability improvements through four focused phases:
1. **Code Quality** - Add type hints to all functions
2. **Testing** - Comprehensive test coverage
3. **Observability** - Metrics tracking
4. **Reliability** - Rate limiting and database backups

Each phase builds on the previous, following a logical order from foundational quality improvements to advanced monitoring and reliability features.

---

## Phase 1: Code Quality

**Goal:** Add type hints to all functions and ensure mypy strict mode compliance

**Duration:** 1-2 weeks

### Plans

**1.1 Type Hints for Core Modules**
- Add type hints to scrapers directory functions
- Add type hints to database directory functions
- Add type hints to ai_agent directory functions
- Add type hints to valuation directory functions
- Add type hints to utils directory functions
- Requirements: QUAL-01 through QUAL-05

**1.2 Type Hints for Entry Points**
- Add type hints to config.py
- Add type hints to main.py
- Add type hints to scheduler directory functions
- Requirements: QUAL-06 through QUAL-08

**1.3 mypy Strict Mode Compliance**
- Run mypy strict mode on entire codebase
- Fix all type errors
- Achieve 100% type coverage
- Requirements: QUAL-09 through QUAL-10

**Dependencies:** None (can start immediately)
**Blocks:** Phase 2 (type hints needed before writing type-safe tests)

---

## Phase 2: Testing

**Goal:** Achieve 70%+ test coverage with comprehensive unit and integration tests

**Duration:** 2-3 weeks

### Plans

**2.1 Scraper Unit Tests**
- Unit tests for OLX scraper with mocked Playwright
- Unit tests for Standvirtual scraper with mocked Playwright
- Unit tests for AutoSapo scraper with mocked Playwright
- Requirements: TEST-01 through TEST-03

**2.2 ML Model Tests**
- Unit tests for ML model training pipeline with mock data
- Unit tests for XGBoost model prediction with mock model
- Requirements: TEST-04 through TEST-05

**2.3 AI Agent Tests**
- Unit tests for AI agent deal finder with mocked LLM
- Unit tests for AI agent valuation with mocked LLM
- Requirements: TEST-06 through TEST-07

**2.4 Database Integration Tests**
- Integration tests for database models
- Integration tests for database CRUD operations
- Requirements: TEST-08 through TEST-09

**2.5 Scheduler Tests**
- Integration tests for scheduler job execution
- Integration tests for APScheduler configuration
- Requirements: TEST-10 through TEST-11

**2.6 CI Integration**
- Achieve 70% test coverage
- Ensure all tests pass in CI pipeline
- Requirements: TEST-12 through TEST-13

**Dependencies:** Phase 1 (type hints needed for type-safe test code)
**Blocks:** Phase 3 (tests provide foundation for metrics instrumentation)

---

## Phase 3: Observability

**Goal:** Implement metrics tracking for scraping, AI API, and scheduler operations

**Duration:** 2-3 weeks

### Plans

**3.1 Scraping Metrics**
- Track listings scraped per minute per source
- Track scraping success rate per source
- Track scraping errors with error types
- Store metrics in database
- Requirements: OBS-01 through OBS-03, OBS-11

**3.2 AI API Metrics**
- Track response time per API call
- Track token usage per API call
- Track estimated cost per API call
- Track API error rate
- Requirements: OBS-04 through OBS-07

**3.3 Scheduler Metrics**
- Track job duration per job type
- Track job success rate per job type
- Track job failure rate with error types
- Requirements: OBS-08 through OBS-10

**3.4 Metrics Visualization**
- Make metrics accessible via dashboard
- Enable metrics export for external monitoring
- Requirements: OBS-12 through OBS-13

**Dependencies:** Phase 2 (tests provide stable codebase for instrumentation)
**Blocks:** Phase 4 (metrics provide data for rate limiting decisions)

---

## Phase 4: Reliability

**Goal:** Implement rate limiting for API calls and automated database backups

**Duration:** 1-2 weeks

### Plans

**4.1 Rate Limiting**
- Implement rate limiting for Grok API calls
- Implement rate limiting for Ollama API calls
- Respect API provider limits and quotas
- Provide backoff and retry for rate-limited requests
- Requirements: REL-01 through REL-04

**4.2 Database Backups**
- Configure automated daily database backups
- Retain last 7 days of backups
- Store backups in configured location
- Test and document backup restoration
- Requirements: REL-05 through REL-08

**4.3 Backup Monitoring**
- Trigger alerts on backup failures
- Log backup success/failure status
- Requirements: REL-09 through REL-10

**Dependencies:** Phase 3 (metrics inform rate limiting thresholds)
**Blocks:** None (final phase)

---

## Phase Summary

| Phase | Plans | Duration | Status |
|-------|-------|----------|--------|
| Phase 1: Code Quality | 3 | 1-2 weeks | Pending |
| Phase 2: Testing | 6 | 2-3 weeks | Pending |
| Phase 3: Observability | 4 | 2-3 weeks | Pending |
| Phase 4: Reliability | 3 | 1-2 weeks | Pending |

**Total Duration:** 6-10 weeks

---

## Execution Order

1. **Phase 1.1** - Type Hints for Core Modules (no dependencies)
2. **Phase 1.2** - Type Hints for Entry Points (no dependencies)
3. **Phase 1.3** - mypy Strict Mode Compliance (depends on 1.1, 1.2)
4. **Phase 2.1** - Scraper Unit Tests (depends on Phase 1)
5. **Phase 2.2** - ML Model Tests (depends on Phase 1)
6. **Phase 2.3** - AI Agent Tests (depends on Phase 1)
7. **Phase 2.4** - Database Integration Tests (depends on Phase 1)
8. **Phase 2.5** - Scheduler Tests (depends on Phase 1)
9. **Phase 2.6** - CI Integration (depends on 2.1-2.5)
10. **Phase 3.1** - Scraping Metrics (depends on Phase 2)
11. **Phase 3.2** - AI API Metrics (depends on Phase 2)
12. **Phase 3.3** - Scheduler Metrics (depends on Phase 2)
13. **Phase 3.4** - Metrics Visualization (depends on 3.1-3.3)
14. **Phase 4.1** - Rate Limiting (depends on Phase 3)
15. **Phase 4.2** - Database Backups (no dependencies)
16. **Phase 4.3** - Backup Monitoring (depends on 4.2)

---

## Parallel Execution

**Within Phase 1:** Plans 1.1 and 1.2 can run in parallel (no dependencies)

**Within Phase 2:** Plans 2.1, 2.2, 2.3 can run in parallel after Phase 1 completes. Plans 2.4 and 2.5 can run in parallel after Phase 1 completes. Plan 2.6 depends on all previous Phase 2 plans.

**Within Phase 3:** Plans 3.1, 3.2, 3.3 can run in parallel after Phase 2 completes. Plan 3.4 depends on 3.1-3.3.

**Within Phase 4:** Plan 4.2 can run in parallel with 4.1. Plan 4.3 depends on 4.2.

---

## Risk Mitigation

**Phase 1 Risks:**
- Type hints may reveal hidden type errors in existing code
  - Mitigation: Address errors incrementally, prioritize critical paths
- mypy strict mode may be too restrictive for some dynamic code
  - Mitigation: Use `# type: ignore` sparingly with comments explaining why

**Phase 2 Risks:**
- Test coverage target may be difficult to achieve
  - Mitigation: Focus on critical paths first, accept 65% if 70% not feasible
- Mocking Playwright may be complex
  - Mitigation: Use pytest-playwright plugin for easier mocking

**Phase 3 Risks:**
- Metrics storage may impact database performance
  - Mitigation: Use time-series database or separate metrics table with proper indexing
- Metrics visualization may require significant dashboard work
  - Mitigation: Start with simple charts, iterate based on user feedback

**Phase 4 Risks:**
- Rate limiting may affect legitimate usage
  - Mitigation: Make limits configurable, monitor metrics to tune thresholds
- Database backups may fail due to storage constraints
  - Mitigation: Monitor backup storage, implement cleanup of old backups

---

## Success Criteria

**Phase 1 Complete:**
- [ ] All functions have type hints
- [ ] mypy strict mode passes without errors
- [ ] Type coverage reaches 100%

**Phase 2 Complete:**
- [ ] Unit tests for scrapers, ML model, AI agent
- [ ] Integration tests for database and scheduler
- [ ] Test coverage reaches 70% or higher
- [ ] All tests pass in CI pipeline

**Phase 3 Complete:**
- [ ] Scraping metrics tracked and visualized
- [ ] AI API metrics tracked and visualized
- [ ] Scheduler metrics tracked and visualized
- [ ] Metrics stored for historical analysis

**Phase 4 Complete:**
- [ ] Rate limiting implemented for Grok and Ollama
- [ ] Automated daily database backups configured
- [ ] Backup restoration tested and documented
- [ ] Backup failures trigger alerts

---

*Last updated: 2026-04-14*
