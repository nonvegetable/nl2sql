"""Provider-neutral LLM boundary for SQL generation."""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    def generate(self, system_prompt: str, user_prompt: str, *, model: str | None = None, api_key: str | None = None) -> str: ...


class ExistingProviders:
    """Adapter around the repository's existing LM Studio/Ollama/cloud providers."""

    def __init__(self, provider: str | None = None) -> None:
        self.provider = provider

    def generate(self, system_prompt: str, user_prompt: str, *, model: str | None = None, api_key: str | None = None) -> str:
        from providers import call_llm
        return call_llm(system_prompt, user_prompt, provider=self.provider, model_name=model, api_key=api_key)
