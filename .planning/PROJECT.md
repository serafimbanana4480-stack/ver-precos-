# AutoDeal IA Hunter: Hardened Edition

Intelligent vehicle deal finder for the Portuguese market, redesigned for maximum resilience, Windows compatibility, and hybrid scraping capabilities.

## 🎯 Vision & Goals
Transform fragments of the Portuguese car market into actionable investment opportunities through autonomous analysis. This "Hardened Edition" focuses on overcoming the aggressive anti-bot measures of 2026 (Cloudflare Turnstile) and ensuring 100% stability on Windows environments.

## 🛠️ Technology Stack
- **Core**: Python 3.12+ (managed with venv)
- **Scraping Engine**: Hybrid (Playwright Stealth + External APIs like ZenRows/Bright Data)
- **Database**: PostgreSQL (Production) / SQLite (Testing) using SQLAlchemy ORM
- **AI Analysis**: Grok/Ollama for textual review, LLaVA for vision-based damage assessment
- **Validation**: Pydantic v2 with strict data type enforcement
- **Task Management**: Structured Queue with priority handling and rate-limit awareness

## 🛡️ Resilience Principles
1. **Windows Reliability**: No reliance on Unix-specific signals; using thread-watchdogs for operation timeouts.
2. **Anti-Bot Defense**: Mandatory navigation "settle times" and automatic fallback to paid proxy/API services upon detection.
3. **Data Integrity**: Stable MD5-based identification to eliminate duplicates.
4. **Observable Growth**: Detailed `[PROGRESS]` logging across all modules.
