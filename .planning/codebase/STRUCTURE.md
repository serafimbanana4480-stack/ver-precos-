# Directory Structure - AutoDeal IA Hunter

```text
d:/VER PRECOS/
├── ai_agent/           # LLM-based deal scoring and verification
├── analysis/           # Data analysis notebooks and scripts
├── dashboard/          # Streamlit dashboard implementation
├── data/               # Persistent data (SQLite, model files, exports)
├── database/           # SQLAlchemy models and database logic
├── logs/               # Application logs with rotation
├── models/             # Saved XGBoost models and vectorizers
├── scheduler/          # Periodic job management
├── scrapers/           # Modular scrapers (OLX, Standvirtual, AutoSapo)
├── services/           # Core background services
├── tests/              # Pytest suite (unit and integration)
├── utils/              # Shared utilities (logging, proxy, captcha, retry)
├── validation/         # Pydantic validation models for CLI and data
├── valuation/          # ML training and prediction logic
├── .planning/          # Project roadmaps and codebase documentation
├── app.py              # Alternative dashboard entry point
├── config.py           # Centralized Pydantic configuration
├── main.py             # CLI application entry point
├── run_hunter.py       # Standalone execution script
└── start.bat           # Windows startup script
```

## Key Files
- `config.py`: Central settings management using environment variables.
- `main.py`: The main conductor for all system operations.
- `database/models.py`: Defines the core data structure of the application.
- `scrapers/olx_scraper.py`: Primary implementation of the OLX scraping logic.
- `valuation/predict.py`: Core logic for vehicle price valuation.
- `ai_agent/deal_finder.py`: Logic for selecting the best deals based on value/price.
