from app.core.config import Settings
from app.services.embeddings.base import EmbeddingProvider
from app.services.embeddings.local_provider import LocalHashingEmbeddingProvider
from app.services.embeddings.openai_provider import OpenAIEmbeddingProvider


class UnknownEmbeddingProviderError(Exception):
    pass


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "local":
        return LocalHashingEmbeddingProvider(dimensions=settings.EMBEDDING_DIMENSIONS)

    if provider == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.EMBEDDING_API_KEY,
            model=settings.EMBEDDING_MODEL,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )

    raise UnknownEmbeddingProviderError(
        f"Unknown EMBEDDING_PROVIDER '{settings.EMBEDDING_PROVIDER}'. Expected 'local' or 'openai'."
    )
