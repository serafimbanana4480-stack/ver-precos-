# Technical Concerns and Debt

## Critical Issues (RESOLVED)

### 0. Circuit Breaker Import Error ✅
**File**: `scrapers/olx_scraper.py`, `scrapers/standvirtual_scraper.py`, `scrapers/autosapo_scraper.py`
**Issue**: Import statements used `_scraping_circuit_breaker` instead of specific circuit breakers
**Impact**: NameError when running scrapers
**Status**: FIXED - Updated imports to use `_olx_circuit_breaker`, `_standvirtual_circuit_breaker`, `_autosapo_circuit_breaker`

### 0.1 Missing asyncio Import ✅
**File**: `scrapers/ai_scraper.py`
**Issue**: Missing `import asyncio` causing NameError when AI scraper fallback is triggered
**Impact**: AI scraper fallback fails completely
**Status**: FIXED - Added `import asyncio` to ai_scraper.py

### 0.2 curl_cffi Invalid Impersonate String ✅
**File**: `scrapers/managed_client.py`
**Issue**: Using invalid impersonate string "chrome120" causing HTTP 404 errors
**Impact**: curl_cffi fallback fails with 404
**Status**: FIXED - Changed impersonate from "chrome120" to "chrome119"

### 0.3 AI-First Scraping Implementation ✅
**Files**: `config.py`, `scrapers/olx_scraper.py`, `scrapers/standvirtual_scraper.py`, `scrapers/autosapo_scraper.py`
**Issue**: AI scraping configured as fallback instead of primary method
**Impact**: AI capabilities underutilized, CSS selectors fragile
**Status**: FIXED - Changed ai_scraper_priority to "primary", modified all scrapers to try AI first with Playwright fallback
**Benefit**: AI extraction now primary method, more resilient to site changes

### 0.4 curl_cffi Enhanced Fetching ✅
**File**: `scrapers/managed_client.py`
**Issue**: Basic curl_cffi implementation with single impersonate string, no retry logic
**Impact**: Lower success rate, no fallback for failed impersonate strings
**Status**: FIXED - Added retry logic with 5 impersonate strings (chrome119, chrome120, chrome124, chrome123, chrome110), enhanced headers for better stealth, 2-second delay between retries
**Benefit**: Higher success rate, better Cloudflare bypass capability

### 1. Duplicate Column Definition 
**File**: `database/models.py`
**Issue**: `deal_score` column defined twice (lines 76 and 103)
**Impact**: SQLAlchemy shadows first definition, causing scale inconsistency (0-10 vs 0-100)
**Status**: FIXED - Removed duplicate at line 103

### 2. Async/Sync Mixing Pattern 
**File**: `main.py`
**Issue**: Conditional asyncio.run() pattern causes event loop issues
**Impact**: Fails in nested async contexts, fragile event loop management
**Status**: FIXED - Made scrape command consistently async with asyncio.run() at entry point only

### 3. Validation Inconsistency 
**File**: `validation/scraped_models.py`
**Issue**: Pydantic validation requires year > 1989, but data_validator allows 1980
**Impact**: Rejects valid Portuguese market vehicles from 1980s
**Status**: FIXED - Aligned to year >= 1980 for both validators

## High Priority Concerns (RESOLVED)

### 4. Shared Circuit Breaker 
**File**: `utils/production_safeguards.py`
**Issue**: All scrapers share same circuit breaker instance
**Impact**: OLX failure opens breaker for Standvirtual too
**Status**: FIXED - Created separate breakers: `_olx_circuit_breaker`, `_standvirtual_circuit_breaker`, `_autosapo_circuit_breaker`

### 5. Brand/Model Encoding 
**File**: `valuation/predict.py`
**Issue**: Uses random hash() for encoding, inconsistent across runs
**Impact**: Same car can have different encodings, inaccurate predictions
**Status**: FIXED - Implemented consistent_hash() with deterministic algorithm (seeded hash)

### 6. In-Memory Deduplication 
**File**: `utils/deduplication.py`
**Issue**: In-memory sets don't work across multiple processes
**Impact**: Deduplication fails in parallel scraping scenarios
**Status**: FIXED - Implemented Redis with in-memory fallback, TTL-based expiration

## Active High-Priority Issues

### 26. OLX Cloudflare Bypass Failure
**File**: `scrapers/session_manager.py`, `scrapers/managed_client.py`
**Issue**: nodriver is not successfully bypassing Cloudflare Turnstile protection on OLX.pt
**Impact**: OLX scraper cannot fetch data, all fallbacks fail (Playwright blocked, nodriver no cf_clearance, curl_cffi 404)
**Status**: ACTIVE - Current nodriver implementation waits 15+ seconds but doesn't get cf_clearance cookie
**Recommendation**: 
- Try undetected-chromedriver as alternative to nodriver
- Use residential proxies
- Consider using managed services (Apify) as primary for OLX
- Increase wait times and add more human-like interactions
**Priority**: HIGH - Blocks OLX scraping completely

## Medium Priority Concerns

### 7. N+1 Query Problem
**File**: `scrapers/standvirtual_scraper.py` save_to_database
**Issue**: Queries database for each listing individually
**Impact**: 50 listings = 50 database queries, poor performance
**Recommendation**: Batch query all URLs first using `Vehicle.url.in_(urls)`
**Priority**: Medium - Performance optimization

### 8. No HTTP Connection Pooling
**File**: Various scrapers
**Issue**: Each HTTP request creates new connections
**Impact**: Slower performance, no connection reuse
**Recommendation**: Use async httpx with connection pooling
**Priority**: Medium - Performance optimization

### 9. Selector Manager Fallback
**File**: `utils/selector_manager.py`
**Issue**: Standvirtual selectors failing 100%
**Impact**: CSS selectors completely unreliable for Standvirtual
**Status**: Mitigated - AI extraction now primary method for Standvirtual
**Priority**: Low - Workaround in place

### 10. Brand/Model Standardization
**File**: Various scrapers
**Issue**: No normalization of brand names (VW vs Volkswagen)
**Impact**: Same brand treated as different, poor ML accuracy
**Recommendation**: Create normalization mapping before ML encoding
**Priority**: Medium - ML accuracy improvement

## Low Priority Concerns

### 11. Missing Error Context
**File**: Various
**Issue**: Error messages lack sufficient debugging context
**Impact**: Difficult to debug issues in production
**Recommendation**: Add URL, source, vehicle_type to error logs
**Status**: Partially addressed - recent logging improvements add context
**Priority**: Low - Nice to have

### 12. No Rate Limiting
**File**: Various scrapers
**Issue**: No rate limiting on scraping requests
**Impact**: Could get IP banned
**Recommendation**: Implement token bucket rate limiter
**Priority**: Medium - Risk mitigation

### 13. AI Scraper Event Loop Fix
**File**: `scrapers/ai_scraper.py`
**Issue**: Event loop management is a band-aid, not proper solution
**Impact**: Root cause (async/sync mixing) addressed in main.py, but fix remains
**Recommendation**: Consider simplifying if no longer needed after main.py fix
**Priority**: Low - Cleanup opportunity

## Architectural Debt

### 14. ML Model Encoding
**File**: `valuation/predict.py`
**Issue**: Using consistent_hash() instead of proper LabelEncoder
**Impact**: Not production-ready for ML, hash is not optimal for categorical encoding
**Recommendation**: Save and load proper LabelEncoder from training
**Priority**: High - ML quality

### 15. Test Coverage Gaps
**File**: tests/
**Issue**: Missing integration tests for Redis, event loop scenarios, new Vehicle fields
**Impact**: Untested critical paths
**Recommendation**: Add Redis integration tests, async event loop tests, Vehicle field tests
**Priority**: Medium - Test quality

### 16. New Vehicle Fields
**File**: database/models.py
**Issue**: New fields (trim_level, has_damage, maintenance_history, aesthetic_score) not fully integrated
**Impact**: Scrapers may not populate these fields, ML model doesn't use them
**Recommendation**: Update scrapers to extract these fields, retrain ML model
**Priority**: Medium - Feature completeness

## External Dependencies

### 17. LLM API Reliability
**Dependency**: Grok API / Ollama
**Issue**: External dependency availability
**Impact**: AI features unavailable if API down
**Mitigation**: Fallback to Ollama, graceful degradation
**Priority**: Low - Has fallbacks

### 18. Managed Service Costs
**Dependency**: Apify, ScraperAPI, ZenRows
**Issue**: Pay-per-use costs
**Impact**: Unexpected costs if overused
**Mitigation**: Monitor usage, set limits
**Priority**: Low - Monitoring needed

### 19. Website Changes
**Dependency**: OLX.pt, Standvirtual, AutoSapo
**Issue**: Website structure changes break scrapers
**Impact**: Scrapers fail until updated
**Mitigation**: AI extraction as fallback, selector manager with fallback
**Priority**: Medium - Operational risk

## Performance Concerns

### 20. Sequential Scraping
**File**: scheduler/daily_job.py
**Issue**: Scrapers run sequentially in loop, not truly parallel
**Impact**: Slower than possible
**Recommendation**: Use asyncio.gather for true parallelism
**Priority**: Medium - Performance improvement

### 21. Large Memory Footprint
**File**: Scrapers with Playwright
**Issue**: Playwright browser instances consume significant memory
**Impact**: Memory pressure in parallel execution
**Recommendation**: Consider headless options, limit concurrent browsers
**Priority**: Low - Resource optimization

## Security Concerns

### 22. API Keys in Logs
**File**: Various
**Issue**: Sentry filter exists but may not be applied to all log outputs
**Impact**: Potential exposure of sensitive data
**Recommendation**: Ensure Sentry filter applied globally, audit log outputs
**Priority**: High - Security

### 23. No Input Sanitization
**File**: Various
**Issue**: User inputs not sanitized before database queries
**Impact**: Potential SQL injection (mitigated by SQLAlchemy ORM)
**Recommendation**: Add input validation, sanitize URLs
**Priority**: Low - ORM provides protection

## Operational Concerns

### 24. No Health Monitoring
**File**: utils/health_check.py
**Issue**: Health check exists but not actively monitored
**Impact**: Outages not detected quickly
**Recommendation**: Set up monitoring alerts for health check endpoint
**Priority**: Medium - Operations

### 25. No Backup Strategy
**File**: database/
**Issue**: No automated database backups
**Impact**: Data loss risk
**Recommendation**: Implement automated backups (pg_dump, WAL archiving)
**Priority**: High - Data safety
