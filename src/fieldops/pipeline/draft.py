"""Work-order drafting — STUB (Phase 0).

Placeholder for the deterministic drafting DAG (FR-6, ADR-008): fan-out context
-> one structured generation -> deterministic validator -> <=1 repair. The stub
emits a fixed draft and a `draft_hash` (the submission idempotency key, NFR-3.2),
with NO LLM call. No submission happens — the human gate (FR-7) is a later phase.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from ..models import RoutingDecision, Ticket, TicketStatus, WorkOrder
from ..tracing import span


def _draft_hash(ticket_id: str, draft: dict) -> str:
    payload = json.dumps({"ticket_id": ticket_id, "draft": draft}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def draft_work_order(session: Session, ticket: Ticket, decision: RoutingDecision) -> WorkOrder:
    with span("draft.stub", ticket_id=ticket.id) as s:
        draft = {
            "owner": decision.predicted_agency,
            "next_action": f"Investigate: {ticket.descriptor or ticket.complaint_type}",
            "due_date": None,
            "cited_precedent_id": None,  # grounded citations arrive in Phase 4
        }
        wo = WorkOrder(
            ticket_id=ticket.id,
            draft=draft,
            validator_status="stub",  # real validator gates in Phase 4
            repair_count=0,
            review_status="pending",  # awaits the human gate (FR-7)
            draft_hash=_draft_hash(ticket.id, draft),
        )
        session.add(wo)
        ticket.status = TicketStatus.DRAFTED
        session.flush()
        s["draft_hash"] = wo.draft_hash
        return wo
