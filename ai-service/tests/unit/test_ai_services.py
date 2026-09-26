import pytest
from unittest.mock import AsyncMock, patch


# ─── Helpers ─────────────────────────────────────────────────────────────────

MOCK_PRODUCTS = [
    {
        "id": "prod-001",
        "name": "iPhone 15 Pro",
        "price": 999.99,
        "category": "Electronics",
        "tags": ["smartphone", "apple"],
        "description": "Latest Apple smartphone",
    },
    {
        "id": "prod-002",
        "name": "AirPods Pro",
        "price": 249.99,
        "category": "Electronics",
        "tags": ["audio", "apple"],
        "description": "Wireless earbuds",
    },
]

MOCK_ORDER_EVENT = {
    "event_type": "ORDER_PLACED",
    "order_number": "ORD-20260221-38F5F24F",
    "customer_name": "Yash Vyas",
    "customer_email": "yash@example.com",
    "total_amount": 999.99,
    "items": [
        {
            "product_id": "prod-001",
            "product_name": "iPhone 15 Pro",
            "quantity": 1,
            "price": 999.99,
        }
    ],
}


# ─── chatbot ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.chatbot.llm_client")
@patch("app.services.chatbot.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_chat_returns_llm_response(mock_products, mock_llm):
    from app.services.chatbot import chat
    mock_llm.generate = AsyncMock(return_value="We have iPhones and AirPods!")
    result = await chat("What do you sell?")
    assert result == "We have iPhones and AirPods!"
    mock_llm.generate.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.chatbot.llm_client")
@patch("app.services.chatbot.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_chat_includes_product_context(mock_products, mock_llm):
    from app.services.chatbot import chat
    mock_llm.generate = AsyncMock(return_value="Sure!")
    await chat("Hi")
    call_args = mock_llm.generate.call_args
    assert "iPhone 15 Pro" in call_args.kwargs["system_prompt"]
    assert "AirPods Pro" in call_args.kwargs["system_prompt"]

@pytest.mark.asyncio
@patch("app.services.chatbot.llm_client")
@patch("app.services.chatbot.get_all_products", new_callable=AsyncMock, return_value=[])
async def test_chat_handles_empty_catalog(mock_products, mock_llm):
    from app.services.chatbot import chat
    mock_llm.generate = AsyncMock(return_value="No products available")
    result = await chat("What do you have?")
    assert result == "No products available"

@pytest.mark.asyncio
@patch("app.services.chatbot.llm_client")
@patch("app.services.chatbot.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_chat_passes_history(mock_products, mock_llm):
    from app.services.chatbot import chat
    mock_llm.generate = AsyncMock(return_value="Based on our conversation...")
    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    await chat("What else?", history=history)
    call_args = mock_llm.generate.call_args
    assert "Hi" in call_args.kwargs["prompt"]
    assert "Hello!" in call_args.kwargs["prompt"]
    assert "What else?" in call_args.kwargs["prompt"]

@pytest.mark.asyncio
@patch("app.services.chatbot.llm_client")
@patch("app.services.chatbot.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_chat_no_history(mock_products, mock_llm):
    from app.services.chatbot import chat
    mock_llm.generate = AsyncMock(return_value="Hi!")
    await chat("Hello")
    call_args = mock_llm.generate.call_args
    assert "user: Hello" in call_args.kwargs["prompt"]


# ─── recommendation ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_recommendations_returns_catalog_products(mock_products, mock_llm):
    from app.services.recommendation import get_recommendations
    mock_llm.generate = AsyncMock(return_value='{"recommendations": [{"name": "AirPods Pro", "reason": "Pairs well"}]}')
    result = await get_recommendations(product_name="iPhone", category="Electronics")
    assert result == [{
        "id": "prod-002", "name": "AirPods Pro", "price": 249.99,
        "category": "Electronics", "image_url": None, "reason": "Pairs well",
    }]

@pytest.mark.asyncio
@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_recommendations_drops_hallucinated_products(mock_products, mock_llm):
    from app.services.recommendation import get_recommendations
    mock_llm.generate = AsyncMock(return_value=(
        '{"recommendations": [{"name": "Galaxy S99", "reason": "Made up"},'
        ' {"name": "iphone 15 pro", "reason": "Real, different case"}]}'
    ))
    result = await get_recommendations(category="Electronics")
    assert [r["id"] for r in result] == ["prod-001"]

@pytest.mark.asyncio
@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_recommendations_invalid_llm_reply_raises_502(mock_products, mock_llm):
    from fastapi import HTTPException
    from app.services.recommendation import get_recommendations
    mock_llm.generate = AsyncMock(return_value="Sorry, the AI service is temporarily busy.")
    with pytest.raises(HTTPException) as exc:
        await get_recommendations(product_name="iPhone")
    assert exc.value.status_code == 502

@pytest.mark.asyncio
@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_recommendations_includes_product_name_in_prompt(mock_products, mock_llm):
    from app.services.recommendation import get_recommendations
    mock_llm.generate = AsyncMock(return_value='{"recommendations": []}')
    await get_recommendations(product_name="iPhone 15 Pro")
    call_args = mock_llm.generate.call_args
    assert "iPhone 15 Pro" in call_args.kwargs["prompt"]

@pytest.mark.asyncio
@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_recommendations_includes_category_in_prompt(mock_products, mock_llm):
    from app.services.recommendation import get_recommendations
    mock_llm.generate = AsyncMock(return_value='{"recommendations": []}')
    await get_recommendations(category="Electronics")
    call_args = mock_llm.generate.call_args
    assert "Electronics" in call_args.kwargs["prompt"]

@pytest.mark.asyncio
@patch("app.services.recommendation.llm_client")
@patch("app.services.recommendation.get_all_products", new_callable=AsyncMock, return_value=[])
async def test_recommendations_empty_catalog_skips_llm(mock_products, mock_llm):
    from app.services.recommendation import get_recommendations
    mock_llm.generate = AsyncMock()
    result = await get_recommendations()
    assert result == []
    mock_llm.generate.assert_not_called()


# ─── suggestion ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.suggestion.llm_client")
@patch("app.services.suggestion.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_suggest_returns_catalog_matches(mock_products, mock_llm):
    from app.services.suggestion import suggest_products
    mock_llm.generate = AsyncMock(return_value=(
        '{"matches": [{"name": "AirPods Pro", "price": 1.0, "match_reason": "Great gift"},'
        ' {"name": "Fake Watch", "match_reason": "Invented"}],'
        ' "search_tags": ["gift", 42], "search_category": "Electronics"}'
    ))
    result = await suggest_products("birthday gift")
    assert [m["id"] for m in result["matches"]] == ["prod-002"]
    assert result["matches"][0]["price"] == 249.99  # catalog price, not the LLM's
    assert result["matches"][0]["match_reason"] == "Great gift"
    assert result["search_tags"] == ["gift"]
    assert result["search_category"] == "Electronics"

@pytest.mark.asyncio
@patch("app.services.suggestion.llm_client")
@patch("app.services.suggestion.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_suggest_includes_query_in_prompt(mock_products, mock_llm):
    from app.services.suggestion import suggest_products
    mock_llm.generate = AsyncMock(return_value="{}")
    result = await suggest_products("warm jacket under $50")
    call_args = mock_llm.generate.call_args
    assert "warm jacket under $50" in call_args.kwargs["prompt"]
    assert result == {"matches": [], "search_tags": [], "search_category": None}

@pytest.mark.asyncio
@patch("app.services.suggestion.llm_client")
@patch("app.services.suggestion.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_suggest_invalid_llm_reply_raises_502(mock_products, mock_llm):
    from fastapi import HTTPException
    from app.services.suggestion import suggest_products
    mock_llm.generate = AsyncMock(return_value="not json at all")
    with pytest.raises(HTTPException) as exc:
        await suggest_products("anything")
    assert exc.value.status_code == 502

@pytest.mark.asyncio
@patch("app.services.suggestion.llm_client")
@patch("app.services.suggestion.get_all_products", new_callable=AsyncMock, return_value=[])
async def test_suggest_empty_catalog_skips_llm(mock_products, mock_llm):
    from app.services.suggestion import suggest_products
    mock_llm.generate = AsyncMock()
    result = await suggest_products("anything")
    assert result["matches"] == []
    mock_llm.generate.assert_not_called()


# ─── notification_ai ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.notification_ai.llm_client")
@patch("app.services.notification_ai.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_personalize_returns_subject_and_body(mock_products, mock_llm):
    from app.services.notification_ai import personalize_notification
    mock_llm.generate = AsyncMock(return_value='{"subject": "Thanks!", "body_html": "<p>Hi Yash</p>"}')
    result = await personalize_notification(MOCK_ORDER_EVENT)
    assert "subject" in result
    assert "body_html" in result
    assert result["subject"] == "Thanks!"
    assert "<p>Hi Yash</p>" in result["body_html"]

@pytest.mark.asyncio
@patch("app.services.notification_ai.llm_client")
@patch("app.services.notification_ai.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_personalize_includes_customer_in_prompt(mock_products, mock_llm):
    from app.services.notification_ai import personalize_notification
    mock_llm.generate = AsyncMock(return_value='{"subject": "Hi", "body_html": "<p>Hey</p>"}')
    await personalize_notification(MOCK_ORDER_EVENT)
    call_args = mock_llm.generate.call_args
    assert "Yash Vyas" in call_args.kwargs["prompt"]
    assert "iPhone 15 Pro" in call_args.kwargs["prompt"]

@pytest.mark.asyncio
@patch("app.services.notification_ai.llm_client")
@patch("app.services.notification_ai.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_personalize_handles_malformed_llm_response(mock_products, mock_llm):
    from app.services.notification_ai import personalize_notification
    mock_llm.generate = AsyncMock(return_value="This is not JSON")
    result = await personalize_notification(MOCK_ORDER_EVENT)
    assert "subject" in result
    assert "body_html" in result
    assert "ORD-20260221-38F5F24F" in result["subject"]

@pytest.mark.asyncio
@patch("app.services.notification_ai.llm_client")
@patch("app.services.notification_ai.get_all_products", new_callable=AsyncMock, return_value=MOCK_PRODUCTS)
async def test_personalize_handles_markdown_fenced_json(mock_products, mock_llm):
    from app.services.notification_ai import personalize_notification
    mock_llm.generate = AsyncMock(return_value='```json\n{"subject": "Thanks!", "body_html": "<p>Hi</p>"}\n```')
    result = await personalize_notification(MOCK_ORDER_EVENT)
    assert result["subject"] == "Thanks!"

@pytest.mark.asyncio
@patch("app.services.notification_ai.llm_client")
@patch("app.services.notification_ai.get_all_products", new_callable=AsyncMock, return_value=[])
async def test_personalize_handles_empty_catalog(mock_products, mock_llm):
    from app.services.notification_ai import personalize_notification
    mock_llm.generate = AsyncMock(return_value='{"subject": "Thanks!", "body_html": "<p>Hi</p>"}')
    result = await personalize_notification(MOCK_ORDER_EVENT)
    assert result["subject"] == "Thanks!"