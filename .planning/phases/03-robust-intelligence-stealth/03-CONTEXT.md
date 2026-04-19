# Phase 3: Robust Intelligence & Stealth Core - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning
**Source:** User Request for "Giant Improvement Plan" + "Better Way" Research

<domain>
## Phase Boundary

This phase transforms the fragile scraping foundation into a production-hardened extraction engine and implements the initial Deal Scoring logic. It addresses the 100% failure rate seen in recent logs.

### Primary Drivers
- **Anti-Bot Defeat:** Move beyond basic Playwright to a stealth+managed architecture.
- **Selector Stability:** Repair Standvirtual extraction which is currently 100% broken.
- **Infrastructure Fix:** Resolve Ollama/Parsera connection issues and proxy pool emptiness.
- **Intelligence:** Implement the basic Market Value Estimation and Deal Scoring (0-10).
</domain>

<decisions>
## Implementation Decisions

### 1. Stealth Extraction Layer
- **Locked:** Implement `playwright-stealth` in `managed_client.py`.
- **Locked:** Force TLS fingerprint matching (JA4 signature mimicry) for local requests.
- **Locked:** Implement "Human-Like" behavior: Randomized scroll, hover-before-click, and varied dwell times.
- **Locked:** Integrate Residential Proxies into the `proxy_manager.py` (mandatory).

### 2. Standvirtual Repair
- **Locked:** Re-audit Standvirtual DOM. Use more robust data attributes (e.g., `[data-testid]`) rather than volatile classes.
- **Locked:** Implement a "Consent Wall Handler" to automatically accept cookies/GDPR before scraping.

### 3. Managed Fallback Resilience
- **Locked:** Fix `ai_scraper.py` connection logic. Ensure Ollama/DeepSeek-R1 is available or fallback to OpenAI/Anthropic.
- **Locked:** Ensure ZenRows is primary managed fallback when local stealth fails.

### 4. Deal Score Engine (Original Phase 3)
- **Locked:** Implement `valuation/engine.py`.
- **Locked:** Algorithm: `Score = f(Price, Year, Km, BrandValue, MarketAverage)`.
- **Locked:** Market value should be calculated daily based on successful scraps of the last 30 days.

### the agent's Discretion
- Selection of specific UI components for the deal score display in logs.
- Specific weights for the scoring algorithm (to be tuned later).
</decisions>

<canonical_refs>
## Canonical References
- [managed_client.py](file:///d:/VER%20PRECOS/scrapers/managed_client.py) — Core resiliency logic.
- [olx_scraper.py](file:///d:/VER%20PRECOS/scrapers/olx_scraper.py) — Current OLX implementation.
- [standvirtual_scraper.py](file:///d:/VER%20PRECOS/scrapers/standvirtual_scraper.py) — Current Standvirtual implementation (BROKEN).
- [ valuation/engine.py](file:///d:/VER%20PRECOS/valuation/engine.py) — Target for scoring logic.
</canonical_refs>
