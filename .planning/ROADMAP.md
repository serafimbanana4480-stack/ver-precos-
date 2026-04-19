# Roadmap: AutoDeal IA Hunter (Hardened Edition)

## Milestone 1: Stability & Foundation (Current)
*Focus: Fixing critical bugs and ensuring the project can survive the 2026 web landscape on Windows.*

### Phase 0.5: Reliability Audit & Fixes
- [x] **Goal:** Implement critical reliability features for Windows environment. (completed 2026-04-13)
**Success Criteria:**
1. Windows Timeout Watchdog implementation verified.
2. MD5 Stable Hashing for IDs implemented.
3. Unstable `:contains()` selector removal completed.

### Phase 1: Hybrid Scraping Prototype
**Goal:** Integrate dual-layer scraping (Playwright + API fallback) with Turnstile handling.
**Success Criteria:**
1. Unified `HybridScraperClient` implemented.
2. Automatic fallback to ZenRows on detection.
3. 10s "Settle Time" logic verified in Playwright.

### Phase 2: Automated Quality Assurance
**Goal:** Stabilize the test suite and increase coverage.
**Success Criteria:**
1. Integration test regressions resolved.
2. 70% test coverage reached for core utilities.

## Milestone 2: Intelligent Hunting
*Focus: Deal identification and market analysis.*

### Phase 3: Robust Intelligence & Stealth Core
**Goal:** Overhaul scraping core with Hybrid Stealth Pipeline (Solver + Fetcher) and implement Valuation Engine.
**Success Criteria:**
1. Hybrid Pipeline (Playwright Stealth + `curl_cffi`) implemented and verified.
2. Market Value estimation and 0-10 Deal Scoring active.
3. 80%+ success rate on Standvirtual/OLX without manual intervention.

### Phase 4: AI Vision Integration
**Goal:** Integrate image-based damage detection.
**Success Criteria:**
1. Damage detection pipeline active.
2. Automatic condition scoring from images.

## Milestone 3: Scale & Monitoring
*Focus: Parallel execution and production health.*

### Phase 5: Multi-Stream Scanning
**Goal:** Enable parallel scraping streams.
**Success Criteria:**
1. Parallel category scouting within Windows limits.

### Phase 6: Professional Dashboard
**Goal:** Create a visual hunting interface.
**Success Criteria:**
1. Dashboard UI with sorting and notifications.

### Phase 7: psequisa mais sobre as melhores tecnicas analiza o codigo a fundo procura por possiveis erros ou melhroias ou erros de pensamento do projeto verifica se para oq quero fazer e a melhor maneira teria outra mas facil ou funcional o mais importante e funcionar corretamente verfica tudo

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 6
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 7 to break down)
