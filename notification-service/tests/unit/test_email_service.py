import pytest
from unittest.mock import patch, MagicMock
from app.services.email_service import (
    send_email,
    build_order_confirmation_email,
    build_order_cancelled_email,
    build_inventory_low_email,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_order_placed_event():
    return {
        "event_type": "ORDER_PLACED",
        "timestamp": "2026-02-21T03:02:36.792213Z",
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


# ─── build_order_confirmation_email ──────────────────────────────────────────

def test_order_confirmation_subject_contains_order_number():
    event = make_order_placed_event()
    subject, _ = build_order_confirmation_email(event)
    assert "ORD-20260221-6BA0A415" in subject

def test_order_confirmation_body_contains_customer_name():
    event = make_order_placed_event()
    _, body = build_order_confirmation_email(event)
    assert "Yash Vyas" in body

def test_order_confirmation_body_contains_product_name():
    event = make_order_placed_event()
    _, body = build_order_confirmation_email(event)
    assert "iPhone 15 Pro" in body

def test_order_confirmation_body_contains_total():
    event = make_order_placed_event()
    _, body = build_order_confirmation_email(event)
    assert "$1999.98" in body

def test_order_confirmation_body_contains_item_price():
    event = make_order_placed_event()
    _, body = build_order_confirmation_email(event)
    assert "$999.99" in body

def test_order_confirmation_body_contains_quantity():
    event = make_order_placed_event()
    _, body = build_order_confirmation_email(event)
    assert ">2<" in body

def test_order_confirmation_multiple_items():
    event = make_order_placed_event()
    event["items"].append({
        "product_id": "prod-002",
        "product_name": "AirPods Pro",
        "quantity": 1,
        "price": 249.99,
    })
    _, body = build_order_confirmation_email(event)
    assert "iPhone 15 Pro" in body
    assert "AirPods Pro" in body

def test_order_confirmation_empty_items():
    event = make_order_placed_event()
    event["items"] = []
    subject, body = build_order_confirmation_email(event)
    assert "ORD-20260221-6BA0A415" in subject
    assert "Yash Vyas" in body


# ─── build_order_cancelled_email ─────────────────────────────────────────────

def test_order_cancelled_subject_contains_order_number():
    event = make_order_cancelled_event()
    subject, _ = build_order_cancelled_email(event)
    assert "ORD-20260221-6BA0A415" in subject

def test_order_cancelled_body_contains_customer_name():
    event = make_order_cancelled_event()
    _, body = build_order_cancelled_email(event)
    assert "Yash Vyas" in body

def test_order_cancelled_body_contains_order_number():
    event = make_order_cancelled_event()
    _, body = build_order_cancelled_email(event)
    assert "ORD-20260221-6BA0A415" in body


# ─── build_inventory_low_email ───────────────────────────────────────────────

def test_inventory_low_subject_contains_product_name():
    event = make_inventory_low_event()
    subject, _ = build_inventory_low_email(event)
    assert "iPhone 15 Pro" in subject

def test_inventory_low_body_contains_product_id():
    event = make_inventory_low_event()
    _, body = build_inventory_low_email(event)
    assert "prod-001" in body

def test_inventory_low_body_contains_quantity():
    event = make_inventory_low_event()
    _, body = build_inventory_low_email(event)
    assert "3" in body

def test_inventory_low_missing_product_name():
    event = {"product_id": "prod-001", "quantity": 3}
    subject, _ = build_inventory_low_email(event)
    assert "Unknown Product" in subject

def test_inventory_low_missing_all_fields():
    event = {}
    subject, body = build_inventory_low_email(event)
    assert "Unknown Product" in subject
    assert "N/A" in body


# ─── send_email (disabled mode) ─────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.email_service.settings")
async def test_send_email_disabled_returns_true(mock_settings):
    mock_settings.EMAIL_ENABLED = False
    result = await send_email("test@example.com", "Test", "<p>Hi</p>")
    assert result is True

@pytest.mark.asyncio
@patch("app.services.email_service.settings")
async def test_send_email_disabled_does_not_call_smtp(mock_settings):
    mock_settings.EMAIL_ENABLED = False
    with patch("app.services.email_service.smtplib.SMTP") as mock_smtp:
        await send_email("test@example.com", "Test", "<p>Hi</p>")
        mock_smtp.assert_not_called()


# ─── send_email (enabled mode) ──────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.email_service.smtplib.SMTP")
@patch("app.services.email_service.settings")
async def test_send_email_enabled_calls_smtp(mock_settings, mock_smtp_class):
    mock_settings.EMAIL_ENABLED = True
    mock_settings.SMTP_HOST = "smtp.gmail.com"
    mock_settings.SMTP_PORT = 587
    mock_settings.SMTP_USERNAME = "user@gmail.com"
    mock_settings.SMTP_PASSWORD = "app-password"
    mock_settings.SMTP_FROM_EMAIL = "user@gmail.com"
    mock_settings.SMTP_FROM_NAME = "FastAPI Store"

    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    result = await send_email("yash@example.com", "Test Subject", "<p>Hello</p>")
    assert result is True
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@gmail.com", "app-password")
    mock_server.send_message.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.email_service.smtplib.SMTP")
@patch("app.services.email_service.settings")
async def test_send_email_smtp_failure_returns_false(mock_settings, mock_smtp_class):
    mock_settings.EMAIL_ENABLED = True
    mock_settings.SMTP_HOST = "smtp.gmail.com"
    mock_settings.SMTP_PORT = 587

    mock_smtp_class.side_effect = Exception("SMTP connection failed")

    result = await send_email("yash@example.com", "Test", "<p>Hi</p>")
    assert result is False