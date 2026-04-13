# Phase 1.1: Validation Layer

**Wave:** 1
**Depends on:** None
**Files modified:** config.py, main.py, scrapers/*.py, ai_agent/*.py
**Autonomous:** true

## Requirements

- VAL-01 - Add pydantic-settings for configuration validation at startup
- VAL-02 - Create pydantic models for CLI argument validation
- VAL-03 - Create pydantic models for scraped data before database insertion
- VAL-04 - Validate scraped data structure and types before saving
- VAL-05 - Add validation for LLM response structure before processing
- VAL-06 - Make validation rules configurable with overrides for edge cases
- VAL-07 - Log all validation failures with context and severity
- VAL-08 - Add alerting for systematic validation failures

## Tasks

### Task 1: Add pydantic-settings to requirements

<read_first>
requirements.txt
</read_first>

<action>
Add pydantic-settings==2.1.0 to requirements.txt in the dependencies section
</action>

<acceptance_criteria>
requirements.txt contains pydantic-settings==2.1.0
</acceptance_criteria>

### Task 2: Refactor config.py to use pydantic-settings

<read_first>
config.py
requirements.txt
</read_first>

<action>
Replace the existing Config class in config.py with a pydantic BaseSettings implementation:

1. Import from pydantic_settings import BaseSettings, SettingsConfigDict
2. Create a Settings class that inherits from BaseSettings
3. Add model_config with SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
4. Convert all configuration variables to typed fields with proper type hints
5. Keep the same variable names for backward compatibility
6. Add validation methods where needed (e.g., URL validation, port range checks)
7. Create a settings instance at module level: settings = Settings()
8. Update all references from Config() to settings
</action>

<acceptance_criteria>
config.py imports BaseSettings from pydantic_settings
config.py contains class Settings(BaseSettings)
config.py has settings = Settings() instance
config.py has no remaining Config class
</acceptance_criteria>

### Task 3: Create validation models for CLI arguments

<read_first>
main.py
</read_first>

<action>
Create a new file validation/cli_models.py with pydantic models for CLI argument validation:

1. Create ScrapeArgs model with fields: source (str), vehicle_type (str), max_listings (int)
2. Create TrainArgs model with fields: force (bool), model_type (str)
3. Create FindDealsArgs model with fields: limit (int), min_profit (float)
4. Add validation: max_listings > 0, limit > 0, min_profit >= 0
5. Add from_argparse classmethod to convert argparse Namespace to pydantic model
6. In main.py, after argparse parsing, validate arguments using these models
7. On validation error, print error message and exit with status 1
</action>

<acceptance_criteria>
validation/cli_models.py exists
validation/cli_models.py contains ScrapeArgs class
validation/cli_models.py contains TrainArgs class
validation/cli_models.py contains FindDealsArgs class
main.py imports validation.cli_models
main.py validates CLI arguments after argparse parsing
</acceptance_criteria>

### Task 4: Create validation models for scraped data

<read_first>
database/models.py
scrapers/standvirtual_scraper.py
</read_first>

<action>
Create a new file validation/scraped_models.py with pydantic models for scraped vehicle data:

1. Create ScrapedVehicle model matching Vehicle model fields
2. Add field validators: year >= 1990, km >= 0, price > 0
3. Add brand validator against known brands list
4. Create ScrapedPriceHistory model for price history
5. In scrapers, before saving to database, validate scraped data using these models
6. On validation error, log warning with vehicle ID and skip that listing
7. Add VALIDATION_MODE config option: strict (fail) vs lenient (log and skip)
</action>

<acceptance_criteria>
validation/scraped_models.py exists
validation/scraped_models.py contains ScrapedVehicle class
validation/scraped_models.py contains ScrapedPriceHistory class
scrapers/standvirtual_scraper.py imports validation.scraped_models
scrapers/standvirtual_scraper.py validates data before database save
config.py has VALIDATION_MODE option
</acceptance_criteria>

### Task 5: Create validation models for LLM responses

<read_first>
ai_agent/llm_review.py
ai_agent/vision_analysis.py
</read_first>

<action>
Create a new file validation/ai_models.py with pydantic models for AI responses:

1. Create LLMReviewResponse model with fields: recommendation (str), confidence (float), issues (List[str])
2. Add validators: confidence between 0.0 and 1.0, recommendation in ["Approved", "Rejected"]
3. Create VisionAnalysisResponse model with fields: condition_score (int), damage_detected (List[str])
4. Add validators: condition_score between 0 and 10
5. In ai_agent modules, validate LLM responses before processing
6. On validation error, log warning and use fallback (no AI review)
</action>

<acceptance_criteria>
validation/ai_models.py exists
validation/ai_models.py contains LLMReviewResponse class
validation/ai_models.py contains VisionAnalysisResponse class
ai_agent/llm_review.py imports validation.ai_models
ai_agent/llm_review.py validates LLM responses
ai_agent/vision_analysis.py imports validation.ai_models
ai_agent/vision_analysis.py validates vision responses
</acceptance_criteria>

### Task 6: Add configurable validation rules

<read_first>
config.py
validation/cli_models.py
validation/scraped_models.py
validation/ai_models.py
</read_first>

<action>
Add configurable validation rules with override capability:

1. In config.py, add VALIDATION_STRICT_MODE (bool) default false
2. In config.py, add VALIDATION_OVERRIDE_RULES (dict) for custom rules
3. In validation models, add a classmethod to load overrides from config
4. Add allow_override parameter to validation methods
5. Document override format in config.py comments
6. Add example overrides to .env.example
</action>

<acceptance_criteria>
config.py has VALIDATION_STRICT_MODE setting
config.py has VALIDATION_OVERRIDE_RULES setting
.env.example has VALIDATION_STRICT_MODE example
.env.example has VALIDATION_OVERRIDE_RULES example
validation models have override support
</acceptance_criteria>

### Task 7: Log validation failures with context

<read_first>
utils/logging_config.py
validation/*.py
</read_first>

<action>
Implement structured logging for validation failures:

1. In utils/logging_config.py, add validation_error logger
2. In all validation modules, on validation failure:
   - Log at WARNING level in lenient mode
   - Log at ERROR level in strict mode
   - Include field name, invalid value, expected value
   - Include source (file, function, line)
   - Include vehicle ID or context if available
3. Use structured logging format with JSON or key-value pairs
4. Add validation_failure_count metric
</action>

<acceptance_criteria>
utils/logging_config.py has validation_error logger
validation modules log failures with context
validation logs include field name and invalid value
validation logs include source location
</acceptance_criteria>

### Task 8: Add alerting for systematic validation failures

<read_first>
config.py
utils/logging_config.py
</read_first>

<action>
Add alerting for systematic validation failures:

1. In config.py, add VALIDATION_FAILURE_THRESHOLD (int) default 10
2. In config.py, add VALIDATION_ALERT_ENABLED (bool) default true
3. In utils/logging_config.py, track validation failure count per hour
4. When failure count exceeds threshold:
   - Log at CRITICAL level
   - Send alert if notification channels configured
   - Include failure rate and top failing fields
5. Reset counter hourly
6. Add validation_health endpoint (returns failure rate)
</action>

<acceptance_criteria>
config.py has VALIDATION_FAILURE_THRESHOLD setting
config.py has VALIDATION_ALERT_ENABLED setting
utils/logging_config.py tracks validation failure count
utils/logging_config.py logs CRITICAL when threshold exceeded
</acceptance_criteria>

## Verification Criteria

- [ ] pydantic-settings installed and configured
- [ ] Configuration validated at startup with clear error messages
- [ ] CLI arguments validated before processing
- [ ] Scraped data validated before database insertion
- [ ] LLM responses validated before processing
- [ ] Validation rules configurable via environment
- [ ] Validation failures logged with full context
- [ ] Systematic failures trigger alerts
- [ ] Existing functionality preserved (backward compatible)

## Must Haves

- Configuration validation prevents invalid startup
- Invalid CLI arguments are rejected with clear error messages
- Invalid scraped data is logged and skipped (not saved)
- Invalid AI responses fall back gracefully
- Validation can be toggled between strict/lenient modes
- All validation failures are logged with actionable context
- Systematic validation issues are detected and alerted
