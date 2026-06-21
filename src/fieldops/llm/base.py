"""The LLMClient interface (ADR-003).

Designed to the common subset of providers so bindings stay swappable. No
side-effecting capability lives here — the agent reasons, deterministic code
acts (governing principle).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class CompletionResult:
    text: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    meta: dict = field(default_factory=dict)


@runtime_checkable
class LLMClient(Protocol):
    """Minimal provider-agnostic surface: chat completion + embeddings."""

    provider: str
    model: str

    def complete(self, messages: list[ChatMessage], **kwargs: object) -> CompletionResult: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...
