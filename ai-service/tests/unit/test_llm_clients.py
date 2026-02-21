import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.llm.gemini_client import GeminiClient
from app.llm.groq_client import GroqClient
from app.llm.ollama_client import OllamaClient


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_gemini_response(text="Hello!"):
    return MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "candidates": [{"content": {"parts": [{"text": text}]}}]
        }),
    )

def make_groq_response(text="Hello!"):
    return MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "choices": [{"message": {"content": text}}]
        }),
    )

def make_ollama_response(text="Hello!"):
    return MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "message": {"content": text}
        }),
    )

def make_429_response():
    return MagicMock(status_code=429, text="Rate limited")

def make_500_response():
    return MagicMock(status_code=500, text="Internal Server Error")


# ─── GeminiClient ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.llm.gemini_client.httpx.AsyncClient")
async def test_gemini_generate_success(mock_client_class):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_gemini_response("Hi there!"))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = GeminiClient()
    result = await client.generate("Hello")
    assert result == "Hi there!"

@pytest.mark.asyncio
@patch("app.llm.gemini_client.httpx.AsyncClient")
async def test_gemini_generate_with_system_prompt(mock_client_class):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_gemini_response("I'm a shopping assistant"))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = GeminiClient()
    result = await client.generate("Hi", system_prompt="You are a shopping assistant")
    assert result == "I'm a shopping assistant"

@pytest.mark.asyncio
@patch("app.llm.gemini_client.httpx.AsyncClient")
async def test_gemini_500_returns_fallback(mock_client_class):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_500_response())
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = GeminiClient()
    result = await client.generate("Hello")
    assert "temporarily busy" in result

@pytest.mark.asyncio
@patch("app.llm.gemini_client.asyncio.sleep", new_callable=AsyncMock)
@patch("app.llm.gemini_client.httpx.AsyncClient")
async def test_gemini_429_retries_then_fallback(mock_client_class, mock_sleep):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_429_response())
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = GeminiClient()
    result = await client.generate("Hello")
    assert "temporarily busy" in result
    assert mock_sleep.call_count == 3  # 3 retries

@pytest.mark.asyncio
@patch("app.llm.gemini_client.httpx.AsyncClient")
async def test_gemini_malformed_response_returns_fallback(mock_client_class):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=MagicMock(
        status_code=200,
        json=MagicMock(return_value={"candidates": []}),
    ))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = GeminiClient()
    result = await client.generate("Hello")
    assert "temporarily busy" in result or "couldn't generate" in result


# ─── GroqClient ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.llm.groq_client.httpx.AsyncClient")
async def test_groq_generate_success(mock_client_class):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_groq_response("Hello from Llama!"))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = GroqClient()
    result = await client.generate("Hello")
    assert result == "Hello from Llama!"

@pytest.mark.asyncio
@patch("app.llm.groq_client.httpx.AsyncClient")
async def test_groq_generate_with_system_prompt(mock_client_class):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_groq_response("I'm an assistant"))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = GroqClient()
    result = await client.generate("Hi", system_prompt="You are helpful")
    assert result == "I'm an assistant"
    # Verify system prompt was included in request
    call_args = mock_client.post.call_args
    messages = call_args.kwargs["json"]["messages"]
    assert messages[0]["role"] == "system"

@pytest.mark.asyncio
@patch("app.llm.groq_client.httpx.AsyncClient")
async def test_groq_500_returns_fallback(mock_client_class):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_500_response())
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = GroqClient()
    result = await client.generate("Hello")
    assert "temporarily busy" in result

@pytest.mark.asyncio
@patch("app.llm.groq_client.asyncio.sleep", new_callable=AsyncMock)
@patch("app.llm.groq_client.httpx.AsyncClient")
async def test_groq_429_retries_then_fallback(mock_client_class, mock_sleep):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_429_response())
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = GroqClient()
    result = await client.generate("Hello")
    assert "temporarily busy" in result
    assert mock_sleep.call_count == 3


# ─── OllamaClient ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.llm.ollama_client.httpx.AsyncClient")
async def test_ollama_generate_success(mock_client_class):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_ollama_response("Local Llama says hi!"))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = OllamaClient()
    result = await client.generate("Hello")
    assert result == "Local Llama says hi!"

@pytest.mark.asyncio
@patch("app.llm.ollama_client.httpx.AsyncClient")
async def test_ollama_500_returns_fallback(mock_client_class):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=make_500_response())
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = OllamaClient()
    result = await client.generate("Hello")
    assert "could not generate" in result.lower() or "temporarily busy" in result.lower()

@pytest.mark.asyncio
@patch("app.llm.ollama_client.httpx.AsyncClient")
async def test_ollama_connection_refused_returns_fallback(mock_client_class):
    import httpx
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = OllamaClient()
    result = await client.generate("Hello")
    assert "ollama" in result.lower() or "could not generate" in result.lower()

@pytest.mark.asyncio
@patch("app.llm.ollama_client.httpx.AsyncClient")
async def test_ollama_timeout_returns_fallback(mock_client_class):
    import httpx
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ReadTimeout("Timeout"))
    mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

    client = OllamaClient()
    result = await client.generate("Hello")
    assert "timed out" in result.lower() or "could not generate" in result.lower()