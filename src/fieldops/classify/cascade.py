"""The classification cascade (sub-phase 2.3, AI-ARCHITECTURE §3).

cheap kNN → (if not confident) Groq → (if still not confident) OpenAI. Only the
residual reaches an expensive model — the cost-control funnel. Degrades
gracefully: if a tier's client is unavailable (e.g. no key), it's skipped, and
the best prediction so far is returned.

LLM clients are injectable so the cascade is testable without keys.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..config import get_settings
from ..llm import Tier, get_llm
from ..llm.base import LLMClient
from ..models import Ticket
from ..tracing import span
from .cheap import classify_cheap
from .llm_classify import classify_llm
from .types import Prediction

_UNSET = object()  # sentinel: distinguish "auto-resolve" from "explicitly none"


def _maybe_get(tier: Tier) -> LLMClient | None:
    try:
        return get_llm(tier)
    except Exception:
        return None  # no key / unavailable → tier skipped


def classify_cascade(
    session: Session,
    ticket: Ticket,
    *,
    groq: LLMClient | None | object = _UNSET,
    openai: LLMClient | None | object = _UNSET,
    cheap_min: float | None = None,
) -> Prediction:
    """Run the cheap→Groq→OpenAI cascade; return the chosen prediction."""
    s = get_settings()
    cheap_min = s.cascade_cheap_min_confidence if cheap_min is None else cheap_min

    with span("classify.cascade", ticket_id=ticket.id) as sp:
        cheap = classify_cheap(session, ticket)
        if cheap.agency and cheap.confidence >= cheap_min:
            sp["chosen"] = cheap.tier
            return cheap

        groq_client = _maybe_get(Tier.CHEAP) if groq is _UNSET else groq
        if groq_client is not None:
            g = classify_llm(ticket, groq_client, tier_name="groq")
            if g.agency and g.confidence >= cheap_min:
                sp["chosen"] = g.tier
                return g

        openai_client = _maybe_get(Tier.AGENT) if openai is _UNSET else openai
        if openai_client is not None:
            o = classify_llm(ticket, openai_client, tier_name="openai")
            if o.agency:
                sp["chosen"] = o.tier
                return o

        sp["chosen"] = cheap.tier  # best effort
        return cheap
