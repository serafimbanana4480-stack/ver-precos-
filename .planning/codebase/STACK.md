# Technology Stack

**Analysis Date:** 2026-04-13

## Languages

**Primary:**
- Python 3.12+ - All application code

**Secondary:**
- None - All code is Python

## Runtime

**Environment:**
- Python 3.12+ (LTS recommended)
- No browser runtime required
- Playwright Chromium for web scraping (managed by Playwright)

**Package Manager:**
- pip
- Lockfile: `requirements.txt` present

## Frameworks

**Core:**
- SQLAlchemy 2.0.25 - ORM for database operations
- Playwright 1.40.0 - Browser automation for web scraping
- APScheduler 3.10.4 - Job scheduling
- Streamlit 1.29.0 - Dashboard UI framework

**Testing:**
- pytest 7.4.3 - Unit and integration tests
- pytest-asyncio 0.21.1 - Async test support

**Build/Dev:**
- None - Pure Python, no build step required
- black 23.12.1 - Code formatting
- flake8 7.0.0 - Linting
- mypy 1.8.0 - Type checking

## Key Dependencies

**Critical:**
- xgboost 2.0.3 - ML model for price prediction
- pandas 2.1.4 - Data manipulation and analysis
- numpy 1.26.2 - Numerical computing
- scikit-learn 1.4.0 - ML utilities and preprocessing
- openai 1.6.1 - LLM API integration (Grok compatibility)

**Infrastructure:**
- python-dotenv 1.0.0 - Environment configuration
- pydantic 2.5.0 - Data validation
- beautifulsoup4 4.12.2 - HTML parsing
- aiohttp 3.9.1 - Async HTTP client
- httpx 0.26.0 - HTTP client for API calls

## Configuration

**Environment:**
- `.env` file for environment variables (`.env.example` provided)
- Key configs: DATABASE_URL, GROK_API_KEY, OLLAMA_URL, DISCORD_WEBHOOK_URL
- Centralized configuration in `config.py`

**Build:**
- No build configuration required
- Direct Python execution

## Platform Requirements

**Development:**
- Any platform with Python 3.12+ (Windows, macOS, Linux)
- Playwright browsers (install via `playwright install chromium`)
- PostgreSQL 15+ (optional - SQLite for local dev)
- Grok API key or Ollama for AI features

**Production:**
- Docker container recommended (Dockerfile and docker-compose.yml provided)
- PostgreSQL database
- Environment variables for secrets
- Optional: Redis for caching

---

*Stack analysis: 2026-04-13*
*Update after major dependency changes*
