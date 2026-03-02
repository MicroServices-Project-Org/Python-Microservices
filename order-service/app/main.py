import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database import engine, Base
from app.routes.order_routes import router as order_router
from app.kafka.producer import start_producer, stop_producer
from app.services.outbox_worker import start_outbox_worker


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (including outbox)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ Connected to PostgreSQL: {settings.POSTGRES_DB}")

    # Start Kafka producer
    try:
        await start_producer()
    except Exception as e:
        print(f"⚠️  Kafka unavailable — outbox worker will retry when Kafka is back: {e}")

    # Start outbox worker as background task
    outbox_task = asyncio.create_task(start_outbox_worker())

    yield

    # Shutdown
    outbox_task.cancel()
    try:
        await outbox_task
    except asyncio.CancelledError:
        pass
    await stop_producer()
    await engine.dispose()
    print("🔌 Order service shutdown complete")

app = FastAPI(
    title="Order Service",
    description="Manages customer orders with guaranteed event delivery via outbox pattern",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(order_router, prefix="/api/orders", tags=["Orders"])


@app.get("/health")
async def health():
    return {"status": "UP", "service": settings.APP_NAME}