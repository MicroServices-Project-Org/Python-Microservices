import json
from aiokafka import AIOKafkaProducer
from app.config import settings


async def publish_ai_notification(event: dict):
    """
    Publish personalized email content to ai-notification-ready topic.
    The Notification Service consumes this and sends the email.
    Non-critical — failure is logged, not raised.
    """
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    try:
        await producer.start()
        await producer.send_and_wait(
            settings.KAFKA_AI_NOTIFICATION_TOPIC,
            value=event,
        )
        print(f"✅ Published ai-notification-ready for {event.get('order_number')}")
    except Exception as e:
        print(f"❌ Failed to publish ai-notification: {e}")
    finally:
        await producer.stop()