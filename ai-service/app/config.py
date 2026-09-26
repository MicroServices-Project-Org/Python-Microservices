from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "ai-service"
    APP_PORT: int = 8005

    # LLM Provider — change this to swap providers
    # Options: "gemini", "groq", "ollama"
    LLM_PROVIDER: str = "groq"

    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile was retired by Groq

    # Ollama (local)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    # Product Service
    PRODUCT_SERVICE_URL: str = "http://localhost:8001"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_GROUP_ID: str = "ai-service-group"
    KAFKA_ORDER_PLACED_TOPIC: str = "order-placed"
    KAFKA_AI_NOTIFICATION_TOPIC: str = "ai-notification-ready"
    KAFKA_PRODUCT_UPDATED_TOPIC: str = "product-updated"  # any event invalidates the cache

    # Redis cache (cache-aside). DB 1 so it doesn't mix with notification's idempotency keys in DB 0
    CACHE_ENABLED: bool = True
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 1
    CACHE_CATALOG_TTL: int = 900    # 15 min
    CACHE_LLM_TTL: int = 21600      # 6 h: validated product IDs picked by the LLM

    model_config = ConfigDict(env_file=".env")


settings = Settings()