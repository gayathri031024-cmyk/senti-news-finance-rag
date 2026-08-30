"""
Embedding provider interface.

Every provider takes a batch of strings and returns one fixed-length
vector per string, as plain lists of floats (never numpy — keeps this
layer dependency-light and easy to test).
"""
from typing import Protocol


class EmbeddingProvider(Protocol):
    dimensions: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...
