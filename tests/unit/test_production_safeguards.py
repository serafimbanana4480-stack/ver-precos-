"""
Extended unit tests for utils/production_safeguards.py.
Tests ProductionError, CircuitBreaker state machine, validate_environment,
get_health_check_summary, and the with_circuit_breaker decorator.
"""
import pytest
import time
from datetime import datetime, timezone

from utils.production_safeguards import (
    ProductionError,
    CircuitBreaker,
    with_circuit_breaker,
    validate_environment,
    get_health_check_summary,
    with_production_error_handling,
)


# ---------------------------------------------------------------------------
# ProductionError Tests
# ---------------------------------------------------------------------------

class TestProductionError:
    """Test ProductionError exception class"""

    def test_production_error_message(self):
        error = ProductionError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_production_error_default_context(self):
        error = ProductionError("Test error")
        assert error.context == {}

    def test_production_error_with_context(self):
        ctx = {"operation": "scrape_olx", "state": "open"}
        error = ProductionError("Circuit open", context=ctx)
        assert error.context["operation"] == "scrape_olx"
        assert error.context["state"] == "open"

    def test_production_error_has_timestamp(self):
        error = ProductionError("Test error")
        assert isinstance(error.timestamp, datetime)
        # Should be UTC
        assert error.timestamp.tzinfo is not None

    def test_production_error_timestamp_is_recent(self):
        before = datetime.now(timezone.utc)
        error = ProductionError("Test error")
        after = datetime.now(timezone.utc)
        assert before <= error.timestamp <= after

    def test_production_error_is_exception(self):
        error = ProductionError("Test")
        assert isinstance(error, Exception)


# ---------------------------------------------------------------------------
# CircuitBreaker State Machine Tests
# ---------------------------------------------------------------------------

class TestCircuitBreakerStateMachine:
    """Test CircuitBreaker complete state machine"""

    def test_initial_state_is_closed(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        assert breaker.state == "closed"
        assert breaker.failure_count == 0
        assert breaker.can_attempt() is True

    def test_failure_count_increments(self):
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        breaker.record_failure()
        assert breaker.failure_count == 1
        breaker.record_failure()
        assert breaker.failure_count == 2

    def test_state_stays_closed_below_threshold(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == "closed"
        assert breaker.can_attempt() is True

    def test_state_opens_at_threshold(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == "open"
        assert breaker.can_attempt() is False

    def test_success_resets_failure_count(self):
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2
        breaker.record_success()
        assert breaker.failure_count == 0

    def test_success_closes_circuit(self):
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        breaker.record_failure()
        breaker.record_success()
        assert breaker.state == "closed"

    def test_half_open_after_recovery_timeout(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == "open"
        time.sleep(1.1)
        # can_attempt transitions to half-open
        result = breaker.can_attempt()
        assert result is True
        assert breaker.state == "half-open"

    def test_half_open_allows_one_attempt(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        breaker.record_failure()
        time.sleep(1.1)
        # First attempt allowed in half-open
        assert breaker.can_attempt() is True
        # Still half-open
        assert breaker.state == "half-open"

    def test_half_open_closes_on_success(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        breaker.record_failure()
        time.sleep(1.1)
        breaker.can_attempt()  # transitions to half-open
        breaker.record_success()
        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    def test_open_circuit_blocks_immediately(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=9999)
        breaker.record_failure()
        assert breaker.state == "open"
        assert breaker.can_attempt() is False

    def test_custom_failure_threshold(self):
        breaker = CircuitBreaker(failure_threshold=10, recovery_timeout=60)
        for i in range(9):
            breaker.record_failure()
            assert breaker.state == "closed", f"Should still be closed after {i+1} failures"
        breaker.record_failure()
        assert breaker.state == "open"


# ---------------------------------------------------------------------------
# with_circuit_breaker Decorator Tests
# ---------------------------------------------------------------------------

class TestCircuitBreakerDecorator:
    """Test with_circuit_breaker decorator behavior"""

    def test_decorator_allows_successful_calls(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        call_count = 0

        @with_circuit_breaker(breaker, "test_success")
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = always_succeeds()
        assert result == "ok"
        assert call_count == 1
        assert breaker.state == "closed"

    def test_decorator_records_failures(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        @with_circuit_breaker(breaker, "test_fail")
        def always_fails():
            raise Exception("Test failure")

        for _ in range(2):
            with pytest.raises(Exception, match="Test failure"):
                always_fails()

        assert breaker.failure_count == 2

    def test_decorator_opens_circuit_and_blocks(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=9999)

        @with_circuit_breaker(breaker, "test_block")
        def failing_op():
            raise Exception("Failure")

        # Trigger 2 failures → circuit opens
        for _ in range(2):
            with pytest.raises(Exception):
                failing_op()

        assert breaker.state == "open"

        # Next call should be blocked
        with pytest.raises(Exception) as exc_info:
            failing_op()
        assert "blocked by circuit breaker" in str(exc_info.value)

    def test_decorator_returns_production_error_when_blocked(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=9999)

        @with_circuit_breaker(breaker, "blocked_op")
        def op():
            raise ValueError("Will fail")

        with pytest.raises(ValueError):
            op()  # 1 failure → opens circuit

        with pytest.raises(ProductionError) as exc_info:
            op()  # blocked
        assert exc_info.value.context.get("operation") == "blocked_op"

    def test_decorator_resets_count_on_success(self):
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2

        @with_circuit_breaker(breaker, "resetter")
        def succeeds():
            return "done"

        succeeds()
        assert breaker.failure_count == 0


# ---------------------------------------------------------------------------
# with_production_error_handling Decorator Tests
# ---------------------------------------------------------------------------

class TestProductionErrorHandlingDecorator:
    """Test with_production_error_handling decorator"""

    def test_returns_result_on_success(self):
        @with_production_error_handling("test_op")
        def good_func():
            return 42

        assert good_func() == 42

    def test_raises_production_error_on_unexpected_exception(self):
        @with_production_error_handling("test_op", raise_on_error=True)
        def bad_func():
            raise RuntimeError("Something broke")

        with pytest.raises(ProductionError) as exc_info:
            bad_func()
        assert "test_op" in str(exc_info.value)

    def test_returns_none_when_raise_disabled(self):
        @with_production_error_handling("silent_op", raise_on_error=False)
        def bad_func():
            raise RuntimeError("Silenced")

        result = bad_func()
        assert result is None

    def test_re_raises_production_error(self):
        @with_production_error_handling("chain_op", raise_on_error=True)
        def raises_production():
            raise ProductionError("original", context={"key": "value"})

        with pytest.raises(ProductionError) as exc_info:
            raises_production()
        assert "original" in str(exc_info.value)


# ---------------------------------------------------------------------------
# validate_environment Tests
# ---------------------------------------------------------------------------

class TestValidateEnvironment:
    """Test validate_environment function structure"""

    def test_returns_dict(self):
        result = validate_environment()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = validate_environment()
        assert "is_valid" in result
        assert "issues" in result
        assert "warnings" in result
        assert "timestamp" in result

    def test_issues_is_list(self):
        result = validate_environment()
        assert isinstance(result["issues"], list)

    def test_warnings_is_list(self):
        result = validate_environment()
        assert isinstance(result["warnings"], list)

    def test_is_valid_is_bool(self):
        result = validate_environment()
        assert isinstance(result["is_valid"], bool)

    def test_timestamp_is_string(self):
        result = validate_environment()
        assert isinstance(result["timestamp"], str)
        # Should be parseable as datetime
        dt = datetime.fromisoformat(result["timestamp"])
        assert dt is not None


# ---------------------------------------------------------------------------
# get_health_check_summary Tests
# ---------------------------------------------------------------------------

class TestGetHealthCheckSummary:
    """Test get_health_check_summary function"""

    def test_returns_dict(self):
        result = get_health_check_summary()
        assert isinstance(result, dict)

    def test_has_overall_status(self):
        result = get_health_check_summary()
        assert "overall_status" in result
        assert result["overall_status"] in ("healthy", "warning", "unhealthy")

    def test_has_environment_section(self):
        result = get_health_check_summary()
        assert "environment" in result
        env = result["environment"]
        assert "is_valid" in env
        assert "issues" in env
        assert "warnings" in env

    def test_has_system_section(self):
        result = get_health_check_summary()
        assert "system" in result
        system = result["system"]
        assert "status" in system

    def test_has_database_section(self):
        result = get_health_check_summary()
        assert "database" in result
        db = result["database"]
        assert "status" in db

    def test_has_top_level_timestamp(self):
        result = get_health_check_summary()
        assert "timestamp" in result
