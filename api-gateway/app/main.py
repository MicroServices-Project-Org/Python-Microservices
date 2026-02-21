import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.auth.keycloak import verify_token
from app.middleware.rate_limit import limiter


# ─── Shared HTTP Client ──────────────────────────────────────────────────────

TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=3.0, pool=5.0)
http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=TIMEOUT)
    print(f"✅ {settings.APP_NAME} started on port {settings.APP_PORT}")
    print(f"🔐 Auth: {'ENABLED (Keycloak)' if settings.AUTH_ENABLED else 'DISABLED (dev mode)'}")
    print(f"📡 Routing to:")
    print(f"   Products  → {settings.PRODUCT_SERVICE_URL}")
    print(f"   Orders    → {settings.ORDER_SERVICE_URL}")
    print(f"   Inventory → {settings.INVENTORY_SERVICE_URL}")
    print(f"   AI        → {settings.AI_SERVICE_URL}")

    yield

    await http_client.aclose()
    print("🔌 API Gateway shut down")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="API Gateway",
    description="Single entry point for all microservices. Handles routing, JWT auth, and rate limiting.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ─── Service URL Mapping ─────────────────────────────────────────────────────

SERVICE_MAP = {
    "products": lambda: settings.PRODUCT_SERVICE_URL,
    "orders": lambda: settings.ORDER_SERVICE_URL,
    "inventory": lambda: settings.INVENTORY_SERVICE_URL,
    "ai": lambda: settings.AI_SERVICE_URL,
}


# ─── Proxy Function ──────────────────────────────────────────────────────────

async def _proxy_request(request: Request, service_url: str, path: str) -> Response:
    """
    Forwards the incoming request to the target microservice.
    Preserves method, headers, query params, and body.
    """
    url = f"{service_url}/api/{path}"

    # Forward query parameters
    if request.query_params:
        url += f"?{request.query_params}"

    # Forward headers (exclude host and content-length)
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "authorization")
    }

    # Read request body
    body = await request.body()

    try:
        resp = await http_client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )

        # Return the downstream response as-is
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
            media_type=resp.headers.get("content-type"),
        )

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {path.split('/')[0]}")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail=f"Service timeout: {path.split('/')[0]}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gateway error: {e}")


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "UP",
        "service": settings.APP_NAME,
        "auth_enabled": settings.AUTH_ENABLED,
    }


# Products — standard rate limit
@app.api_route(
    "/api/products/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def proxy_products(request: Request, path: str, token: dict = Depends(verify_token)):
    return await _proxy_request(request, settings.PRODUCT_SERVICE_URL, f"products/{path}")


@app.api_route("/api/products", methods=["GET", "POST"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def proxy_products_root(request: Request, token: dict = Depends(verify_token)):
    return await _proxy_request(request, settings.PRODUCT_SERVICE_URL, "products")


# Orders — standard rate limit
@app.api_route(
    "/api/orders/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def proxy_orders(request: Request, path: str, token: dict = Depends(verify_token)):
    return await _proxy_request(request, settings.ORDER_SERVICE_URL, f"orders/{path}")


@app.api_route("/api/orders", methods=["GET", "POST"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def proxy_orders_root(request: Request, token: dict = Depends(verify_token)):
    return await _proxy_request(request, settings.ORDER_SERVICE_URL, "orders")


# Inventory — standard rate limit
@app.api_route(
    "/api/inventory/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def proxy_inventory(request: Request, path: str, token: dict = Depends(verify_token)):
    return await _proxy_request(request, settings.INVENTORY_SERVICE_URL, f"inventory/{path}")


@app.api_route("/api/inventory", methods=["GET", "POST"])
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def proxy_inventory_root(request: Request, token: dict = Depends(verify_token)):
    return await _proxy_request(request, settings.INVENTORY_SERVICE_URL, "inventory")


# AI — stricter rate limit (LLM calls are expensive)
@app.api_route(
    "/api/ai/{path:path}",
    methods=["GET", "POST"],
)
@limiter.limit(settings.RATE_LIMIT_AI)
async def proxy_ai(request: Request, path: str, token: dict = Depends(verify_token)):
    return await _proxy_request(request, settings.AI_SERVICE_URL, f"ai/{path}")


@app.api_route("/api/ai", methods=["GET", "POST"])
@limiter.limit(settings.RATE_LIMIT_AI)
async def proxy_ai_root(request: Request, token: dict = Depends(verify_token)):
    return await _proxy_request(request, settings.AI_SERVICE_URL, "ai")