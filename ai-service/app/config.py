from pydantic_settings import BaseSettings, SettingsConfigDict


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
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

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

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()