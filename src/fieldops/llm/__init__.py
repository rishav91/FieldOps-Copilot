"""Provider-agnostic LLM access (ADR-003).

One `LLMClient` interface; the rest of the system never imports a vendor SDK
directly. Default binding: OpenAI for quality-critical tiers (agent, drafting,
judge, embeddings), Grok (xAI) for the cheap/high-volume classifier tier.
"""
from .base import ChatMessage, CompletionResult, LLMClient
from .factory import Tier, get_llm

__all__ = ["LLMClient", "ChatMessage", "CompletionResult", "Tier", "get_llm"]
