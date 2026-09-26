import json
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from app.models.outbox import Outbox, OutboxStatus
from app.kafka.producer import publish_event, ensure_producer
from app.config import settings


async def start_outbox_worker():
    """
    Background worker that polls the outbox table for PENDING events,
    publishes them to Kafka, and marks them as SENT.
    Runs in a loop with a configurable poll interval.
    """
    print(f"📤 Outbox worker started — polling every {settings.OUTBOX_POLL_INTERVAL_SECONDS}s")

    while True:
        try:
            # If Kafka was down at startup (or the producer never started), start it here,
            # so PENDING events are delivered once Kafka is back without a service restart
            if await ensure_producer():
                await _process_pending_events()
            await _cleanup_old_events()
        except Exception as e:
            print(f"❌ Outbox worker error: {e}")

        await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL_SECONDS)


async def _process_pending_events():
    """Read PENDING events from outbox and publish to Kafka."""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Outbox)
                .where(Outbox.status == OutboxStatus.PENDING)
                .order_by(Outbox.created_at.asc())
                .limit(50)  # Process in batches
            )
            events = list(result.scalars().all())

            if not events:
                return

            for event in events:
                try:
                    payload = json.loads(event.event_payload)
                    await publish_event(event.topic, payload)

                    # Mark as SENT
                    event.status = OutboxStatus.SENT
                    event.sent_at = datetime.now(timezone.utc)
                    print(f"📨 Outbox delivered: {event.topic} — {payload.get('order_number', 'N/A')}")

                except Exception as e:
                    print(f"⚠️ Failed to publish outbox event {event.id}: {e}")
                    # Event stays PENDING — will be retried next cycle

            await db.commit()

        except Exception as e:
            await db.rollback()
            print(f"❌ Outbox processing error: {e}")


async def _cleanup_old_events():
    """Delete SENT events older than the retention period."""
    async with AsyncSessionLocal() as db:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=settings.OUTBOX_RETENTION_DAYS)
            result = await db.execute(
                delete(Outbox)
                .where(Outbox.status == OutboxStatus.SENT)
                .where(Outbox.sent_at < cutoff)
            )
            deleted = result.rowcount
            if deleted > 0:
                await db.commit()
                print(f"🧹 Outbox cleanup: deleted {deleted} old events")
        except Exception as e:
            await db.rollback()
            print(f"❌ Outbox cleanup error: {e}")