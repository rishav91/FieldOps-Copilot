"""OpenAI binding (ADR-003) — the quality-critical tiers + embeddings.

Also serves as the OpenAI-compatible base for Groq, which exposes the same
chat-completions surface. The `openai` SDK is imported lazily so the package
imports cleanly without keys (Phase-0 stubs run offline).
"""
from __future__ import annotations

from .base import ChatMessage, CompletionResult


class OpenAIClient:
    provider = "openai"
    _base_url: str | None = None  # None => api.openai.com

    def __init__(self, api_key: str, model: str, embed_model: str | None = None) -> None:
        if not api_key:
            raise ValueError(f"{self.provider}: missing API key")
        from openai import OpenAI  # lazy import

        self._client = OpenAI(api_key=api_key, base_url=self._base_url)
        self.model = model
        self.embed_model = embed_model

    def complete(self, messages: list[ChatMessage], **kwargs: object) -> CompletionResult:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            **kwargs,
        )
        usage = resp.usage
        return CompletionResult(
            text=resp.choices[0].message.content or "",
            model=self.model,
            provider=self.provider,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            # Cost wiring (per-provider pricing) lands with the spend breaker; see
            # OBSERVABILITY §6. Skeleton reports 0.0.
            cost_usd=0.0,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embed_model:
            raise NotImplementedError(f"{self.provider}: no embedding model configured")
        resp = self._client.embeddings.create(model=self.embed_model, input=texts)
        return [d.embedding for d in resp.data]
