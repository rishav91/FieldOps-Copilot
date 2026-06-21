"""End-to-end spine test against Postgres + pgvector.

Skipped automatically when the DB isn't reachable (e.g. `make db-up` not run), so
the offline unit suite stays green in any environment.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from fieldops.models import Ticket, TicketStatus


@pytest.fixture(scope="module")
def db_ready():
    from fieldops.db import init_db

    try:
        init_db()
    except OperationalError as exc:  # DB not up
        pytest.skip(f"Postgres not reachable: {exc}")


def test_spine_flows_one_ticket(db_ready):
    from fieldops.db import session_scope
    from fieldops.pipeline.runner import run_ticket

    with session_scope() as session:
        result = run_ticket(session)

    assert result.status == TicketStatus.DRAFTED.value
    assert result.predicted_agency == "DEP"  # 311 ground-truth stand-in (ADR-006)
    assert result.routing_path == "fast"
    assert result.draft_hash
    assert result.trace_id


def test_ingest_is_idempotent(db_ready):
    from fieldops.db import session_scope
    from fieldops.pipeline.runner import run_ticket

    with session_scope() as session:
        run_ticket(session)
    with session_scope() as session:
        run_ticket(session)
        count = session.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.unique_key == "59812345")
        )
    assert count == 1  # upsert by unique_key — no duplicate ticket (NFR-3.2)
