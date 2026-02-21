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
    SMTP_PASSWORD: str = ""  # Gmail App Password (not your login password)
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "FastAPI Store"

    # Feature flag — disable emails during development
    EMAIL_ENABLED: bool = False

    model_config = ConfigDict(env_file=".env")


settings = Settings()