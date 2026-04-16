# Coding Conventions - AutoDeal IA Hunter

## Python Style
- **Version:** Python 3.12+
- **Formatting:** Clean code following PEP 8 (implicitly enforced via Black).
- **Type Hinting:** Required for new modules; partially implemented in legacy code.
- **Async/Await:** Preferred for all I/O bound operations (scraping, API calls).

## Design Patterns
- **Pydantic Models:** Used for configuration, CLI arguments, and data validation.
- **Centralized Config:** All settings must be in `config.py` using `BaseSettings`.
- **Dependency Injection:** (Informal) Passing service instances or configuration objects to functions/classes.
- **Fail-Safe Startup:** Environment and dependency verification before main loop execution.

## Error Handling
- **Tenacity:** Use `@retry` decorators for network and database operations.
- **Custom Exceptions:** Domain-specific exceptions defined for scrapers and AI logic.
- **Logging:** 
  - Use `logger = logging.getLogger(__name__)`.
  - Sensitive data (passwords, keys) must be redacted.
  - Standard format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.

## Documentation
- **File Headers:** Every major file should have a docstring explaining its purpose.
- **Function Docstrings:** Use Google/Sphinx style for public methods.
- **Comments:** Explain "Why" not "What" in complex logic sections.

## Database
- **SQLAlchemy 2.0:** Use the modern `Session` and `Select` patterns.
- **Migrations:** Alembic is the designated tool for schema changes.
- **Safety:** Always use transactions; avoid raw SQL where possible.
