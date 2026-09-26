from app.llm.base import LLMClient
from app.llm.gemini_client import GeminiClient
from app.config import settings
from app.llm.groq_client import GroqClient
from app.llm.ollama_client import OllamaClient


def get_llm_client() -> LLMClient:
    """
    Factory function that returns the configured LLM client.
    To swap providers, change LLM_PROVIDER in .env:
      - "groq"    → Groq / GPT-OSS 120B (default)
      - "gemini"  → Google Gemini (free tier)
      - "ollama"  → Ollama (local)
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
        f"Supported: groq, gemini, ollama"
    )


# Singleton instance — used across the app
llm_client = get_llm_client()