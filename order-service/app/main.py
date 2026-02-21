from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database import engine, Base
from app.routes.order_routes import router as order_router
from app.kafka.producer import start_producer, stop_producer

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ Connected to PostgreSQL: {settings.POSTGRES_DB}")

    # Start Kafka producer
    try:
        await start_producer()
    except Exception as e:
        print(f"⚠️  Kafka unavailable — orders will work without events: {e}")

    yield

    await stop_producer()
    await engine.dispose()
    print("🔌 Order service shutdown complete")

app = FastAPI(
    title="Order Service",
    description="Manages customer orders",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(order_router, prefix="/api/orders", tags=["Orders"])

@app.get("/health")
async def health():
    return {"status": "UP", "service": settings.APP_NAME}