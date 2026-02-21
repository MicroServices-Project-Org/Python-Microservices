import json
import asyncio
from aiokafka import AIOKafkaConsumer
from app.config import settings
from app.services.notification_ai import personalize_notification
from app.kafka.producer import publish_ai_notification


async def start_consumer():
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

    except Exception as e:
        print(f"❌ AI Kafka consumer error: {e}")
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