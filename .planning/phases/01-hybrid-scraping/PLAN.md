# Phase 1: Hybrid Scraping Prototype

## Overview
Implement a resilient scraping architecture that combines local Playwright execution with a paid API fallback (ZenRows) for cases where local automation is detected or blocked by Cloudflare.

## 🏁 Acceptance Criteria
- [ ] Unified `HybridScraperClient` implemented in `scrapers/managed_client.py`.
- [ ] Automatic fallback to ZenRows when `403 Forbidden` or "Access Denied" patterns are detected in Playwright.
- [ ] Playwright navigation includes a mandatory 10s "Settle Time" for Turnstile.
- [ ] Integration: `olx_scraper.py` and `standvirtual_scraper.py` migrated to use the `HybridScraperClient`.
- [ ] Configuration: `ZENROWS_API_KEY` added to `config.py` and `.env.example`.

## 🛠️ Implementation Steps

### Step 1: Managed Client Enhancement
- Update `scrapers/managed_client.py` to support ZenRows API.
- Implement a `get_html(url, source)` method that tries Playwright first, then ZenRows.

### Step 2: Detection Logic
- Implement a `detect_blocking(html, response_code)` utility in `utils/error_classifier.py`.
- Patterns to check: Turnstile iframe presence, "Houston, temos um problema", "Access Denied".

### Step 3: Scraper Refactoring
- Update `OLXScraper` and `StandvirtualScraper` to delegate HTML retrieval to the `HybridScraperClient`.
- Ensure Pydantic validation still occurs after retrieval.

## 🧪 Verification Plan
- **Mocked Failure Test**: Simulate a Playwright 403 error and verify that the ZenRows path is called.
- **Settle Time Verification**: Use logs to verify that the 10s wait is applied correctly.
- **Real-World Sample**: Perform a single-page scrape of OLX Portugal and verify data extraction.
