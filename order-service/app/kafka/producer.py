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

async def publish_order_placed(order_data: dict):
    """Publish order-placed event to Kafka."""
    if not _producer:
        print("⚠️  Kafka producer not started — skipping event publish")
        return
    try:
        await _producer.send_and_wait(
            settings.KAFKA_ORDER_TOPIC,
            value=order_data
        )
        print(f"📨 Published order-placed event: {order_data['order_number']}")
    except Exception as e:
        # Log but don't fail the order — Kafka is non-critical path
        print(f"❌ Failed to publish Kafka event: {e}")