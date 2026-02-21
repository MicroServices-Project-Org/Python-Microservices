from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "order-service"
    APP_PORT: int = 8002

    # PostgreSQL
    POSTGRES_USER: str = "admin"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "order_db"

    # Inventory Service
    INVENTORY_SERVICE_URL: str = "http://localhost:8003"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ORDER_TOPIC: str = "order-placed"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = ConfigDict(env_file=".env")

settings = Settings()