import pytest

from app.services.llm.factory import get_llm_provider, UnknownLLMProviderError
from app.services.llm.local_provider import LocalEchoLLMProvider
from app.services.llm.openai_provider import LLMProviderError, OpenAILLMProvider


def test_local_provider_does_not_make_network_calls_and_returns_placeholder():
    provider = LocalEchoLLMProvider()
    answer = provider.generate(system_prompt="rules", user_prompt="context + question")

    assert "not a real llm" in answer.lower() or "placeholder" in answer.lower()


def test_openai_provider_requires_api_key():
    with pytest.raises(LLMProviderError):
        OpenAILLMProvider(api_key="", model="gpt-4o-mini")


def test_factory_returns_local_provider():
    from app.core.config import Settings

    settings = Settings(LLM_PROVIDER="local")
    provider = get_llm_provider(settings)

    assert isinstance(provider, LocalEchoLLMProvider)


def test_factory_returns_openai_provider():
    from app.core.config import Settings

    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="sk-fake-key-for-test", LLM_MODEL="gpt-4o-mini")
    provider = get_llm_provider(settings)

    assert isinstance(provider, OpenAILLMProvider)


def test_factory_rejects_unknown_provider():
    from app.core.config import Settings

    settings = Settings(LLM_PROVIDER="not-a-real-provider")
    with pytest.raises(UnknownLLMProviderError):
        get_llm_provider(settings)
