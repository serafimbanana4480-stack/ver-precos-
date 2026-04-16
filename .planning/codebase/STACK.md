# Technology Stack - AutoDeal IA Hunter

## Core Engine
- **Language:** Python 3.12+
- **Database:** SQLite (Default for local) / PostgreSQL (Supported via SQLAlchemy)
- **ORM:** SQLAlchemy 2.0+
- **Migrations:** Alembic 1.13+ (Installed but needs configuration)
- **Validation:** Pydantic 2.6+ (Core models), Pydantic-settings 2.2+ (Configuration)

## Web Scraping
- **Engine:** Playwright 1.44+
- **Stealth:** `playwright-stealth`
- **Parsing:** BeautifulSoup4, lxml
- **HTTP Clients:** Requests, aiohttp, httpx
- **AI Extraction:** Parsera (AI-powered scraping)
- **Managed Services:** ScraperAPI, ZenRows, Apify (Integrated but optional)

## AI & Machine Learning
- **ML Engine:** XGBoost 2.0.3 (Price prediction)
- **Data Analysis:** Pandas, NumPy
- **Model Management:** Scikit-learn, joblib
- **LLM Integration:** 
  - **Ollama:** Local model execution (`deepseek-r1:8b`)
  - **Grok API:** x.ai integration for high-end analysis
  - **LangChain:** For LLM orchestration

## Frontend & Dashboard
- **Framework:** Streamlit 1.29+
- **Visualization:** Plotly, Altair

## Operations & Infrastructure
- **Scheduler:** APScheduler 3.10+
- **Monitoring:** Sentry SDK
- **Notifications:** Discord Webhook
- **Logging:** Standard logging with log rotation
- **Containerization:** Docker & Docker Compose
- **Environment:** python-dotenv

## Development & Quality
- **Testing:** Pytest, pytest-asyncio, pytest-cov, pytest-mock
- **Mocking:** factory-boy
- **Linting/Formatting:** Black, Flake8, Mypy
