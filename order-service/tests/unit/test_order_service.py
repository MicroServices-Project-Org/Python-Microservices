import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import HTTPException
from app.services.order_service import (
    create_order, get_order, get_all_orders,
    get_orders_by_email, update_order_status, cancel_order
)
from app.schemas.order import OrderCreate, OrderItemCreate, OrderStatusUpdate
from app.models.order import OrderStatus

# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_mock_item(product_id="prod-001", quantity=2, unit_price=999.99):
    item = MagicMock()
    item.id = uuid4()
    item.order_id = uuid4()
    item.product_id = product_id
    item.product_name = "iPhone 15 Pro"
    item.quantity = quantity
    item.unit_price = unit_price
    item.total_price = round(quantity * unit_price, 2)
    return item

def make_mock_order(status=OrderStatus.CONFIRMED):
    order = MagicMock()
    order.id = uuid4()
    order.order_number = "ORD-20260221-ABC12345"
    order.customer_name = "Yash Vyas"
    order.customer_email = "yash@example.com"
    order.total_amount = 1999.98
    order.status = status
    order.items = [make_mock_item()]
    order.created_at = datetime.now(timezone.utc)
    order.updated_at = datetime.now(timezone.utc)
    return order

def make_mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db

SAMPLE_ORDER = OrderCreate(
    customer_name="Yash Vyas",
    customer_email="yash@example.com",
    items=[
        OrderItemCreate(
            product_id="prod-001",
            product_name="iPhone 15 Pro",
            quantity=2,
            unit_price=999.99
        )
    ]
)

SAMPLE_ORDER_MULTI = OrderCreate(
    customer_name="Yash Vyas",
    customer_email="yash@example.com",
    items=[
        OrderItemCreate(
            product_id="prod-001",
            product_name="iPhone 15 Pro",
            quantity=2,
            unit_price=999.99
        ),
        OrderItemCreate(
            product_id="prod-002",
            product_name="AirPods Pro",
            quantity=1,
            unit_price=249.99
        )
    ]
)


# ─── create_order ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_order_success():
    db = make_mock_db()
    mock_order = make_mock_order()

    async def mock_refresh(obj, attrs=None):
        if hasattr(obj, 'items'):
            obj.items = [make_mock_item()]

    db.refresh = mock_refresh

    with patch("app.services.order_service.inventory_client.check_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.inventory_client.reduce_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.publish_order_placed", AsyncMock()):
        result = await create_order(SAMPLE_ORDER, db)

    db.add.assert_called()
    db.flush.assert_called()

@pytest.mark.asyncio
async def test_create_order_calculates_total_correctly():
    db = make_mock_db()

    async def mock_refresh(obj, attrs=None):
        if hasattr(obj, 'items'):
            obj.items = [make_mock_item(quantity=2, unit_price=999.99)]

    db.refresh = mock_refresh

    with patch("app.services.order_service.inventory_client.check_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.inventory_client.reduce_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.publish_order_placed", AsyncMock()):
        result = await create_order(SAMPLE_ORDER, db)

    assert result.total_amount == 1999.98

@pytest.mark.asyncio
async def test_create_order_multi_item_total():
    db = make_mock_db()

    async def mock_refresh(obj, attrs=None):
        if hasattr(obj, 'items'):
            obj.items = [
                make_mock_item("prod-001", 2, 999.99),
                make_mock_item("prod-002", 1, 249.99)
            ]
    db.refresh = mock_refresh

    with patch("app.services.order_service.inventory_client.check_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.inventory_client.reduce_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.publish_order_placed", AsyncMock()):
        result = await create_order(SAMPLE_ORDER_MULTI, db)

    # 2 * 999.99 + 1 * 249.99 = 2249.97
    assert result.total_amount == 2249.97

@pytest.mark.asyncio
async def test_create_order_insufficient_stock_raises_400():
    db = make_mock_db()

    with patch("app.services.order_service.inventory_client.check_stock", AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc:
            await create_order(SAMPLE_ORDER, db)

    assert exc.value.status_code == 400
    assert "Insufficient stock" in exc.value.detail

@pytest.mark.asyncio
async def test_create_order_checks_all_items():
    db = make_mock_db()
    check_mock = AsyncMock(return_value=True)

    async def mock_refresh(obj, attrs=None):
        if hasattr(obj, 'items'):
            obj.items = []
    db.refresh = mock_refresh

    with patch("app.services.order_service.inventory_client.check_stock", check_mock), \
         patch("app.services.order_service.inventory_client.reduce_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.publish_order_placed", AsyncMock()):
        await create_order(SAMPLE_ORDER_MULTI, db)

    assert check_mock.call_count == 2

@pytest.mark.asyncio
async def test_create_order_stops_on_first_out_of_stock():
    db = make_mock_db()
    # First item out of stock
    check_mock = AsyncMock(side_effect=[False, True])

    with patch("app.services.order_service.inventory_client.check_stock", check_mock):
        with pytest.raises(HTTPException) as exc:
            await create_order(SAMPLE_ORDER_MULTI, db)

    assert exc.value.status_code == 400
    # Should stop after first failure — only called once
    assert check_mock.call_count == 1

@pytest.mark.asyncio
async def test_create_order_reduces_stock_for_all_items():
    db = make_mock_db()
    reduce_mock = AsyncMock(return_value=True)

    async def mock_refresh(obj, attrs=None):
        if hasattr(obj, 'items'):
            obj.items = [
                make_mock_item("prod-001", 2, 999.99),
                make_mock_item("prod-002", 1, 249.99)
            ]
    db.refresh = mock_refresh

    with patch("app.services.order_service.inventory_client.check_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.inventory_client.reduce_stock", reduce_mock), \
         patch("app.services.order_service.publish_order_placed", AsyncMock()):
        await create_order(SAMPLE_ORDER_MULTI, db)

    assert reduce_mock.call_count == 2

@pytest.mark.asyncio
async def test_create_order_publishes_kafka_event():
    db = make_mock_db()
    kafka_mock = AsyncMock()

    async def mock_refresh(obj, attrs=None):
        if hasattr(obj, 'items'):
            obj.items = [make_mock_item()]
    db.refresh = mock_refresh

    with patch("app.services.order_service.inventory_client.check_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.inventory_client.reduce_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.publish_order_placed", kafka_mock):
        await create_order(SAMPLE_ORDER, db)

    kafka_mock.assert_called_once()
    event = kafka_mock.call_args[0][0]
    assert event["event_type"] == "ORDER_PLACED"
    assert "order_number" in event
    assert "customer_email" in event
    assert "items" in event

@pytest.mark.asyncio
async def test_create_order_generates_unique_order_number():
    db1 = make_mock_db()
    db2 = make_mock_db()

    async def mock_refresh(obj, attrs=None):
        if hasattr(obj, 'items'):
            obj.items = [make_mock_item()]

    db1.refresh = mock_refresh
    db2.refresh = mock_refresh

    with patch("app.services.order_service.inventory_client.check_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.inventory_client.reduce_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.publish_order_placed", AsyncMock()):
        order1 = await create_order(SAMPLE_ORDER, db1)
        order2 = await create_order(SAMPLE_ORDER, db2)

    assert order1.order_number != order2.order_number
    assert order1.order_number.startswith("ORD-")
    assert order2.order_number.startswith("ORD-")

@pytest.mark.asyncio
async def test_create_order_status_is_confirmed():
    db = make_mock_db()

    async def mock_refresh(obj, attrs=None):
        if hasattr(obj, 'items'):
            obj.items = [make_mock_item()]
    db.refresh = mock_refresh

    with patch("app.services.order_service.inventory_client.check_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.inventory_client.reduce_stock", AsyncMock(return_value=True)), \
         patch("app.services.order_service.publish_order_placed", AsyncMock()):
        result = await create_order(SAMPLE_ORDER, db)

    assert result.status == OrderStatus.CONFIRMED


# ─── get_order ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_order_success():
    db = make_mock_db()
    mock_order = make_mock_order()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_order
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_order(str(mock_order.id), db)
    assert result.order_number == "ORD-20260221-ABC12345"

@pytest.mark.asyncio
async def test_get_order_not_found_raises_404():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await get_order(str(uuid4()), db)
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_get_order_invalid_id_raises_400():
    db = make_mock_db()

    with pytest.raises(HTTPException) as exc:
        await get_order("not-a-uuid", db)
    assert exc.value.status_code == 400


# ─── get_all_orders ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_orders_returns_list():
    db = make_mock_db()
    orders = [make_mock_order(), make_mock_order()]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = orders
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_all_orders(db)
    assert len(result) == 2

@pytest.mark.asyncio
async def test_get_all_orders_empty():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_all_orders(db)
    assert result == []


# ─── get_orders_by_email ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_orders_by_email_returns_list():
    db = make_mock_db()
    orders = [make_mock_order(), make_mock_order()]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = orders
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_orders_by_email("yash@example.com", db)
    assert len(result) == 2

@pytest.mark.asyncio
async def test_get_orders_by_email_empty():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_orders_by_email("nobody@example.com", db)
    assert result == []


# ─── update_order_status ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_order_status_success():
    db = make_mock_db()
    mock_order = make_mock_order(status=OrderStatus.CONFIRMED)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_order
    db.execute = AsyncMock(return_value=mock_result)

    async def mock_refresh(obj, attrs=None):
        pass
    db.refresh = mock_refresh

    result = await update_order_status(
        str(mock_order.id),
        OrderStatusUpdate(status=OrderStatus.SHIPPED),
        db
    )
    assert result.status == OrderStatus.SHIPPED

@pytest.mark.asyncio
async def test_update_order_status_not_found_raises_404():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await update_order_status(
            str(uuid4()),
            OrderStatusUpdate(status=OrderStatus.SHIPPED),
            db
        )
    assert exc.value.status_code == 404


# ─── cancel_order ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_order_success():
    db = make_mock_db()
    mock_order = make_mock_order(status=OrderStatus.CONFIRMED)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_order
    db.execute = AsyncMock(return_value=mock_result)

    async def mock_refresh(obj, attrs=None):
        pass
    db.refresh = mock_refresh

    result = await cancel_order(str(mock_order.id), db)
    assert result.status == OrderStatus.CANCELLED

@pytest.mark.asyncio
async def test_cancel_shipped_order_raises_400():
    db = make_mock_db()
    mock_order = make_mock_order(status=OrderStatus.SHIPPED)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_order
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await cancel_order(str(mock_order.id), db)
    assert exc.value.status_code == 400
    assert "Cannot cancel" in exc.value.detail

@pytest.mark.asyncio
async def test_cancel_delivered_order_raises_400():
    db = make_mock_db()
    mock_order = make_mock_order(status=OrderStatus.DELIVERED)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_order
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await cancel_order(str(mock_order.id), db)
    assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_cancel_order_not_found_raises_404():
    db = make_mock_db()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc:
        await cancel_order(str(uuid4()), db)
    assert exc.value.status_code == 404