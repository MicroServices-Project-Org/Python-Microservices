import asyncio
import logging

from aiokafka import AIOKafkaConsumer

from app.cache import redis_cache
from app.config import settings

logger = logging.getLogger(__name__)

RETRY_SECONDS = 10


async def start_cache_invalidator():
    """
    Invalidates the AI cache on every product-updated event (create/update/delete).
    Separate from the order-placed consumer so its per-message LLM throttle
    doesn't delay invalidation. Its own group so it gets every event; "latest"
    because events from before startup don't matter to a cache.
    """
    while True:
        consumer = AIOKafkaConsumer(
            settings.KAFKA_PRODUCT_UPDATED_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=f"{settings.KAFKA_GROUP_ID}-cache",
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        try:
            await consumer.start()
            logger.info("AI cache invalidator listening on: %s", settings.KAFKA_PRODUCT_UPDATED_TOPIC)
            async for _ in consumer:
                await redis_cache.invalidate()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("AI cache invalidator error, retrying in %ss: %s", RETRY_SECONDS, e)
        finally:
            await consumer.stop()
        await asyncio.sleep(RETRY_SECONDS)
