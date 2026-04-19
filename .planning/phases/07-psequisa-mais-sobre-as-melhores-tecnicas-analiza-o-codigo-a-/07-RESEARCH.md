# Phase 7: Tech Audit & Deep Optimization - Research

**Objective:** What do I need to know to PLAN this phase well?

## 1. Scraping Resilience & IA-First
- **Current State:** `scrapers/managed_client.py` uses Playwright Stealth. `scrapers/ai_scraper.py` uses Parsera, which also internally uses Playwright.
- **The Problem:** Modern Turnstile/Cloudflare protections in 2026 can detect Playwright Stealth through CDP (Chrome DevTools Protocol) leaks.
- **Planning Requirements:**
  - **Fetching layer:** Implement `curl_cffi` to flawlessly impersonate TLS/JA4 signatures of Chrome for raw HTML fetching, effectively bypassing basic WAFs. For Javascript-heavy pages requiring rendering, research integrating `nodriver` (which avoids standard CDP detection).
  - **Extraction layer:** Bypass fragile CSS selectors (`BeautifulSoup`) by routing the fetched text/DOM to `AIScraper` (via `deepseek-r1:8b` and `x.ai`).
  - **Modification:** Ensure `scrapers/ai_scraper.py` can accept raw HTML strings directly instead of just URLs, decoupling the downloading from the extraction.

## 2. Event/Queue Architecture (CLI Monolith)
- **Current State:** `main.py` executes sequentially inside `asyncio.run()`, blocking the valuate/train tasks while scraping.
- **The Problem:** Heavy operations (AI text extraction) freeze the system and prevent parallel scaling.
- **Planning Requirements:**
  - Since Windows is the target OS, heavy systems like Celery + external Redis add massive deployment friction. 
  - **Proposed Queue:** Implement an internal Asyncio Producer/Consumer queue within `main.py`, OR a lightweight local task queue backed by SQLite (e.g. using a `tasks` table with status `pending/processing/done`). This preserves the standard "Run `start.bat`" monolith experience while giving enterprise-level async features.
  - Separate `Scraper Workers` (I/O bound) from `AI Extract / Valuate Workers` (CPU / GPU bound).

## 3. XGBoost Data Enrichment
- **Current State:** The XGBoost model uses basic attributes (`price`, `year`, `km`).
- **The Problem:** Ignores massive text context (damage, revisions, trim level).
- **Planning Requirements:**
  - Update database `Vehicle` model to include fields like `trim_level` (string), `has_damage` (boolean), `maintenance_history` (boolean), `aesthetic_score` (1-10).
  - Update `AIScraper._get_default_elements()` to explicitly ask the LLM for these fields according to the ad description.
  - Update `valuation/train_model.py` to handle these new features in the ML pipeline.

## 4. Dual Logging & Local Metrics
- **Current State:** `utils/logging_config.py` sets up standard text logging.
- **The Problem:** Streamlit dashboard cannot easily read metrics (like block rate) from unstructured text.
- **Planning Requirements:**
  - Introduce a `JsonFormatter` alongside the standard formatter.
  - Output metrics to a `logs/metrics.jsonlines` file.
  - Ensure the secret redactor filters both formats.
  - Provide a utility class `MetricsTracker` to increment success/403 errors and periodically flush to the dashboard's data source.
