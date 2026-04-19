# Project Structure

## Directory Layout

```
autodeal-ia-hunter/
├── main.py                 # CLI entry point (async)
├── config.py              # Configuration management (pydantic-settings)
├── app.py                 # Optional FastAPI application
├── run_hunter.py          # Standalone deal hunter script
├── requirements.txt       # Python dependencies
├── requirements-minimal.txt
├── .env.example          # Environment variables template
├── .env                  # Actual environment variables (gitignored)
├── .gitignore
├── Dockerfile            # Docker image definition
├── docker-compose.yml    # Docker Compose configuration
├── alembic.ini           # Alembic configuration
├── pyproject.toml        # Project metadata
├── mypy.ini              # MyPy configuration
├── CLAUDE.md             # Project documentation for Claude
├── README.md             # Project README
│
├── scrapers/             # Web scraping modules (async)
│   ├── __init__.py
│   ├── olx_scraper.py    # OLX.pt scraper (async, circuit breaker: _olx_circuit_breaker)
│   ├── standvirtual_scraper.py  # Standvirtual scraper (async, AI-first, circuit breaker: _standvirtual_circuit_breaker)
│   ├── autosapo_scraper.py      # AutoSapo.pt scraper (async, circuit breaker: _autosapo_circuit_breaker)
│   ├── ai_scraper.py     # AI-powered scraping (Parsera, event loop management)
│   ├── ai_extractor.py   # Custom AI extraction with LLM fallback
│   ├── vision_analyzer.py       # Vision AI for image analysis
│   ├── managed_client.py        # Managed scraping services (Apify, ScraperAPI, ZenRows)
│   └── session_manager.py       # Cloudflare bypass (nodriver)
│
├── database/             # Database layer
│   ├── __init__.py
│   ├── db.py             # Database connection and session management (context manager, retry)
│   └── models.py         # SQLAlchemy ORM models (Vehicle with new fields: trim_level, has_damage, maintenance_history, aesthetic_score)
│
├── valuation/            # ML valuation
│   ├── __init__.py
│   ├── train_model.py    # Model training pipeline
│   └── predict.py        # Price prediction and deal scoring (consistent hash encoding)
│
├── ai_agent/             # AI analysis
│   ├── __init__.py
│   ├── llm_review.py     # LLM-based vehicle review (Grok/Ollama)
│   ├── vision_analysis.py        # Vision AI for condition assessment
│   └── deal_finder.py    # Deal finding orchestration
│
├── scheduler/            # Job scheduling
│   ├── __init__.py
│   └── daily_job.py      # Daily automated job (APScheduler BackgroundScheduler)
│
├── dashboard/            # Streamlit dashboard
│   ├── __init__.py
│   ├── app.py            # Dashboard application
│   ├── components/       # Reusable dashboard components
│   └── pages/            # Dashboard pages
│
├── services/             # Business services
│   ├── __init__.py
│   └── deal_hunter.py    # Main deal hunting service
│
├── utils/                # Utility modules
│   ├── __init__.py
│   ├── helpers.py        # General helper functions
│   ├── logging_config.py # Logging configuration
│   ├── retry.py          # Retry decorators (tenacity: retry_network, retry_ai_api, retry_database)
│   ├── data_validation.py # Data validation utilities
│   ├── selector_manager.py     # CSS selector management with fallback
│   ├── production_safeguards.py # Circuit breakers (separate per scraper), error handling
│   ├── deduplication.py  # Deduplication (Redis with in-memory fallback)
│   ├── proxy_manager.py  # Proxy pool management
│   ├── captcha_solver.py # CAPTCHA detection and solving
│   ├── captcha_rate_limiter.py  # CAPTCHA rate limiting
│   ├── html_change_detector.py # HTML change detection
│   ├── ml_parser.py      # ML-based parsing
│   ├── parsers.py        # HTML parsers
│   ├── request_queue.py  # Request queue management
│   ├── proxy_monitor.py  # Proxy monitoring
│   ├── health_check.py   # Health check utilities
│   └── error_classifier.py     # Error classification
│
├── validation/           # Validation models
│   ├── __init__.py
│   ├── scraped_models.py # Pydantic models for scraped data (year >= 1980)
│   ├── cli_models.py     # Pydantic models for CLI
│   └── ai_models.py      # Pydantic models for AI outputs
│
├── tests/                # Test suite
│   ├── __init__.py
│   ├── conftest.py       # Pytest configuration
│   ├── factories.py      # Test data factories
│   ├── unit/             # Unit tests
│   │   ├── test_olx_scraper.py
│   │   ├── test_standvirtual_scraper.py
│   │   ├── test_autosapo_scraper.py
│   │   ├── test_managed_client.py
│   │   ├── test_database.py
│   │   ├── test_config.py
│   │   └── test_selector_manager.py
│   ├── integration/      # Integration tests
│   │   ├── test_deal_scorer.py
│   │   └── test_database.py
│   └── test_circuit_breaker.py
│
├── alembic/              # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/         # Migration versions
│
├── analysis/             # Analysis modules
│   └── deal_scorer.py
│
├── data/                 # Data directory
│   ├── exports/          # Exported data files
│   └── html_fingerprints/ # HTML fingerprints for change detection
│
├── models/               # Trained ML models
│
├── logs/                 # Log files
│
├── exports/              # Exported files
│
├── scratch/              # Scratch/development scripts
│   ├── test_pw.py
│   ├── test_nodriver.py
│   ├── test_standvirtual.py
│   ├── test_hybrid_client.py
│   └── test_ai_scraper.py
│
└── .planning/            # Planning and documentation
    ├── PROJECT.md        # Project overview
    ├── REQUIREMENTS.md   # Requirements
    ├── ROADMAP.md        # Roadmap
    ├── STATE.md          # Project state
    ├── config.json       # Planning configuration
    ├── phases/           # Phase plans
    ├── research/         # Research documents
    └── codebase/         # Codebase documentation (this directory)
        ├── STACK.md
        ├── INTEGRATIONS.md
        ├── ARCHITECTURE.md
        ├── STRUCTURE.md
        ├── CONVENTIONS.md
        ├── TESTING.md
        └── CONCERNS.md
```

## Key Files

### Entry Points
- **main.py**: CLI entry point with async command routing (scrape, train, valuate, find-deals, scheduler, dashboard, health-check)
- **app.py**: Optional FastAPI application
- **run_hunter.py**: Standalone deal hunter script (async)

### Configuration
- **config.py**: Centralized configuration using pydantic-settings
- **.env**: Environment variables (gitignored)
- **.env.example**: Environment template

### Database
- **database/db.py**: Database connection, session management (context manager), health check, retry decorator
- **database/models.py**: SQLAlchemy ORM models (Vehicle, PriceHistory, Watchlist, AIReview, ScrapingLog)
- **alembic/**: Database migrations

### Scraping (Async-First)
- **scrapers/olx_scraper.py**: OLX.pt scraper (async, resilient fallback, _olx_circuit_breaker)
- **scrapers/standvirtual_scraper.py**: Standvirtual scraper (async, AI-first, _standvirtual_circuit_breaker)
- **scrapers/autosapo_scraper.py**: AutoSapo.pt scraper (async, _autosapo_circuit_breaker)
- **scrapers/managed_client.py**: Managed services integration (Apify, ScraperAPI, ZenRows)
- **scrapers/ai_scraper.py**: AI-powered extraction (Parsera, event loop management for nested async)
- **scrapers/ai_extractor.py**: Custom AI extraction with LLM fallback
- **scrapers/session_manager.py**: Cloudflare bypass (nodriver, human-like interactions)

### AI/ML
- **valuation/train_model.py**: XGBoost model training
- **valuation/predict.py**: Price prediction and deal scoring (consistent hash encoding for brand/model)
- **ai_agent/llm_review.py**: LLM-based vehicle review (Grok/Ollama)
- **ai_agent/vision_analysis.py**: Vision AI for condition assessment
- **ai_agent/deal_finder.py**: Deal finding orchestration

### Services
- **services/deal_hunter.py**: Main deal hunting service (parallel scraping, deal scoring, vision analysis)
- **scheduler/daily_job.py**: Automated daily job (APScheduler BackgroundScheduler, multi-channel notifications)

### Dashboard
- **dashboard/app.py**: Streamlit dashboard

### Utilities
- **utils/retry.py**: Retry decorators (retry_network, retry_ai_api, retry_database)
- **utils/production_safeguards.py**: Circuit breakers (separate per scraper: _olx, _standvirtual, _autosapo), error handling
- **utils/data_validation.py**: Data validation
- **utils/deduplication.py**: Deduplication (Redis with in-memory fallback, TTL-based)
- **utils/selector_manager.py**: CSS selector management with fallback
- **utils/proxy_manager.py**: Proxy management
- **utils/captcha_solver.py**: CAPTCHA detection
- **utils/captcha_rate_limiter.py**: CAPTCHA rate limiting
- **utils/html_change_detector.py**: HTML change detection

### Validation
- **validation/scraped_models.py**: Pydantic models for scraped data (year >= 1980 aligned with data_validator)
- **validation/cli_models.py**: Pydantic models for CLI
- **validation/ai_models.py**: Pydantic models for AI outputs

### Testing
- **tests/conftest.py**: Pytest configuration
- **tests/factories.py**: Test data factories
- **tests/unit/**: Unit tests
- **tests/integration/**: Integration tests
- **tests/test_circuit_breaker.py**: Circuit breaker tests
