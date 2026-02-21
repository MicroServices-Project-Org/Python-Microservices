import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.kafka.consumer import _handle_order_placed


# ─── Helpers ─────────────────────────────────────────────────────────────────

MOCK_ORDER_EVENT = {
    "event_type": "ORDER_PLACED",
    "order_number": "ORD-20260221-38F5F24F",
    "customer_name": "Yash Vyas",
    "customer_email": "yash@example.com",
    "total_amount": 999.99,
    "items": [
        {
            "product_id": "prod-001",
            "product_name": "iPhone 15 Pro",
            "quantity": 1,
            "price": 999.99,
        }
    ],
}


# ─── _handle_order_placed ────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.kafka.consumer.publish_ai_notification", new_callable=AsyncMock)
@patch("app.kafka.consumer.personalize_notification", new_callable=AsyncMock)
async def test_handle_order_placed_calls_personalize(mock_personalize, mock_publish):
    mock_personalize.return_value = {
        "subject": "Thanks for your order!",
        "body_html": "<p>Hi Yash</p>",
    }
    await _handle_order_placed(MOCK_ORDER_EVENT)
    mock_personalize.assert_called_once_with(MOCK_ORDER_EVENT)

@pytest.mark.asyncio
@patch("app.kafka.consumer.publish_ai_notification", new_callable=AsyncMock)
@patch("app.kafka.consumer.personalize_notification", new_callable=AsyncMock)
async def test_handle_order_placed_publishes_notification(mock_personalize, mock_publish):
    mock_personalize.return_value = {
        "subject": "Thanks!",
        "body_html": "<p>Hi</p>",
    }
    await _handle_order_placed(MOCK_ORDER_EVENT)
    mock_publish.assert_called_once()
    published = mock_publish.call_args[0][0]
    assert published["order_number"] == "ORD-20260221-38F5F24F"
    assert published["customer_email"] == "yash@example.com"
    assert published["customer_name"] == "Yash Vyas"
    assert published["subject"] == "Thanks!"
    assert published["body_html"] == "<p>Hi</p>"

@pytest.mark.asyncio
@patch("app.kafka.consumer.publish_ai_notification", new_callable=AsyncMock)
@patch("app.kafka.consumer.personalize_notification", new_callable=AsyncMock)
async def test_handle_order_placed_preserves_customer_info(mock_personalize, mock_publish):
    mock_personalize.return_value = {"subject": "S", "body_html": "<p>B</p>"}
    event = {**MOCK_ORDER_EVENT, "customer_email": "other@test.com", "customer_name": "Jane"}
    await _handle_order_placed(event)
    published = mock_publish.call_args[0][0]
    assert published["customer_email"] == "other@test.com"
    assert published["customer_name"] == "Jane"