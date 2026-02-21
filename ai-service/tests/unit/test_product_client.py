import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.clients.product_client import get_all_products, search_products, format_products_for_context


# ─── get_all_products ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.clients.product_client.httpx.AsyncClient")
async def test_get_all_products_list_response(mock_client_class):
    products = [{"name": "iPhone", "price": 999}]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value=products),
        raise_for_status=MagicMock(),
    ))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await get_all_products()
    assert result == products

@pytest.mark.asyncio
@patch("app.clients.product_client.httpx.AsyncClient")
async def test_get_all_products_dict_with_products_key(mock_client_class):
    data = {"products": [{"name": "iPhone"}], "total": 1}
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value=data),
        raise_for_status=MagicMock(),
    ))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await get_all_products()
    assert result == [{"name": "iPhone"}]

@pytest.mark.asyncio
@patch("app.clients.product_client.httpx.AsyncClient")
async def test_get_all_products_connection_error_returns_empty(mock_client_class):
    import httpx
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await get_all_products()
    assert result == []


# ─── search_products ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.clients.product_client.httpx.AsyncClient")
async def test_search_products_list_response(mock_client_class):
    products = [{"name": "iPhone", "price": 999}]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value=products),
        raise_for_status=MagicMock(),
    ))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await search_products("iPhone")
    assert result == products

@pytest.mark.asyncio
@patch("app.clients.product_client.httpx.AsyncClient")
async def test_search_products_error_returns_empty(mock_client_class):
    import httpx
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await search_products("iPhone")
    assert result == []


# ─── format_products_for_context ─────────────────────────────────────────────

def test_format_empty_list():
    result = format_products_for_context([])
    assert "No products available" in result

def test_format_single_product():
    products = [{"name": "iPhone 15 Pro", "price": 999.99, "category": "Electronics", "tags": ["smartphone"]}]
    result = format_products_for_context(products)
    assert "iPhone 15 Pro" in result
    assert "$999.99" in result
    assert "Electronics" in result
    assert "smartphone" in result

def test_format_product_without_tags():
    products = [{"name": "Widget", "price": 10, "category": "Other"}]
    result = format_products_for_context(products)
    assert "Widget" in result
    assert "Other" in result

def test_format_product_with_description():
    products = [{"name": "iPhone", "price": 999, "category": "Electronics", "tags": [], "description": "Latest phone"}]
    result = format_products_for_context(products)
    assert "Latest phone" in result

def test_format_limits_to_50_products():
    products = [{"name": f"Product {i}", "price": i, "category": "Test", "tags": []} for i in range(100)]
    result = format_products_for_context(products)
    assert "Product 49" in result
    assert "Product 50" not in result

def test_format_handles_missing_fields():
    products = [{}]
    result = format_products_for_context(products)
    assert "Unknown" in result

def test_format_handles_product_name_key():
    products = [{"product_name": "Widget", "price": 5, "category": "Other", "tags": []}]
    result = format_products_for_context(products)
    assert "Widget" in result