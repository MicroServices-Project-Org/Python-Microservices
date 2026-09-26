import json
import logging
from aiokafka import AIOKafkaProducer
from app.config import settings

logger = logging.getLogger(__name__)

# Global producer instance. Only set once start() has succeeded.
_producer: AIOKafkaProducer = None
_start_failing = False  # log a failed start once per outage, not every outbox poll


async def start_producer():
    """Start the producer. Raises if Kafka is unreachable (the outbox worker retries via ensure_producer)."""
    global _producer
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    try:
        await producer.start()
    except Exception:
        await producer.stop()
        raise
    _producer = producer
    print("✅ Kafka producer started")


async def ensure_producer() -> bool:
    """Start the producer if it isn't running. Returns True when it's ready to publish."""
    global _start_failing
    if _producer is not None:
        return True
    try:
        await start_producer()
    except Exception as e:
        if not _start_failing:
            logger.warning("Kafka unavailable, outbox events stay PENDING until it's back: %s", e)
        _start_failing = True
        return False
    if _start_failing:
        logger.info("Kafka reachable again, resuming outbox delivery")
    _start_failing = False
    return True


async def stop_producer():
    global _producer
    if _producer:
        await _producer.stop()
        print("🔌 Kafka producer stopped")


async def publish_event(topic: str, payload: dict):
    """
    Publish an event to a Kafka topic.
    Used by the outbox worker to deliver events.
    Raises exception on failure so the outbox worker can retry.
    """
    if not _producer:
        raise RuntimeError("Kafka producer not started")

    await _producer.send_and_wait(topic, value=payload)