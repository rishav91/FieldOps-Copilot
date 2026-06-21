"""Classifier + routing — STUB (Phase 0).

Placeholder for the real cascade (FR-3): classical/cheap -> Groq -> OpenAI with
*calibrated* confidence (Phase 2). The stub reuses the existing 311 `agency`
label as a stand-in prediction (ADR-006) with no calibrated confidence, and
records a `routing_decision`. It makes NO LLM call so the skeleton runs offline.

Confidence is left null and the gate (FR-4) is intentionally not wired:
calibration is a first-class step (ADR-007) that lands in Phase 2.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Raw311Record, RoutingDecision, RoutingPath, Ticket, TicketStatus
from ..tracing import span

STUB_GATE_VERSION = "stub-v0"


def classify_ticket(session: Session, ticket: Ticket) -> RoutingDecision:
    with span("classify.stub", ticket_id=ticket.id) as s:
        predicted_agency = _stub_agency(session, ticket)
        decision = RoutingDecision(
            ticket_id=ticket.id,
            predicted_agency=predicted_agency,
            predicted_type=ticket.complaint_type,
            confidence_calibrated=None,  # no calibrated score until Phase 2
            path=RoutingPath.FAST,  # gate not wired in Phase 0
            gate_version=STUB_GATE_VERSION,
        )
        session.add(decision)
        ticket.status = TicketStatus.ROUTED
        session.flush()
        s["predicted_agency"] = predicted_agency
        s["path"] = decision.path.value
        return decision


def _stub_agency(session: Session, ticket: Ticket) -> str:
    """Stand-in prediction: the 311 ground-truth agency from the raw payload."""
    raw = session.get(Raw311Record, ticket.unique_key)
    agency = (raw.payload.get("agency") if raw else None) or "DSNY"
    return agency
