# Architecture

**Analysis Date:** 2026-04-13 (Updated after Phase 1)

## Pattern Overview

**Overall:** Monolithic CLI Application with Scheduled Jobs

**Key Characteristics:**
- Single entry point (main.py) with subcommands
- Layered architecture with clear separation of concerns
- Scheduled autonomous agent for daily operations
- Database-driven state management
- Modular scrapers for different sources

## Layers

**CLI Layer:**
- Purpose: Parse user commands and route to appropriate handlers
- Contains: main.py (argparse-based CLI)
- Location: `main.py`
- Depends on: All other layers (scrapers, database, valuation, AI agent)
- Used by: User via terminal

**Scraper Layer:**
- Purpose: Extract vehicle listings from external websites
- Contains: OLXScraper, StandvirtualScraper, AutoSapoScraper
- Location: `scrapers/*.py`
- Depends on: Playwright (browser automation), BeautifulSoup (HTML parsing), database layer
- Used by: CLI layer (scrape command), scheduler

**Database Layer:**
- Purpose: Data persistence and retrieval
- Contains: SQLAlchemy models, session management, connection pooling
- Location: `database/models.py`, `database/db.py`
- Depends on: SQLAlchemy, PostgreSQL/SQLite
- Used by: All layers (scrapers save data, valuation reads data, AI agent queries data)

**Valuation Layer:**
- Purpose: ML-based price prediction and vehicle valuation
- Contains: XGBoost model training, prediction logic
- Location: `valuation/train_model.py`, `valuation/predict.py`
- Depends on: Database layer (for training data), XGBoost, scikit-learn
- Used by: CLI layer (train, valuate commands)

**AI Agent Layer:**
- Purpose: AI-powered deal finding and analysis
- Contains: DealFinder, LLMReviewer, VisionAnalyzer
- Location: `ai_agent/*.py`
- Depends on: Database layer, Grok API/Ollama, valuation layer
- Used by: CLI layer (find-deals command), scheduler

**Scheduler Layer:**
- Purpose: Automated daily job execution
- Contains: APScheduler configuration, daily job logic
- Location: `scheduler/daily_job.py`
- Depends on: Scraper layer, AI agent layer, database layer
- Used by: CLI layer (scheduler command)

**Dashboard Layer:**
- Purpose: Web-based visualization and exploration
- Contains: Streamlit application
- Location: `dashboard/app.py`
- Depends on: Database layer, Plotly/Altair for visualization
- Used by: User via browser

**Utility Layer:**
- Purpose: Shared helpers and configuration
- Contains: Logging setup, helper functions, configuration management, retry logic, deduplication
- Location: `utils/*.py`, `config.py`
- Depends on: Python standard library, tenacity, pydantic-settings
- Used by: All layers

**Validation Layer (added in Phase 1):**
- Purpose: Data validation and type safety across the application
- Contains: CLI argument models, scraped data models, AI response models
- Location: `validation/*.py`
- Depends on: pydantic, pydantic-settings
- Used by: CLI layer, scraper layer, AI agent layer

**Retry Layer (added in Phase 1):**
- Purpose: Automatic retry logic for transient errors
- Contains: Network retry, AI API retry, database retry decorators
- Location: `utils/retry.py`
- Depends on: tenacity
- Used by: Scraper layer, AI agent layer, database layer

## Data Flow

**Scraping Flow:**

1. User runs: `python main.py scrape --source all`
2. CLI parses args and validates using pydantic models (validation layer)
3. Scraper instantiated with @retry_network decorator for transient errors (retry layer)
4. Scraper launches Playwright browser with stealth
5. Browser navigates to target URL, handles consent, scrolls to load content
6. HTML parsed with BeautifulSoup, listing data extracted
7. Data validated using ScrapedVehicle model (validation layer)
8. Deduplication check via utils/deduplication (utility layer)
9. Scraper saves to database via get_db_context() context manager with @retry_database (retry layer)
10. ScrapingLog entry created/updated for tracking

**Training Flow:**

1. User runs: `python main.py train`
2. CLI calls train_model() from valuation/train_model.py
3. Database queried for vehicles with price, year, km data
4. Data preprocessed (handle missing values, encode categoricals, create derived features)
5. XGBoost model trained on training set (80/20 split)
6. Model evaluated (MAE, RMSE, R2 metrics)
7. Model saved to models/xgboost_model.json
8. Feature names and encoders saved for inference

**Deal Finding Flow:**

1. User runs: `python main.py find-deals`
2. CLI calls DealFinder.find_best_deals()
3. Database queried for active vehicles with deal_score >= threshold
4. Results filtered by recency (last 7 days)
5. Results sorted by deal_score and profit_potential
6. Top N deals returned as dictionaries (to avoid DetachedInstanceError)

**Daily Scheduler Flow:**

1. User runs: `python main.py scheduler`
2. APScheduler initialized with Europe/Lisbon timezone
3. Daily job scheduled at 08:00
4. Job executes: scrape → train → valuate → find-deals → notify
5. Process repeats daily

**State Management:**
- Database-centric: All state in SQLite/PostgreSQL
- Scraping metadata in ScrapingLog table
- Price history in PriceHistory table
- AI reviews in AIReview table
- No in-memory state persistence

## Key Abstractions

**Scraper:**
- Purpose: Abstract scraping logic for each source
- Examples: `scrapers/olx_scraper.py`, `scrapers/standvirtual_scraper.py`, `scrapers/autosapo_scraper.py`
- Pattern: Class with scrape_listings(), save_to_database(), _parse_*() methods
- Common interface: All scrapers implement same method signatures

**Vehicle Model:**
- Purpose: SQLAlchemy ORM model representing a vehicle listing
- Location: `database/models.py`
- Pattern: DeclarativeBase with relationships (price_history, ai_reviews)
- Methods: to_dict() for serialization (prevents DetachedInstanceError)

**Context Manager:**
- Purpose: Database session management with automatic commit/rollback
- Location: `database/db.py`
- Pattern: get_db_context() context manager
- Usage: `with get_db_context() as db:` ensures cleanup

**AI Agent:**
- Purpose: Encapsulate AI-powered analysis logic
- Examples: `ai_agent/deal_finder.py`, `ai_agent/llm_review.py`, `ai_agent/vision_analysis.py`
- Pattern: Class with analyze_*() methods, returns structured results

## Entry Points

**CLI Entry:**
- Location: `main.py`
- Triggers: User runs `python main.py <command>`
- Responsibilities: Argument parsing, command routing, logging setup

**Scheduler Entry:**
- Location: `scheduler/daily_job.py`
- Triggers: APScheduler trigger at configured time
- Responsibilities: Orchestrate daily pipeline (scrape → analyze → notify)

**Dashboard Entry:**
- Location: `dashboard/app.py`
- Triggers: User accesses Streamlit URL
- Responsibilities: Render UI, query database, display visualizations

## Error Handling

**Strategy:** Try/except at operation level, log errors, continue processing

**Patterns:**
- Database operations wrapped in context manager with automatic rollback on exception
- Scraping errors logged at WARNING level, individual listing failures don't halt batch
- Model training returns None on insufficient data, CLI checks and exits gracefully
- AI agent errors logged, vehicles skipped on analysis failure

## Cross-Cutting Concerns

**Logging:**
- Python logging module with file and stream handlers
- Centralized configuration in `utils/logging_config.py`
- Levels: INFO (default), configurable via LOG_LEVEL env var
- File output: logs/autodeal.log

**Configuration:**
- Centralized in `config.py` using pydantic-settings BaseSettings (refactored in Phase 1)
- Environment variables loaded from .env file via python-dotenv
- Settings class provides validation, type safety, and field validators
- Configurable validation rules with override support
- Defaults provided for all optional settings
- Backward compatibility: config alias points to settings instance

**Database Sessions:**
- Context manager pattern for session lifecycle
- Connection pooling via QueuePool
- Automatic commit on success, rollback on exception
- Session closed automatically in finally block

**Stealth Scraping:**
- Playwright stealth scripts to detect webdriver
- Random user agents from list
- Request delays to avoid rate limiting
- Cookie consent handling

**Validation (added in Phase 1):**
- Pydantic models for CLI arguments, scraped data, AI responses
- Configurable validation rules with override support
- Structured logging for validation failures with context
- Validation failure tracking and alerting

**Retry Logic (added in Phase 1):**
- Tenacity decorators for network, AI API, and database operations
- Exponential backoff with configurable max attempts
- Exception type filtering (retry only on transient errors)
- Structured logging for retry attempts

**Deduplication (added in Phase 1):**
- In-memory tracking of processed URLs and vehicle IDs
- Configurable deduplication window (default 1 hour)
- Automatic reset after window expiration
- Integration with scrapers and AI agents

---

*Architecture analysis: 2026-04-13*
*Update when major patterns change*
