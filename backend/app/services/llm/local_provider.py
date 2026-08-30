"""
Local/offline LLM provider.

Mirrors the role of services/embeddings/local_provider.py: a
dependency-free, no-API-key stand-in so the query pipeline (retrieval,
context building, prompt construction, response/citation shaping) can
be wired up, run, and demonstrated end-to-end without any external
call or LLM_API_KEY configured.

IMPORTANT — this is NOT a real answer generator and must not be
treated as one:
  - It does not read or reason over the retrieved context.
  - It does not synthesize a natural-language financial answer.
  - Its output must never be used as evidence that the grounding
    rules in generation/prompts.py actually work, or that the system
    avoids hallucination or fabricated citations.

Those properties can only be verified against a real LLM
(LLM_PROVIDER=openai, or another real provider, with a valid
LLM_API_KEY) — see README's Phase 4 verification section for what has
and hasn't been confirmed this way.
"""

_PLACEHOLDER_NOTICE = (
    "[local provider — placeholder, not a real LLM] This is a canned "
    "response from LLM_PROVIDER=local, used only to exercise the API "
    "shape (retrieval -> context -> prompt -> answer -> citations) "
    "without an external call. It has not read the retrieved context "
    "and is not a grounded answer. Set LLM_PROVIDER=openai with a "
    "valid LLM_API_KEY to get a real, grounded answer."
)


class LocalEchoLLMProvider:
    def __init__(self, model: str = "local-echo-v1"):
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return _PLACEHOLDER_NOTICE
