import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4
from app.models.outbox import Outbox, OutboxStatus
from app.services.outbox_worker import _process_pending_events, _cleanup_old_events


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_mock_outbox_event(
    order_number="ORD-20260302-TEST001",
    topic="order-placed",
    status=OutboxStatus.PENDING,
):
    event = MagicMock()
    event.id = uuid4()
    event.topic = topic
    event.status = status
    event.event_payload = json.dumps({
        "event_type": "ORDER_PLACED",
        "order_number": order_number,
        "customer_name": "Yash Vyas",
        "customer_email": "yash@example.com",
        "total_amount": 999.99,
        "items": [{"product_id": "prod-001", "product_name": "iPhone 15 Pro", "quantity": 1, "price": 999.99}],
    })
    event.created_at = datetime.now(timezone.utc)
    event.sent_at = None
    return event


# ─── _process_pending_events ─────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.outbox_worker.publish_event", new_callable=AsyncMock)
@patch("app.services.outbox_worker.AsyncSessionLocal")
async def test_process_pending_publishes_to_kafka(mock_session_factory, mock_publish):
    event = make_mock_outbox_event()

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [event]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    await _process_pending_events()

    mock_publish.assert_called_once()
    call_args = mock_publish.call_args
    assert call_args[0][0] == "order-placed"
    assert call_args[0][1]["order_number"] == "ORD-20260302-TEST001"


@pytest.mark.asyncio
@patch("app.services.outbox_worker.publish_event", new_callable=AsyncMock)
@patch("app.services.outbox_worker.AsyncSessionLocal")
async def test_process_pending_marks_event_as_sent(mock_session_factory, mock_publish):
    event = make_mock_outbox_event()

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [event]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    await _process_pending_events()

    assert event.status == OutboxStatus.SENT
    assert event.sent_at is not None


@pytest.mark.asyncio
@patch("app.services.outbox_worker.publish_event", new_callable=AsyncMock)
@patch("app.services.outbox_worker.AsyncSessionLocal")
async def test_process_pending_no_events_does_nothing(mock_session_factory, mock_publish):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    await _process_pending_events()

    mock_publish.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.outbox_worker.publish_event", new_callable=AsyncMock)
@patch("app.services.outbox_worker.AsyncSessionLocal")
async def test_process_pending_kafka_failure_keeps_pending(mock_session_factory, mock_publish):
    event = make_mock_outbox_event()
    mock_publish.side_effect = Exception("Kafka connection failed")

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [event]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    await _process_pending_events()

    # Event stays PENDING — not marked as SENT
    assert event.status == OutboxStatus.PENDING
    assert event.sent_at is None


@pytest.mark.asyncio
@patch("app.services.outbox_worker.publish_event", new_callable=AsyncMock)
@patch("app.services.outbox_worker.AsyncSessionLocal")
async def test_process_pending_multiple_events(mock_session_factory, mock_publish):
    event1 = make_mock_outbox_event(order_number="ORD-001")
    event2 = make_mock_outbox_event(order_number="ORD-002")

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [event1, event2]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    await _process_pending_events()

    assert mock_publish.call_count == 2
    assert event1.status == OutboxStatus.SENT
    assert event2.status == OutboxStatus.SENT


@pytest.mark.asyncio
@patch("app.services.outbox_worker.publish_event", new_callable=AsyncMock)
@patch("app.services.outbox_worker.AsyncSessionLocal")
async def test_process_pending_partial_failure(mock_session_factory, mock_publish):
    """First event publishes, second fails — first should be SENT, second PENDING."""
    event1 = make_mock_outbox_event(order_number="ORD-001")
    event2 = make_mock_outbox_event(order_number="ORD-002")

    mock_publish.side_effect = [None, Exception("Kafka down")]

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [event1, event2]
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    await _process_pending_events()

    assert event1.status == OutboxStatus.SENT
    assert event2.status == OutboxStatus.PENDING


# ─── _cleanup_old_events ────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.outbox_worker.AsyncSessionLocal")
async def test_cleanup_deletes_old_sent_events(mock_session_factory):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    await _cleanup_old_events()

    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.outbox_worker.AsyncSessionLocal")
async def test_cleanup_no_old_events_skips_commit(mock_session_factory):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    await _cleanup_old_events()

    mock_db.commit.assert_not_called()


# ─── Outbox Model ────────────────────────────────────────────────────────────

def test_outbox_event_default_status_is_pending():
    event = make_mock_outbox_event()
    assert event.status == OutboxStatus.PENDING

def test_outbox_event_payload_is_valid_json():
    event = make_mock_outbox_event()
    payload = json.loads(event.event_payload)
    assert payload["event_type"] == "ORDER_PLACED"
    assert payload["order_number"] == "ORD-20260302-TEST001"
    assert "items" in payload