import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.routes.ai_routes import router as ai_router
from app.kafka.consumer import start_consumer
from app.kafka.cache_invalidator import start_cache_invalidator
from app.cache import redis_cache
from prometheus_fastapi_instrumentator import Instrumentator
from app.logging_config import setup_logging
from app.tracing_config import setup_tracing

setup_logging("ai-service")

# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer_task = asyncio.create_task(start_consumer())
    invalidator_task = asyncio.create_task(start_cache_invalidator())
    print(f"✅ {settings.APP_NAME} started — LLM provider: {settings.LLM_PROVIDER}")
    print(f"📡 Kafka consumer background task started")

    yield

    for task in (consumer_task, invalidator_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await redis_cache.close()
    print("🔌 AI Service shut down")


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Service",
    description="AI-powered shopping assistant, recommendations, smart search, and notification personalization",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

setup_tracing("ai-service", app)

app.include_router(ai_router, prefix="/api/ai", tags=["AI"])


@app.get("/health")
async def health():
    return {
        "status": "UP",
        "service": settings.APP_NAME,
        "llm_provider": settings.LLM_PROVIDER,
    }