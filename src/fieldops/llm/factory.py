"""Tier → provider binding (ADR-003).

Call sites ask for a *tier* (what the work is), not a vendor. This is the single
place the default binding lives, so swapping a provider is one edit here.

    CHEAP  -> Groq                high-volume classifier fallback
    AGENT  -> OpenAI GPT-4-class  agent, drafting, judge
    EMBED  -> OpenAI embeddings   dedup + retrieval
"""
from __future__ import annotations

import enum

from ..config import get_settings
from .base import LLMClient
from .groq_client import GroqClient
from .openai_client import OpenAIClient


class Tier(str, enum.Enum):
    CHEAP = "cheap"
    AGENT = "agent"
    EMBED = "embed"


def get_llm(tier: Tier) -> LLMClient:
    s = get_settings()
    if tier is Tier.CHEAP:
        return GroqClient(
            api_key=s.groq_api_key or "", model=s.groq_cheap_model, base_url=s.groq_base_url
        )
    if tier is Tier.AGENT:
        return OpenAIClient(api_key=s.openai_api_key or "", model=s.openai_agent_model)
    if tier is Tier.EMBED:
        return OpenAIClient(
            api_key=s.openai_api_key or "",
            model=s.openai_embed_model,
            embed_model=s.openai_embed_model,
        )
    raise ValueError(f"unknown tier: {tier}")
