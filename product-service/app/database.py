from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

class Database:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

db_instance = Database()

async def connect_db():
    auth = {}
    if settings.MONGO_USERNAME:
        auth = {"username": settings.MONGO_USERNAME, "password": settings.MONGO_PASSWORD, "authSource": "admin"}
    db_instance.client = AsyncIOMotorClient(
        host=settings.MONGO_HOST,
        port=settings.MONGO_PORT,
        **auth,
    )
    db_instance.db = db_instance.client[settings.DB_NAME]
    print(f"✅ Connected to MongoDB: {settings.DB_NAME}")

async def close_db():
    if db_instance.client:
        db_instance.client.close()
        print("🔌 MongoDB connection closed")

def get_db() -> AsyncIOMotorDatabase:
    return db_instance.db
