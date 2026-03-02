import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fastapi import HTTPException, status
from app.config import settings
from app.clients.circuit_breaker import CircuitBreaker, CircuitBreakerError


# ─── Circuit Breaker ──────────────────────────────────────────────────────────
# Opens after 5 consecutive failures, resets after 30 seconds
inventory_breaker = CircuitBreaker(name="inventory-service", fail_max=5, reset_timeout=30)
inventory_breaker.exclude(HTTPException)  # Don't count 404/400 as failures


# ─── HTTP Client ──────────────────────────────────────────────────────────────
def get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.INVENTORY_SERVICE_URL,
        timeout=httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=5.0),
    )


# ─── Raw HTTP calls ──────────────────────────────────────────────────────────

async def _raw_check_stock(product_id: str, quantity: int) -> bool:
    """Raw HTTP call to check stock."""
    async with get_client() as client:
        print(f"📡 Checking stock: {product_id} (qty: {quantity})")
        response = await client.get(
            f"/api/inventory/{product_id}/check",
            params={"quantity": quantity},
        )
        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found in inventory",
            )
        response.raise_for_status()
        result = response.json().get("in_stock", False)
        print(f"✅ Stock check result: {product_id} → in_stock={result}")
        return result


async def _raw_reduce_stock(product_id: str, quantity: int) -> bool:
    """Raw HTTP call to reduce stock."""
    async with get_client() as client:
        print(f"📡 Reducing stock: {product_id} (qty: {quantity})")
        response = await client.patch(
            f"/api/inventory/{product_id}/reduce",
            json={"quantity": quantity},
        )
        response.raise_for_status()
        print(f"✅ Stock reduced: {product_id} by {quantity}")
        return True


# ─── Retry callback ──────────────────────────────────────────────────────────

def _log_retry(retry_state):
    print(
        f"🔄 Retry attempt {retry_state.attempt_number}/3 "
        f"for inventory call — waiting {retry_state.next_action.sleep:.1f}s"
    )


# ─── Check Stock (Retry → Circuit Breaker → Timeout) ─────────────────────────

@retry(
    retry=retry_if_exception_type((httpx.TransportError, CircuitBreakerError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=_log_retry,
    reraise=True,
)
async def check_stock(product_id: str, quantity: int) -> bool:
    """
    Call Inventory Service to verify stock.

    Resilience layers (outermost to innermost):
    1. Retry — retries up to 3 times on transient network errors
    2. Circuit Breaker — opens after 5 consecutive failures, fails fast for 30s
    3. Timeout — 3s connect, 5s read
    """
    try:
        return await inventory_breaker.call(_raw_check_stock, product_id, quantity)

    except CircuitBreakerError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inventory service is temporarily unavailable. Please try again later.",
        )
    except HTTPException:
        raise  # Business errors pass through
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        print(f"❌ Inventory Service unreachable for {product_id}: {e}")
        raise  # Let tenacity retry — if all retries exhausted, outer handler catches


# ─── Reduce Stock (Circuit Breaker + Timeout, no retry) ──────────────────────

async def reduce_stock(product_id: str, quantity: int) -> bool:
    """
    Reduce stock after order is confirmed.
    Uses circuit breaker but no retry — stock reduction is not idempotent.
    """
    try:
        return await inventory_breaker.call(_raw_reduce_stock, product_id, quantity)

    except CircuitBreakerError:
        print(f"⚡ Circuit breaker OPEN — cannot reduce stock for {product_id}")
        return False
    except Exception as e:
        print(f"⚠️ Failed to reduce stock for {product_id}: {e}")
        return False