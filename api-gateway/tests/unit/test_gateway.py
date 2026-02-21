import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient
from app.main import app


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_downstream_response(status_code=200, content=b'{"ok": true}', content_type="application/json"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = {"content-type": content_type}
    return resp


@pytest.fixture
def client():
    """AsyncClient that talks directly to the FastAPI app (no real HTTP)."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ─── Health Check ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UP"
    assert data["service"] == "api-gateway"
    assert "auth_enabled" in data


# ─── Product Routes ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_products_list(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        content=b'{"products": [{"name": "iPhone"}]}',
    ))
    resp = await client.get("/api/products")
    assert resp.status_code == 200
    assert "products" in resp.json()

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_products_by_id(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        content=b'{"name": "iPhone 15 Pro"}',
    ))
    resp = await client.get("/api/products/abc123")
    assert resp.status_code == 200
    call_args = mock_client.request.call_args
    assert "products/abc123" in call_args.kwargs["url"]

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_products_search(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        content=b'{"products": []}',
    ))
    resp = await client.get("/api/products/search?q=iphone")
    assert resp.status_code == 200
    call_args = mock_client.request.call_args
    assert "q=iphone" in call_args.kwargs["url"]

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_products_create(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(status_code=201))
    resp = await client.post("/api/products", json={"name": "Test", "price": 10})
    assert resp.status_code == 201
    call_args = mock_client.request.call_args
    assert call_args.kwargs["method"] == "POST"


# ─── Order Routes ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_orders_list(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        content=b'[{"order_number": "ORD-001"}]',
    ))
    resp = await client.get("/api/orders")
    assert resp.status_code == 200

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_orders_create(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(status_code=201))
    resp = await client.post("/api/orders", json={
        "customer_name": "Yash",
        "customer_email": "yash@example.com",
        "items": [],
    })
    assert resp.status_code == 201

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_orders_by_id(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response())
    resp = await client.get("/api/orders/some-uuid")
    assert resp.status_code == 200
    call_args = mock_client.request.call_args
    assert "orders/some-uuid" in call_args.kwargs["url"]


# ─── Inventory Routes ───────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_inventory_list(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response())
    resp = await client.get("/api/inventory")
    assert resp.status_code == 200

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_inventory_check_stock(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        content=b'{"product_id": "prod-001", "in_stock": true}',
    ))
    resp = await client.get("/api/inventory/prod-001/check?quantity=5")
    assert resp.status_code == 200
    call_args = mock_client.request.call_args
    assert "inventory/prod-001/check" in call_args.kwargs["url"]
    assert "quantity=5" in call_args.kwargs["url"]

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_inventory_reduce(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response())
    resp = await client.patch("/api/inventory/prod-001/reduce", json={"quantity": 5})
    assert resp.status_code == 200


# ─── AI Routes ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_ai_chat(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        content=b'{"reply": "Hello!"}',
    ))
    resp = await client.post("/api/ai/chat", json={"message": "Hi"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "Hello!"

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_ai_recommendations(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        content=b'{"recommendations": []}',
    ))
    resp = await client.get("/api/ai/recommendations?product_name=iPhone")
    assert resp.status_code == 200

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_proxy_ai_suggest(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        content=b'{"result": "{}"}',
    ))
    resp = await client.post("/api/ai/suggest", json={"query": "birthday gift"})
    assert resp.status_code == 200


# ─── Error Handling ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_service_unavailable_returns_503(mock_client, client):
    import httpx
    mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    resp = await client.get("/api/products")
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_service_timeout_returns_504(mock_client, client):
    import httpx
    mock_client.request = AsyncMock(side_effect=httpx.ReadTimeout("Timeout"))
    resp = await client.get("/api/orders")
    assert resp.status_code == 504
    assert "timeout" in resp.json()["detail"].lower()

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_downstream_404_forwarded(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        status_code=404,
        content=b'{"detail": "Not found"}',
    ))
    resp = await client.get("/api/products/nonexistent")
    assert resp.status_code == 404

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_downstream_400_forwarded(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(
        status_code=400,
        content=b'{"detail": "Bad request"}',
    ))
    resp = await client.post("/api/orders", json={})
    assert resp.status_code == 400


# ─── Auth (disabled mode) ───────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_no_auth_header_works_when_disabled(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response())
    resp = await client.get("/api/products")
    assert resp.status_code == 200

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_auth_header_stripped_before_forwarding(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response())
    resp = await client.get(
        "/api/products",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert resp.status_code == 200
    call_args = mock_client.request.call_args
    forwarded_headers = call_args.kwargs["headers"]
    assert "authorization" not in {k.lower() for k in forwarded_headers}


# ─── Query Params Forwarding ────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_query_params_forwarded(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response())
    resp = await client.get("/api/products/search?q=phone&page=2")
    call_args = mock_client.request.call_args
    assert "q=phone" in call_args.kwargs["url"]
    assert "page=2" in call_args.kwargs["url"]

@pytest.mark.asyncio
@patch("app.main.http_client")
async def test_request_body_forwarded(mock_client, client):
    mock_client.request = AsyncMock(return_value=make_downstream_response(status_code=201))
    body = {"customer_name": "Yash", "items": []}
    resp = await client.post("/api/orders", json=body)
    assert resp.status_code == 201
    call_args = mock_client.request.call_args
    assert len(call_args.kwargs["content"]) > 0