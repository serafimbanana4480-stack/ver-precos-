# Phase 1.4: Test Infrastructure

**Wave:** 1
**Depends on:** None
**Files modified:** requirements.txt, tests/conftest.py, tests/unit/*.py, tests/integration/*.py, .github/workflows/tests.yml
**Autonomous:** true

## Requirements

- TEST-01 - Add pytest-cov for coverage reporting with minimum 70% coverage target
- TEST-02 - Add pytest-mock for mocking utilities in tests
- TEST-03 - Add factory-boy for test data creation with database models
- TEST-10 - Add CI/CD integration for automated test runs

## Tasks

### Task 1: Add test dependencies to requirements

<read_first>
requirements.txt
</read_first>

<action>
Add test dependencies to requirements.txt:

1. Add pytest-cov==4.1.0 to testing section
2. Add pytest-mock==3.12.0 to testing section
3. Add factory-boy==3.3.0 to testing section
4. Add pytest-asyncio==0.21.1 to testing section (already present, verify)
5. Add pytest-playwright if needed for Playwright testing
6. Separate test dependencies with comment "# Testing"
</action>

<acceptance_criteria>
requirements.txt contains pytest-cov==4.1.0
requirements.txt contains pytest-mock==3.12.0
requirements.txt contains factory-boy==3.3.0
</acceptance_criteria>

### Task 2: Create test directory structure

<read_first>
main.py
</read_first>

<action>
Create test directory structure:

1. Create tests/ directory at project root
2. Create tests/unit/ subdirectory
3. Create tests/integration/ subdirectory
4. Create tests/conftest.py for shared fixtures
5. Create tests/__init__.py
6. Create tests/unit/__init__.py
7. Create tests/integration/__init__.py
8. Add .pytest.ini configuration file
9. Add pyproject.toml for pytest configuration if preferred
</action>

<acceptance_criteria>
tests/ directory exists
tests/unit/ directory exists
tests/integration/ directory exists
tests/conftest.py exists
tests/__init__.py exists
.pytest.ini exists
</acceptance_criteria>

### Task 4: Configure pytest

<read_first>
.pytest.ini or pyproject.toml
</read_first>

<action>
Configure pytest in .pytest.ini or pyproject.toml:

1. Set testpaths = tests
2. Set python_files = test_*.py
3. Set python_classes = Test*
4. Set python_functions = test_*
5. Add coverage configuration:
   - coverage: run = true
   - coverage: report = term-missing
   - coverage: fail_under = 70
6. Add pytest-mock configuration
7. Add asyncio_mode = auto
8. Add markers for unit/integration tests
</action>

<acceptance_criteria>
.pytest.ini exists or pyproject.toml has pytest section
pytest.ini has testpaths = tests
pytest.ini has coverage: run = true
pytest.ini has coverage: fail_under = 70
pytest.ini has asyncio_mode = auto
</acceptance_criteria>

### Task 5: Create test fixtures

<read_first>
tests/conftest.py
database/models.py
database/db.py
</read_first>

<action>
Create shared test fixtures in tests/conftest.py:

1. Import pytest, factory_boy
2. Create database fixture using in-memory SQLite
3. Create session fixture with rollback after each test
4. Create sample data fixtures for Vehicle, PriceHistory
5. Create mock fixtures for external services (Grok, Ollama)
6. Create temporary directory fixture for file operations
7. Add fixtures for config settings (test environment)
8. Add autouse fixture to set up logging for tests
</action>

<acceptance_criteria>
tests/conftest.py has db fixture
tests/conftest.py has session fixture
tests/conftest.py has mock_grok fixture
tests/conftest.py has mock_ollama fixture
tests/conftest.py has temp_dir fixture
</acceptance_criteria>

### Task 6: Create test factories

<read_first>
tests/conftest.py
database/models.py
</read_first>

<action>
Create test data factories using factory-boy:

1. Create tests/factories.py
2. Create VehicleFactory with:
   - year = factory.Faker('year')
   - km = factory.Faker('random_int', min=0, max=300000)
   - price = factory.Faker('random_int', min=1000, max=100000)
   - brand = factory.Iterator(['Volkswagen', 'Renault', 'Peugeot'])
   - model = factory.Faker('word')
3. Create PriceHistoryFactory
4. Create AIReviewFactory
5. Create ScrapingLogFactory
6. Add related factories (Vehicle with PriceHistory)
7. Configure factories to use in-memory database
</action>

<acceptance_criteria>
tests/factories.py exists
tests/factories.py has VehicleFactory
tests/factories.py has PriceHistoryFactory
tests/factories.py has AIReviewFactory
tests/factories.py has ScrapingLogFactory
</acceptance_criteria>

### Task 7: Create unit test for database models

<read_first>
database/models.py
tests/conftest.py
tests/factories.py
</read_first>

<action>
Create tests/unit/test_database.py:

1. Test Vehicle model creation
2. Test PriceHistory relationship
3. Test AIReview relationship
4. Test enum values (VehicleType, FuelType, Transmission)
5. Test to_dict() method
6. Test model constraints (positive values, required fields)
7. Use pytest-mock for mocking
8. Use factories for test data
9. Achieve coverage > 70% for database/models.py
</action>

<acceptance_criteria>
tests/unit/test_database.py exists
tests/unit/test_database.py has test_vehicle_creation
tests/unit/test_database.py has test_price_history_relationship
tests/unit/test/database.py has test_to_dict
</acceptance_criteria>

### Task 8: Create unit test for config

<read_first>
config.py
tests/conftest.py
</read_first>

<action>
Create tests/unit/test_config.py:

1. Test Settings class initialization
2. Test environment variable loading
3. Test default values
4. Test validation methods
5. Test type conversion (int, float, bool)
6. Test invalid configuration (should raise ValidationError)
7. Use monkeypatch to set environment variables
8. Test config overrides
</action>

<acceptance_criteria>
tests/unit/test_config.py exists
tests/unit/test_config.py has test_settings_init
tests/unit/test_config.py has test_env_var_loading
tests/unit/test_config.py has test_validation
</acceptance_criteria>

### Task 9: Create integration test for database operations

<read_first>
database/db.py
tests/conftest.py
tests/factories.py
</read_first>

<action>
Create tests/integration/test_database.py:

1. Test database connection
2. Test session lifecycle (commit, rollback)
3. Test get_db_context context manager
4. Test health_check function
5. Test concurrent operations (if applicable)
6. Test transaction rollback on error
7. Use in-memory SQLite for tests
8. Use real database operations (not mocked)
</action>

<acceptance_criteria>
tests/integration/test_database.py exists
tests/integration/test_database.py has test_db_connection
tests/integration/test_database.py has test_session_lifecycle
tests/integration/test_database.py has test_context_manager
</acceptance_criteria>

### Task 10: Create GitHub Actions workflow

<read_first>
.github/workflows/ or .github/workflows/tests.yml
</read_first>

<action>
Create GitHub Actions workflow for automated tests:

1. Create .github/workflows/tests.yml
2. Configure trigger: push, pull_request
3. Set up Python 3.12
4. Install dependencies: pip install -r requirements.txt
5. Run tests: pytest --cov
6. Upload coverage to Codecov (optional)
7. Run type checking: mypy
8. Run linting: flake8
9. Run formatting check: black --check
10. Cache dependencies for faster builds
</action>

<acceptance_criteria>
.github/workflows/tests.yml exists
.github/workflows/tests.yml has pytest step
.github/workflows/tests.yml has coverage step
.github/workflows/tests.yml has mypy step
.github/workflows/tests.yml has flake8 step
</acceptance_coverage>
tests/unit/test_config.py has test_validation
</acceptance_criteria>

### Task 11: Run initial test suite

<read_first>
tests/
requirements.txt
</read_first>

<action>
Run initial test suite to verify setup:

1. Install test dependencies: pip install -r requirements.txt
2. Run all tests: pytest
3. Run with coverage: pytest --cov
4. Check coverage report
5. Fix any failing tests
6. Aim for initial coverage > 50% (will improve in Phase 2)
7. Document any skipped tests with reasons
</action>

<acceptance_criteria>
pytest runs successfully
pytest --cov generates coverage report
coverage > 50%
no tests fail
</acceptance_criteria>

## Verification Criteria

- [ ] pytest-cov installed and configured
- [ ] pytest-mock installed and used
- [ ] factory-boy installed and configured
- [ ] Test directory structure created
- [ ] Shared fixtures in conftest.py
- [ ] Test factories for database models
- [ ] Unit tests for database models
- [ ] Unit tests for config
- [ ] Integration tests for database
- [ ] GitHub Actions workflow created
- [ ] Initial test suite runs successfully
- [ ] Coverage reporting functional

## Must Haves

- Test infrastructure is set up and functional
- Tests can be run locally and in CI/CD
- Coverage reporting works
- Test fixtures provide reusable test data
- Factories simplify test data creation
- Tests are organized (unit vs integration)
