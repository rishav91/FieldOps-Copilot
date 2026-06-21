"""Standing guardrails (FR-10, AI-ARCHITECTURE §6)."""
from .pii import contains_pii, redact

__all__ = ["redact", "contains_pii"]
