import pytest
from unittest.mock import AsyncMock, patch
from app.kafka.consumer import (
    _handle_message,
    _handle_order_placed,
    _handle_order_cancelled,
    _handle_inventory_low,
    _handle_ai_notification,
    _is_duplicate,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_order_placed_event():
    return {
        "event_type": "ORDER_PLACED",
        "order_number": "ORD-20260221-6BA0A415",
        "customer_name": "Yash Vyas",
        "customer_email": "yash@example.com",
        "total_amount": 1999.98,
        "items": [
            {
                "product_id": "prod-001",
                "product_name": "iPhone 15 Pro",
                "quantity": 2,
                "price": 999.99,
            }
        ],
    }

def make_order_cancelled_event():
    return {
        "event_type": "ORDER_CANCELLED",
        "order_number": "ORD-20260221-6BA0A415",
        "customer_name": "Yash Vyas",
        "customer_email": "yash@example.com",
    }

def make_inventory_low_event():
    return {
        "event_type": "INVENTORY_LOW",
        "product_id": "prod-001",
        "product_name": "iPhone 15 Pro",
        "quantity": 3,
    }

def make_ai_notification_event():
    return {
        "order_number": "ORD-20260221-6BA0A415",
        "customer_email": "yash@example.com",
        "subject": "Your personalized recommendations!",
        "body_html": "<p>Based on your purchase, you might like...</p>",
    }


# ─── _handle_message routing ────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.kafka.consumer._handle_order_placed", new_callable=AsyncMock)
async def test_handle_message_routes_order_placed(mock_handler):
    event = make_order_placed_event()
    await _handle_message("order-placed", event)
    mock_handler.assert_called_once_with(event)

@pytest.mark.asyncio
@patch("app.kafka.consumer._handle_order_cancelled", new_callable=AsyncMock)
async def test_handle_message_routes_order_cancelled(mock_handler):
    event = make_order_cancelled_event()
    await _handle_message("order-cancelled", event)
    mock_handler.assert_called_once_with(event)

@pytest.mark.asyncio
@patch("app.kafka.consumer._handle_inventory_low", new_callable=AsyncMock)
async def test_handle_message_routes_inventory_low(mock_handler):
    event = make_inventory_low_event()
    await _handle_message("inventory-low", event)
    mock_handler.assert_called_once_with(event)

@pytest.mark.asyncio
@patch("app.kafka.consumer._handle_ai_notification", new_callable=AsyncMock)
async def test_handle_message_routes_ai_notification(mock_handler):
    event = make_ai_notification_event()
    await _handle_message("ai-notification-ready", event)
    mock_handler.assert_called_once_with(event)

@pytest.mark.asyncio
async def test_handle_message_unknown_topic_does_not_crash():
    await _handle_message("unknown-topic", {"data": "test"})


# ─── _handle_order_placed ───────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=False)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock, return_value=True)
@patch("app.kafka.consumer.build_order_confirmation_email")
async def test_handle_order_placed_sends_email(mock_build, mock_send, mock_dup):
    mock_build.return_value = ("Order Confirmed", "<p>Confirmed</p>")
    event = make_order_placed_event()

    await _handle_order_placed(event)

    mock_build.assert_called_once_with(event)
    mock_send.assert_called_once_with("yash@example.com", "Order Confirmed", "<p>Confirmed</p>")

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=False)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock, return_value=True)
@patch("app.kafka.consumer.build_order_confirmation_email")
async def test_handle_order_placed_uses_correct_email(mock_build, mock_send, mock_dup):
    mock_build.return_value = ("Subject", "<p>Body</p>")
    event = make_order_placed_event()
    event["customer_email"] = "other@example.com"

    await _handle_order_placed(event)
    mock_send.assert_called_once_with("other@example.com", "Subject", "<p>Body</p>")

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=True)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock)
async def test_handle_order_placed_skips_duplicate(mock_send, mock_dup):
    event = make_order_placed_event()
    await _handle_order_placed(event)
    mock_send.assert_not_called()


# ─── _handle_order_cancelled ────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=False)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock, return_value=True)
@patch("app.kafka.consumer.build_order_cancelled_email")
async def test_handle_order_cancelled_sends_email(mock_build, mock_send, mock_dup):
    mock_build.return_value = ("Order Cancelled", "<p>Cancelled</p>")
    event = make_order_cancelled_event()

    await _handle_order_cancelled(event)

    mock_build.assert_called_once_with(event)
    mock_send.assert_called_once_with("yash@example.com", "Order Cancelled", "<p>Cancelled</p>")

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=True)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock)
async def test_handle_order_cancelled_skips_duplicate(mock_send, mock_dup):
    event = make_order_cancelled_event()
    await _handle_order_cancelled(event)
    mock_send.assert_not_called()


# ─── _handle_inventory_low ──────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=False)
@patch("app.kafka.consumer.settings")
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock, return_value=True)
@patch("app.kafka.consumer.build_inventory_low_email")
async def test_handle_inventory_low_sends_to_admin(mock_build, mock_send, mock_settings, mock_dup):
    mock_settings.SMTP_FROM_EMAIL = "admin@store.com"
    mock_build.return_value = ("Low Stock", "<p>Low stock</p>")
    event = make_inventory_low_event()

    await _handle_inventory_low(event)

    mock_build.assert_called_once_with(event)
    mock_send.assert_called_once_with("admin@store.com", "Low Stock", "<p>Low stock</p>")

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=False)
@patch("app.kafka.consumer.settings")
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock, return_value=True)
@patch("app.kafka.consumer.build_inventory_low_email")
async def test_handle_inventory_low_fallback_admin_email(mock_build, mock_send, mock_settings, mock_dup):
    mock_settings.SMTP_FROM_EMAIL = ""
    mock_build.return_value = ("Low Stock", "<p>Low stock</p>")
    event = make_inventory_low_event()

    await _handle_inventory_low(event)
    mock_send.assert_called_once_with("admin@example.com", "Low Stock", "<p>Low stock</p>")

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=True)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock)
async def test_handle_inventory_low_skips_duplicate(mock_send, mock_dup):
    event = make_inventory_low_event()
    await _handle_inventory_low(event)
    mock_send.assert_not_called()


# ─── _handle_ai_notification ────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=False)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock, return_value=True)
async def test_handle_ai_notification_sends_email(mock_send, mock_dup):
    event = make_ai_notification_event()
    await _handle_ai_notification(event)

    mock_send.assert_called_once_with(
        "yash@example.com",
        "Your personalized recommendations!",
        "<p>Based on your purchase, you might like...</p>",
    )

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=False)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock, return_value=True)
async def test_handle_ai_notification_default_subject(mock_send, mock_dup):
    event = {
        "order_number": "ORD-001",
        "customer_email": "yash@example.com",
        "body_html": "<p>Hello</p>",
    }
    await _handle_ai_notification(event)
    call_args = mock_send.call_args
    assert "ORD-001" in call_args[0][1]

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=False)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock)
async def test_handle_ai_notification_missing_email_skips(mock_send, mock_dup):
    event = {
        "order_number": "ORD-001",
        "subject": "Test",
        "body_html": "<p>Hi</p>",
    }
    await _handle_ai_notification(event)
    mock_send.assert_not_called()

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=False)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock, return_value=True)
async def test_handle_ai_notification_default_body(mock_send, mock_dup):
    event = {
        "order_number": "ORD-001",
        "customer_email": "yash@example.com",
        "subject": "Test Subject",
    }
    await _handle_ai_notification(event)
    call_args = mock_send.call_args
    assert "Thank you for your order" in call_args[0][2]

@pytest.mark.asyncio
@patch("app.kafka.consumer._is_duplicate", new_callable=AsyncMock, return_value=True)
@patch("app.kafka.consumer.send_email", new_callable=AsyncMock)
async def test_handle_ai_notification_skips_duplicate(mock_send, mock_dup):
    event = make_ai_notification_event()
    await _handle_ai_notification(event)
    mock_send.assert_not_called()


# ─── _is_duplicate (Redis) ──────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.kafka.consumer._get_redis")
async def test_is_duplicate_returns_false_for_new_event(mock_get_redis):
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)  # SET NX returns True = new key
    mock_get_redis.return_value = mock_redis

    result = await _is_duplicate("ORD-001_ORDER_PLACED")
    assert result is False

@pytest.mark.asyncio
@patch("app.kafka.consumer._get_redis")
async def test_is_duplicate_returns_true_for_existing_event(mock_get_redis):
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=None)  # SET NX returns None = key exists
    mock_get_redis.return_value = mock_redis

    result = await _is_duplicate("ORD-001_ORDER_PLACED")
    assert result is True

@pytest.mark.asyncio
@patch("app.kafka.consumer._get_redis")
async def test_is_duplicate_redis_down_returns_false(mock_get_redis):
    mock_get_redis.side_effect = Exception("Redis connection refused")

    result = await _is_duplicate("ORD-001_ORDER_PLACED")
    assert result is False  # Process the event if Redis is down

@pytest.mark.asyncio
@patch("app.kafka.consumer._get_redis")
async def test_is_duplicate_sets_correct_key(mock_get_redis):
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_get_redis.return_value = mock_redis

    await _is_duplicate("ORD-001_ORDER_PLACED")

    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert call_args[0][0] == "processed:ORD-001_ORDER_PLACED"
    assert call_args[1]["nx"] is True
    assert call_args[1]["ex"] > 0