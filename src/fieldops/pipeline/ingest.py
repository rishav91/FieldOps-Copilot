"""Ingest + normalize (FR-1, ARCHITECTURE §3).

Phase 0 reads one bundled sample record; the real Socrata SODA pull lands in
Phase 1. Normalization maps a raw 311 payload to the canonical `ticket`. Writes
are idempotent: upsert raw by `unique_key`, ticket by `unique_key` (NFR-3.2).
"""
from __future__ import annotations

import json
from datetime import datetime
from importlib import resources

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Raw311Record, Ticket, TicketStatus
from ..tracing import span


def load_sample_record() -> dict:
    """The bundled demo record (PRD use case 3: the ambiguous ceiling/floor leak)."""
    with resources.files("fieldops.data").joinpath("sample_311.json").open() as f:
        return json.load(f)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _to_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def ingest_record(session: Session, raw: dict) -> Ticket:
    """Upsert the raw payload and its canonical ticket. Idempotent by unique_key."""
    unique_key = str(raw["unique_key"])
    with span("ingest.normalize", unique_key=unique_key):
        if session.get(Raw311Record, unique_key) is None:
            session.add(Raw311Record(unique_key=unique_key, payload=raw))

        ticket = session.scalar(select(Ticket).where(Ticket.unique_key == unique_key))
        if ticket is None:
            ticket = Ticket(unique_key=unique_key, status=TicketStatus.INGESTED)
            session.add(ticket)

        # (Re)normalize fields from the source of truth.
        ticket.complaint_type = raw.get("complaint_type")
        ticket.descriptor = raw.get("descriptor")
        ticket.borough = (raw.get("borough") or "").upper() or None
        ticket.latitude = _to_float(raw.get("latitude"))
        ticket.longitude = _to_float(raw.get("longitude"))
        ticket.created_date = _parse_dt(raw.get("created_date"))
        ticket.closed_date = _parse_dt(raw.get("closed_date"))

        session.flush()  # assign ticket.id
        return ticket
