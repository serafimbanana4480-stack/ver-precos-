# Architecture

**Analysis Date:** 2026-04-13

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
- Contains: Logging setup, helper functions, configuration management
- Location: `utils/*.py`, `config.py`
- Depends on: Python standard library
- Used by: All layers

## Data Flow

**Scraping Flow:**

1. User runs: `python main.py scrape --source all`
2. CLI parses args and instantiates scrapers (OLXScraper, StandvirtualScraper, AutoSapoScraper)
3. Scraper launches Playwright browser with stealth
4. Browser navigates to target URL, handles consent, scrolls to load content
5. HTML parsed with BeautifulSoup, listing data extracted
6. Scraper saves to database via get_db_context() context manager
7. ScrapingLog entry created/updated for tracking

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
- Centralized in `config.py` using python-dotenv
- Environment variables loaded from .env file
- Config class provides validation and type safety
- Defaults provided for all optional settings

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

---

*Architecture analysis: 2026-04-13*
*Update when major patterns change*
