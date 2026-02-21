from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import connect_db, close_db
from app.routes.product_routes import router as product_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()

app = FastAPI(title="Product Service", version="1.0.0", lifespan=lifespan)

app.include_router(product_router, prefix="/api/products", tags=["Products"])

@app.get("/health")
async def health():
    return {"status": "UP", "service": "product-service"}