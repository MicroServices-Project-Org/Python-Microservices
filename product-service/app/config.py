from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "product-service"
    APP_PORT: int = 8001
    MONGO_HOST: str = "127.0.0.1"
    MONGO_PORT: int = 27017
    # Leave empty to connect without auth. docker-compose sets the root user
    # (the mongodb container requires auth).
    MONGO_USERNAME: str = ""
    MONGO_PASSWORD: str = ""
    DB_NAME: str = "product_db"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_PRODUCT_TOPIC: str = "product-updated"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
