# Code Conventions

## Python Style

### Formatting
- **Black**: Code formatter (configured in pyproject.toml)
- **Line length**: 88 characters (Black default)
- **Import ordering**: Grouped (stdlib, third-party, local)
- **Type hints**: Required for function signatures

### Linting
- **Flake8**: Linter for style and error checking
- **MyPy**: Static type checker (configured in mypy.ini)
- **Strict mode**: Enabled for better type safety

### Naming Conventions
- **Classes**: PascalCase (e.g., `OLXScraper`)
- **Functions/Methods**: snake_case (e.g., `scrape_listings`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_LISTINGS`)
- **Private members**: Leading underscore (e.g., `_llm`)
- **Protected members**: Single underscore (e.g., `_parse_element`)
- **Circuit breakers**: Prefix with underscore (e.g., `_olx_circuit_breaker`)

## Async/Await Patterns

### Async Functions
- All scrapers use async/await pattern
- Playwright async API exclusively
- aiohttp/httpx for async HTTP
- asyncio.run() only at entry point (main.py)
- No conditional asyncio.run() - consistent async pattern

### Event Loop Management
- Never call asyncio.run() inside async functions
- Use existing event loop from context
- AI scraper has event loop management for nested async contexts (Parsera)
- Check for closed loops and create new ones if needed

### Error Handling in Async
- Use try/except blocks for async operations
- Log errors with context (URL, source, operation)
- Return empty lists on failure (not None)
- Use proper await for async calls

## Database Patterns

### Session Management
- Use context manager: `with get_db_context() as db:`
- Never manually close sessions
- Commit explicitly before context exit
- Rollback on errors
- Use retry decorator for connection resilience

### Query Patterns
- Use SQLAlchemy ORM queries
- Filter with expressions, not raw SQL
- Use indexes for common queries
- Batch operations where possible (avoid N+1 queries)
- Use to_dict() to avoid DetachedInstanceError

### Model Conventions
- Use SQLAlchemy ORM models
- Define relationships with back_populates
- Use enums for categorical fields
- Add indexes for query performance
- No duplicate column definitions

## Validation Patterns

### Pydantic Models
- Use Pydantic for structure validation
- Define field validators for custom logic
- Use Field() for constraints
- Keep models in validation/ directory
- Aligned validation across Pydantic and custom validators

### Custom Validators
- Use utils/data_validation.py for business logic
- Return (is_valid, error_message) tuples
- Validate ranges, formats, business rules
- Log validation failures
- Year validation: >= 1980 (Portuguese market)

### Dual Validation
- Always validate structure (Pydantic)
- Always validate content (custom)
- Fail fast on structure errors
- Log warnings for content issues

## Logging Conventions

### Log Levels
- **DEBUG**: Detailed diagnostic information
- **INFO**: General progress messages
- **WARNING**: Unexpected but recoverable issues
- **ERROR**: Errors that don't stop execution
- **CRITICAL**: Errors that stop execution

### Log Format
- Use structured logging (python-json-logger)
- Include context (module, function, line)
- Use prefixes for categorization (e.g., `[SCRAPER]`, `[DATABASE]`, `[AI_SCRAPER]`)
- Never log sensitive data (API keys, passwords)

### Log Messages
- Be descriptive and specific
- Include relevant context (URL, source, vehicle_id)
- Use consistent prefixes
- Log before and after operations
- Track skip reasons (dedup, validation, missing URL)

## Configuration Patterns

### Environment Variables
- Use .env for local development
- Use pydantic-settings for configuration
- Define defaults in config.py
- Validate settings at startup

### Settings Structure
- Group related settings
- Use validators for constraints
- Provide property methods for derived values
- Document non-obvious settings

## Error Handling Patterns

### Retry Decorators
- Use tenacity for retries
- Separate decorators for different operation types (retry_network, retry_ai_api, retry_database)
- Configure exponential backoff
- Log retry attempts

### Circuit Breakers
- Use circuit breakers for external services
- Separate breakers per scraper (not shared)
- Configure failure threshold and recovery timeout
- Log circuit state changes
- Prevent cascading failures across sources

### Graceful Degradation
- Fallback to alternative methods
- Return empty results on failure
- Log fallback usage
- Never crash on single failure
- Redis with in-memory fallback for deduplication

## Testing Patterns

### Test Structure
- Use pytest for testing
- Separate unit and integration tests
- Use fixtures for common setup
- Use factories for test data

### Test Naming
- Prefix with `test_`
- Describe what is being tested
- Use descriptive names
- Group related tests

### Async Testing
- Use pytest-asyncio for async tests
- Mark async tests with @pytest.mark.asyncio
- Use pytest fixtures for async setup
- Mock external dependencies

## Documentation Patterns

### Docstrings
- Use Google-style docstrings
- Document parameters and return values
- Include examples for complex functions
- Document exceptions raised

### Comments
- Explain why, not what
- Comment complex logic
- Remove obsolete comments
- Keep comments up to date
- Document technical decisions (e.g., why consistent hash instead of LabelEncoder)

## Data Processing Patterns

### Encoding
- Use deterministic hashing for categorical variables (consistent_hash)
- Document when proper encoders (LabelEncoder) should be used
- Ensure consistency across runs
- Avoid random hash() for ML features

### Deduplication
- Use Redis for distributed deduplication
- Fallback to in-memory for single-process
- Use TTL-based expiration
- Log deduplication statistics
