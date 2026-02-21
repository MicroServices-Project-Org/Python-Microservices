import asyncio
import httpx
from app.llm.base import LLMClient
from app.config import settings


class GeminiClient(LLMClient):
    """
    Google Gemini LLM client using the REST API.
    Uses httpx instead of the google-generativeai SDK to keep
    dependencies minimal and consistent with the rest of the project.
    Includes retry with exponential backoff for rate limiting (429).
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    MAX_RETRIES = 3
    FALLBACK_MSG = "Sorry, the AI service is temporarily busy. Please try again in a moment."

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        url = f"{self.BASE_URL}/{settings.GEMINI_MODEL}:generateContent"

        # Build request body
        contents = []
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": system_prompt}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will follow these instructions."}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024,
            }
        }

        # Retry with exponential backoff for 429 rate limits
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        url,
                        json=body,
                        params={"key": settings.GEMINI_API_KEY},
                    )

                    if resp.status_code == 429:
                        wait = 2 ** attempt * 2  # 2s, 4s, 8s
                        print(f"⏳ Gemini rate limited — retrying in {wait}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
                        await asyncio.sleep(wait)
                        continue

                    if resp.status_code != 200:
                        print(f"❌ Gemini API error {resp.status_code}: {resp.text[:200]}")
                        return self.FALLBACK_MSG

                    data = resp.json()

                    # Extract text from Gemini response
                    try:
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError) as e:
                        print(f"❌ Gemini response parsing error: {e}")
                        return self.FALLBACK_MSG

            except httpx.TransportError as e:
                print(f"❌ Gemini connection error: {e}")
                return self.FALLBACK_MSG
            except Exception as e:
                print(f"❌ Unexpected Gemini error: {e}")
                return self.FALLBACK_MSG

        print("❌ Gemini rate limit exceeded after all retries")
        return self.FALLBACK_MSG