# External Integrations - AutoDeal IA Hunter

## Data Sources (Scraping)
- **OLX.pt:** Primary source for private listings.
- **Standvirtual.com:** Primary source for professional/quality vehicle listings.
- **AutoSapo.pt:** Secondary source for vehicle listings.

## AI Services
- **x.ai (Grok):** Used for advanced vehicle analysis and deal verification.
- **Ollama (Local):** Local LLM fallback (`deepseek-r1:8b`) for cost-effective AI extraction.
- **Anthropic:** (Reserved/Optional) Secondary LLM provider support.

## Managed Scraping Proxies (Optional)
- **ScraperAPI:** For bypassing advanced anti-bot measures.
- **ZenRows:** Alternative for difficult-to-scrape targets.
- **Apify:** Managed scraping platform integration.

## Monitoring & error Tracking
- **Sentry:** Centralized error logging and performance monitoring.
- **Discord:** Webhook integration for real-time deal alerts.

## Infrastructure
- **PostgreSQL:** (Self-hosted/Managed) Supported for production workloads.
- **Redis:** (Optional) Integrated for caching and task queue management.
- **Telegram:** Bot integration for mobile alerts.

## CAPTCHA Solving
- **2Captcha / Anti-Captcha:** Services for automated CAPTCHA resolution during scraping.
