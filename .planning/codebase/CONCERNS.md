# Technical Concerns & Debt - AutoDeal IA Hunter

## Critical Concerns
1. **Low Test Coverage (Scrapers/AI):** The core value proposition (scraping and AI analysis) has 0% test coverage. This makes the system fragile to website changes and LLM behavior shifts.
2. **Missing Database Migrations:** Alembic is installed but not configured. Schema changes currently require manual intervention or database recreation.
3. **Sensitive Data Leakage:** While Sentry hides secrets, general application logs still potentially leak sensitive information if set to DEBUG level.
4. **Anti-Bot Sophistication:** Target sites (OLX, Standvirtual) are increasing their protection. The current Playwright/Stealth combination may not be sufficient for 2026-level challenges without frequent updates.

## Technical Debt
- **Partial Type Hinting:** Only about 60% of functions have full type annotations, preventing full "Mypy Strict" enforcement.
- **Metrics Visibility:** The system lacks structured metrics for scraping success rates, AI latency, and scheduler performance.
- **Documentation Gaps:** Some utility modules (`proxy_manager.py`, `captcha_solver.py`) lack internal documentation/docstrings.
- **Alembic Configuration:** Project uses multiple models but lacks versioned migration scripts.

## Risks
- **External API Costs:** Heavy reliance on managed scrapers and high-end LLMs could lead to significant operational costs if not monitored/throttled.
- **Model Drift:** The XGBoost valuation model requires regular retraining with fresh data to remain accurate as the car market fluctuates.
- **Dependency Obsolescence:** Several packages (like `playwright-stealth`) require specific older versions of `setuptools` or other utilities, creating potential dependency hell during updates.

## Recommended Fixes
1. **Execute Phase 2 (QA):** Prioritize test coverage for scrapers and AI agents.
2. **Configure Alembic:** Initialize and generate a baseline migration.
3. **Log Scrubbing:** Implement a global log filter to redact sensitive patterns.
4. **Metrics Infrastructure:** Implement a lightweight metrics collector (e.g., Prometheus-ready or local JSON logs).
