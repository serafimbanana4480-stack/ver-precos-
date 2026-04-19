# Requirements: AutoDeal IA Hunter (Hardened)

## 1. Functional Requirements

### 1.1 Hybrid Scraping Engine
- **Primary Sweep**: Use Playwright Stealth to scan index pages (OLX, Standvirtual).
- **Deep Extraction**: Use Scraper API fallbacks (ZenRows/Bright Data) for detailed listing pages when blocked.
- **Settle Time**: Implement a 10s non-blocking wait to allow Turnstile challenges to clear.
- **Selector Manager**: Abstract all site changes into a centralized manager using robust CSS and Regex patterns.

### 1.2 Data Integrity & Processing
- **Stable IDs**: Ensure `source_id` is derived from URL/Metadata using deterministic hashing (MD5).
- **Unified Parsers**: Centralize extraction of price, mileage, and year using Regex to handle diverse European formats.
- **Strict Validation**: All scraped data must pass Pydantic models before database ingestion.

### 1.3 Analysis & Scouting
- **Deal Score**: Calculate a 0-10 score based on market averages, mileage, age, and condition.
- **Vision Analysis**: Detect visible damages (dents, scratches) using AI-powered image analysis.
- **Multi-Category Scanning**: Ability to scan multiple car brands/models in parallel within OS constraints.

## 2. Technical Constraints
- **Operating System**: 100% Windows 10/11 compatibility.
- **Python Version**: 3.12 or higher.
- **Environment**: Virtual environment (venv) for dependency isolation.

## 3. Compliance & Security
- **Rate Limiting**: Per-domain request throttling to mimic human behavior.
- **Secrets Management**: Configuration must be loaded from `.env` or system environment variables.
