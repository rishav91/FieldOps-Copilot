"""Embedding generation for dedup + retrieval (FR-2).

Text is **redacted (FR-10.1) before** the external embedding call. The embedder
is injectable so tests run without an API key; the default binds the OpenAI
EMBED tier (ADR-003).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..guardrails import redact
from ..llm import Tier, get_llm
from ..llm.base import LLMClient
from ..models import Embedding, Ticket
from ..tracing import span


def ticket_text(ticket: Ticket) -> str:
    """The text we embed: complaint type + descriptor."""
    return f"{ticket.complaint_type or ''}: {ticket.descriptor or ''}".strip(": ").strip()


def embed_ticket(session: Session, ticket: Ticket, client: LLMClient | None = None) -> Embedding:
    """Embed one ticket (redacted) and upsert its vector. Idempotent per ticket."""
    client = client or get_llm(Tier.EMBED)
    text = redact(ticket_text(ticket)) or ""
    with span("dedup.embed", ticket_id=ticket.id, redacted=text != ticket_text(ticket)):
        vector = client.embed([text])[0]
        emb = session.get(Embedding, ticket.id)
        if emb is None:
            emb = Embedding(ticket_id=ticket.id, vector=vector, model=client.model)
            session.add(emb)
        else:
            emb.vector = vector
            emb.model = client.model
        session.flush()
        return emb


def embed_missing(
    session: Session,
    client: LLMClient | None = None,
    *,
    limit: int | None = None,
    batch_size: int = 128,
) -> int:
    """Embed all tickets lacking a vector, batching the API calls. Returns count.

    Texts are redacted (FR-10.1) before the batched external call; one API
    request per `batch_size` tickets keeps a few-thousand backfill cheap and
    avoids rate-limit storms (NFR-5.5).
    """
    client = client or get_llm(Tier.EMBED)
    stmt = (
        select(Ticket)
        .outerjoin(Embedding, Embedding.ticket_id == Ticket.id)
        .where(Embedding.ticket_id.is_(None))
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    tickets = session.scalars(stmt).all()

    total = 0
    for start in range(0, len(tickets), batch_size):
        chunk = tickets[start : start + batch_size]
        texts = [redact(ticket_text(t)) or "" for t in chunk]
        with span("dedup.embed_batch", n=len(chunk)):
            vectors = client.embed(texts)
        for ticket, vector in zip(chunk, vectors):
            session.add(Embedding(ticket_id=ticket.id, vector=vector, model=client.model))
        session.flush()
        total += len(chunk)
    return total
