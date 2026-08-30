from app.core.config import Settings
from app.services.llm.base import LLMProvider
from app.services.llm.local_provider import LocalEchoLLMProvider
from app.services.llm.openai_provider import OpenAILLMProvider
from app.services.llm.groq_provider import GroqLLMProvider


class UnknownLLMProviderError(Exception):
    pass


def get_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.LLM_PROVIDER.lower()

    if provider == "local":
        return LocalEchoLLMProvider(model=settings.LLM_MODEL)

    if provider == "openai":
        return OpenAILLMProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
        )

    if provider == "groq":
        return GroqLLMProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
        )

    raise UnknownLLMProviderError(
        f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. "
        f"Expected 'local', 'openai', or 'groq'."
    )
