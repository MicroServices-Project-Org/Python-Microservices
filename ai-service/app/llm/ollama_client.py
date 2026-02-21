import httpx
from app.llm.base import LLMClient
from app.config import settings


class OllamaClient(LLMClient):
    """
    Ollama LLM client — runs models locally on your machine.
    No API key needed. Ollama must be running (ollama serve).
    Uses the OpenAI-compatible /api/chat endpoint.
    """

    FALLBACK_MSG = "Sorry, the AI service could not generate a response. Is Ollama running?"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json=body,
                )

                if resp.status_code != 200:
                    print(f"❌ Ollama error {resp.status_code}: {resp.text[:200]}")
                    return self.FALLBACK_MSG

                data = resp.json()

                try:
                    return data["message"]["content"]
                except (KeyError, IndexError) as e:
                    print(f"❌ Ollama response parsing error: {e}")
                    return self.FALLBACK_MSG

        except httpx.ConnectError:
            print("❌ Cannot connect to Ollama. Is it running? Start with: ollama serve")
            return self.FALLBACK_MSG
        except httpx.ReadTimeout:
            print("❌ Ollama request timed out. The model may be loading or the prompt is too long.")
            return self.FALLBACK_MSG
        except Exception as e:
            print(f"❌ Unexpected Ollama error: {e}")
            return self.FALLBACK_MSG