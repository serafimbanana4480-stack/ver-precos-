---
wave: 1
depends_on: []
files_modified:
  - scrapers/**/*.py
  - database/**/*.py
  - ai_agent/**/*.py
  - valuation/**/*.py
  - utils/**/*.py
  - config.py
  - main.py
  - scheduler/**/*.py
  - pyproject.toml
requirements:
  - QUAL-01
  - QUAL-02
  - QUAL-03
  - QUAL-04
  - QUAL-05
  - QUAL-06
  - QUAL-07
  - QUAL-08
  - QUAL-09
  - QUAL-10
autonomous: true
---

# Phase 1: Code Quality - Plan

**Goal:** Add type hints to all functions and ensure mypy strict mode compliance

## Overview

This phase adds type hints to all Python functions in the codebase and configures mypy strict mode to improve type safety and code quality. The work is organized into three waves:

1. Type hints for core modules (scrapers, database, ai_agent, valuation, utils)
2. Type hints for entry points (config.py, main.py, scheduler)
3. mypy strict mode configuration and compliance

## Plan 1.1: Type Hints for Core Modules

### Task 1.1.1: Add type hints to scrapers

<read_first>
- scrapers/olx_scraper.py
- scrapers/standvirtual_scraper.py
- scrapers/autosapo_scraper.py
- scrapers/base_scraper.py
</read_first>

<action>
Add type hints to all functions in scrapers directory:
- scrapers/olx_scraper.py: Add type hints to OLXScraper class methods
- scrapers/standvirtual_scraper.py: Add type hints to StandvirtualScraper class methods
- scrapers/autosapo_scraper.py: Add type hints to AutoSapoScraper class methods
- scrapers/base_scraper.py: Add type hints to BaseScraper class methods

Use standard Python type hints (PEP 484):
- Add return type annotations to all methods
- Add parameter type annotations to all methods
- Use Optional[T] for nullable types
- Use List[T], Dict[K, V] for collections
- Leverage existing pydantic models for complex data structures

Add `from __future__ import annotations` at the top of each file to enable postponed evaluation of annotations.
</action>

<acceptance_criteria>
- scrapers/olx_scraper.py contains type hints for all methods
- scrapers/standvirtual_scraper.py contains type hints for all methods
- scrapers/autosapo_scraper.py contains type hints for all methods
- scrapers/base_scraper.py contains type hints for all methods
- All files contain `from __future__ import annotations`
- mypy can check these files without errors (basic mode)
</acceptance_criteria>

### Task 1.1.2: Add type hints to database module

<read_first>
- database/db.py
- database/models.py
</read_first>

<action>
Add type hints to all functions in database directory:
- database/db.py: Add type hints to init_db and all database functions
- database/models.py: Add type hints to all SQLAlchemy model classes

Use standard Python type hints:
- Add return type annotations to all functions
- Add parameter type annotations to all functions
- Use Optional[T] for nullable database fields
- Leverage existing pydantic models where applicable

Add `from __future__ import annotations` at the top of each file.
</action>

<acceptance_criteria>
- database/db.py contains type hints for all functions
- database/models.py contains type hints for all model classes
- All files contain `from __future__ import annotations`
- mypy can check these files without errors (basic mode)
</acceptance_criteria>

### Task 1.1.3: Add type hints to ai_agent module

<read_first>
- ai_agent/deal_finder.py
- ai_agent/valuation.py
</read_first>

<action>
Add type hints to all functions in ai_agent directory:
- ai_agent/deal_finder.py: Add type hints to DealFinder class methods
- ai_agent/valuation.py: Add type hints to valuation functions

Use standard Python type hints:
- Add return type annotations to all methods
- Add parameter type annotations to all methods
- Use Optional[T] for nullable types
- Use List[T], Dict[K, V] for collections
- Leverage existing pydantic models for complex data structures

Add `from __future__ import annotations` at the top of each file.
</action>

<acceptance_criteria>
- ai_agent/deal_finder.py contains type hints for all methods
- ai_agent/valuation.py contains type hints for all functions
- All files contain `from __future__ import annotations`
- mypy can check these files without errors (basic mode)
</acceptance_criteria>

### Task 1.1.4: Add type hints to valuation module

<read_first>
- valuation/train_model.py
- valuation/predict.py
</read_first>

<action>
Add type hints to all functions in valuation directory:
- valuation/train_model.py: Add type hints to train_model function
- valuation/predict.py: Add type hints to update_vehicle_valuations function

Use standard Python type hints:
- Add return type annotations to all functions
- Add parameter type annotations to all functions
- Use Optional[T] for nullable types
- Use List[T], Dict[K, V] for collections

Add `from __future__ import annotations` at the top of each file.
</action>

<acceptance_criteria>
- valuation/train_model.py contains type hints for all functions
- valuation/predict.py contains type hints for all functions
- All files contain `from __future__ import annotations`
- mypy can check these files without errors (basic mode)
</acceptance_criteria>

### Task 1.1.5: Add type hints to utils module

<read_first>
- utils/logging_config.py
- utils/health_check.py
</read_first>

<action>
Add type hints to all functions in utils directory:
- utils/logging_config.py: Add type hints to setup_logging function
- utils/health_check.py: Add type hints to get_system_health function

Use standard Python type hints:
- Add return type annotations to all functions
- Add parameter type annotations to all functions
- Use Optional[T] for nullable types
- Use Dict[K, V] for return types where appropriate

Add `from __future__ import annotations` at the top of each file.
</action>

<acceptance_criteria>
- utils/logging_config.py contains type hints for all functions
- utils/health_check.py contains type hints for all functions
- All files contain `from __future__ import annotations`
- mypy can check these files without errors (basic mode)
</acceptance_criteria>

## Plan 1.2: Type Hints for Entry Points

### Task 1.2.1: Add type hints to config.py

<read_first>
- config.py
</read_first>

<action>
Add type hints to all functions and classes in config.py:
- Add type hints to Config class attributes and methods
- Add type hints to any helper functions

Use standard Python type hints:
- Add return type annotations to all methods
- Add parameter type annotations to all methods
- Use Optional[T] for nullable configuration values
- Leverage pydantic for complex configuration structures

Add `from __future__ import annotations` at the top of the file.
</action>

<acceptance_criteria>
- config.py contains type hints for all functions and classes
- config.py contains `from __future__ import annotations`
- mypy can check config.py without errors (basic mode)
</acceptance_criteria>

### Task 1.2.2: Add type hints to main.py

<read_first>
- main.py
</read_first>

<action>
Add type hints to all functions in main.py:
- Add type hints to main function
- Add type hints to any helper functions

Use standard Python type hints:
- Add return type annotations to all functions
- Add parameter type annotations to all functions
- Use Optional[T] for nullable types
- Use None for void return types

Add `from __future__ import annotations` at the top of the file.
</action>

<acceptance_criteria>
- main.py contains type hints for all functions
- main.py contains `from __future__ import annotations`
- mypy can check main.py without errors (basic mode)
</acceptance_criteria>

### Task 1.2.3: Add type hints to scheduler module

<read_first>
- scheduler/daily_job.py
</read_first>

<action>
Add type hints to all functions in scheduler directory:
- scheduler/daily_job.py: Add type hints to run_scheduler function
- Add type hints to any helper functions

Use standard Python type hints:
- Add return type annotations to all functions
- Add parameter type annotations to all functions
- Use Optional[T] for nullable types
- Use None for void return types

Add `from __future__ import annotations` at the top of the file.
</action>

<acceptance_criteria>
- scheduler/daily_job.py contains type hints for all functions
- scheduler/daily_job.py contains `from __future__ import annotations`
- mypy can check scheduler/daily_job.py without errors (basic mode)
</acceptance_criteria>

## Plan 1.3: mypy Strict Mode Compliance

### Task 1.3.1: Configure mypy strict mode

<read_first>
- pyproject.toml
</read_first>

<action>
Configure mypy strict mode in pyproject.toml:
- Add mypy configuration section
- Set strict mode to true
- Configure python_version to 3.12
- Add common mypy settings (warn_return_any, warn_unused_configs, etc.)
- Add exclude patterns for third-party code if needed

Configuration should include:
```
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
```
</action>

<acceptance_criteria>
- pyproject.toml contains [tool.mypy] section
- strict mode is set to true
- python_version is set to 3.12
- Common warning flags are configured
</acceptance_criteria>

### Task 1.3.2: Run mypy strict mode and fix errors

<read_first>
- pyproject.toml
</read_first>

<action>
Run mypy in strict mode and fix any errors:
- Run `mypy . --strict` to check the entire codebase
- Fix type errors reported by mypy
- Add `# type: ignore` comments only when absolutely necessary with explanatory comments
- Iterate until mypy passes without errors

Common fixes may include:
- Adding missing type imports
- Fixing type mismatches
- Adding type assertions where needed
- Using Union types appropriately
</action>

<acceptance_criteria>
- mypy . --strict runs without errors
- Type coverage reaches 100% for all Python files
- Any `# type: ignore` comments have explanatory comments
- All type errors from mypy are resolved
</acceptance_criteria>

### Task 1.3.3: Add mypy to CI pipeline

<read_first>
- .github/workflows/ci.yml
</read_first>

<action>
Add mypy type checking to CI pipeline:
- Add mypy step to GitHub Actions workflow
- Configure mypy to run on every commit
- Fail CI if mypy reports any errors
- Ensure mypy runs with strict mode configuration

CI step should include:
```yaml
- name: Type check with mypy
  run: mypy . --strict
```
</action>

<acceptance_criteria>
- .github/workflows/ci.yml contains mypy type checking step
- mypy runs with --strict flag
- CI will fail if mypy reports errors
- mypy step runs on every commit
</acceptance_criteria>

## Verification Criteria

**Phase 1 is complete when:**
- [ ] All functions in scrapers directory have type hints
- [ ] All functions in database directory have type hints
- [ ] All functions in ai_agent directory have type hints
- [ ] All functions in valuation directory have type hints
- [ ] All functions in utils directory have type hints
- [ ] All functions in config.py have type hints
- [ ] All functions in main.py have type hints
- [ ] All functions in scheduler directory have type hints
- [ ] mypy strict mode is configured in pyproject.toml
- [ ] mypy strict mode passes without errors
- [ ] Type coverage reaches 100%
- [ ] mypy type checking is in CI pipeline

## must_haves

1. Type hints on all functions in scrapers, database, ai_agent, valuation, utils directories
2. Type hints on all functions in entry points (config.py, main.py, scheduler)
3. mypy strict mode configured and passing
4. 100% type coverage achieved
5. CI pipeline enforces type checking
