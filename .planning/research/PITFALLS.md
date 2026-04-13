# Pitfalls Research

**Analysis Date:** 2026-04-13

## Domain: Python ML/Web Scraping Project with Technical Debt

### Common Mistakes in Testing

**Pitfall 1: Testing Implementation Details**
- **Warning Sign:** Tests mock internal functions, not public interfaces
- **Prevention:** Test behavior, not implementation. Use black-box testing where possible.
- **Phase to Address:** Phase 2 (Testing infrastructure)

**Pitfall 2: Brittle Scraping Tests**
- **Warning Sign:** Tests break when HTML structure changes slightly
- **Prevention:** Use CSS selectors that are semantic, not position-dependent. Mock HTML responses in tests.
- **Phase to Address:** Phase 2 (Testing infrastructure)

**Pitfall 3: Database State Leaks Between Tests**
- **Warning Sign:** Tests pass individually but fail in suite
- **Prevention:** Use fresh database for each test (in-memory SQLite), proper teardown in fixtures.
- **Phase to Address:** Phase 2 (Testing infrastructure)

**Pitfall 4: Mocking Everything**
- **Warning Sign:** Tests don't catch integration issues
- **Prevention:** Mock only external dependencies (APIs, file system). Test real database operations.
- **Phase to Address:** Phase 2 (Testing infrastructure)

### Common Mistakes in Validation

**Pitfall 5: Validation After Database Insert**
- **Warning Sign:** Invalid data enters database, validation catches it too late
- **Prevention:** Validate before database operations. Use pydantic models at input boundaries.
- **Phase to Address:** Phase 1 (Validation layer)

**Pitfall 6: Overly Strict Validation**
- **Warning Sign:** Valid data rejected because rules are too rigid
- **Prevention:** Make validation configurable. Allow overrides for edge cases.
- **Phase to Address:** Phase 1 (Validation layer)

**Pitfall 7: Silent Validation Failures**
- **Warning Sign:** Invalid data silently skipped or defaulted
- **Prevention:** Log validation failures with context. Alert on systematic issues.
- **Phase to Address:** Phase 1 (Validation layer + Monitoring)

### Common Mistakes in Migrations

**Pitfall 8: Breaking Existing Data**
- **Warning Sign:** Migration causes data loss or corruption
- **Prevention:** Test migrations on production data copy. Use transactional migrations. Have rollback plan.
- **Phase to Address:** Phase 2 (Database migrations)

**Pitfall 9: Non-Reversible Migrations**
- **Warning Sign:** Can't rollback after migration
- **Prevention:** Write downgrade migrations. Test rollback path.
- **Phase to Address:** Phase 2 (Database migrations)

**Pitfall 10: Migration in Production Without Staging Test**
- **Warning Sign:** Production migration fails, system down
- **Prevention:** Always test on staging first. Run migration in dry-run mode.
- **Phase to Address:** Phase 2 (Database migrations)

### Common Mistakes in Retry Logic

**Pitfall 11: Infinite Retry Loops**
- **Warning Sign:** Process hangs forever on persistent failure
- **Prevention:** Set max retry attempts. Use exponential backoff with jitter.
- **Phase to Address:** Phase 1 (Retry logic)

**Pitfall 12: Retrying Non-Idempotent Operations**
- **Warning Sign:** Duplicate data created on retry
- **Prevention:** Ensure operations are idempotent. Use deduplication logic.
- **Phase to Address:** Phase 1 (Retry logic)

**Pitfall 13: No Retry on Transient Errors**
- **Warning Sign:** System fails on temporary network issues
- **Prevention:** Retry on specific error types (network timeouts, rate limits). Don't retry on logic errors.
- **Phase to Address:** Phase 1 (Retry logic)

### Common Mistakes in Monitoring

**Pitfall 14: Logging Everything**
- **Warning Sign:** Log files grow uncontrollably, performance degradation
- **Prevention:** Log at appropriate levels. Implement log rotation. Filter sensitive data.
- **Phase to Address:** Phase 1 (Monitoring)

**Pitfall 15: No Context in Logs**
- **Warning Sign:** Errors logged without enough information to debug
- **Prevention:** Include request ID, user context, stack traces. Use structured logging.
- **Phase to Address:** Phase 1 (Monitoring)

**Pitfall 16: Alert Fatigue**
- **Warning Sign:** Too many alerts, teams ignore them
- **Prevention:** Alert only on actionable issues. Use severity levels. Aggregate related alerts.
- **Phase to Address:** Phase 1 (Monitoring)

### Common Mistakes in Caching

**Pitfall 17: Cache Invalidation Issues**
- **Warning Sign:** Stale data served to users
- **Prevention:** Use TTL (time-to-live). Implement cache invalidation on data updates. Document cache strategy.
- **Phase to Address:** Phase 3 (Caching)

**Pitfall 18: Cache Stampede**
- **Warning Sign:** Multiple processes refresh cache simultaneously
- **Prevention:** Use cache locking. Implement stale-while-revalidate pattern.
- **Phase to Address:** Phase 3 (Caching)

**Pitfall 19: Caching Everything**
- **Warning Sign:** Memory exhaustion, low cache hit rate
- **Prevention:** Cache only expensive queries. Monitor cache hit rate. Evict least recently used.
- **Phase to Address:** Phase 3 (Caching)

### Common Mistakes in AI/ML Integration

**Pitfall 20: No Fallback for AI Failures**
- **Warning Sign:** System crashes when AI API is down
- **Prevention:** Implement fallback to local Ollama. Graceful degradation without AI.
- **Phase to Address:** Phase 1 (Retry logic + Monitoring)

**Pitfall 21: Not Retraining Model**
- **Warning Sign:** Model performance degrades over time
- **Prevention:** Schedule regular retraining. Monitor model metrics. Automate retraining pipeline.
- **Phase to Address:** Phase 3 (Optimization)

**Pitfall 22: No Model Versioning**
- **Warning Sign:** Can't rollback bad model deployment
- **Prevention:** Version model artifacts. Track model performance per version. Keep previous versions.
- **Phase to Address:** Phase 3 (Optimization)

### Common Mistakes in Scraping

**Pitfall 23: Aggressive Scraping**
- **Warning Sign:** IP blocked, legal issues
- **Prevention:** Respect robots.txt. Use rate limiting. Randomize request timing. Implement backoff.
- **Phase to Address:** Phase 1 (Retry logic)

**Pitfall 24: Scraping Without Consent**
- **Warning Sign:** Legal action, terms of service violation
- **Prevention:** Check terms of service. Use official APIs if available. Attribute data sources.
- **Phase to Address:** Ongoing (operational practice)

**Pitfall 25: No Error Handling for Scraping**
- **Warning Sign:** Single bad listing crashes entire scrape
- **Prevention:** Catch errors per listing. Log failures. Continue with other listings.
- **Phase to Address:** Phase 1 (Error handling)

### Common Mistakes in Database Operations

**Pitfall 26: N+1 Query Problem**
- **Warning Sign:** Performance degrades with data volume
- **Prevention:** Use eager loading (joinedload, selectinload). Monitor query patterns.
- **Phase to Address:** Phase 3 (Performance)

**Pitfall 27: Not Using Transactions**
- **Warning Sign:** Partial data updates on failure
- **Prevention:** Always use transactions for multi-step operations. Rollback on error.
- **Phase to Address:** Phase 2 (Database best practices)

**Pitfall 28: No Connection Pooling**
- **Warning Sign:** Database connection exhaustion
- **Prevention:** Configure connection pool (already done with QueuePool). Monitor pool usage.
- **Phase to Address:** Phase 3 (Performance)

### Common Mistakes in Configuration

**Pitfall 29: Hardcoded Configuration**
- **Warning Sign:** Can't change settings without code deployment
- **Prevention:** Use environment variables. Provide .env.example. Document all config options.
- **Phase to Address:** Already done (good practice maintained)

**Pitfall 30: No Configuration Validation**
- **Warning Sign:** Application starts with invalid config, fails at runtime
- **Prevention:** Validate configuration at startup using pydantic-settings. Fail fast on invalid config.
- **Phase to Address:** Phase 1 (Validation)

### Domain-Specific Pitfalls

**Pitfall 31: Brand/Model Parsing Fragility**
- **Warning Sign:** New vehicle brands not recognized, parsing fails
- **Prevention:** Use external vehicle database API. Implement fuzzy matching. Log unrecognized patterns.
- **Phase to Address:** Phase 2 (Data quality)

**Pitfall 32: Price Prediction Drift**
- **Warning Sign:** Model predictions become inaccurate over time
- **Prevention:** Monitor prediction accuracy vs actual prices. Retrain on schedule. Track feature importance changes.
- **Phase to Address:** Phase 3 (ML monitoring)

**Pitfall 33: Deal Score Gaming**
- **Warning Sign:** Sellers manipulate listings to get high scores
- **Prevention:** Use multiple factors for scoring. Detect anomalous patterns. Manual review for top deals.
- **Phase to Address:** Ongoing (operational practice)

## Prevention Strategies Summary

**Testing:**
- Use test factories for data creation
- Mock only external dependencies
- Test behavior, not implementation
- Fresh database per test
- Integration tests for critical paths

**Validation:**
- Validate at input boundaries
- Make validation configurable
- Log validation failures
- Alert on systematic issues

**Migrations:**
- Test on staging first
- Use transactional migrations
- Write downgrade migrations
- Have rollback plan

**Retry:**
- Set max retry attempts
- Use exponential backoff
- Retry only transient errors
- Ensure idempotency

**Monitoring:**
- Log at appropriate levels
- Include context in logs
- Alert on actionable issues
- Aggregate related alerts

**Caching:**
- Use TTL for all cached data
- Implement cache invalidation
- Monitor cache hit rate
- Cache only expensive operations

**AI/ML:**
- Implement fallback mechanisms
- Schedule model retraining
- Version model artifacts
- Monitor model performance

**Scraping:**
- Respect rate limits
- Handle errors gracefully
- Use stealth techniques
- Check terms of service
