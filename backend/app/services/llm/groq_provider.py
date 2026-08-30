"""
Groq LLM provider.

Uses Groq's OpenAI-compatible Chat Completions API.
"""

import httpx

from app.services.llm.base import LLMProvider
from app.services.llm.openai_provider import LLMProviderError


class GroqLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise LLMProviderError("LLM_API_KEY is not configured.")

        try:
            response = httpx.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {
                            "role": "user",
                            "content": user_prompt,
                        },
                    ],
                    "temperature": 0.2,
                },
                timeout=60.0,
            )

            if response.status_code >= 400:
                raise LLMProviderError(
                    f"Groq API returned {response.status_code}: {response.text}"
                )

            data = response.json()

            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMProviderError(
                    f"Unexpected response from Groq: {data}"
                ) from exc

        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"Groq API request failed: {exc}"
            ) from exc