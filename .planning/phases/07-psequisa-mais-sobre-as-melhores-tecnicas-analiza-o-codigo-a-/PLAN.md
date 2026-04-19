# Phase 7: Tech Audit & Deep Optimization - Execution Plan

**Goal:** Transform the scraping foundation to a resilient IA-First engine with asynchronous queue background processing, enriched data extraction, and dual observability logging.

## Wave 1: Core Infrastructure & Data Model
This wave lays the foundation for advanced metrics and database support for the new IA features.

- **Task 07-01-01: Advanced Observability & Metrics Logger**
  - **Description:** Implement a dual-logging strategy (Text + JSON) inside `utils/logging_config.py` and output to `logs/metrics.jsonlines`.
  - **Files:** `utils/logging_config.py`, `requirements.txt`
  - **Verification:** `<automated>` Run `python -c "import logging; from utils.logging_config import setup_logging; setup_logging(); logging.info('test')"` and verify `metrics.jsonlines` is created.

- **Task 07-01-02: Database Schema Upgrade (IA Features)**
  - **Description:** Update `database/models.py` (Vehicle model) to include `trim_level` (String), `has_damage` (Boolean), `maintenance_history` (Boolean), and `aesthetic_score` (Integer). Run alembic migration.
  - **Files:** `database/models.py`, `alembic/versions/`
  - **Verification:** `<automated>` Run `alembic upgrade head` and verify columns exist in SQLite.

## Wave 2: Resilient IA-First Scraping
Replacing Playwright Stealth with `curl_cffi` and enhancing Parsera prompts.

- **Task 07-02-01: Integrate curl_cffi for Stealth HTML Fetching**
  - **Description:** Install `curl_cffi`. Modify `scrapers/ai_scraper.py` to use `curl_cffi.requests.AsyncSession` for pulling raw HTML pages with proper impersonation.
  - **Files:** `requirements.txt`, `scrapers/ai_scraper.py`, `scrapers/managed_client.py`
  - **Verification:** `<automated>` Run a test script to fetch an actively protected `olx.pt` car listing without 403 errors.

- **Task 07-02-02: Enhance LLM Extraction Prompts**
  - **Description:** Update `AIScraper._get_default_elements()` to explicitly extract the new database columns: `trim_level`, `has_damage`, `maintenance_history`, and `aesthetic_score`.
  - **Files:** `scrapers/ai_scraper.py`
  - **Verification:** `<automated>` Execute `pytest tests/unit/test_ai_scraper.py` testing the JSON extraction schema.

## Wave 3: Internal Queuing System
Restructuring `main.py` into a modern producer-consumer architecture.

- **Task 07-03-01: Build Local Asyncio Queue Manager**
  - **Description:** Create `services/queue_manager.py` that implements an `asyncio.Queue` capable of tracking statuses to prevent the main event loop from freezing during heavy LLM prompts.
  - **Files:** `services/queue_manager.py`
  - **Verification:** `<automated>` Run unit tests verifying jobs enter and exit the queue asynchronously.

- **Task 07-03-02: Retrofit main.py for Background Processing**
  - **Description:** Update `main.py` to use the `queue_manager`. Scraping lists/URLs become job items, and an internal worker processes them dynamically while keeping the CLI responsive to logs.
  - **Files:** `main.py`
  - **Verification:** `<automated>` Run `python main.py scrape` in test mode and observe non-blocking worker logs.

## Wave 4: Validation & Dashboard

- **Task 07-04-01: Wire Metrics to Streamlit Dashboard**
  - **Description:** Update the Streamlit dashboard to read `logs/metrics.jsonlines` to display success/block ratios and extraction health in real-time.
  - **Files:** `dashboard/app.py`
  - **Verification:** `<manual>` Run `streamlit run dashboard/app.py` and visibly verify the new health metrics component.
