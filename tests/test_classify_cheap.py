"""Cheap kNN classifier tests (sub-phase 2.2)."""
from __future__ import annotations

import random

import pytest
from sqlalchemy.exc import OperationalError

from fieldops.classify import vote
from fieldops.config import get_settings


def test_vote_majority_and_fraction():
    agency, frac, n = vote(["DEP", "DEP", "DOT"])
    assert agency == "DEP"
    assert frac == pytest.approx(2 / 3)
    assert n == 3


def test_vote_ignores_invalid_and_empty():
    assert vote(["FBI", None, ""]) == (None, 0.0, 0)
    agency, frac, n = vote(["dep", "DEP"])  # normalized + counted
    assert agency == "DEP" and frac == 1.0 and n == 2


class _FakeEmbedder:
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


@pytest.fixture(scope="module")
def db_ready():
    from fieldops.db import init_db

    try:
        init_db()
    except OperationalError as exc:
        pytest.skip(f"Postgres not reachable: {exc}")


def _raw(uk: str, descriptor: str, agency: str) -> dict:
    return {
        "unique_key": uk,
        "created_date": "2024-07-01T09:00:00.000",
        "complaint_type": "Water System",
        "descriptor": descriptor,
        "agency": agency,
        "borough": "BROOKLYN",
        "latitude": "40.6782",
        "longitude": "-73.9442",
    }


def test_classify_cheap_votes_neighbor_agency(db_ready):  # noqa: ARG001
    import uuid

    from fieldops.classify import classify_cheap
    from fieldops.db import session_scope
    from fieldops.dedup import embed_ticket
    from fieldops.models import Ticket
    from fieldops.pipeline.ingest import ingest_record

    fake = _FakeEmbedder(get_settings().embedding_dim)
    run = uuid.uuid4().hex[:8]

    with session_scope() as session:
        # Three DEP-labeled "leak" tickets + a query ticket with the same text.
        for i in range(3):
            t = ingest_record(session, _raw(f"{run}-dep-{i}", f"water leak {run}", "DEP"))
            embed_ticket(session, t, fake)
        query = ingest_record(session, _raw(f"{run}-q", f"water leak {run}", "DEP"))
        embed_ticket(session, query, fake)

        pred = classify_cheap(session, session.get(Ticket, query.id), k=3)
        assert pred.agency == "DEP"
        assert pred.tier == "cheap-knn"
        assert pred.confidence == pytest.approx(1.0)
