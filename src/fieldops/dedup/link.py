"""Deterministic dedup linking (FR-2, ARCHITECTURE §3/§6).

A new ticket is a duplicate of an earlier one when their descriptions are close
in embedding space **and** they fall within a geo + time window. Matching is
deterministic (a cosine threshold + bounding box + day window); it links via
`duplicate_of` and bumps the canonical's `report_count` — it never deletes.
"""
from __future__ import annotations

from datetime import timedelta
from math import cos, radians

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Embedding, Ticket, TicketStatus
from ..tracing import span
from .embed import embed_ticket


def find_canonical(
    session: Session,
    ticket: Ticket,
    emb: Embedding | None = None,
    *,
    threshold: float | None = None,
    geo_meters: float | None = None,
    time_days: int | None = None,
) -> Ticket | None:
    """Closest earlier non-duplicate ticket within threshold + geo/time, or None."""
    s = get_settings()
    threshold = s.dedup_cosine_threshold if threshold is None else threshold
    geo_meters = s.dedup_geo_meters if geo_meters is None else geo_meters
    time_days = s.dedup_time_days if time_days is None else time_days

    emb = emb or session.get(Embedding, ticket.id)
    if emb is None:
        return None

    dist = Embedding.vector.cosine_distance(emb.vector)
    stmt = (
        select(Ticket)
        .join(Embedding, Embedding.ticket_id == Ticket.id)
        .where(Ticket.id != ticket.id)
        .where(Ticket.duplicate_of.is_(None))
        .where(dist <= threshold)
    )

    if ticket.created_date is not None:
        lo = ticket.created_date - timedelta(days=time_days)
        stmt = stmt.where(
            Ticket.created_date >= lo, Ticket.created_date <= ticket.created_date
        )

    if ticket.latitude is not None and ticket.longitude is not None:
        lat_d = geo_meters / 111_320.0
        lng_d = geo_meters / (111_320.0 * max(cos(radians(ticket.latitude)), 1e-6))
        stmt = stmt.where(
            Ticket.latitude.between(ticket.latitude - lat_d, ticket.latitude + lat_d),
            Ticket.longitude.between(ticket.longitude - lng_d, ticket.longitude + lng_d),
        )

    return session.scalars(stmt.order_by(dist).limit(1)).first()


def link_duplicate(session: Session, ticket: Ticket, canonical: Ticket) -> None:
    """Mark `ticket` a duplicate of `canonical` and bump the canonical's count."""
    ticket.duplicate_of = canonical.id
    ticket.status = TicketStatus.DUPLICATE
    canonical.report_count = (canonical.report_count or 1) + 1
    session.flush()


def dedup_ticket(session: Session, ticket: Ticket, client=None, **window) -> Ticket | None:
    """Ensure the ticket is embedded, find a canonical, and link if found."""
    with span("dedup.link", ticket_id=ticket.id) as sp:
        emb = session.get(Embedding, ticket.id) or embed_ticket(session, ticket, client)
        canonical = find_canonical(session, ticket, emb, **window)
        if canonical is not None:
            link_duplicate(session, ticket, canonical)
            sp["duplicate_of"] = canonical.id
        return canonical
