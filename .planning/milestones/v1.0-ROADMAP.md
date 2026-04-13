# Roadmap

**Project:** AutoDeal IA Hunter
**Created:** 2026-04-13
**Granularity:** Coarse (3-5 phases, 1-3 plans each)

## Overview

This roadmap addresses technical debt in the existing AutoDeal IA Hunter codebase through three focused phases:
1. **Foundation** - Establish validation, retry logic, monitoring, and test infrastructure
2. **Quality** - Comprehensive testing, database migrations, and logging improvements
3. **Optimization** - Caching, query optimization, and performance tuning

Each phase builds on the previous, following the research-recommended build order.

---

## Phase 1: Foundation

**Goal:** Establish core infrastructure for reliability and observability

**Duration:** 1-2 weeks

### Plans

**1.1 Validation Layer**
- Implement pydantic models for CLI argument validation
- Implement pydantic models for scraped data validation
- Add pydantic-settings for configuration validation
- Add validation error logging and alerting
- Requirements: VAL-01 through VAL-08

**1.2 Error Handling & Retry**
- Add tenacity retry decorator with exponential backoff
- Implement retry logic for scraping failures
- Implement retry logic for AI API failures
- Add idempotency checks and deduplication
- Requirements: ERR-01 through ERR-08

**1.3 Monitoring & Code Quality**
- Add sentry-sdk for error tracking
- Implement structured logging with context
- Add log rotation and sensitive data filtering
- Upgrade black, flake8, mypy to latest versions
- Add type hints and enable mypy strict mode
- Requirements: MON-01 through MON-10, QUAL-01 through QUAL-08

**1.4 Test Infrastructure**
- Add pytest-cov, pytest-mock, factory-boy
- Create test fixtures and factories
- Set up CI/CD integration for automated tests
- Requirements: TEST-01 through TEST-03, TEST-10

**Dependencies:** None (can start immediately)
**Blocks:** Phase 2 (needs foundation in place)

---

## Phase 2: Quality

**Goal:** Comprehensive testing and database versioning

**Duration:** 2-3 weeks

### Plans

**2.1 Comprehensive Test Suite**
- Create unit tests for scrapers with mocked Playwright
- Create unit tests for ML model training pipeline
- Create unit tests for AI agent with mocked LLM
- Create integration tests for database models
- Create integration tests for scheduler
- Achieve 70%+ code coverage
- Requirements: TEST-04 through TEST-09

**2.2 Database Migrations**
- Configure Alembic for database migrations
- Create initial migration from existing models
- Write downgrade migrations
- Test migrations on database copy
- Test rollback path
- Add migration step to Docker startup
- Requirements: DB-01 through DB-08

**2.3 Logging Improvements**
- Refactor logging throughout codebase for consistency
- Ensure all database operations use transactions
- Add health check endpoint
- Implement alert severity levels
- Aggregate related alerts
- Requirements: MON-05 through MON-07, DB-08

**Dependencies:** Phase 1 (test infrastructure, monitoring foundation)
**Blocks:** Phase 3 (needs quality foundation for optimization)

---

## Phase 3: Optimization

**Goal:** Performance improvements and caching

**Duration:** 1-2 weeks

### Plans

**3.1 Caching Layer**
- Enable Redis caching
- Add hiredis for performance
- Implement cache decorators for repeated queries
- Set TTL for cached data
- Implement cache invalidation on updates
- Monitor cache hit rate
- Requirements: PERF-01 through PERF-06

**3.2 Query Optimization**
- Fix N+1 query pattern in deal finder
- Optimize database queries with eager loading
- Add proper database indexing
- Configure connection pool settings
- Benchmark performance improvements
- Requirements: PERF-07 through PERF-10

**3.3 Performance Tuning**
- Fix DetachedInstanceError workarounds
- Reduce function complexity
- Extract helper functions
- Final performance validation
- Requirements: QUAL-06 through QUAL-08

**Dependencies:** Phase 2 (needs quality foundation and migrations)
**Blocks:** None (final phase)

---

## Phase Summary

| Phase | Plans | Duration | Status |
|-------|-------|----------|--------|
| Phase 1: Foundation | 4 | 1-2 weeks | Pending |
| Phase 2: Quality | 3 | 2-3 weeks | Pending |
| Phase 3: Optimization | 3 | 1-2 weeks | Pending |

**Total Duration:** 4-7 weeks

---

## Execution Order

1. **Phase 1.1** - Validation Layer (no dependencies)
2. **Phase 1.2** - Error Handling & Retry (no dependencies)
3. **Phase 1.3** - Monitoring & Code Quality (no dependencies)
4. **Phase 1.4** - Test Infrastructure (no dependencies)
5. **Phase 2.1** - Comprehensive Test Suite (depends on 1.4)
6. **Phase 2.2** - Database Migrations (depends on 1.3)
7. **Phase 2.3** - Logging Improvements (depends on 1.3)
8. **Phase 3.1** - Caching Layer (depends on 2.3)
9. **Phase 3.2** - Query Optimization (depends on 2.2)
10. **Phase 3.3** - Performance Tuning (depends on 2.1)

---

## Parallel Execution

**Within Phase 1:** Plans 1.1, 1.2, 1.3, 1.4 can run in parallel (no dependencies)

**Within Phase 2:** Plans 2.1 and 2.2 can run in parallel after Phase 1 completes. Plan 2.3 depends on 1.3 only.

**Within Phase 3:** Plans 3.1 and 3.2 can run in parallel after Phase 2 completes. Plan 3.3 depends on 2.1.

---

## Risk Mitigation

**Phase 1 Risks:**
- Validation changes may break existing data flow
  - Mitigation: Add validation in non-blocking mode initially, log violations
- Sentry integration may expose sensitive data
  - Mitigation: Filter sensitive data before sending to Sentry

**Phase 2 Risks:**
- Test coverage target may be difficult to achieve
  - Mitigation: Focus on critical paths first, accept 60% if 70% not feasible
- Database migrations may fail in production
  - Mitigation: Test thoroughly on staging, have rollback plan ready

**Phase 3 Risks:**
- Caching may cause stale data issues
  - Mitigation: Use conservative TTL, monitor cache effectiveness
- Query optimization may change behavior
  - Mitigation: Thorough testing, benchmark before and after

---

## Success Criteria

**Phase 1 Complete:**
- [ ] Validation layer in place with error logging
- [ ] Retry logic implemented for transient failures
- [ ] Sentry integrated and sending error reports
- [ ] Code quality tools upgraded and passing
- [ ] Test infrastructure set up with CI/CD

**Phase 2 Complete:**
- [ ] 70%+ code coverage achieved
- [ ] Alembic configured and initial migration created
- [ ] All database operations use transactions
- [ ] Logging consistent throughout codebase
- [ ] Health check endpoint functional

**Phase 3 Complete:**
- [ ] Redis caching enabled with 50%+ hit rate
- [ ] N+1 queries eliminated
- [ ] Performance benchmarks show improvement
- [ ] DetachedInstanceError workarounds removed
- [ ] Function complexity reduced

---

## v2 Considerations

After Phase 3 completion, consider v2 requirements:
- Automated database backups
- Advanced monitoring with Prometheus + Grafana
- Distributed scraping with queue system
- ML model retraining pipeline automation
- Dashboard authentication

These are deferred to avoid scope creep in v1.

---

*Last updated: 2026-04-13*
