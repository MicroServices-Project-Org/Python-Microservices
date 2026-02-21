import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fastapi import HTTPException, status
from app.config import settings

# ─── HTTP Client ──────────────────────────────────────────────────────────────
def get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.INVENTORY_SERVICE_URL,
        timeout=httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=5.0)
    )

# ─── Retry decorator ─────────────────────────────────────────────────────────
@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True
)
async def check_stock(product_id: str, quantity: int) -> bool:
    """
    Call Inventory Service to verify stock.
    Retries up to 3 times on transient network errors.
    """
    async with get_client() as client:
        try:
            response = await client.get(
                f"/api/inventory/{product_id}/check",
                params={"quantity": quantity}
            )
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product {product_id} not found in inventory"
                )
            response.raise_for_status()
            return response.json().get("in_stock", False)

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inventory service timed out"
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inventory service unavailable"
            )

async def reduce_stock(product_id: str, quantity: int) -> bool:
    """Reduce stock after order is confirmed."""
    async with get_client() as client:
        try:
            response = await client.patch(
                f"/api/inventory/{product_id}/reduce",
                json={"quantity": quantity}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"⚠️  Failed to reduce stock for {product_id}: {e}")
            return False