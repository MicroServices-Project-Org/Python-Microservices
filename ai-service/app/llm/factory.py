from app.llm.base import LLMClient
from app.llm.gemini_client import GeminiClient
from app.config import settings
from app.llm.groq_client import GroqClient
from app.llm.ollama_client import OllamaClient


def get_llm_client() -> LLMClient:
    """
    Factory function that returns the configured LLM client.
    To swap providers, change LLM_PROVIDER in .env:
      - "gemini"  → Google Gemini (free tier)
      - "openai"  → OpenAI (future)
      - "groq"    → Groq (future)
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "gemini":
        return GeminiClient()

    if provider == "groq":
        return GroqClient()

    if provider == "ollama":
        return OllamaClient()

    raise ValueError(
        f"Unknown LLM provider: '{provider}'. "
        f"Supported: gemini, openai, groq"
    )


# Singleton instance — used across the app
llm_client = get_llm_client()