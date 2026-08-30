"""
OpenAI LLM provider.

Calls OpenAI's /v1/chat/completions endpoint directly over HTTP (no
SDK dependency, matching services/embeddings/openai_provider.py).
Requires LLM_API_KEY. Uses temperature=0 by default: this is a
grounded-answer generator over a fixed context, not a creative-writing
task, so we want the most literal, least "creative" reading of the
retrieved chunks.
"""
import httpx

_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


class LLMProviderError(Exception):
    """Raised when the chat completion API call fails (auth, network, malformed response, etc.)."""


class OpenAILLMProvider:
    def __init__(self, api_key: str, model: str, temperature: float = 0.0):
        if not api_key:
            raise LLMProviderError(
                "LLM_API_KEY is required when LLM_PROVIDER=openai"
            )
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = httpx.post(
                _CHAT_COMPLETIONS_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": self.temperature,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=60.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"OpenAI chat completion request failed: {exc}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Unexpected OpenAI response shape: {data}") from exc
