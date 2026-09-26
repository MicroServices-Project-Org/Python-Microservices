from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "api-gateway"
    APP_PORT: int = 9000

    # Downstream service URLs
    PRODUCT_SERVICE_URL: str = "http://localhost:8001"
    ORDER_SERVICE_URL: str = "http://localhost:8002"
    INVENTORY_SERVICE_URL: str = "http://localhost:8003"
    AI_SERVICE_URL: str = "http://localhost:8005"
    SEARCH_SERVICE_URL: str = "http://localhost:8006"

    # Keycloak
    KEYCLOAK_URL: str = "http://localhost:8081"
    KEYCLOAK_REALM: str = "microservices"
    KEYCLOAK_CLIENT_ID: str = "api-gateway"
    # Where the gateway fetches signing keys, if different from KEYCLOAK_URL.
    # In Docker the gateway reaches Keycloak at http://keycloak:8080, but tokens
    # are issued via http://localhost:8081, so KEYCLOAK_URL must stay the public
    # URL (it's checked against the token's `iss`).
    KEYCLOAK_INTERNAL_URL: str = ""

    # Rate limiting
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_AI: str = "15/minute"

    # Auth feature flag — disable during development
    AUTH_ENABLED: bool = False

    @property
    def KEYCLOAK_JWKS_URL(self) -> str:
        base = self.KEYCLOAK_INTERNAL_URL or self.KEYCLOAK_URL
        return f"{base}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"

    @property
    def KEYCLOAK_ISSUER(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()