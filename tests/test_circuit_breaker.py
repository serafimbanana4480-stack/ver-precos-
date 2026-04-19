"""
Test suite for circuit breaker pattern
"""
import pytest
import time
from utils.production_safeguards import CircuitBreaker, ProductionError


def test_circuit_breaker_initial_state():
    """Test that circuit breaker starts in closed state"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    
    assert breaker.state == 'closed'
    assert breaker.failure_count == 0
    assert breaker.can_attempt() is True


def test_circuit_breaker_opens_on_threshold():
    """Test that circuit breaker opens after threshold failures"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    
    # Record failures up to threshold
    for _ in range(3):
        breaker.record_failure()
    
    assert breaker.state == 'open'
    assert breaker.can_attempt() is False


def test_circuit_breaker_closes_on_success():
    """Test that circuit breaker closes on success"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    
    # Record some failures
    breaker.record_failure()
    breaker.record_failure()
    
    # Record success
    breaker.record_success()
    
    assert breaker.state == 'closed'
    assert breaker.failure_count == 0


def test_circuit_breaker_recovery_timeout():
    """Test that circuit breaker recovers after timeout"""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    
    # Open the circuit
    for _ in range(3):
        breaker.record_failure()
    
    assert breaker.state == 'open'
    assert breaker.can_attempt() is False
    
    # Wait for recovery timeout
    time.sleep(1.1)
    
    # Should now allow attempts (transitions to half-open on can_attempt check)
    assert breaker.can_attempt() is True


def test_circuit_breaker_decorator():
    """Test circuit breaker decorator"""
    from utils.production_safeguards import with_circuit_breaker
    
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
    call_count = 0
    
    @with_circuit_breaker(breaker, "test operation")
    def failing_function():
        nonlocal call_count
        call_count += 1
        raise Exception("Test error")
    
    # First two attempts should fail but not open circuit yet
    for _ in range(2):
        try:
            failing_function()
        except:
            pass
    
    # Circuit should now be open after 2 failures
    assert breaker.state == 'open'
    
    # Third attempt should be blocked
    try:
        failing_function()
        assert False, "Should have raised ProductionError"
    except Exception as e:
        assert "blocked by circuit breaker" in str(e)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
