import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException
from app.services.product_service import (
    create_product, get_product, get_all_products,
    search_products, update_product, delete_product
)
from app.schemas.product import ProductCreate, ProductUpdate

# ─── Fixtures ────────────────────────────────────────────────────────────────

MOCK_OID = ObjectId("507f1f77bcf86cd799439011")

MOCK_DOC = {
    "_id": MOCK_OID,
    "name": "iPhone 15 Pro",
    "description": "Latest Apple smartphone",
    "price": 999.99,
    "category": "Electronics",
    "tags": ["smartphone", "apple"],
    "image_url": None,
    "stock_quantity": 100,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
}

SAMPLE_CREATE = ProductCreate(
    name="iPhone 15 Pro",
    description="Latest Apple smartphone",
    price=999.99,
    category="Electronics",
    tags=["smartphone"],
    stock_quantity=100
)

@pytest.fixture
def mock_db():
    with patch("app.services.product_service.get_db") as mock:
        db = MagicMock()
        mock.return_value = db
        yield db


# ─── create_product ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_product_success(mock_db):
    mock_db.products.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=MOCK_OID)
    )
    result = await create_product(SAMPLE_CREATE)
    assert result.name == "iPhone 15 Pro"
    assert result.category == "Electronics"
    assert result.stock_quantity == 100
    mock_db.products.insert_one.assert_called_once()

@pytest.mark.asyncio
async def test_create_product_inserts_timestamps(mock_db):
    mock_db.products.insert_one = AsyncMock(
        return_value=MagicMock(inserted_id=MOCK_OID)
    )
    result = await create_product(SAMPLE_CREATE)
    assert result.created_at is not None
    assert result.updated_at is not None


# ─── get_product ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_product_success(mock_db):
    mock_db.products.find_one = AsyncMock(return_value=dict(MOCK_DOC))
    result = await get_product(str(MOCK_OID))
    assert result.name == "iPhone 15 Pro"
    assert result.id == str(MOCK_OID)

@pytest.mark.asyncio
async def test_get_product_not_found_raises_404(mock_db):
    mock_db.products.find_one = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await get_product(str(MOCK_OID))
    assert exc.value.status_code == 404
    assert "not found" in exc.value.detail.lower()

@pytest.mark.asyncio
async def test_get_product_invalid_id_raises_400(mock_db):
    with pytest.raises(HTTPException) as exc:
        await get_product("not-a-valid-id")
    assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_get_product_uses_correct_id(mock_db):
    mock_db.products.find_one = AsyncMock(return_value=dict(MOCK_DOC))
    await get_product(str(MOCK_OID))
    mock_db.products.find_one.assert_called_once_with({"_id": MOCK_OID})


# ─── get_all_products ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_products_returns_paginated(mock_db):
    async def mock_async_iter():
        yield dict(MOCK_DOC)
        yield dict(MOCK_DOC)

    mock_cursor = MagicMock()
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_async_iter()
    mock_db.products.count_documents = AsyncMock(return_value=2)
    mock_db.products.find.return_value = mock_cursor

    result = await get_all_products(page=1, page_size=10)
    assert result.total == 2
    assert result.page == 1
    assert result.page_size == 10
    assert len(result.products) == 2

@pytest.mark.asyncio
async def test_get_all_products_applies_pagination(mock_db):
    async def mock_async_iter():
        yield dict(MOCK_DOC)

    mock_cursor = MagicMock()
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_async_iter()
    mock_db.products.count_documents = AsyncMock(return_value=10)
    mock_db.products.find.return_value = mock_cursor

    await get_all_products(page=2, page_size=5)
    mock_cursor.skip.assert_called_once_with(5)   # (page-1) * page_size
    mock_cursor.limit.assert_called_once_with(5)


# ─── search_products ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_products_returns_matches(mock_db):
    async def mock_async_iter():
        yield dict(MOCK_DOC)

    mock_cursor = MagicMock()
    mock_db.products.find.return_value = mock_cursor
    mock_cursor.__aiter__ = lambda self: mock_async_iter()

    results = await search_products("iPhone")
    assert len(results) == 1
    assert results[0].name == "iPhone 15 Pro"

@pytest.mark.asyncio
async def test_search_products_returns_empty_list(mock_db):
    async def mock_async_iter():
        return
        yield  # make it an async generator

    mock_cursor = MagicMock()
    mock_db.products.find.return_value = mock_cursor
    mock_cursor.__aiter__ = lambda self: mock_async_iter()

    results = await search_products("nonexistent")
    assert results == []


# ─── update_product ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_product_success(mock_db):
    updated_doc = dict(MOCK_DOC)
    updated_doc["price"] = 899.99
    mock_db.products.find_one_and_update = AsyncMock(return_value=updated_doc)

    result = await update_product(str(MOCK_OID), ProductUpdate(price=899.99))
    assert result.price == 899.99

@pytest.mark.asyncio
async def test_update_product_not_found_raises_404(mock_db):
    mock_db.products.find_one_and_update = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await update_product(str(MOCK_OID), ProductUpdate(price=899.99))
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_update_product_no_fields_raises_400(mock_db):
    with pytest.raises(HTTPException) as exc:
        await update_product(str(MOCK_OID), ProductUpdate())
    assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_update_product_invalid_id_raises_400(mock_db):
    with pytest.raises(HTTPException) as exc:
        await update_product("bad-id", ProductUpdate(price=899.99))
    assert exc.value.status_code == 400


# ─── delete_product ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_product_success(mock_db):
    mock_db.products.delete_one = AsyncMock(
        return_value=MagicMock(deleted_count=1)
    )
    result = await delete_product(str(MOCK_OID))
    assert "deleted successfully" in result["message"]

@pytest.mark.asyncio
async def test_delete_product_not_found_raises_404(mock_db):
    mock_db.products.delete_one = AsyncMock(
        return_value=MagicMock(deleted_count=0)
    )
    with pytest.raises(HTTPException) as exc:
        await delete_product(str(MOCK_OID))
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_delete_product_invalid_id_raises_400(mock_db):
    with pytest.raises(HTTPException) as exc:
        await delete_product("bad-id")
    assert exc.value.status_code == 400