"""Groq binding (ADR-003) — the cheap/high-volume classifier tier.

Groq is OpenAI-compatible, so this reuses the OpenAI chat surface with Groq's
base URL. Embeddings stay on OpenAI (ADR-003), so `embed` is not provided here.
"""
from __future__ import annotations

from .openai_client import OpenAIClient


class GroqClient(OpenAIClient):
    provider = "groq"

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self._base_url = base_url
        super().__init__(api_key=api_key, model=model, embed_model=None)

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Embeddings use the OpenAI tier (ADR-003); call get_llm(Tier.EMBED)."
        )
