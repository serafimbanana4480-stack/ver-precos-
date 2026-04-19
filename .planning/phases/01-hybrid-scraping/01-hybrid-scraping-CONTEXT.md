# Phase 1: Hybrid Scraping Prototype - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning
**Mode:** Auto-generated (Discuss skipped for autonomous execution)

<domain>
## Phase Boundary
Implement a resilient scraping architecture combining local Playwright execution with ZenRows API fallback for Cloudflare-protected listings. Includes Turnstile handling and unified parsing.
</domain>

<decisions>
## Implementation Decisions

### Hybrid Client Architecture
- Use `scrapers/managed_client.py` as the entry point for all HTML retrieval.
- Primary path: Playwright Stealth with local execution.
- Fallback path: ZenRows API integration (triggered on 403, 401, or specific anti-bot patterns).

### Anti-Bot Mitigation
- Implement a **10-second "Settle Time"** using `asyncio.sleep` after the initial page load to allow Turnstile challenges to resolve.
- Add `check_is_blocked` logic to detect common Portuguese anti-bot messages ("Houston, temos um problema", "Access Denied").

### Configuration
- `ZENROWS_API_KEY` to be managed via `config.py` and environment variables.

### the agent's Discretion
- Choice of specific regular expressions for the unified parsing engine.
- Structure of the error classification library.

</decisions>

<code_context>
## Existing Code Insights
- `scrapers/olx_scraper.py` and `scrapers/standvirtual_scraper.py` need refactoring to use the new `ManagedClient`.
- `config.py` already contains basic scraper settings.
</code_context>

<specifics>
## Specific Ideas
- The `ManagedClient` should be a singleton or managed instance accessible by all scrapers.
</specifics>

<deferred>
## Deferred Ideas
- Residential proxy rotation (standard proxies will be used first).
</deferred>
