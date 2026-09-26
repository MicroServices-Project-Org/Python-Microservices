from unittest.mock import patch

from app import database


@patch("app.database.AsyncIOMotorClient")
async def test_connect_without_auth_by_default(mock_client):
    with patch.object(database.settings, "MONGO_USERNAME", ""):
        await database.connect_db()
    kwargs = mock_client.call_args.kwargs
    assert "username" not in kwargs and "password" not in kwargs


@patch("app.database.AsyncIOMotorClient")
async def test_connect_with_auth_when_username_set(mock_client):
    with patch.object(database.settings, "MONGO_USERNAME", "admin"), \
         patch.object(database.settings, "MONGO_PASSWORD", "secret"):
        await database.connect_db()
    kwargs = mock_client.call_args.kwargs
    assert kwargs["username"] == "admin"
    assert kwargs["password"] == "secret"
    assert kwargs["authSource"] == "admin"
