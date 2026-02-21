
# ─────────────────────────────────────────────
# tests/integration/test_product_routes.py
# ─────────────────────────────────────────────
import pytest
from httpx import AsyncClient, ASGITransport
from testcontainers.mongodb import MongoDbContainer
from app.main import app
from app.database import db_instance
from motor.motor_asyncio import AsyncIOMotorClient

@pytest.fixture(scope="session")
def mongo_container():
    with MongoDbContainer("mongo:7.0") as mongo:
        yield mongo

@pytest.fixture(scope="session", autouse=True)
def setup_db(mongo_container):
    """Wire testcontainer MongoDB into the app."""
    uri = mongo_container.get_connection_url()
    db_instance.client = AsyncIOMotorClient(uri)
    db_instance.db = db_instance.client["test_product_db"]
    yield
    db_instance.client.close()

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c

@pytest.mark.asyncio
async def test_create_product_endpoint(client):
    payload = {
        "name": "Test Product",
        "description": "A test product",
        "price": "49.99",
        "category": "Test",
        "tags": ["test"],
        "stock_quantity": 10
    }
    res = await client.post("/api/products", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Test Product"
    assert "id" in data

@pytest.mark.asyncio
async def test_get_all_products_endpoint(client):
    res = await client.get("/api/products")
    assert res.status_code == 200
    data = res.json()
    assert "products" in data
    assert "total" in data

@pytest.mark.asyncio
async def test_get_product_not_found_endpoint(client):
    res = await client.get("/api/products/507f1f77bcf86cd799439011")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_search_products_endpoint(client):
    res = await client.get("/api/products/search?q=Test")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

@pytest.mark.asyncio
async def test_health_endpoint(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "UP"