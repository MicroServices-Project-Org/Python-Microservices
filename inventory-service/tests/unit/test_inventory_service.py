import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import HTTPException
from app.services.inventory_service import (
    create_inventory, get_inventory, get_all_inventory,
    check_stock, reduce_stock, restock,
    update_inventory, delete_inventory
)
from app.schemas.inventory import InventoryCreate, InventoryUpdate

# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_mock_item(product_id="prod-001", quantity=100, reserved_qty=0):
    """Create a mock Inventory ORM object."""
    item = MagicMock()
    item.id = uuid4()
    item.product_id = product_id
    item.product_name = "iPhone 15 Pro"
    item.quantity = quantity
    item.reserved_qty = reserved_qty
    item.available_qty = quantity - reserved_qty
    item.created_at = datetime.now(timezone.utc)
    item.updated_at = datetime.now(timezone.utc)
    return item

def make_mock_db():
    """Create a mock AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db

SAMPLE_CREATE = InventoryCreate(
    product_id="prod-001",
    product_name="iPhone 15 Pro",
    quantity=100
)


# ─── create_inventory ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_inventory_success():
    db = make_mock_db()
    # No existing item
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    async def mock_refresh(item):
        item.id = uuid4()

    db.refresh = mock_refresh

    result = await create_inventory(SAMPLE_CREATE, db)
    assert result.product_id == "prod-001"
    assert result.quantity == 100
    db.add.assert_called_once()
    db.flush.assert_called_once()

@pytest.mark.asyncio
async def test_create_inventory_duplicate_raises_409():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = make_mock_item()
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await create_inventory(SAMPLE_CREATE, db)
    assert exc.value.status_code == 409
    assert "already exists" in exc.value.detail


# ─── get_inventory ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_inventory_success():
    db = make_mock_db()
    mock_item = make_mock_item()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_item
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_inventory("prod-001", db)
    assert result.product_id == "prod-001"

@pytest.mark.asyncio
async def test_get_inventory_not_found_raises_404():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await get_inventory("prod-nonexistent", db)
    assert exc.value.status_code == 404
    assert "not found" in exc.value.detail.lower()


# ─── get_all_inventory ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_inventory_returns_list():
    db = make_mock_db()
    items = [make_mock_item("prod-001"), make_mock_item("prod-002")]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = items
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_all_inventory(db)
    assert len(result) == 2

@pytest.mark.asyncio
async def test_get_all_inventory_returns_empty_list():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_all_inventory(db)
    assert result == []


# ─── check_stock ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_stock_returns_true_when_sufficient():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = make_mock_item(quantity=100)
    db.execute = AsyncMock(return_value=mock_result)

    result = await check_stock("prod-001", 10, db)
    assert result is True

@pytest.mark.asyncio
async def test_check_stock_returns_false_when_insufficient():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = make_mock_item(quantity=5)
    db.execute = AsyncMock(return_value=mock_result)

    result = await check_stock("prod-001", 100, db)
    assert result is False

@pytest.mark.asyncio
async def test_check_stock_exact_quantity_returns_true():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = make_mock_item(quantity=10)
    db.execute = AsyncMock(return_value=mock_result)

    result = await check_stock("prod-001", 10, db)
    assert result is True


# ─── reduce_stock ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reduce_stock_success():
    db = make_mock_db()
    mock_item = make_mock_item(quantity=100)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_item
    db.execute = AsyncMock(return_value=mock_result)

    async def mock_refresh(item):
        item.available_qty = item.quantity - item.reserved_qty
    db.refresh = mock_refresh

    result = await reduce_stock("prod-001", 10, db)
    assert result.quantity == 90

@pytest.mark.asyncio
async def test_reduce_stock_insufficient_raises_400():
    db = make_mock_db()
    mock_item = make_mock_item(quantity=5)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_item
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await reduce_stock("prod-001", 100, db)
    assert exc.value.status_code == 400
    assert "Insufficient stock" in exc.value.detail

@pytest.mark.asyncio
async def test_reduce_stock_not_found_raises_404():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await reduce_stock("prod-nonexistent", 10, db)
    assert exc.value.status_code == 404


# ─── restock ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_restock_success():
    db = make_mock_db()
    mock_item = make_mock_item(quantity=100)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_item
    db.execute = AsyncMock(return_value=mock_result)

    async def mock_refresh(item):
        item.available_qty = item.quantity
    db.refresh = mock_refresh

    result = await restock("prod-001", 50, db)
    assert result.quantity == 150

@pytest.mark.asyncio
async def test_restock_not_found_raises_404():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await restock("prod-nonexistent", 50, db)
    assert exc.value.status_code == 404


# ─── update_inventory ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_inventory_success():
    db = make_mock_db()
    mock_item = make_mock_item()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_item
    db.execute = AsyncMock(return_value=mock_result)

    async def mock_refresh(item):
        pass
    db.refresh = mock_refresh

    result = await update_inventory(
        "prod-001",
        InventoryUpdate(product_name="iPhone 15 Pro Max"),
        db
    )
    assert result.product_name == "iPhone 15 Pro Max"

@pytest.mark.asyncio
async def test_update_inventory_not_found_raises_404():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await update_inventory("prod-nonexistent", InventoryUpdate(product_name="X"), db)
    assert exc.value.status_code == 404


# ─── delete_inventory ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_inventory_success():
    db = make_mock_db()
    mock_item = make_mock_item()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_item
    db.execute = AsyncMock(return_value=mock_result)

    result = await delete_inventory("prod-001", db)
    assert "deleted successfully" in result["message"]
    db.delete.assert_called_once_with(mock_item)

@pytest.mark.asyncio
async def test_delete_inventory_not_found_raises_404():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await delete_inventory("prod-nonexistent", db)
    assert exc.value.status_code == 404