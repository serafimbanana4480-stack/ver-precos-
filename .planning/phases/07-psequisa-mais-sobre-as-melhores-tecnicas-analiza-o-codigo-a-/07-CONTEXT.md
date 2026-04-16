# Phase 7: Tech Audit & Deep Optimization - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning
**Source:** Interactive Discussion

<domain>
## Phase Boundary
Comprehensive technical audit and deep architectural optimization of the AutoDeal IA Hunter. The focus is on establishing a highly functional, resilient 2026-grade infrastructure, replacing brittle components with IA-First approaches, and introducing robust asynchronous event handling, without losing the convenience of the CLI monolith.
</domain>

<decisions>
## Implementation Decisions

### Scraping Resilience
- **Stealth Evolution & IA-First:** Move beyond basic Playwright towards advanced stealth tools (like `curl_cffi` or `nodriver` for connection bypassing) but shift the primary extraction burden completely to the **IA-First Scraper**. 
- Eliminate dependence on fragile CSS selectors by piping raw DOM text or markdown to the LLM/Parsera for structured extraction.

### Application Architecture
- **CLI-Monolith with Internal Event Queues:** Keep the `main.py` CLI as the primary orchestrator, but introduce a **Queue/Event-driven architecture** (e.g., lightweight Redis/Celery or `asyncio` queues) under the hood. 
- Separate the heavy scraping jobs from the valuation and ML tasks to run asynchronously without locking the system.

### Data Quality & Model Accuracy (XGBoost)
- **Feature Engineering over Algorithm Swapping:** The XGBoost model logic remains, but its predictive power will be drastically improved through better inputs.
- Use the IA-First Scraper to extract deep metadata (exact trim levels, aesthetic damage, maintenance history text analysis) to feed the model high-quality features.

### Error Handling & Observability
- **Dual Logging Strategy (Hybrid 1 + 3):** Implement structured JSON logging specifically for tracking operation metrics (success/block rates, AI extraction failures) that the Streamlit dashboard can easily consume natively.
- Concurrently maintain the standard plain text `.log` records for easy human readability and debugging.
- Ensure automated secret redaction is active across both formats.

### the agent's Discretion
- Choice between lightweight async queues vs Redis based on complexity/benefit ratio.
- Structure of the JSON metrics schema for the dashboard.
- Specific implementation framework for the IA-First DOM to Markdown conversion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core Operations
- `main.py` — Represents the CLI orchestrator to be preserved.
- `scrapers/ai_scraper.py` — Basis for the IA-First extraction overhaul.
- `config.py` — Update configuration for event queues and dual logging.

</canonical_refs>

<specifics>
## Specific Ideas
- The system should feel like a simple CLI to the user, but operate like an enterprise worker-queue system internally.

</specifics>

<deferred>
## Deferred Ideas
- Testing new ML algorithms (CatBoost/Neural Nets) - deferred in favor of enriching data for XGBoost.
- Fully separating into microservices (FastAPI) - deferred.

---
*Phase: 07-psequisa-mais-sobre-as-melhores-tecnicas-analiza-o-codigo-a*
*Context gathered: 2026-04-16 via gsd-discuss-phase*
