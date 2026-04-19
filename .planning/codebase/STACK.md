# Technology Stack

## Core Technologies

### Language & Runtime
- **Python 3.12+**: Primary language for the application
- **asyncio**: Async I/O framework for concurrent operations

### Database
- **PostgreSQL 15+**: Primary database for storing vehicle listings and metadata
- **SQLAlchemy 2.0.25+**: ORM for database operations with async support
- **Alembic 1.13.1+**: Database migration tool
- **Redis 5.0.1+**: Optional caching and distributed deduplication

### Web Scraping
- **Playwright 1.44.0+**: Browser automation for scraping dynamic content (async API)
- **Playwright Stealth 1.0.6**: Anti-detection plugin for Playwright
- **nodriver**: Stealth browser automation for Cloudflare bypass
- **BeautifulSoup4 4.12.2**: HTML parsing library
- **lxml 4.9.0**: XML/HTML parser
- **Requests 2.31.0**: HTTP library for synchronous requests
- **aiohttp 3.9.0**: Async HTTP client
- **httpx 0.26.0**: Modern async HTTP client with HTTP/2 support
- **curl_cffi 0.7.3**: HTTP client with TLS fingerprinting bypass

### Machine Learning
- **XGBoost 2.0.3+**: Gradient boosting library for price prediction
- **pandas 2.0.0+**: Data manipulation and analysis
- **numpy 1.24.0+**: Numerical computing
- **scikit-learn 1.3.0+: Machine learning utilities
- **joblib 1.3.2**: Model serialization

### AI / LLM
- **OpenAI API**: For Grok API compatibility
- **Anthropic API**: Alternative LLM support
- **Parsera**: AI-powered web scraping with LLM integration
- **LangChain Ollama**: Ollama integration for local LLM
- **LangChain Core**: Core LangChain functionality

### Vision
- **Pillow 10.0.0+**: Image processing library

### Scheduler
- **APScheduler 3.10.4+**: Python job scheduling library with BackgroundScheduler

### Dashboard
- **Streamlit 1.29.0+**: Web application framework for dashboard
- **Plotly 5.18.0**: Interactive plotting library
- **Altair 5.0.1**: Declarative visualization library

### Notifications
- **discord-webhook 1.3.0**: Discord webhook integration

### Utilities
- **python-dotenv 1.0.1**: Environment variable management
- **pydantic 2.6.0**: Data validation using Python type annotations
- **pydantic-settings 2.2.0**: Settings management for Pydantic
- **tenacity 8.2.3**: Retry library with exponential backoff
- **sentry-sdk 1.40.0**: Error tracking and performance monitoring
- **python-dateutil 2.8.2**: Date parsing utilities
- **pytz 2023.3**: Timezone support
- **tqdm 4.66.1**: Progress bars
- **colorama 0.4.6**: Terminal color formatting
- **python-json-logger 2.0.7**: JSON structured logging

### Optional Dependencies
- **reportlab 4.0.7**: PDF generation
- **fpdf 1.7.2**: Alternative PDF library

### Testing
- **pytest 7.4.3**: Testing framework
- **pytest-asyncio 0.21.1**: Async support for pytest
- **pytest-cov 4.1.0**: Code coverage plugin
- **pytest-mock 3.12.0**: Mocking utilities
- **factory-boy 3.3.0**: Test data generation

### Development
- **black 24.1.1**: Code formatter
- **flake8 7.1.0**: Linter
- **mypy 1.9.0**: Static type checker

## Infrastructure

### Containerization
- **Docker**: Containerization platform
- **Docker Compose**: Multi-container orchestration

### Deployment
- **Railway**: Cloud deployment platform
- **Render**: Alternative cloud deployment platform
- **VPS**: Self-hosted deployment option

## External Services

### LLM APIs
- **Grok API**: Primary LLM for vehicle analysis
- **Ollama**: Local LLM alternative (self-hosted at http://localhost:11434)

### Managed Scraping Services
- **Apify**: Managed scraping service (optional fallback)
- **ScraperAPI**: Residential proxy scraping service (optional)
- **ZenRows**: Web scraping API (optional)

### Notification Services
- **Discord**: Webhook-based notifications
- **Email**: SMTP-based email notifications
- **Telegram**: Bot-based notifications

## Version Control
- **Git**: Version control system
- **GitHub**: Code hosting and CI/CD

## Key Technical Decisions

### Async-First Architecture
- All scrapers use async/await pattern
- Playwright async API for browser automation
- aiohttp/httpx for async HTTP requests
- asyncio event loop management in main.py

### Resilience Patterns
- Circuit breakers per scraper (separate instances)
- Retry decorators with exponential backoff
- Fallback chain: Playwright → CSS selectors → AI extraction → Managed services
- In-memory and Redis-based deduplication with fallback

### Data Validation
- Pydantic models for structure validation
- Custom data validators for business logic
- Dual validation (structure + content)
