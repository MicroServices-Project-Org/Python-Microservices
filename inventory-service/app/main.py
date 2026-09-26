import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database import engine, Base
from app.routes.inventory_routes import router as inventory_router
from app.kafka.consumer import start_consumer
from prometheus_fastapi_instrumentator import Instrumentator
from app.logging_config import setup_logging
from app.tracing_config import setup_tracing

setup_logging("inventory-service")

# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ Connected to PostgreSQL: {settings.POSTGRES_DB}")
    # Restocks cancelled orders; retries on its own while Kafka is down
    consumer_task = asyncio.create_task(start_consumer())
    yield
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()
    print("🔌 PostgreSQL connection closed")

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Inventory Service",
    description="Manages product stock levels",
    version="1.0.0",
    lifespan=lifespan
)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

setup_tracing("inventory-service", app)

app.include_router(inventory_router, prefix="/api/inventory", tags=["Inventory"])

@app.get("/health")
async def health():
    return {"status": "UP", "service": settings.APP_NAME}