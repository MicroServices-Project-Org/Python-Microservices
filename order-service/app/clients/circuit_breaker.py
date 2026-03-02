import time
from enum import Enum
from typing import Callable, Any


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Raised when the circuit is open and requests are rejected."""
    pass


class CircuitBreaker:
    """
    Async-native circuit breaker — no external dependencies.

    States:
      CLOSED    → normal operation, requests pass through
      OPEN      → circuit tripped, requests fail immediately
      HALF_OPEN → one test request allowed, success closes, failure reopens

    Usage:
      breaker = CircuitBreaker(name="inventory", fail_max=5, reset_timeout=30)
      result = await breaker.call(my_async_function, arg1, arg2)
    """

    def __init__(self, name: str, fail_max: int = 5, reset_timeout: int = 30):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout

        self._state = CircuitState.CLOSED
        self._fail_counter = 0
        self._last_failure_time = 0.0
        self._exclude_exceptions: list[type] = []

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            # Check if reset timeout has elapsed → transition to HALF_OPEN
            if time.time() - self._last_failure_time >= self.reset_timeout:
                self._state = CircuitState.HALF_OPEN
                print(f"⚡ Circuit Breaker [{self.name}]: open → half_open (allowing test request)")
        return self._state

    @property
    def fail_counter(self) -> int:
        return self._fail_counter

    def exclude(self, *exceptions: type) -> "CircuitBreaker":
        """Exceptions to exclude from failure counting (e.g., business errors)."""
        self._exclude_exceptions.extend(exceptions)
        return self

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute the function through the circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            print(
                f"⚡ Circuit Breaker [{self.name}]: OPEN — failing fast "
                f"(failures={self._fail_counter}, resets in "
                f"{max(0, int(self.reset_timeout - (time.time() - self._last_failure_time)))}s)"
            )
            raise CircuitBreakerError(
                f"Circuit breaker [{self.name}] is open — service unavailable"
            )

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            # Don't count excluded exceptions (business errors like 404)
            if any(isinstance(e, exc) for exc in self._exclude_exceptions):
                raise

            self._on_failure(e)
            raise

    def _on_success(self):
        """Reset failure counter on success."""
        if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
            if self._fail_counter > 0:
                print(f"🟢 Circuit Breaker [{self.name}]: success — resetting failure counter")
            self._fail_counter = 0
            if self._state == CircuitState.HALF_OPEN:
                print(f"⚡ Circuit Breaker [{self.name}]: half_open → closed (service recovered)")
            self._state = CircuitState.CLOSED

    def _on_failure(self, exc: Exception):
        """Increment failure counter, open circuit if threshold reached."""
        self._fail_counter += 1
        self._last_failure_time = time.time()
        print(
            f"🔴 Circuit Breaker [{self.name}]: failure #{self._fail_counter}/{self.fail_max} "
            f"— {type(exc).__name__}"
        )

        if self._fail_counter >= self.fail_max:
            old_state = self._state
            self._state = CircuitState.OPEN
            if old_state != CircuitState.OPEN:
                print(
                    f"⚡ Circuit Breaker [{self.name}]: {old_state.value} → open "
                    f"(will reset in {self.reset_timeout}s)"
                )