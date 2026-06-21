"""Cheap classifier tier (sub-phase 2.2) — embedding kNN, no LLM.

Predicts an agency by majority vote over the k nearest tickets (by cosine over
pgvector embeddings), using their 311 ground-truth agency as the neighbor label
(ADR-006). Raw confidence is the winning vote fraction — a signal calibration
(2.5) later turns into a real probability. Falls back to the deterministic
complaint-type prior when a ticket has no embedding.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Embedding, Raw311Record, Ticket
from ..tracing import span
from .taxonomy import agency_for_complaint_type, is_valid_agency, normalize_agency
from .types import Prediction


def vote(agencies: Sequence[str | None]) -> tuple[str | None, float, int]:
    """Majority vote over neighbor agencies → (agency, vote_fraction, n_valid)."""
    valid = [normalize_agency(a) for a in agencies if is_valid_agency(a)]
    if not valid:
        return None, 0.0, 0
    counts = Counter(valid)
    top, n = counts.most_common(1)[0]
    return top, n / len(valid), len(valid)


def _prior(ticket: Ticket) -> Prediction:
    prior = agency_for_complaint_type(ticket.complaint_type)
    return Prediction(prior, 0.5 if prior else 0.0, "prior", 0)


def classify_cheap(
    session: Session,
    ticket: Ticket,
    *,
    k: int | None = None,
    max_distance: float | None = None,
) -> Prediction:
    """kNN-vote the agency over *close* neighbors; fall back to the prior.

    Only neighbors within `max_distance` (cosine) vote, so unrelated tickets
    don't pollute the result. With no embedding or no close neighbor, we defer to
    the deterministic complaint-type prior.
    """
    s = get_settings()
    k = k or s.cheap_knn_k
    max_distance = s.cheap_knn_max_distance if max_distance is None else max_distance

    with span("classify.cheap", ticket_id=ticket.id) as sp:
        emb = session.get(Embedding, ticket.id)
        if emb is None:
            sp["tier"] = "prior"
            return _prior(ticket)

        dist = Embedding.vector.cosine_distance(emb.vector)
        rows = session.execute(
            select(Raw311Record.payload)
            .join(Ticket, Ticket.unique_key == Raw311Record.unique_key)
            .join(Embedding, Embedding.ticket_id == Ticket.id)
            .where(Ticket.id != ticket.id)
            .where(dist <= max_distance)
            .order_by(dist)
            .limit(k)
        ).all()
        agency, confidence, n = vote([payload.get("agency") for (payload,) in rows])
        if agency is None:  # no close, validly-labeled neighbor
            sp["tier"] = "prior"
            return _prior(ticket)
        sp["tier"] = "cheap-knn"
        sp["agency"] = agency
        return Prediction(agency, confidence, "cheap-knn", n)
