"""Shared agent interface + a deterministic fallback LLM.

FakeLLM lets every agent run offline and in CI without OPENAI_API_KEY: it
returns template-based, deterministic completions so tests are reproducible.
Setting OPENAI_API_KEY swaps in a real chat-completion call transparently.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.config import settings


@dataclass
class AgentResult:
    output: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseLLM(ABC):
    @abstractmethod
    def complete(self, system: str, prompt: str) -> str: ...


class FakeLLM(BaseLLM):
    """Deterministic, template-based completion — no network, no API key."""

    def complete(self, system: str, prompt: str) -> str:
        return prompt.strip()


class OpenAIChatLLM(BaseLLM):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, system: str, prompt: str) -> str:
        from openai import OpenAI  # imported lazily; optional dependency

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


def build_llm() -> BaseLLM:
    if settings.openai_api_key:
        return OpenAIChatLLM(settings.openai_api_key, settings.llm_model)
    return FakeLLM()


class BaseAgent(ABC):
    name: str
    description: str
    capabilities: list[str] = []

    def __init__(self, llm: BaseLLM | None = None) -> None:
        self.llm = llm or build_llm()

    @abstractmethod
    def run(self, query: str, context: dict[str, Any] | None = None) -> AgentResult: ...
