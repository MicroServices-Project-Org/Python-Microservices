import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


REC = {"id": "p1", "name": "AirPods Pro", "price": 249.99, "category": "Electronics", "image_url": None, "reason": "r"}


@patch("app.routes.ai_routes.recommendation.get_recommendations", new_callable=AsyncMock, return_value=[REC])
async def test_recommendations_route_returns_structured_list(mock_rec, client):
    resp = await client.get("/api/ai/recommendations", params={"product_name": "iPhone"})
    assert resp.status_code == 200
    assert resp.json() == {"recommendations": [REC]}
    mock_rec.assert_awaited_once_with("iPhone", "")


@patch("app.routes.ai_routes.suggestion.suggest_products", new_callable=AsyncMock, return_value={
    "matches": [{**{k: v for k, v in REC.items() if k != "reason"}, "match_reason": "gift"}],
    "search_tags": ["gift"], "search_category": "Electronics",
})
async def test_suggest_route_returns_structured_result(mock_suggest, client):
    resp = await client.post("/api/ai/suggest", json={"query": "gift"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["matches"][0]["id"] == "p1"
    assert body["matches"][0]["match_reason"] == "gift"
    assert body["search_tags"] == ["gift"]
    assert "result" not in body


@patch("app.routes.ai_routes.suggestion.suggest_products", new_callable=AsyncMock,
       side_effect=HTTPException(status_code=502, detail="AI service returned an invalid response. Please try again."))
async def test_suggest_route_invalid_llm_reply_is_502(mock_suggest, client):
    resp = await client.post("/api/ai/suggest", json={"query": "gift"})
    assert resp.status_code == 502
