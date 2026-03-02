from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "notification-service"
    APP_PORT: int = 8004

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_GROUP_ID: str = "notification-group"
    KAFKA_ORDER_PLACED_TOPIC: str = "order-placed"
    KAFKA_ORDER_CANCELLED_TOPIC: str = "order-cancelled"
    KAFKA_INVENTORY_LOW_TOPIC: str = "inventory-low"
    KAFKA_AI_NOTIFICATION_READY_TOPIC: str = "ai-notification-ready"

    # Gmail SMTP
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "FastAPI Store"

    # Feature flags
    EMAIL_ENABLED: bool = False

    # Redis — idempotency
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_IDEMPOTENCY_TTL: int = 604800  # 7 days in seconds

    model_config = ConfigDict(env_file=".env")


settings = Settings()