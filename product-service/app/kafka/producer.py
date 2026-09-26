import asyncio
import json
import logging
from typing import Optional
from aiokafka import AIOKafkaProducer
from app.config import settings

logger = logging.getLogger(__name__)

_producer: Optional[AIOKafkaProducer] = None

# Seconds between start attempts while Kafka is unreachable
RETRY_SECONDS = 10


async def start_producer() -> bool:
    """
    Try to start the producer once. Returns False instead of raising if Kafka is
    unreachable, so the service still starts (product writes never depend on Kafka).
    """
    global _producer
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
    )
    try:
        await producer.start()
    except Exception as e:
        await producer.stop()
        logger.warning(f"Kafka unavailable, product events are skipped until it's back: {e}")
        return False
    _producer = producer
    logger.info("✅ Product Service Kafka producer started")
    return True


async def retry_producer_until_started():
    """Background task: keep trying to start the producer until it succeeds."""
    while not await start_producer():
        await asyncio.sleep(RETRY_SECONDS)


async def stop_producer():
    global _producer
    if _producer:
        await _producer.stop()
        logger.info("🔌 Product Service Kafka producer stopped")


async def publish_event(topic: str, payload: dict):
    """
    Fire-and-forget event publish.
    Logs and swallows failures so product writes never fail because of Kafka.
    The reconciliation job in Search Service is the safety net.
    """
    if not _producer:
        logger.warning("Kafka producer not started — skipping event publish")
        return

    try:
        await _producer.send_and_wait(topic, value=payload)
        logger.info(f"📤 Published to '{topic}': {payload.get('event_type')} for product {payload.get('product_id')}")
    except Exception as e:
        logger.error(f"❌ Failed to publish to '{topic}': {e}")