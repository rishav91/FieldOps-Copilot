"""The walking-skeleton spine (Phase 0).

Flows one ticket: ingest -> store -> (stub) classify -> (stub) draft, all under a
single trace. Returns a summary the CLI/API renders to the console.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..tracing import span, trace
from .classify import classify_ticket
from .draft import draft_work_order
from .ingest import ingest_record, load_sample_record


@dataclass
class PipelineResult:
    ticket_id: str
    unique_key: str
    status: str
    predicted_agency: str | None
    routing_path: str | None
    draft_hash: str | None
    trace_id: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def run_ticket(session: Session, raw: dict | None = None) -> PipelineResult:
    """Run one record through the deterministic spine under one trace."""
    raw = raw or load_sample_record()
    unique_key = str(raw["unique_key"])

    with trace(ticket_id=None) as trace_id, span("pipeline.run", unique_key=unique_key):
        ticket = ingest_record(session, raw)
        decision = classify_ticket(session, ticket)
        work_order = draft_work_order(session, ticket, decision)

        return PipelineResult(
            ticket_id=ticket.id,
            unique_key=ticket.unique_key,
            status=ticket.status.value,
            predicted_agency=decision.predicted_agency,
            routing_path=decision.path.value,
            draft_hash=work_order.draft_hash,
            trace_id=trace_id,
        )
