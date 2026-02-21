# ─────────────────────────────────────────────
# tests/unit/test_product_service.py
# ─────────────────────────────────────────────
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.product_service import create_product, get_product, delete_product
from app.schemas.product import ProductCreate
from bson import ObjectId

MOCK_PRODUCT = {
    "_id": ObjectId("507f1f77bcf86cd799439011"),
    "name": "iPhone 15 Pro",
    "description": "Latest Apple smartphone",
    "price": "999.99",
    "category": "Electronics",
    "tags": ["smartphone", "apple"],
    "image_url": None,
    "stock_quantity": 100,
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
}

@pytest.fixture
def mock_db():
    with patch("app.services.product_service.get_db") as mock:
        db = MagicMock()
        mock.return_value = db
        yield db

@pytest.mark.asyncio
async def test_create_product(mock_db):
    mock_db.products.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=ObjectId("507f1f77bcf86cd799439011"))
    )
    payload = ProductCreate(
        name="iPhone 15 Pro",
        description="Latest Apple smartphone",
        price="999.99",
        category="Electronics",
        tags=["smartphone"],
        stock_quantity=100
    )
    result = await create_product(payload)
    assert result.name == "iPhone 15 Pro"
    assert result.category == "Electronics"
    mock_db.products.insert_one.assert_called_once()

@pytest.mark.asyncio
async def test_get_product_not_found(mock_db):
    from fastapi import HTTPException
    mock_db.products.find_one = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await get_product("507f1f77bcf86cd799439011")
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_get_product_invalid_id(mock_db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await get_product("invalid-id")
    assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_delete_product_success(mock_db):
    mock_db.products.delete_one = AsyncMock(
        return_value=MagicMock(deleted_count=1)
    )
    result = await delete_product("507f1f77bcf86cd799439011")
    assert "deleted successfully" in result["message"]
