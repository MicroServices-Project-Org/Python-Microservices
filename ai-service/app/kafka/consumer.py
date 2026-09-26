import json
import asyncio
import logging
from aiokafka import AIOKafkaConsumer
from app.config import settings
from app.services.notification_ai import personalize_notification
from app.kafka.producer import publish_ai_notification

logger = logging.getLogger(__name__)

# Seconds to wait before reconnecting after the consumer fails (e.g. Kafka down at startup)
RETRY_SECONDS = 10


async def start_consumer():
    """
    Runs the order-placed consumer until the task is cancelled. If Kafka is
    unreachable (at startup or later), it retries every RETRY_SECONDS instead of
    exiting, so the service recovers on its own when Kafka comes back.
    """
    while True:
        try:
            await _consume()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("AI Kafka consumer failed, retrying in %ss: %s", RETRY_SECONDS, e)
        await asyncio.sleep(RETRY_SECONDS)


async def _consume():
    """
    Consumes order-placed events, generates personalized email content
    via LLM, and publishes the result to ai-notification-ready topic.
    """
    consumer = AIOKafkaConsumer(
        settings.KAFKA_ORDER_PLACED_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_GROUP_ID,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    try:
        await consumer.start()
        print(f"📡 AI Kafka consumer listening on: {settings.KAFKA_ORDER_PLACED_TOPIC}")

        async for msg in consumer:
            try:
                await _handle_order_placed(msg.value)
                # Rate limit: pause between messages to respect Gemini free tier (15 RPM)
                await asyncio.sleep(5)
            except Exception as e:
                print(f"❌ Error processing order-placed event: {e}")
    finally:
        await consumer.stop()


async def _handle_order_placed(event: dict):
    """
    Generates personalized notification content and publishes it
    to ai-notification-ready for the Notification Service to send.
    """
    print(f"🤖 Personalizing notification for order: {event.get('order_number')}")

    personalized = await personalize_notification(event)

    # Build the event for Notification Service
    notification_event = {
        "order_number": event.get("order_number"),
        "customer_email": event.get("customer_email"),
        "customer_name": event.get("customer_name"),
        "subject": personalized["subject"],
        "body_html": personalized["body_html"],
    }

    await publish_ai_notification(notification_event)