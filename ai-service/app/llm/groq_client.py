import asyncio
import httpx
from app.llm.base import LLMClient
from app.config import settings


class GroqClient(LLMClient):
    """
    Groq LLM client using the REST API.
    Groq uses OpenAI-compatible API format, making it easy to swap.
    Free tier: 30 RPM on Llama 3.3 70B.
    """

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    MAX_RETRIES = 3
    FALLBACK_MSG = "Sorry, the AI service is temporarily busy. Please try again in a moment."

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": settings.GROQ_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
        }

        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        self.BASE_URL,
                        json=body,
                        headers=headers,
                    )

                    if resp.status_code == 429:
                        wait = 2 ** attempt * 2  # 2s, 4s, 8s
                        print(f"⏳ Groq rate limited — retrying in {wait}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                        await asyncio.sleep(wait)
                        continue

                    if resp.status_code != 200:
                        print(f"❌ Groq API error {resp.status_code}: {resp.text[:200]}")
                        return self.FALLBACK_MSG

                    data = resp.json()

                    try:
                        return data["choices"][0]["message"]["content"]
                    except (KeyError, IndexError) as e:
                        print(f"❌ Groq response parsing error: {e}")
                        return self.FALLBACK_MSG

            except httpx.TransportError as e:
                print(f"❌ Groq connection error: {e}")
                return self.FALLBACK_MSG
            except Exception as e:
                print(f"❌ Unexpected Groq error: {e}")
                return self.FALLBACK_MSG

        print("❌ Groq rate limit exceeded after all retries")
        return self.FALLBACK_MSG