# Phase 3: Ultra-Resilient Stealth Extraction & Intelligent Valuation - Research

## 1. The "Better Way" for 2026 Scraping
The current implementation relies on a "Settle Time" and basic Playwright, which is being identified and blocked. To survive the 2026 anti-bot landscape (Cloudflare Turnstile, Datadome, etc.), we must upgrade to a **Hybrid Pipeline Architecture**.

### Hybrid Pipeline Strategy
1. **The Browser Solver:** Use a stealth-patched browser automation tool (like `nodriver` or `playwright-stealth`) to:
   - Solve the initial JavaScript challenge.
   - Capture the `cf_clearance` cookie and specific session tokens.
2. **The High-Volume Fetcher:** Use `curl_cffi` to perform the actual listing fetches using the captured cookies.
   - **Benefit:** `curl_cffi` can spoof JA4/JA3 TLS fingerprints, making the requests indistinguishable from a real browser at the networking layer.
   - **Cost:** Significantly lower CPU/RAM than keeping multiple Playwright instances open.

## 2. Technical Requirements
- **Library:** `curl_cffi` for TLS/JA4 fingerprinting.
- **Stealth:** `playwright-stealth` or transitioning core automation to `nodriver`.
- **Proxies:** Mandatory integration of Residential Proxy Pool (e.g., Bright Data, SmartProxy, or similar) into `proxy_manager.py`.
- **Selectors:** Transition Standvirtual scrapers to use `[data-testid]` or JSON extract (if found in the page source) instead of volatile CSS classes.

## 3. Dealing with Blocking Patterns
- **Blocking Detected:** `houston, temos um problema` is a known OLX/Cloudflare block message.
- **Mitigation:**
  - Increase retry backoff (exponential).
  - Implement automatic "Session Refresh" (Browser Solver re-runs to get new cookies).

## 4. Intelligent Valuation Engine
- **Logic:** Valuation should not just be `Average - Current`. It must account for:
  - **Km Adjusted Price:** Price per Km compared to model average.
  - **Year Depreciation:** Comparing relative value within the same production cycle.
  - **Condition Score:** (Phase 4 integration) Placeholder for vision analysis results.
- **Storage:** New table `valuation_history` to track model averages over time.

## 5. Implementation Roadmap for this Phase
- [ ] Task 1: Refactor `managed_client.py` to include `curl_cffi` fetcher.
- [ ] Task 2: Implement Browser Solver logic (Session Manager).
- [ ] Task 3: Integrate Residential Proxies into `proxy_manager.py`.
- [ ] Task 4: Fix Standvirtual selectors using high-fidelity attributes.
- [ ] Task 5: Implement `valuation/engine.py` for Deal Scoring.
