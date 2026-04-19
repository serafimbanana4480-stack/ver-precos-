# Research: 2026 Anti-Bot Measures and Selector Strategy

## Target Sites: OLX.pt & Standvirtual.com

### 1. Anti-Bot Protections (Current State 2026)
- **Cloudflare Turnstile**: High prevalence of invisible challenges.
- **Fingerprinting**: Canvas/WebGL/TLS fingerprinting is highly active.
- **PoW Loops**: Non-residential proxies are flagged and slowed down.

**Countermeasures Ready/Needed:**
| Status | Countermeasure | Detail |
| :--- | :--- | :--- |
| ✅ | Playwright Stealth | Currently integrated but needs update for latest evasions. |
| ❌ | Settle Time | Need to implement a 5-10s delay after `goto()` for Turnstile to clear. |
| ❌ | Residential Proxies | Current config allows proxies but residential pool is recommended. |
| ❌ | PoW Handling | Need to increase timeouts for initial page load to account for proof-of-work challenges. |

### 2. Structural Analysis & Extraction Strategy

#### OLX.pt
- **Issue**: Year and Km are concatenated into strings like `2021 - 100.000 km`.
- **Selector**: `a[class*='css-'] span:has-text(" km")`.
- **Extraction**: Regex `(\d{4}) - (.* km)` is required for reliability.

#### Standvirtual.com
- **Issue**: Dynamic obfuscated classes (starting with `ooa-`).
- **Selector**: Attribute-based or relative positioning is safer.
- **Extraction**:
    - Km: Identified by " km" suffix.
    - Year: Standalone 4-digit number at end of specs list.

### 3. Critical Improvements for Phase 0.5
1. **Regex Extraction**: Update `SelectorManager` or `olx_scraper.py` to handle concatenated strings instead of assuming 1:1 selector-to-field mapping.
2. **Dynamic Classes**: Implement fuzzy attribute matching (e.g., `[class*="ooa-"]`) combined with position/text analysis.
3. **Turnstile Settle**: Add explicit `time.sleep(10)` or active wait for Turnstile container to disappear.
