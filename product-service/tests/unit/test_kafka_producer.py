import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.kafka.producer as producer


@pytest.fixture(autouse=True)
def reset_producer(monkeypatch):
    monkeypatch.setattr(producer, "_producer", None)


def fake_kafka(start_side_effect=None):
    instance = MagicMock()
    instance.start = AsyncMock(side_effect=start_side_effect)
    instance.stop = AsyncMock()
    instance.send_and_wait = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_start_producer_returns_false_when_kafka_down():
    kafka = fake_kafka(ConnectionError("Kafka down"))
    with patch("app.kafka.producer.AIOKafkaProducer", return_value=kafka):
        assert await producer.start_producer() is False  # doesn't raise, so startup continues
    assert producer._producer is None
    kafka.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_skipped_while_producer_not_started():
    await producer.publish_event("product-updated", {"event_type": "PRODUCT_CREATED"})  # no error


@pytest.mark.asyncio
@patch("app.kafka.producer.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_until_started(mock_sleep):
    up = fake_kafka()
    with patch("app.kafka.producer.AIOKafkaProducer", side_effect=[fake_kafka(ConnectionError()), fake_kafka(ConnectionError()), up]):
        await producer.retry_producer_until_started()
    assert producer._producer is up
    assert mock_sleep.await_count == 2
    await producer.publish_event("product-updated", {"event_type": "PRODUCT_CREATED"})
    up.send_and_wait.assert_awaited_once()
