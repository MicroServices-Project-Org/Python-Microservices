from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.database import engine, Base
from app.routes.inventory_routes import router as inventory_router

# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ Connected to PostgreSQL: {settings.POSTGRES_DB}")
    yield
    await engine.dispose()
    print("🔌 PostgreSQL connection closed")

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Inventory Service",
    description="Manages product stock levels",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(inventory_router, prefix="/api/inventory", tags=["Inventory"])

@app.get("/health")
async def health():
    return {"status": "UP", "service": settings.APP_NAME}