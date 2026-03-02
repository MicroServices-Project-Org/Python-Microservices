import json
import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer
from app.config import settings
from app.services.email_service import (
    send_email,
    build_order_confirmation_email,
    build_order_cancelled_email,
    build_inventory_low_email,
)

# Redis client for idempotency checks
_redis: redis.Redis | None = None


async def _get_redis() -> redis.Redis:
    """Lazy-initialize the Redis client."""
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
    return _redis


async def _is_duplicate(event_key: str) -> bool:
    """
    Check if this event has already been processed.
    Uses Redis SET NX (set if not exists) with TTL.
    Returns True if duplicate (already processed), False if new.
    """
    try:
        r = await _get_redis()
        # SET NX returns True if key was set (new event), False if already exists (duplicate)
        is_new = await r.set(
            f"processed:{event_key}",
            "1",
            nx=True,
            ex=settings.REDIS_IDEMPOTENCY_TTL,
        )
        return not is_new  # If not new → it's a duplicate
    except Exception as e:
        print(f"⚠️ Redis error (proceeding without idempotency check): {e}")
        return False  # If Redis is down, process the event anyway


async def start_consumer():
    """
    Starts the Kafka consumer, subscribes to all 4 topics,
    and routes each event to the appropriate handler.
    """
    consumer = AIOKafkaConsumer(
        settings.KAFKA_ORDER_PLACED_TOPIC,
        settings.KAFKA_ORDER_CANCELLED_TOPIC,
        settings.KAFKA_INVENTORY_LOW_TOPIC,
        settings.KAFKA_AI_NOTIFICATION_READY_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_GROUP_ID,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    try:
        await consumer.start()
        print(
            f"📡 Kafka consumer listening on: "
            f"{settings.KAFKA_ORDER_PLACED_TOPIC}, "
            f"{settings.KAFKA_ORDER_CANCELLED_TOPIC}, "
            f"{settings.KAFKA_INVENTORY_LOW_TOPIC}, "
            f"{settings.KAFKA_AI_NOTIFICATION_READY_TOPIC}"
        )

        async for msg in consumer:
            try:
                await _handle_message(msg.topic, msg.value)
            except Exception as e:
                print(f"❌ Error processing message from {msg.topic}: {e}")

    except Exception as e:
        print(f"❌ Kafka consumer error: {e}")
    finally:
        await consumer.stop()
        # Close Redis connection
        if _redis:
            await _redis.aclose()


async def _handle_message(topic: str, event: dict):
    """Routes Kafka messages to the correct handler based on topic."""

    if topic == settings.KAFKA_ORDER_PLACED_TOPIC:
        await _handle_order_placed(event)

    elif topic == settings.KAFKA_ORDER_CANCELLED_TOPIC:
        await _handle_order_cancelled(event)

    elif topic == settings.KAFKA_INVENTORY_LOW_TOPIC:
        await _handle_inventory_low(event)

    elif topic == settings.KAFKA_AI_NOTIFICATION_READY_TOPIC:
        await _handle_ai_notification(event)

    else:
        print(f"⚠️ Unknown topic: {topic}")


async def _handle_order_placed(event: dict):
    """Handles order-placed events — sends confirmation email."""
    event_key = f"{event.get('order_number')}_ORDER_PLACED"

    if await _is_duplicate(event_key):
        print(f"⚠️ Duplicate skipped: {event_key}")
        return

    print(f"📦 Processing order-placed: {event.get('order_number')}")
    subject, body = build_order_confirmation_email(event)
    await send_email(event["customer_email"], subject, body)


async def _handle_order_cancelled(event: dict):
    """Handles order-cancelled events — sends cancellation email."""
    event_key = f"{event.get('order_number')}_ORDER_CANCELLED"

    if await _is_duplicate(event_key):
        print(f"⚠️ Duplicate skipped: {event_key}")
        return

    print(f"🚫 Processing order-cancelled: {event.get('order_number')}")
    subject, body = build_order_cancelled_email(event)
    await send_email(event["customer_email"], subject, body)


async def _handle_inventory_low(event: dict):
    """Handles inventory-low events — sends alert to admin."""
    event_key = f"{event.get('product_id')}_INVENTORY_LOW"

    if await _is_duplicate(event_key):
        print(f"⚠️ Duplicate skipped: {event_key}")
        return

    print(f"⚠️ Processing inventory-low: {event.get('product_id')}")
    subject, body = build_inventory_low_email(event)
    admin_email = settings.SMTP_FROM_EMAIL or "admin@example.com"
    await send_email(admin_email, subject, body)


async def _handle_ai_notification(event: dict):
    """
    Handles ai-notification-ready events.
    The AI Service generates a personalized email body and sends it here.
    """
    event_key = f"{event.get('order_number')}_AI_NOTIFICATION"

    if await _is_duplicate(event_key):
        print(f"⚠️ Duplicate skipped: {event_key}")
        return

    print(f"🤖 Processing ai-notification: {event.get('order_number')}")
    subject = event.get("subject", f"A message about your order {event.get('order_number', '')}")
    body = event.get("body_html", "<p>Thank you for your order!</p>")
    to_email = event.get("customer_email")

    if not to_email:
        print("❌ ai-notification-ready event missing customer_email")
        return

    await send_email(to_email, subject, body)