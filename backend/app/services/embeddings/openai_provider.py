"""
OpenAI embeddings provider.

Calls OpenAI's /v1/embeddings endpoint directly over HTTP (no SDK
dependency). Requires EMBEDDING_API_KEY. Requests EMBEDDING_DIMENSIONS
explicitly via the API's `dimensions` parameter (supported by the
text-embedding-3-* model family) so the output size always matches
the pgvector column, regardless of which of those models is chosen.
"""
import httpx

_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class EmbeddingProviderError(Exception):
    """Raised when the embeddings API call fails (auth, network, etc.)."""


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, model: str, dimensions: int):
        if not api_key:
            raise EmbeddingProviderError(
                "EMBEDDING_API_KEY is required when EMBEDDING_PROVIDER=openai"
            )
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = httpx.post(
                _EMBEDDINGS_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts, "dimensions": self.dimensions},
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError(f"OpenAI embeddings request failed: {exc}") from exc

        data = response.json()["data"]
        # The API returns results indexed but not guaranteed in input order.
        ordered = sorted(data, key=lambda item: item["index"])
        return [item["embedding"] for item in ordered]
