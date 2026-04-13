# Codebase Structure

**Analysis Date:** 2026-04-13

## Directory Layout

```
VER PRECOS/
├── scrapers/              # Web scraping modules for different sources
│   ├── olx_scraper.py
│   ├── standvirtual_scraper.py
│   └── autosapo_scraper.py
├── database/              # Database models and connection management
│   ├── models.py
│   └── db.py
├── valuation/             # ML model training and price prediction
│   ├── train_model.py
│   └── predict.py
├── ai_agent/              # AI-powered analysis and deal finding
│   ├── deal_finder.py
│   ├── llm_review.py
│   └── vision_analysis.py
├── scheduler/             # Job scheduling and daily automation
│   └── daily_job.py
├── dashboard/             # Streamlit web dashboard
│   └── app.py
├── utils/                 # Shared utilities and helpers
│   ├── helpers.py
│   └── logging_config.py
├── data/                  # Data directory (exports, watchlist)
│   └── exports/
├── models/                # Trained ML models
├── logs/                  # Application logs
├── main.py                # CLI entry point
├── config.py              # Centralized configuration
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── Dockerfile            # Docker image definition
└── docker-compose.yml    # Docker Compose configuration
```

## Directory Purposes

**scrapers/**
- Purpose: Web scraping modules for different vehicle listing sources
- Contains: Python scraper classes (OLXScraper, StandvirtualScraper, AutoSapoScraper)
- Key files: Each source has its own scraper with common interface
- Subdirectories: None (flat structure)

**database/**
- Purpose: Database models, ORM configuration, and session management
- Contains: SQLAlchemy models, connection setup, context managers
- Key files: models.py (Vehicle, PriceHistory, AIReview, ScrapingLog), db.py (session management)
- Subdirectories: None

**valuation/**
- Purpose: ML model training and vehicle price prediction
- Contains: XGBoost training logic, prediction utilities
- Key files: train_model.py (training pipeline), predict.py (inference)
- Subdirectories: None

**ai_agent/**
- Purpose: AI-powered vehicle analysis and deal finding
- Contains: LLM review, vision analysis, deal scoring
- Key files: deal_finder.py (main agent), llm_review.py (text analysis), vision_analysis.py (image analysis)
- Subdirectories: None

**scheduler/**
- Purpose: Automated job scheduling and daily pipeline execution
- Contains: APScheduler configuration, daily job orchestration
- Key files: daily_job.py (scheduler setup and job definition)
- Subdirectories: None

**dashboard/**
- Purpose: Streamlit web interface for data visualization
- Contains: Streamlit application with filters, charts, and export
- Key files: app.py (main dashboard)
- Subdirectories: None

**utils/**
- Purpose: Shared utility functions and configuration
- Contains: Logging setup, helper functions
- Key files: logging_config.py (logging setup), helpers.py (shared helpers)
- Subdirectories: None

**data/**
- Purpose: Data storage for exports and watchlist
- Contains: exports/ (CSV exports), watchlist.json
- Key files: watchlist.json (user watchlist criteria)
- Subdirectories: exports/

**models/**
- Purpose: Trained ML model artifacts
- Contains: xgboost_model.json, feature_names.json, label_encoders.joblib, model_metrics.json
- Key files: xgboost_model.json (trained model)
- Subdirectories: None

**logs/**
- Purpose: Application log files
- Contains: autodeal.log (main application log)
- Key files: autodeal.log
- Subdirectories: None

## Key File Locations

**Entry Points:**
- `main.py` - CLI entry point with argparse command routing
- `dashboard/app.py` - Streamlit dashboard entry point
- `scheduler/daily_job.py` - Scheduler entry point

**Configuration:**
- `config.py` - Centralized configuration using python-dotenv
- `.env.example` - Environment variables template
- `requirements.txt` - Python dependencies

**Core Logic:**
- `scrapers/*.py` - Scraping logic for each source
- `database/models.py` - SQLAlchemy ORM models
- `valuation/train_model.py` - ML model training
- `ai_agent/deal_finder.py` - Deal finding logic
- `scheduler/daily_job.py` - Daily job orchestration

**Testing:**
- `test_database.py` - Database tests (only test file present)
- No comprehensive test suite yet

**Documentation:**
- `README.md` - User-facing documentation
- No developer-specific documentation beyond code comments

## Naming Conventions

**Files:**
- snake_case.py: Python modules (e.g., olx_scraper.py, deal_finder.py)
- snake_case.txt: Configuration files (requirements.txt)
- UPPERCASE: Environment files (.env.example)
- Dockerfile: Docker image definition
- docker-compose.yml: Docker Compose configuration

**Directories:**
- snake_case: All directories (scrapers, database, valuation, ai_agent)
- Plural for collections: scrapers, utils, models, logs

**Special Patterns:**
- *_scraper.py: Scraper modules (olx_scraper.py)
- *_model.py: ML model files (train_model.py)
- *_config.py: Configuration files (config.py, logging_config.py)

## Where to Add New Code

**New Scraper:**
- Primary code: `scrapers/{source}_scraper.py`
- Tests: `test_{source}_scraper.py` (not yet implemented)
- Config if needed: Add source URL to config.py

**New AI Agent:**
- Implementation: `ai_agent/{agent_name}.py`
- Tests: `test_{agent_name}.py` (not yet implemented)

**New Dashboard Page:**
- Implementation: Add to `dashboard/app.py` (single file architecture)
- Tests: Not applicable (Streamlit app)

**New Scheduled Job:**
- Implementation: Add to `scheduler/daily_job.py`
- Tests: `test_scheduler.py` (not yet implemented)

**Utilities:**
- Shared helpers: `utils/helpers.py`
- Type definitions: Inline in modules (no separate types directory)

## Special Directories

**data/**
- Purpose: Runtime data storage (exports, watchlist)
- Source: Generated at runtime
- Committed: No (in .gitignore)

**models/**
- Purpose: Trained ML model artifacts
- Source: Generated by training pipeline
- Committed: No (in .gitignore)

**logs/**
- Purpose: Application log files
- Source: Generated at runtime
- Committed: No (in .gitignore)

**__pycache__/**
- Purpose: Python bytecode cache
- Source: Generated by Python interpreter
- Committed: No (in .gitignore)

---

*Structure analysis: 2026-04-13*
*Update when directory structure changes*
