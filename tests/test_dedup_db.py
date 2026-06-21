"""Embed + dedup + backfill integration against Postgres + pgvector (Phase 1).

Auto-skips when the DB isn't reachable. Uses a deterministic fake embedder so no
API key is needed: identical text -> identical vector (cosine distance 0).
"""
from __future__ import annotations

import random

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from fieldops.config import get_settings
from fieldops.models import Ticket, TicketStatus


class FakeEmbedder:
    """Deterministic embedder: same text -> same unit vector."""

    provider = "fake"
    model = "fake-embed"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            rng = random.Random(text)
            vec = [rng.gauss(0, 1) for _ in range(self.dim)]
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            out.append([x / norm for x in vec])
        return out

    def complete(self, *_a, **_k):  # pragma: no cover - not used
        raise NotImplementedError


@pytest.fixture(scope="module")
def db_ready():
    from fieldops.db import init_db

    try:
        init_db()
    except OperationalError as exc:
        pytest.skip(f"Postgres not reachable: {exc}")


def _raw(unique_key: str, descriptor: str, created: str) -> dict:
    return {
        "unique_key": unique_key,
        "created_date": created,
        "complaint_type": "Water System",
        "descriptor": descriptor,
        "agency": "DEP",
        "borough": "BROOKLYN",
        "latitude": "40.6782",
        "longitude": "-73.9442",
    }


def test_embed_then_dedup_links_duplicates(db_ready):  # noqa: ARG001
    import uuid

    from fieldops.db import session_scope
    from fieldops.dedup import dedup_ticket, embed_ticket
    from fieldops.models import Embedding
    from fieldops.pipeline.ingest import ingest_record

    fake = FakeEmbedder(get_settings().embedding_dim)
    # Unique per run so leftover rows in the persistent dev DB can't match.
    run = uuid.uuid4().hex[:8]
    same = f"Hydrant leaking onto the street {run}"

    with session_scope() as session:
        t1 = ingest_record(session, _raw(f"{run}-1", same, "2024-05-01T09:00:00.000"))
        t2 = ingest_record(session, _raw(f"{run}-2", same, "2024-05-01T11:00:00.000"))
        t3_text = f"Sidewalk cracked and uneven {run}"
        t3 = ingest_record(session, _raw(f"{run}-3", t3_text, "2024-05-01T10:00:00.000"))
        t1_id, t2_id, t3_id = t1.id, t2.id, t3.id

        for ticket in (t1, t2, t3):
            embed_ticket(session, ticket, fake)
            assert session.get(Embedding, ticket.id) is not None

        # t2 duplicates the earlier t1 (identical text, same place, same day).
        canonical = dedup_ticket(session, session.get(Ticket, t2_id))
        assert canonical is not None and canonical.id == t1_id

        # t3 is unrelated -> no canonical.
        assert dedup_ticket(session, session.get(Ticket, t3_id)) is None

        session.flush()
        assert session.get(Ticket, t2_id).status == TicketStatus.DUPLICATE
        assert session.get(Ticket, t2_id).duplicate_of == t1_id
        assert session.get(Ticket, t1_id).report_count == 2


def test_run_backfill_ingests_from_mocked_socrata(db_ready):  # noqa: ARG001
    from fieldops.db import session_scope
    from fieldops.ingest.backfill import run_backfill
    from fieldops.ingest.socrata import SodaClient

    records = [_raw("bf-1", "Pothole on the corner", "2024-06-01T08:00:00.000")]

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(httpx.QueryParams(request.url.query).get("$offset", "0"))
        return httpx.Response(200, json=records if offset == 0 else [])

    client = SodaClient(transport=httpx.MockTransport(handler))
    n = run_backfill(client, months=12)
    assert n == 1
    # Idempotent: a second run upserts, no duplicate ticket row (NFR-3.2).
    run_backfill(client, months=12)
    with session_scope() as session:
        count = session.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.unique_key == "bf-1")
        )
    assert count == 1
