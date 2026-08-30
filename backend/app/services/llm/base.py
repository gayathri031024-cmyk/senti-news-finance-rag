"""
LLM provider interface.

Every provider takes a system prompt (the grounding rules) and a user
prompt (question + retrieved context) and returns the generated answer
as plain text. Mirrors the shape of
services/embeddings/base.py's EmbeddingProvider so both "generate a
vector" and "generate an answer" follow the same swappable-provider
pattern.
"""
from typing import Protocol


class LLMProvider(Protocol):
    model: str

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        ...
