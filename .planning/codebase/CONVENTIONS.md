# Coding Conventions

**Analysis Date:** 2026-04-13

## Naming Patterns

**Files:**
- snake_case.py for all Python modules (e.g., olx_scraper.py, deal_finder.py)
- No specific test file naming pattern yet (only test_database.py exists)

**Functions:**
- snake_case for all functions (e.g., scrape_listings, train_model, find_best_deals)
- No special prefix for async functions
- Private methods use _prefix (e.g., _parse_brand_model, _handle_consent)

**Variables:**
- snake_case for variables (e.g., vehicle_data, deal_score, max_listings)
- UPPER_SNAKE_CASE for constants (e.g., DATABASE_URL, GROK_API_KEY, MAX_RETRIES)
- _prefix for private class members (e.g., _headless, _timeout)

**Types:**
- PascalCase for class names (e.g., Vehicle, DealFinder, StandvirtualScraper)
- PascalCase for enum classes (e.g., VehicleType, FuelType, Transmission, Source)
- UPPER_CASE for enum values (e.g., VehicleType.CAR, FuelType.GASOLINE)

## Code Style

**Formatting:**
- black 23.12.1 for code formatting
- 88 character line length (black default)
- Double quotes for strings (black default)
- Semicolons not used (Python convention)

**Linting:**
- flake8 7.0.0 for linting
- mypy 1.8.0 for type checking
- Run: `flake8 .` or `mypy .` (not currently automated in scripts)

## Import Organization

**Order:**
1. Standard library imports (os, sys, logging, datetime)
2. Third-party imports (sqlalchemy, pandas, xgboost, playwright)
3. Local imports (from config import, from database.models import)

**Grouping:**
- Blank line between groups
- Not strictly alphabetical within groups

**Path Aliases:**
- No path aliases configured
- Use relative imports for local modules

## Error Handling

**Patterns:**
- Try/except at operation level, log errors, continue processing
- Generic Exception catching with logging
- No custom error classes defined
- Database operations wrapped in context manager with automatic rollback

**Error Types:**
- Log errors at WARNING or ERROR level
- Return None or empty list on failure (e.g., train_model returns None on insufficient data)
- CLI exits with status code 1 on critical errors

**Logging:**
- Log error with context before raising: logger.error(f"Error scraping: {e}")
- No exception chaining currently used

## Logging

**Framework:**
- Python logging module
- Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

**Patterns:**
- Centralized configuration in utils/logging_config.py
- File handler (logs/autodeal.log) and stream handler (stdout)
- Log at service boundaries and external calls
- Format: timestamp, name, level, message

## Comments

**When to Comment:**
- Docstrings for all classes and public functions (triple-quoted strings)
- Explain non-obvious logic (e.g., brand/model parsing)
- Document configuration options in config.py

**Docstrings:**
- Required for all classes and public methods
- Format: Triple-quoted strings at function/class start
- Args and Returns documented in docstrings

**TODO Comments:**
- No TODO comments currently in codebase
- No issue tracking integration

## Function Design

**Size:**
- Functions can be long (e.g., scrape_listings is ~200 lines)
- Private helper methods extracted for parsing logic
- No strict size limit enforced

**Parameters:**
- No strict parameter limit
- Use keyword arguments for optional parameters
- Type hints used in some functions but not consistently

**Return Values:**
- Explicit return statements
- Return None on failure
- Return empty list [] for no results

## Module Design

**Exports:**
- No explicit export mechanism (Python implicit)
- __init__.py files in each directory for package structure
- No barrel files (index.py) used

**Barrel Files:**
- __init__.py files empty or contain minimal imports
- No circular dependency issues observed

---

*Convention analysis: 2026-04-13*
*Update when patterns change*
