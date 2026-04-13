# External Integrations

**Analysis Date:** 2026-04-13

## APIs & External Services

**AI/LLM Services:**
- Grok API (xAI) - LLM analysis of vehicle descriptions and vision analysis
  - SDK/Client: openai npm package v1.6.1 (API compatible)
  - Auth: API key in GROK_API_KEY env var
  - Endpoints used: Chat completions, vision analysis
  - Alternative: Ollama (local LLM) via OLLAMA_URL env var

- Ollama - Local LLM alternative
  - Integration method: HTTP API via httpx client
  - Auth: None (local service)
  - Models: grok-2-vision, LLM_MODEL, VISION_MODEL configurable

**Web Scraping Targets:**
- OLX.pt - Vehicle listings
  - Integration method: Playwright browser automation
  - Auth: None (public site)
  - Rate limits: Respect REQUEST_DELAY_SECONDS (default 2s), MAX_RETRIES (default 3)

- Standvirtual.com - Vehicle listings
  - Integration method: Playwright browser automation with stealth
  - Auth: None (public site)
  - Rate limits: Respect REQUEST_DELAY_SECONDS, MAX_RETRIES

- AutoSapo.pt - Vehicle listings
  - Integration method: Playwright browser automation
  - Auth: None (public site)
  - Rate limits: Respect REQUEST_DELAY_SECONDS, MAX_RETRIES

## Data Storage

**Databases:**
- SQLite - Local development database
  - Connection: sqlite:///autodeal.db (default when USE_SQLITE=true)
  - Client: SQLAlchemy ORM v2.0.25
  - Migrations: None (Alembic available but not configured)

- PostgreSQL - Production database (optional)
  - Connection: via DATABASE_URL env var
  - Client: SQLAlchemy ORM v2.0.25 with psycopg (commented out in requirements)
  - Migrations: Alembic v1.13.1 available
  - Connection pooling: QueuePool with 5 base connections, 10 max overflow

**Caching:**
- Redis - Optional caching layer
  - Connection: REDIS_URL env var (default: redis://localhost:6379/0)
  - Client: redis npm package v5.0.1
  - Usage: Optional (USE_REDIS=false by default)

## Authentication & Identity

**Auth Provider:**
- None - No user authentication system
  - Application is autonomous agent, not multi-user
  - No OAuth or session management

**API Authentication:**
- Grok API - Bearer token authentication
  - Token storage: GROK_API_KEY env var
  - Token rotation: Manual (update env var)

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service
  - Logging to file (logs/autodeal.log) and stdout

**Analytics:**
- None - No analytics service

**Logs:**
- File-based logging - logs/autodeal.log
  - Integration: Python logging module
  - Rotation: None (append-only)
  - Format: Structured with timestamp, name, level, message

## CI/CD & Deployment

**Hosting:**
- Docker container - docker-compose.yml provided
  - Deployment: Manual docker-compose up -d
  - Environment vars: .env file (gitignored)

**CI Pipeline:**
- None - No CI/CD configured

## Environment Configuration

**Development:**
- Required env vars: None (all have defaults)
- Secrets location: .env file (gitignored, .env.example provided)
- Mock/stub services: SQLite for database, Ollama as optional LLM alternative

**Staging:**
- Not configured (single environment)

**Production:**
- Secrets management: Environment variables in Docker container
- Database: PostgreSQL recommended
- Failover/redundancy: Not configured

## Webhooks & Callbacks

**Incoming:**
- Discord Webhook - Deal notifications
  - Endpoint: DISCORD_WEBHOOK_URL env var
  - Verification: None (trust URL)
  - Events: Top deals found

**Outgoing:**
- None - No outgoing webhooks configured

**Email:**
- SMTP - Optional email notifications
  - Provider: Gmail via smtp.gmail.com (configurable via EMAIL_SMTP_HOST)
  - Auth: EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD
  - Recipients: EMAIL_TO (comma-separated)

**Telegram:**
- Telegram Bot - Optional notifications
  - Auth: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  - Bot API: Telegram Bot API via httpx

---

*Integration audit: 2026-04-13*
*Update when adding/removing external services*
