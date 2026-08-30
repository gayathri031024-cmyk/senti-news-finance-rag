import math

import pytest

from app.services.embeddings.factory import get_embedding_provider, UnknownEmbeddingProviderError
from app.services.embeddings.local_provider import LocalHashingEmbeddingProvider
from app.services.embeddings.openai_provider import EmbeddingProviderError, OpenAIEmbeddingProvider


def test_local_provider_produces_correct_dimensions():
    provider = LocalHashingEmbeddingProvider(dimensions=128)
    vectors = provider.embed_texts(["hello world", "financial report"])

    assert len(vectors) == 2
    assert all(len(v) == 128 for v in vectors)


def test_local_provider_is_deterministic():
    provider = LocalHashingEmbeddingProvider(dimensions=64)
    v1 = provider.embed_texts(["net interest income"])[0]
    v2 = provider.embed_texts(["net interest income"])[0]

    assert v1 == v2


def test_local_provider_vectors_are_l2_normalized():
    provider = LocalHashingEmbeddingProvider(dimensions=64)
    vectors = provider.embed_texts(["some text with several words in it"])
    norm = math.sqrt(sum(x * x for x in vectors[0]))

    assert norm == pytest.approx(1.0, abs=1e-6)


def test_local_provider_ranks_relevant_text_higher():
    provider = LocalHashingEmbeddingProvider(dimensions=384)
    query = provider.embed_texts(["What was the net interest income?"])[0]
    relevant, irrelevant = provider.embed_texts([
        "Net interest income grew 3.2 percent to Rs 330.8 billion.",
        "The bank opened new branches in twelve cities.",
    ])

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b))

    assert cosine(query, relevant) > cosine(query, irrelevant)


def test_local_provider_empty_text_returns_zero_vector():
    provider = LocalHashingEmbeddingProvider(dimensions=32)
    vectors = provider.embed_texts([""])

    assert vectors[0] == [0.0] * 32


def test_openai_provider_requires_api_key():
    with pytest.raises(EmbeddingProviderError):
        OpenAIEmbeddingProvider(api_key="", model="text-embedding-3-small", dimensions=384)


def test_factory_returns_local_provider(monkeypatch):
    from app.core.config import Settings

    settings = Settings(EMBEDDING_PROVIDER="local", EMBEDDING_DIMENSIONS=64)
    provider = get_embedding_provider(settings)

    assert isinstance(provider, LocalHashingEmbeddingProvider)
    assert provider.dimensions == 64


def test_factory_returns_openai_provider():
    from app.core.config import Settings

    settings = Settings(
        EMBEDDING_PROVIDER="openai",
        EMBEDDING_API_KEY="sk-fake-key-for-test",
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSIONS=384,
    )
    provider = get_embedding_provider(settings)

    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_factory_rejects_unknown_provider():
    from app.core.config import Settings

    settings = Settings(EMBEDDING_PROVIDER="not-a-real-provider")
    with pytest.raises(UnknownEmbeddingProviderError):
        get_embedding_provider(settings)
