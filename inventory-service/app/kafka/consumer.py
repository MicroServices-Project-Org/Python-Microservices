import asyncio
import logging
from aiokafka import AIOKafkaConsumer
from app.config import settings
from app.database import AsyncSessionLocal
from app.services.inventory_service import parse_cancelled_order, restock_cancelled_order

logger = logging.getLogger(__name__)

# Seconds to wait before reconnecting after the consumer fails (e.g. Kafka down at startup)
RETRY_SECONDS = 10


async def start_consumer():
    """
    Runs the order-cancelled consumer until the task is cancelled. If Kafka or the
    database is unavailable, it retries every RETRY_SECONDS instead of exiting.
    """
    while True:
        try:
            await _consume()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Inventory Kafka consumer failed, retrying in %ss: %s", RETRY_SECONDS, e)
        await asyncio.sleep(RETRY_SECONDS)


async def _consume():
    """
    Restocks every cancelled order. Offsets are committed only after the restock
    transaction commits, so a crash re-delivers the event instead of losing it
    (and processed_events makes the re-delivery a no-op). "earliest" so that events
    published while this service was down are still applied.
    """
    consumer = AIOKafkaConsumer(
        settings.KAFKA_ORDER_CANCELLED_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    try:
        await consumer.start()
        logger.info("Inventory Kafka consumer listening on: %s", settings.KAFKA_ORDER_CANCELLED_TOPIC)
        async for msg in consumer:
            await _handle_order_cancelled(msg.value)
            await consumer.commit()
    finally:
        await consumer.stop()


async def _handle_order_cancelled(raw: bytes):
    """
    Malformed events are logged and skipped (retrying can't fix them). Database
    errors propagate, so the event is retried rather than committed unapplied.
    """
    try:
        order_number, items = parse_cancelled_order(raw)
    except (TypeError, ValueError) as e:  # invalid JSON, or a tombstone (None value)
        logger.error("Skipping malformed order-cancelled event (%s): %.500r", e, raw)
        return

    async with AsyncSessionLocal() as db:
        async with db.begin():
            restocked = await restock_cancelled_order(order_number, items, db)
    if restocked is None:
        logger.info("Order %s already restocked, skipping duplicate event", order_number)
    else:
        logger.info("Restocked %d of %d item(s) from cancelled order %s", restocked, len(items), order_number)
