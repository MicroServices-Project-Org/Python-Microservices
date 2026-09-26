import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.kafka.producer as producer


@pytest.fixture(autouse=True)
def reset_producer(monkeypatch):
    monkeypatch.setattr(producer, "_producer", None)
    monkeypatch.setattr(producer, "_start_failing", False)


def fake_kafka(start_side_effect=None):
    instance = MagicMock()
    instance.start = AsyncMock(side_effect=start_side_effect)
    instance.stop = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_failed_start_leaves_no_half_started_producer():
    kafka = fake_kafka(ConnectionError("Kafka down"))
    with patch("app.kafka.producer.AIOKafkaProducer", return_value=kafka):
        with pytest.raises(ConnectionError):
            await producer.start_producer()
    assert producer._producer is None
    kafka.stop.assert_awaited_once()  # the failed client is cleaned up
    with pytest.raises(RuntimeError):
        await producer.publish_event("order-placed", {})


@pytest.mark.asyncio
async def test_ensure_producer_starts_once_kafka_is_back():
    down, up = fake_kafka(ConnectionError("Kafka down")), fake_kafka()
    with patch("app.kafka.producer.AIOKafkaProducer", side_effect=[down, down, up]):
        assert await producer.ensure_producer() is False
        assert await producer.ensure_producer() is False
        assert await producer.ensure_producer() is True
    assert producer._producer is up
    assert await producer.ensure_producer() is True  # already running: no new client


@pytest.mark.asyncio
async def test_ensure_producer_logs_outage_once(caplog):
    with patch("app.kafka.producer.AIOKafkaProducer", side_effect=lambda **kw: fake_kafka(ConnectionError("down"))):
        for _ in range(5):
            await producer.ensure_producer()
    assert sum("Kafka unavailable" in r.message for r in caplog.records) == 1


@pytest.mark.asyncio
@patch("app.services.outbox_worker.asyncio.sleep", new_callable=AsyncMock)
@patch("app.services.outbox_worker._cleanup_old_events", new_callable=AsyncMock)
@patch("app.services.outbox_worker._process_pending_events", new_callable=AsyncMock)
@patch("app.services.outbox_worker.ensure_producer", new_callable=AsyncMock)
async def test_outbox_worker_waits_for_producer(mock_ensure, mock_process, mock_cleanup, mock_sleep):
    import asyncio
    from app.services.outbox_worker import start_outbox_worker
    mock_ensure.side_effect = [False, True]
    mock_sleep.side_effect = [None, asyncio.CancelledError()]
    with pytest.raises(asyncio.CancelledError):
        await start_outbox_worker()
    mock_process.assert_awaited_once()  # skipped while Kafka was down, ran once it was back
    assert mock_cleanup.await_count == 2
