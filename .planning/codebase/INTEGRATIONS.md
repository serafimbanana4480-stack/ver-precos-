# External Integrations

## LLM Providers

### Grok API (Primary)
- **Purpose**: Vehicle description analysis, market assessment
- **Configuration**: `GROK_API_KEY`, `GROK_API_URL`
- **Usage**: LLM review of vehicle listings via OpenAI-compatible API
- **Fallback**: Ollama (local LLM)

### Ollama (Alternative)
- **Purpose**: Local LLM alternative for vehicle analysis
- **Configuration**: `USE_OLLAMA=true`, `OLLAMA_URL` (default: http://localhost:11434)
- **Usage**: LLM review when Grok unavailable or for privacy
- **Models**: Supports various local models (llama2, mistral, etc.)
- **Integration**: LangChain Ollama for structured outputs

## Scraping Sources

### OLX.pt
- **URL**: https://www.olx.pt
- **Protection**: Cloudflare Turnstile, rate limiting, anti-bot measures
- **Bypass Strategy**: 
  - nodriver for Cloudflare challenge solving
  - curl_cffi with TLS fingerprinting bypass
  - Playwright async with stealth plugin
  - AI extraction fallback (Parsera)
  - Managed services (Apify) as last resort
- **Data**: Cars and motorcycles
- **Circuit Breaker**: Separate instance `_olx_circuit_breaker`

### Standvirtual
- **URL**: https://www.standvirtual.com
- **Protection**: Dynamic JavaScript rendering, anti-scraping
- **Bypass Strategy**:
  - AI extraction as primary method (CSS selectors unreliable)
  - Playwright async with stealth
  - Apify managed service fallback
- **Data**: Cars and motorcycles
- **Circuit Breaker**: Separate instance `_standvirtual_circuit_breaker`

### AutoSapo.pt
- **URL**: https://www.autosapo.pt
- **Protection**: Lighter protection, static content
- **Bypass Strategy**:
  - Playwright async with basic stealth
  - CSS selectors (reliable)
  - AI extraction fallback
- **Data**: Cars and motorcycles
- **Circuit Breaker**: Separate instance `_autosapo_circuit_breaker`

## Managed Scraping Services (Optional Fallbacks)

### Apify
- **Purpose**: Managed scraping service with residential proxies
- **Configuration**: `APIFY_API_KEY`, `APIFY_ACTOR_ID`, `APIFY_ENABLED`
- **Usage**: Fallback when local scraping fails
- **Cost**: Pay-per-use
- **Integration**: Used via managed_client.py

### ScraperAPI
- **Purpose**: Residential proxy scraping for IP bypass
- **Configuration**: `SCRAPERAPI_API_KEY`
- **Usage**: Bypass IP-based blocking
- **Cost**: Pay-per-request
- **Integration**: Used via managed_client.py

### ZenRows
- **Purpose**: Web scraping API with anti-bot bypass
- **Configuration**: `ZENROWS_API_KEY`
- **Usage**: Alternative managed scraping
- **Cost**: Pay-per-request
- **Integration**: Used via managed_client.py

## Notification Channels

### Discord
- **Purpose**: Real-time deal alerts
- **Configuration**: `DISCORD_WEBHOOK_URL`
- **Format**: Rich embed with vehicle details, score, profit
- **Triggers**: High-score deals found (above threshold)
- **Implementation**: scheduler/daily_job.py

### Email
- **Purpose**: Daily deal summaries
- **Configuration**: 
  - `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`
  - `EMAIL_SMTP_USER`, `EMAIL_SMTP_PASSWORD`
  - `EMAIL_FROM`, `EMAIL_TO`
- **Format**: HTML email with vehicle details, top 10 deals
- **Triggers**: Daily analysis results
- **Implementation**: scheduler/daily_job.py

### Telegram
- **Purpose**: Mobile deal alerts
- **Configuration**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- **Format**: Markdown message with vehicle details, top 10 deals
- **Triggers**: High-score deals found
- **Implementation**: scheduler/daily_job.py

## Database

### PostgreSQL
- **Purpose**: Primary data storage
- **Configuration**: `DATABASE_URL`
- **ORM**: SQLAlchemy 2.0+ with async support
- **Migrations**: Alembic for schema management
- **Tables**: 
  - Vehicle (listings, valuations, AI reviews)
  - PriceHistory (price tracking)
  - Watchlist (user favorites)
  - AIReview (LLM analysis results)
  - ScrapingLog (scraping metadata)
- **Connection**: Context manager pattern with retry decorator
- **Health Check**: Dedicated health check endpoint

### Redis (Optional)
- **Purpose**: Caching and distributed deduplication
- **Configuration**: `REDIS_URL`, `USE_REDIS`
- **Client**: redis-py with decode_responses
- **Usage**: 
  - URL deduplication across processes (key: `dedup:url:{url}`)
  - Vehicle processing deduplication (key: `dedup:vehicle:{id}`)
  - TTL: Configurable via `deduplication_window` (default 1 hour)
- **Fallback**: In-memory deduplication (utils/deduplication.py)
- **Implementation**: Automatic fallback if Redis unavailable

## Error Tracking

### Sentry
- **Purpose**: Error monitoring and performance tracking
- **Configuration**: `SENTRY_DSN`, `SENTRY_ENVIRONMENT`
- **Usage**: Automatic error reporting via sentry-sdk
- **Features**: 
  - Stack traces with context
  - Performance monitoring
  - Release tracking
  - Sensitive data filtering
- **Integration**: Initialized in main.py.
