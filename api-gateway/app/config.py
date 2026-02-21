from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "api-gateway"
    APP_PORT: int = 9000

    # Downstream service URLs
    PRODUCT_SERVICE_URL: str = "http://localhost:8001"
    ORDER_SERVICE_URL: str = "http://localhost:8002"
    INVENTORY_SERVICE_URL: str = "http://localhost:8003"
    AI_SERVICE_URL: str = "http://localhost:8005"

    # Keycloak
    KEYCLOAK_URL: str = "http://localhost:8081"
    KEYCLOAK_REALM: str = "microservices"
    KEYCLOAK_CLIENT_ID: str = "api-gateway"

    # Rate limiting
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_AI: str = "15/minute"

    # Auth feature flag — disable during development
    AUTH_ENABLED: bool = False

    @property
    def KEYCLOAK_JWKS_URL(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"

    @property
    def KEYCLOAK_ISSUER(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"

    model_config = ConfigDict(env_file=".env")


settings = Settings()