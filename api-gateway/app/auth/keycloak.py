import httpx
import jwt
from jwt import PyJWKClient
from fastapi import Request, HTTPException, status
from app.config import settings

# Cache the JWKS client — avoids fetching keys on every request
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Lazy-initialize the JWKS client (fetches Keycloak's public keys)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.KEYCLOAK_JWKS_URL)
    return _jwks_client


async def verify_token(request: Request) -> dict:
    """
    FastAPI dependency that validates the JWT from the Authorization header.
    Returns the decoded token payload if valid.
    Raises 401 if missing/invalid, 403 if expired.

    When AUTH_ENABLED=False, returns a dummy payload (development mode).
    """
    if not settings.AUTH_ENABLED:
        return {"sub": "dev-user", "email": "dev@example.com", "roles": ["admin"]}

    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ", 1)[1]

    try:
        # Get the signing key from Keycloak's JWKS endpoint
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and validate the JWT
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
            issuer=settings.KEYCLOAK_ISSUER,
            options={"verify_exp": True},
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token has expired",
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
        )
    except jwt.PyJWKClientError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate token: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )