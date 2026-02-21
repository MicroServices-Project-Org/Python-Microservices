import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from app.auth.keycloak import verify_token


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_mock_request(auth_header=None):
    request = MagicMock()
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header
    request.headers = headers
    return request


# ─── Auth Disabled ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.auth.keycloak.settings")
async def test_auth_disabled_returns_dev_user(mock_settings):
    mock_settings.AUTH_ENABLED = False
    request = make_mock_request()
    result = await verify_token(request)
    assert result["sub"] == "dev-user"
    assert result["email"] == "dev@example.com"
    assert "admin" in result["roles"]

@pytest.mark.asyncio
@patch("app.auth.keycloak.settings")
async def test_auth_disabled_ignores_auth_header(mock_settings):
    mock_settings.AUTH_ENABLED = False
    request = make_mock_request(auth_header="Bearer some-token")
    result = await verify_token(request)
    assert result["sub"] == "dev-user"


# ─── Auth Enabled — Missing/Invalid Header ──────────────────────────────────

@pytest.mark.asyncio
@patch("app.auth.keycloak.settings")
async def test_auth_enabled_missing_header_raises_401(mock_settings):
    mock_settings.AUTH_ENABLED = True
    request = make_mock_request()
    with pytest.raises(HTTPException) as exc:
        await verify_token(request)
    assert exc.value.status_code == 401
    assert "Missing" in exc.value.detail

@pytest.mark.asyncio
@patch("app.auth.keycloak.settings")
async def test_auth_enabled_no_bearer_prefix_raises_401(mock_settings):
    mock_settings.AUTH_ENABLED = True
    request = make_mock_request(auth_header="Token abc123")
    with pytest.raises(HTTPException) as exc:
        await verify_token(request)
    assert exc.value.status_code == 401
    assert "Missing" in exc.value.detail

@pytest.mark.asyncio
@patch("app.auth.keycloak.settings")
async def test_auth_enabled_empty_bearer_raises_401(mock_settings):
    mock_settings.AUTH_ENABLED = True
    request = make_mock_request(auth_header="Bearer ")
    with pytest.raises(HTTPException) as exc:
        await verify_token(request)
    assert exc.value.status_code == 401


# ─── Auth Enabled — Token Validation ────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.auth.keycloak._get_jwks_client")
@patch("app.auth.keycloak.jwt.decode")
@patch("app.auth.keycloak.settings")
async def test_auth_enabled_valid_token_returns_payload(mock_settings, mock_decode, mock_jwks):
    mock_settings.AUTH_ENABLED = True
    mock_settings.KEYCLOAK_CLIENT_ID = "api-gateway"
    mock_settings.KEYCLOAK_ISSUER = "http://localhost:8081/realms/microservices"

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="fake-key")
    mock_jwks.return_value = mock_jwks_client

    mock_decode.return_value = {"sub": "user-123", "email": "yash@example.com"}

    request = make_mock_request(auth_header="Bearer valid-token")
    result = await verify_token(request)
    assert result["sub"] == "user-123"
    assert result["email"] == "yash@example.com"

@pytest.mark.asyncio
@patch("app.auth.keycloak._get_jwks_client")
@patch("app.auth.keycloak.jwt.decode")
@patch("app.auth.keycloak.settings")
async def test_auth_enabled_expired_token_raises_403(mock_settings, mock_decode, mock_jwks):
    import jwt as pyjwt
    mock_settings.AUTH_ENABLED = True
    mock_settings.KEYCLOAK_CLIENT_ID = "api-gateway"
    mock_settings.KEYCLOAK_ISSUER = "http://localhost:8081/realms/microservices"

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="fake-key")
    mock_jwks.return_value = mock_jwks_client

    mock_decode.side_effect = pyjwt.ExpiredSignatureError("Token expired")

    request = make_mock_request(auth_header="Bearer expired-token")
    with pytest.raises(HTTPException) as exc:
        await verify_token(request)
    assert exc.value.status_code == 403
    assert "expired" in exc.value.detail.lower()

@pytest.mark.asyncio
@patch("app.auth.keycloak._get_jwks_client")
@patch("app.auth.keycloak.jwt.decode")
@patch("app.auth.keycloak.settings")
async def test_auth_enabled_invalid_audience_raises_401(mock_settings, mock_decode, mock_jwks):
    import jwt as pyjwt
    mock_settings.AUTH_ENABLED = True
    mock_settings.KEYCLOAK_CLIENT_ID = "api-gateway"
    mock_settings.KEYCLOAK_ISSUER = "http://localhost:8081/realms/microservices"

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="fake-key")
    mock_jwks.return_value = mock_jwks_client

    mock_decode.side_effect = pyjwt.InvalidAudienceError("Bad audience")

    request = make_mock_request(auth_header="Bearer bad-audience-token")
    with pytest.raises(HTTPException) as exc:
        await verify_token(request)
    assert exc.value.status_code == 401
    assert "audience" in exc.value.detail.lower()

@pytest.mark.asyncio
@patch("app.auth.keycloak._get_jwks_client")
@patch("app.auth.keycloak.jwt.decode")
@patch("app.auth.keycloak.settings")
async def test_auth_enabled_invalid_issuer_raises_401(mock_settings, mock_decode, mock_jwks):
    import jwt as pyjwt
    mock_settings.AUTH_ENABLED = True
    mock_settings.KEYCLOAK_CLIENT_ID = "api-gateway"
    mock_settings.KEYCLOAK_ISSUER = "http://localhost:8081/realms/microservices"

    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="fake-key")
    mock_jwks.return_value = mock_jwks_client

    mock_decode.side_effect = pyjwt.InvalidIssuerError("Bad issuer")

    request = make_mock_request(auth_header="Bearer bad-issuer-token")
    with pytest.raises(HTTPException) as exc:
        await verify_token(request)
    assert exc.value.status_code == 401
    assert "issuer" in exc.value.detail.lower()