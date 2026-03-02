import pytest
import time
from unittest.mock import AsyncMock
from fastapi import HTTPException
from app.clients.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_breaker(fail_max=3, reset_timeout=1):
    """Create a circuit breaker with low thresholds for fast testing."""
    return CircuitBreaker(name="test-service", fail_max=fail_max, reset_timeout=reset_timeout)


async def success_func():
    return "ok"


async def failure_func():
    raise ConnectionError("Service down")


# ─── Initial State ──────────────────────────────────────────────────────────

def test_initial_state_is_closed():
    breaker = make_breaker()
    assert breaker.state == CircuitState.CLOSED

def test_initial_fail_counter_is_zero():
    breaker = make_breaker()
    assert breaker.fail_counter == 0


# ─── Success Path ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_success_returns_result():
    breaker = make_breaker()
    result = await breaker.call(success_func)
    assert result == "ok"

@pytest.mark.asyncio
async def test_success_keeps_circuit_closed():
    breaker = make_breaker()
    await breaker.call(success_func)
    assert breaker.state == CircuitState.CLOSED
    assert breaker.fail_counter == 0

@pytest.mark.asyncio
async def test_success_resets_fail_counter():
    breaker = make_breaker(fail_max=5)
    # Cause some failures
    for _ in range(3):
        try:
            await breaker.call(failure_func)
        except ConnectionError:
            pass
    assert breaker.fail_counter == 3

    # Success resets counter
    await breaker.call(success_func)
    assert breaker.fail_counter == 0


# ─── Failure Path ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_failure_increments_counter():
    breaker = make_breaker()
    try:
        await breaker.call(failure_func)
    except ConnectionError:
        pass
    assert breaker.fail_counter == 1

@pytest.mark.asyncio
async def test_failure_raises_original_exception():
    breaker = make_breaker()
    with pytest.raises(ConnectionError):
        await breaker.call(failure_func)

@pytest.mark.asyncio
async def test_failures_below_threshold_stay_closed():
    breaker = make_breaker(fail_max=5)
    for _ in range(4):
        try:
            await breaker.call(failure_func)
        except ConnectionError:
            pass
    assert breaker.state == CircuitState.CLOSED
    assert breaker.fail_counter == 4


# ─── Circuit Opens ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_circuit_opens_after_fail_max():
    breaker = make_breaker(fail_max=3)
    for _ in range(3):
        try:
            await breaker.call(failure_func)
        except ConnectionError:
            pass
    assert breaker.state == CircuitState.OPEN

@pytest.mark.asyncio
async def test_open_circuit_rejects_immediately():
    breaker = make_breaker(fail_max=2, reset_timeout=60)
    # Trip the circuit
    for _ in range(2):
        try:
            await breaker.call(failure_func)
        except ConnectionError:
            pass
    assert breaker.state == CircuitState.OPEN

    # Next call should fail immediately with CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        await breaker.call(success_func)

@pytest.mark.asyncio
async def test_open_circuit_does_not_call_function():
    breaker = make_breaker(fail_max=2, reset_timeout=60)
    for _ in range(2):
        try:
            await breaker.call(failure_func)
        except ConnectionError:
            pass

    mock_func = AsyncMock(return_value="ok")
    with pytest.raises(CircuitBreakerError):
        await breaker.call(mock_func)
    mock_func.assert_not_called()


# ─── Half-Open State ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_circuit_transitions_to_half_open_after_timeout():
    breaker = make_breaker(fail_max=2, reset_timeout=1)
    for _ in range(2):
        try:
            await breaker.call(failure_func)
        except ConnectionError:
            pass
    assert breaker._state == CircuitState.OPEN

    # Wait for reset timeout
    time.sleep(1.1)
    assert breaker.state == CircuitState.HALF_OPEN

@pytest.mark.asyncio
async def test_half_open_success_closes_circuit():
    breaker = make_breaker(fail_max=2, reset_timeout=1)
    for _ in range(2):
        try:
            await breaker.call(failure_func)
        except ConnectionError:
            pass

    time.sleep(1.1)
    assert breaker.state == CircuitState.HALF_OPEN

    # Success in half-open → closes circuit
    result = await breaker.call(success_func)
    assert result == "ok"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.fail_counter == 0

@pytest.mark.asyncio
async def test_half_open_failure_reopens_circuit():
    breaker = make_breaker(fail_max=2, reset_timeout=1)
    for _ in range(2):
        try:
            await breaker.call(failure_func)
        except ConnectionError:
            pass

    time.sleep(1.1)
    assert breaker.state == CircuitState.HALF_OPEN

    # Failure in half-open → reopens circuit
    try:
        await breaker.call(failure_func)
    except ConnectionError:
        pass
    assert breaker._state == CircuitState.OPEN


# ─── Exclude Exceptions ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_excluded_exceptions_not_counted():
    breaker = make_breaker(fail_max=3)
    breaker.exclude(HTTPException)

    async def raise_http_error():
        raise HTTPException(status_code=404, detail="Not found")

    for _ in range(5):
        try:
            await breaker.call(raise_http_error)
        except HTTPException:
            pass

    # HTTPException is excluded — circuit should still be closed
    assert breaker.state == CircuitState.CLOSED
    assert breaker.fail_counter == 0

@pytest.mark.asyncio
async def test_excluded_exception_still_raised():
    breaker = make_breaker()
    breaker.exclude(HTTPException)

    async def raise_http_error():
        raise HTTPException(status_code=404, detail="Not found")

    with pytest.raises(HTTPException):
        await breaker.call(raise_http_error)

@pytest.mark.asyncio
async def test_non_excluded_exceptions_counted():
    breaker = make_breaker(fail_max=3)
    breaker.exclude(HTTPException)

    # ConnectionError is NOT excluded — should count
    for _ in range(3):
        try:
            await breaker.call(failure_func)
        except ConnectionError:
            pass

    assert breaker.state == CircuitState.OPEN


# ─── Async Function Args ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_passes_args_to_function():
    breaker = make_breaker()

    async def add(a, b):
        return a + b

    result = await breaker.call(add, 3, 4)
    assert result == 7

@pytest.mark.asyncio
async def test_passes_kwargs_to_function():
    breaker = make_breaker()

    async def greet(name, greeting="Hello"):
        return f"{greeting}, {name}!"

    result = await breaker.call(greet, "Yash", greeting="Hi")
    assert result == "Hi, Yash!"