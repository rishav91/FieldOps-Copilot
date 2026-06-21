"""Population profiling for the Phase 2 GO/NO-GO gate (ROADMAP)."""
from .ambiguity import AmbiguityProfile, classify_ticket_text, profile_ambiguity

__all__ = ["classify_ticket_text", "profile_ambiguity", "AmbiguityProfile"]
