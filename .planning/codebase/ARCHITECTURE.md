# System Architecture

## High-Level Design

The AutoDeal IA Hunter follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   CLI (main) │  │  Dashboard   │  │  Scheduler   │      │
│  │   (async)    │  │  (Streamlit) │  │  (APScheduler)│     │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Deal Hunter  │  │ AI Agent     │  │ Deal Scorer  │      │
│  │ (orchestrate)│  │ (LLM+Vision) │  │ (valuation)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Data Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Scrapers    │  │  Database    │  │  ML Model    │      │
│  │ (async)      │  │ (SQLAlchemy) │  │ (XGBoost)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Infrastructure Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Config     │  │   Logging    │  │   Sentry     │      │
│  │ (pydantic)   │  │ (structured) │  │ (monitoring) │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Scraping Layer (Async-First)
- **OLX Scraper**: Async scraper with resilient fallback chain
  - Playwright async → CSS selectors → AI extraction → Managed services
  - Circuit breaker: `_olx_circuit_breaker`
  - Cloudflare bypass via nodriver
- **Standvirtual Scraper**: Async scraper with AI-first approach
  - AI extraction → CSS selectors → Managed services
  - Circuit breaker: `_standvirtual_circuit_breaker`
  - CSS selectors unreliable, AI prioritized
- **AutoSapo Scraper**: Async scraper with CSS-first approach
  - Playwright async → CSS selectors → AI extraction
  - Circuit breaker: `_autosapo_circuit_breaker`
  - Lighter protection, CSS reliable
- **Managed Client**: Unified interface for managed scraping services
  - Apify, ScraperAPI, ZenRows integration
  - Resilient fetching with fallbacks
- **AI Scraper**: AI-powered extraction using Parsera
  - Event loop management for nested async contexts
  - LLM backend (Ollama/Grok)
- **AI Extractor**: Custom AI extraction with LLM fallback
  - HTML compression for context optimization
  - Regex fallback for structured extraction
- **Session Manager**: Handles Cloudflare bypass with nodriver
  - Human-like interactions (scrolling, delays)
  - Cookie extraction for curl_cffi

### 2. Data Layer
- **Database (PostgreSQL)**: Persistent storage via SQLAlchemy 2.0+
  - Context manager pattern for session handling
  - Retry decorator for connection resilience
  - Health check endpoint
- **Models**: ORM models
  - Vehicle: Listings, valuations, AI reviews, new fields (trim_level, has_damage, maintenance_history, aesthetic_score)
  - PriceHistory: Price tracking over time
  - Watchlist: User favorites
  - AIReview: LLM analysis results
  - ScrapingLog: Scraping metadata and statistics
- **Validation**: Dual validation approach
  - Pydantic models for structure validation (year >= 1980)
  - Custom validators for business logic (utils/data_validation.py)
- **Deduplication**: Hybrid approach
  - Redis for distributed deduplication (cross-process)
  - In-memory fallback when Redis unavailable
  - TTL-based expiration (configurable window)

### 3. ML Layer
- **XGBoost Model**: Price prediction and valuation
  - Consistent hash encoding for brand/model (deterministic)
  - Feature engineering: age, km_per_year, categorical encoding
  - Model serialization with joblib
- **Deal Scorer**: Calculates deal scores and profit potential
  - Price difference percentage scoring
  - KM and year adjustments
  - Condition score integration
- **Training Pipeline**: Model training with feature engineering
  - Automatic retraining capability
  - Feature name persistence

### 4. AI Layer
- **LLM Review**: Analyzes vehicle descriptions
  - Grok API (primary) or Ollama (fallback)
  - Hidden issues detection
  - Market position assessment
  - Approval/rejection with confidence
- **Vision Analysis**: Analyzes vehicle images for condition
  - Exterior damage detection
  - Tire condition assessment
  - Interior wear analysis
  - Condition score (0-10)
- **Deal Finder**: Orchestrates AI analysis pipeline
  - Top deals selection
  - Second review with deduplication
  - Combined score calculation

### 5. Service Layer
- **Deal Hunter**: Main orchestration service
  - Parallel scraping execution
  - Deal scoring pipeline
  - Vision analysis triggering
- **Scheduler**: Automated daily job execution
  - APScheduler BackgroundScheduler
  - Daily scraping job (configurable time)
  - Periodic analysis job (every N hours)
  - Multi-channel notifications
- **Notification Service**: Multi-channel notifications
  - Discord webhooks
  - Email (SMTP)
  - Telegram bot

### 6. Presentation Layer
- **CLI**: Command-line interface via main.py
  - Async execution with asyncio.run()
  - Commands: init, scrape, train, valuate, find-deals, scheduler, dashboard, health-check
  - Production safeguards integration
- **Dashboard**: Streamlit dashboard for visualization
  - Vehicle listings table
  - Top deals display
  - Analytics and charts
  - Export functionality
- **API**: Optional FastAPI endpoint (app.py)
  - RESTful API for programmatic access

## Data Flow

### Scraping Pipeline (Async)
```
1. Trigger (CLI/Scheduler)
2. Initialize Scrapers (async)
3. Parallel Scraping (asyncio.gather)
   ├─ OLX: Playwright async → CSS → AI → Managed
   ├─ Standvirtual: AI → CSS → Managed
   └─ AutoSapo: Playwright async → CSS → AI → Managed
4. Validate Data (Pydantic + custom)
5. Deduplicate (Redis/in-memory)
6. Save to Database (context manager)
7. Update Valuations (batch)
```

### Deal Finding Pipeline
```
1. Query Database for new listings
2. Update ML valuations (batch processing)
3. Calculate deal scores (price difference)
4. Filter by threshold (configurable)
5. AI Review (LLM - Grok/Ollama)
6. Vision Analysis (if high score)
7. Calculate combined score
8. Send notifications (Discord/Email/Telegram)
```

## Key Patterns

### Async-First Architecture
- All scrapers use async/await pattern
- Playwright async API exclusively
- aiohttp/httpx for async HTTP
- asyncio.run() only at main.py entry point
- Event loop management in AI scraper for nested contexts

### Resilient Fetching
Each scraper implements a fallback chain:
1. Primary method (Playwright async/CSS)
2. AI extraction (Parsera/custom)
3. Managed services (Apify/ScraperAPI/ZenRows)
4. Circuit breaker protection

### Circuit Breaker Pattern
- Separate circuit breakers per scraper (not shared)
- Failure threshold: 3 failures
- Recovery timeout: 300 seconds
- Prevents cascading failures across sources

### Retry Pattern
- Tenacity for retries with exponential backoff
- Separate decorators: retry_network, retry_ai_api, retry_database
- Configurable max attempts and wait times

### Validation Pattern
- Pydantic models for structure validation
- Custom validators for business logic
- Dual validation (structure + content)
- Aligned year validation (>= 1980 for Portuguese market)

### Deduplication Pattern
- Redis for distributed deduplication (cross-process)
- In-memory fallback when Redis unavailable
- TTL-based expiration (configurable)
- Automatic fallback with loggings and scrapers.
