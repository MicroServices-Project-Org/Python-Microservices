from abc import ABC, abstractmethod


class LLMClient(ABC):
    """
    Abstract base class for LLM providers.
    To add a new provider (OpenAI, Groq, Ollama):
      1. Create a new class that extends LLMClient
      2. Implement the generate() method
      3. Register it in factory.py
    """

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        Send a prompt to the LLM and return the response text.

        Args:
            prompt: The user's message or constructed prompt
            system_prompt: System-level instructions for the LLM

        Returns:
            The LLM's response as a string
        """
        pass