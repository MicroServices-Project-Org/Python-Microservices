import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import connect_db, close_db
from app.routes.product_routes import router as product_router
from app.kafka.producer import start_producer, stop_producer, retry_producer_until_started
from prometheus_fastapi_instrumentator import Instrumentator
from app.logging_config import setup_logging
from app.tracing_config import setup_tracing

setup_logging("product-service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    # Don't fail startup if Kafka is down: publish_event skips events until the producer
    # starts, and Search Service's reconcile job repairs anything missed
    retry_task = None
    if not await start_producer():
        retry_task = asyncio.create_task(retry_producer_until_started())
    yield
    if retry_task:
        retry_task.cancel()
    await stop_producer()
    await close_db()

app = FastAPI(title="Product Service", version="1.0.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

setup_tracing("product-service", app)

app.include_router(product_router, prefix="/api/products", tags=["Products"])

@app.get("/health")
async def health():
    return {"status": "UP", "service": "product-service"}