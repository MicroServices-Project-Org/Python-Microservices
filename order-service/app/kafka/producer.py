import json
from aiokafka import AIOKafkaProducer
from app.config import settings

# Global producer instance
_producer: AIOKafkaProducer = None


async def start_producer():
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await _producer.start()
    print("✅ Kafka producer started")


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