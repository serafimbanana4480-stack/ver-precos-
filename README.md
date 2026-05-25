# 🚗 AutoDeal IA Hunter

Intelligent vehicle deal finder for Portugal using AI, machine learning, and web scraping.

## 📊 Project Status

> **Last updated:** 2026-05-25

| Metric | Status |
|--------|--------|
| **Branch** | `master` |
| **Last commit** | `62dfc8c` — feat: BLOCKER — auto-mode recovery failed |
| **Uncommitted changes** | 352 files modified/deleted |
| **Python files** | 576 modules |
| **Total files** | ~1,964 (excl. venv, cache) |

**Current state:**
- ✅ Multi-source scrapers (OLX.pt, Standvirtual, AutoSapo) implemented
- ✅ ML valuation pipeline (XGBoost) with training & prediction
- ✅ AI analysis layer (LLM + Vision)
- ✅ Streamlit dashboard active
- ✅ Scheduler & notification system (Discord, Email, Telegram)
- ✅ Docker Compose setup ready
- ⚠️ Auto-mode recovery blocked — requires manual intervention
- 🔄 Heavy refactoring in progress (Pydantic schemas, database alignment, test coverage)

## 🎯 Features

- **Multi-Source Scraping**: Automatically scrapes OLX.pt, Standvirtual, and AutoSapo.pt
- **ML-Based Valuation**: XGBoost model trained on thousands of listings for accurate price prediction
- **AI Analysis**: 
  - LLM analysis of vehicle descriptions (Grok API or Ollama)
  - Vision AI analysis of vehicle images for condition assessment
- **Deal Scoring**: Calculates deal scores and profit potential
- **Autonomous Agent**: Runs daily to find the best deals automatically
- **Beautiful Dashboard**: Streamlit dashboard with filters, charts, and export options
- **Notifications**: Discord, Email, and Telegram alerts for top deals
- **Docker Ready**: Full Docker Compose setup for easy deployment

## 🏗️ Architecture

```
AutoDeal IA Hunter
├── Scrapers (Playwright + Rust)
│   ├── OLX.pt
│   ├── Standvirtual
│   └── AutoSapo
├── Database (SQLite by default; PostgreSQL optional)
├── ML Valuation (XGBoost)
├── AI Agent
│   ├── LLM Review (Grok/Ollama)
│   └── Vision Analysis
├── Scheduler (APScheduler)
└── Dashboard (Streamlit)
```

## 📋 Requirements

- Python 3.12+
- SQLite (default, no extra install) or PostgreSQL 15+ (optional)
- Docker & Docker Compose (optional)
- Grok API key or Ollama for AI features

## 🚀 Quick Start

### Option 1: Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd autodeal-ia-hunter
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start with Docker Compose:
```bash
docker-compose up -d
```

4. Access the dashboard at `http://localhost:8501`

### Option 2: Local Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install chromium
playwright install-deps chromium
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. (Optional) Configure PostgreSQL in `.env`; otherwise SQLite (`autodeal.db`) is used by default.

5. Initialize database:
```bash
py -3 main.py init
py -3 main.py health-check
```

6. Run scrapers:
```bash
python main.py scrape
```

7. Train ML model:
```bash
python main.py train
```

8. Update valuations:
```bash
python main.py valuate
```

9. Find deals:
```bash
python main.py find-deals
```

10. Start dashboard:
```bash
python main.py dashboard
```

## 📖 Usage

### Command Line Interface

```bash
# Initialize database
py -3 main.py init

# Verify imports (non-pytest script)
py -3 scripts/verify_imports.py

# Run tests (skips legacy compat placeholders by default)
py -3 -m pytest tests/ -q

# Run scrapers
python main.py scrape --source all --vehicle-type carros --max-listings 50

# Train ML model
python main.py train --force

# Update valuations
python main.py valuate --batch-size 100

# Find best deals
python main.py find-deals --limit 20 --min-profit 1500

# Run scheduler (continuous)
python main.py scheduler

# Start dashboard
python main.py dashboard --port 8501
```

### Dashboard Features

- **Overview**: Key metrics and statistics
- **Vehicle Listings**: Filterable, sortable table
- **Top Deals**: AI-reviewed best opportunities
- **Analytics**: Price history and trends
- **Export**: CSV export of listings

## 🔧 Configuration

Edit `.env` file to configure:

- Database connection
- AI API keys (Grok or Ollama)
- Notification settings (Discord, Email, Telegram)
- Scraping intervals
- Deal scoring thresholds

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | - |
| `GROK_API_KEY` | Grok API key for LLM | - |
| `USE_OLLAMA` | Use local Ollama instead of Grok | false |
| `OLLAMA_URL` | Ollama API URL | http://localhost:11434 |
| `DISCORD_WEBHOOK_URL` | Discord webhook for notifications | - |
| `EMAIL_SMTP_*` | Email configuration | - |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - |
| `SCRAPING_INTERVAL_HOURS` | Scraping frequency | 6 |
| `DEAL_SCORE_THRESHOLD` | Minimum deal score | 7.0 |

## 🤖 AI Features

### LLM Analysis

The system uses LLM (Grok or Ollama) to analyze vehicle descriptions for:
- Hidden issues (accidents, mechanical problems)
- Value-adding features (maintenance history, extras)
- Market position assessment
- Overall recommendation (Approved/Rejected)

### Vision Analysis

Vision AI analyzes vehicle images to detect:
- Exterior damage (dents, scratches, rust)
- Tire condition
- Interior wear
- Overall condition score (0-10)

## 📊 ML Model

The XGBoost model is trained on:
- Year, KM, price
- Brand, model, fuel type, transmission
- Horsepower, engine size
- Location data

Features:
- Automatic retraining
- Price prediction with confidence intervals
- Feature importance analysis

## 📅 Scheduler

The automated scheduler runs:
- Daily scraping at configured time
- Periodic analysis every N hours
- Automatic deal finding
- Notification delivery

## 🚢 Deployment

### Railway

1. Connect GitHub repository to Railway
2. Add environment variables
3. Deploy

### Render

1. Push code to GitHub
2. Create new web service on Render
3. Configure environment variables
4. Deploy

### VPS

1. SSH into server
2. Clone repository
3. Configure `.env`
4. Run with Docker Compose:
```bash
docker-compose up -d
```

## 📁 Project Structure

```
autodeal-ia-hunter/
├── main.py                 # Entry point
├── config.py              # Configuration
├── requirements.txt       # Dependencies
├── .env.example          # Environment template
├── scrapers/             # Scraping modules
│   ├── olx_scraper.py
│   ├── standvirtual_scraper.py
│   └── autosapo_scraper.py
├── database/             # Database layer
│   ├── models.py
│   └── db.py
├── valuation/            # ML valuation
│   ├── train_model.py
│   └── predict.py
├── ai_agent/             # AI analysis
│   ├── llm_review.py
│   ├── vision_analysis.py
│   └── deal_finder.py
├── scheduler/            # Job scheduler
│   └── daily_job.py
├── dashboard/            # Streamlit dashboard
│   └── app.py
├── utils/                # Utilities
│   ├── helpers.py
│   └── logging_config.py
├── data/                 # Data directory
├── models/               # ML models
├── logs/                 # Log files
├── exports/              # Exported files
├── Dockerfile            # Docker image
├── docker-compose.yml    # Docker Compose config
└── README.md            # This file
```

## 🔍 Troubleshooting

### Database Connection Issues

Check PostgreSQL is running:
```bash
docker-compose ps postgres
```

### Scraping Errors

- Check internet connection
- Verify source websites are accessible
- Adjust delays in config if rate-limited

### Model Training Fails

Ensure sufficient data:
```bash
python main.py scrape --max-listings 200
```

### AI Features Not Working

- Verify API key is set
- Check Ollama is running if using local AI
- Review logs in `logs/autodeal.log`

## 📝 License

This project is for educational purposes. Respect website terms of service when scraping.

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For issues and questions:
- Check the troubleshooting section
- Review logs in `logs/autodeal.log`
- Open an issue on GitHub

## 🙏 Acknowledgments

- OLX-tracker (Rust): https://github.com/nikuscs/olx-tracker
- Standvirtual scraper: https://github.com/migue1neto/Standvirtual
- Playwright: https://playwright.dev
- XGBoost: https://xgboost.readthedocs.io
- Streamlit: https://streamlit.io

---

**Note**: This tool is for educational and personal use. Always comply with website terms of service and local laws when scraping data.
