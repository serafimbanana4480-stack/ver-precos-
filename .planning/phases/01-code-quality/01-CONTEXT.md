# Phase 1: Code Quality - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Add type hints to all functions in the codebase and ensure mypy strict mode compliance to improve type safety and code quality.

</domain>

<decisions>
## Implementation Decisions

### Type Hint Strategy
- Add type hints incrementally, starting with core modules (scrapers, database, ai_agent, valuation, utils)
- Then add type hints to entry points (config.py, main.py, scheduler)
- Use standard Python type hints (PEP 484)
- Leverage existing pydantic models for data structures where applicable

### mypy Strict Mode
- Enable mypy strict mode after adding type hints to all functions
- Use `# type: ignore` sparingly with explanatory comments for unavoidable cases
- Target 100% type coverage for all Python files

### Type Coverage Enforcement
- Add mypy to CI pipeline to enforce type checking on every commit
- Configure mypy strict mode in pyproject.toml or setup.cfg
- Fail CI if mypy reports any errors

### Claude's Discretion
- Specific type hint patterns (e.g., Union vs Optional, Protocol vs ABC) can be decided during implementation
- mypy configuration details can be adjusted as needed during implementation
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements
- `.planning/REQUIREMENTS.md` — QUAL-01 through QUAL-10 (type hints and mypy strict mode)

### Codebase Structure
- `.planning/codebase/STRUCTURE.md` — Module organization
- `.planning/codebase/CONVENTIONS.md` — Code style patterns

### Configuration
- `config.py` — Configuration structure (for entry point type hints)
- `pyproject.toml` — Project configuration (for mypy setup)

### External Specs
- PEP 484 — Type hints specification
- mypy documentation — Strict mode configuration
</canonical_refs>

<specifics>
## Specific Ideas

- Use `from __future__ import annotations` to enable postponed evaluation of annotations (Python 3.7+)
- Consider using `typing.TYPE_CHECKING` for imports that are only needed for type hints
- Leverage existing pydantic models as type hints for complex data structures
- Add `# type: ignore` comments only when absolutely necessary with explanation
</specifics>

<deferred>
## Deferred Ideas

None — all scope items are in the roadmap for this milestone
</deferred>

---
*Phase: 01-code-quality*
*Context gathered: 2026-04-14*
