# AutoDeal IA Hunter

## What This Is

Intelligent vehicle deal finder for Portugal using AI, machine learning, and web scraping. Automatically scrapes OLX.pt, Standvirtual, and AutoSapo.pt, uses XGBoost for price prediction, and AI analysis (Grok/Ollama) to identify the best vehicle deals with daily autonomous operation.

## Core Value

Accurate deal identification through ML-based valuation and AI-powered analysis of vehicle listings.

## Requirements

### Validated

- ✓ Multi-source web scraping (OLX, Standvirtual, AutoSapo) — existing
- ✓ XGBoost ML model for price prediction — existing
- ✓ Database layer with SQLAlchemy ORM — existing
- ✓ CLI interface with argparse — existing
- ✓ Streamlit dashboard — existing
- ✓ APScheduler for daily automation — existing
- ✓ LLM integration (Grok/Ollama) — existing
- ✓ Vision analysis capability — existing
- ✓ Notification channels (Discord, Email, Telegram) — existing
- ✓ Docker deployment setup — existing

### Active

- [ ] Comprehensive test coverage (pytest) — currently only test_database.py exists
- [ ] Input validation with pydantic models
- [ ] Database migrations with Alembic
- [ ] Retry mechanism for transient scraping failures
- [ ] Caching layer (Redis) for performance
- [ ] Monitoring and alerting system
- [ ] Automated database backups
- [ ] Authentication for dashboard
- [ ] Rate limiting for API calls
- [ ] Robust error handling and logging improvements

### Out of Scope

- Multi-user authentication system — single-user autonomous agent
- Real-time websockets — not needed for batch processing
- Mobile app — dashboard is web-based
- Payment processing — not a commercial platform
- User account management — autonomous operation only

## Context

**Existing Codebase:**
- Python 3.12+ monolithic CLI application with layered architecture
- Database-driven state management (SQLite for dev, PostgreSQL for production)
- Modular scrapers with Playwright browser automation
- XGBoost model trained on scraped vehicle data
- AI agents for deal finding and analysis
- Daily scheduler for autonomous operation

**Technical Debt:**
- DetachedInstanceError workarounds in deal_finder.py
- Alembic installed but not configured for migrations
- No input validation on CLI arguments or scraped data
- Minimal test coverage (only test_database.py)
- No retry mechanism for transient failures
- No caching layer for performance optimization

**Known Issues:**
- Scrapers depend on HTML structure (fragile to site changes)
- Brand/model parsing uses hardcoded lists
- No monitoring/alerting for scraping failures
- Environment variables stored in plain text .env file
- Dashboard has no authentication
- SQLite used in development (limited concurrency)

**Deployment:**
- Docker Compose setup provided
- Supports Railway, Render, and VPS deployment
- Requires Grok API key or Ollama for AI features
- PostgreSQL recommended for production

## Constraints

- **Tech Stack**: Python 3.12+, SQLAlchemy, Playwright, XGBoost — established codebase
- **AI Dependency**: Requires Grok API key or local Ollama installation — AI features dependent on external service
- **Scraping**: Must respect rate limits and terms of service of target sites — legal and ethical constraint
- **Database**: SQLite for development (limited concurrency), PostgreSQL for production — scaling constraint
- **Testing**: pytest framework available but minimal coverage — quality gate constraint
- **Deployment**: Docker containerization required for production — infrastructure constraint

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Monolithic CLI architecture | Simple deployment, clear command structure | — Pending |
| XGBoost for price prediction | Industry-standard for tabular data, good performance | ✓ Good |
| Playwright for scraping | Handles JavaScript-heavy sites, stealth capabilities | ✓ Good |
| SQLAlchemy ORM | Type safety, relationship management, migration support | ✓ Good |
| Streamlit dashboard | Rapid development, Python-native, good for data apps | ✓ Good |
| APScheduler for automation | Built-in job scheduling, timezone support | ✓ Good |
| Grok/Ollama for AI | Flexibility between cloud and local AI | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-13 after initialization*
