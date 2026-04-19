# Phase 3: Ultra-Resilient Stealth Extraction & Intelligent Valuation - Plan

This phase overhauls the scraping core to defeat anti-bot measures and implements the Deal Scoring engine for automated market analysis.

## 🌊 Wave 1: Core Stealth & Infrastructure (Foundational)

### [PH3-01] Add Stealth & Request Dependencies
**type:** execute
**autonomous:** true
**requirements:** [M1-P3-INFRA]
**files_modified:** [requirements.txt]
**depends_on:** []

<read_first>
- [requirements.txt](file:///d:/VER%20PRECOS/requirements.txt)
</read_first>

<acceptance_criteria>
- `requirements.txt` contains `curl_cffi>=0.7.0`
- `requirements.txt` contains `nodriver>=0.3.0`
</acceptance_criteria>

<action>
Add `curl_cffi>=0.7.0` and `nodriver>=0.3.0` to the scraping section of `requirements.txt`.
</action>

### [PH3-02] Repair AI Scraper & Ollama Connectivity
**type:** execute
**autonomous:** true
**requirements:** [M1-P1-BUG]
**files_modified:** [scrapers/ai_scraper.py]
**depends_on:** []

<read_first>
- [scrapers/ai_scraper.py](file:///d:/VER%20PRECOS/scrapers/ai_scraper.py)
</read_first>

<acceptance_criteria>
- `ai_scraper.py` uses configurable timeout for Ollama connection.
- `ai_scraper.py` implements a fallback from `deepseek-r1:8b` to `llama3.1` or `mistral` if the primary model is unavailable.
- Connection error handling is improved to catch `httpx.ConnectError` specifically.
</acceptance_criteria>

<action>
Update the `AIScraper` class in `scrapers/ai_scraper.py`:
1. Add a `timeout` parameter to `Parsera` initialization.
2. Implement a `_verify_llm_connection` check before starting a scrape.
3. Improve the `scrape_listings` method to handle connection failures by returning an empty list instead of crashing or raising unhandled exceptions.
</action>

### [PH3-03] Implement Stealth Session Manager
**type:** execute
**autonomous:** true
**requirements:** [M1-P3-STEALTH]
**files_modified:** [scrapers/session_manager.py]
**depends_on:** []

<read_first>
- [scrapers/managed_client.py](file:///d:/VER%20PRECOS/scrapers/managed_client.py)
</read_first>

<acceptance_criteria>
- `scrapers/session_manager.py` created.
- File contains `SessionManager` class with `get_clearance_cookies(url)` method.
- Method uses `playwright-stealth` or `nodriver` to obtain and return cookies.
</acceptance_criteria>

<action>
Create `scrapers/session_manager.py`. This class will be responsible for the "Solver" part of the hybrid pipeline. It should use Playwright with `playwright_stealth` to navigate to a target (like Standvirtual or OLX), solve the JavaScript challenge, and return the cookies.
</action>

## 🌊 Wave 2: Resilient Extraction (Implementation)

### [PH3-04] Refactor Managed Client for Hybrid Fetching
**type:** execute
**autonomous:** true
**requirements:** [M1-P3-HYBRID]
**files_modified:** [scrapers/managed_client.py]
**depends_on:** [PH3-01, PH3-03]

<read_first>
- [scrapers/managed_client.py](file:///d:/VER%20PRECOS/scrapers/managed_client.py)
</read_first>

<acceptance_criteria>
- `ManagedScrapingClient` identifies and uses `curl_cffi` for requests.
- `get_html` method implements the 2-step pipeline: Browser Solver -> `curl_cffi` Fetcher.
- TLS/JA4 fingerprinting is set to mimic `chrome` in `curl_cffi`.
</acceptance_criteria>

<action>
Modify `scrapers/managed_client.py`:
1. Import `AsyncSession` from `curl_cffi.requests`.
2. Add `scrape_with_curl_cffi` method that mimics browser networking.
3. Update `get_html` to orchestrate `SessionManager` (Wave 1) and use the obtained cookies in `curl_cffi`.
</action>

### [PH3-05] Repair Standvirtual Electors
**type:** execute
**autonomous:** true
**requirements:** [M1-P1-BUG]
**files_modified:** [scrapers/standvirtual_scraper.py, utils/selector_manager.py]
**depends_on:** []

<read_first>
- [scrapers/standvirtual_scraper.py](file:///d:/VER%20PRECOS/scrapers/standvirtual_scraper.py)
- [utils/selector_manager.py](file:///d:/VER%20PRECOS/utils/selector_manager.py)
</read_first>

<acceptance_criteria>
- `standvirtual_scraper.py` uses `data-testid` selectors where available.
- Title selector updated to: `[data-testid="ad-title"] a`.
- Price selector updated to: `[data-testid="ad-price"]`.
- `selector_manager.py` contains the updated definitions for `standvirtual`.
</acceptance_criteria>

<action>
Update selectors for Standvirtual in both `utils/selector_manager.py` (defaults) and `scrapers/standvirtual_scraper.py`. Verify against recent DOM changes (captured in user logs showing `[data-testid]` use).
</action>

## 🌊 Wave 3: Intelligence & Scoring (Features)

### [PH3-06] Implement Market Valuation Engine
**type:** execute
**autonomous:** true
**requirements:** [M2-P3-VAL]
**files_modified:** [valuation/engine.py, models/listing.py]
**depends_on:** []

<read_first>
- [models/listing.py](file:///d:/VER%20PRECOS/models/listing.py)
</read_first>

<acceptance_criteria>
- `valuation/engine.py` created with `ValuationEngine` class.
- Method `calculate_deal_score(listing)` implemented.
- Scoring logic accounts for: `(Price vs Average for Year/Km) * ReliabilityWeight`.
- Deal labels (0-2: Bad, 3-5: Fair, 6-8: Good, 9-10: Great) implemented.
</acceptance_criteria>

<action>
Create `valuation/engine.py`. Implement logic to calculate the market average for a given vehicle model/year/km using the existing database and then score individual listings relative to that average.
</action>

### [PH3-07] Integrate Deal Scoring into Pipeline
**type:** execute
**autonomous:** true
**requirements:** [M2-P3-INT]
**files_modified:** [main.py, services/hunter_service.py]
**depends_on:** [PH3-06]

<read_first>
- [main.py](file:///d:/VER%20PRECOS/main.py)
- [services/hunter_service.py](file:///d:/VER%20PRECOS/services/hunter_service.py)
</read_first>

<acceptance_criteria>
- `HunterService` calls `ValuationEngine` after each successful scrape.
- Deal scores are saved to the database for each listing.
- Log output shows the Deal Score for newly discovered listings.
</acceptance_criteria>

<action>
Modify `services/hunter_service.py` (or the equivalent core service) to instantiate `ValuationEngine` and process listings after they are saved to the database. Ensure the `deal_score` field is updated.
</action>

## 🌊 Wave 4: Verification & Monitoring

### [PH3-08] Resilience & Performance Verification
**type:** execute
**autonomous:** true
**requirements:** [M1-P3-VER]
**files_modified:** [tests/integration/test_scraping_resiliency.py]
**depends_on:** [PH3-04]

<read_first>
- [scrapers/managed_client.py](file:///d:/VER%20PRECOS/scrapers/managed_client.py)
</read_first>

<acceptance_criteria>
- `tests/integration/test_scraping_resiliency.py` created.
- Test mocks a "Blocked" Playwright result and verifies that `ManagedScrapingClient` correctly switches to the `curl_cffi` fetcher.
</acceptance_criteria>

<action>
Create a comprehensive integration test suite for the new hybrid scraping pipeline.
</action>

## 🎯 must_haves
1. **Zero Standard Block Rate:** Local scraping must pass Cloudflare Turnstile at least 80% of the time via the Hybrid Solver+Fetcher.
2. **Valid Deal Scores:** Listings in the database MUST have a `deal_score` between 0 and 10.
3. **Standvirtual Success:** Standvirtual scrapes must return valid titles and prices (no more selector failures).

## 🛡️ threat_model
- **Threat:** IP Banning due to excessive scraping.
- **Mitigation:** Residential Proxy rotation + Randomized Settle Time + Managed API fallback.
- **Threat:** Data Corruption from invalid pricing.
- **Mitigation:** Strict input validation in `ValuationEngine` (discardING outliers > 5x market average).
