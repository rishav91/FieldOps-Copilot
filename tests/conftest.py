"""Shared test fixtures.

The DB-gated tests insert a few fixture vectors and expect *exact* nearest-
neighbor recall. pgvector's HNSW index is **approximate**, and once the dev DB
holds thousands of real vectors (after a gate-run backfill), the approximate
search can miss isolated fixture vectors — making those tests flaky. Raising
`hnsw.ef_search` on each test connection restores high recall for the tiny
fixture sets without affecting production behavior.
"""
from __future__ import annotations

import pytest
from sqlalchemy import event


@pytest.fixture(autouse=True, scope="session")
def _high_recall_ann() -> None:
    from fieldops.db import engine

    eng = engine()

    @event.listens_for(eng, "connect")
    def _set_ef_search(dbapi_conn, _rec):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("SET hnsw.ef_search = 1000")
        cur.close()

    # Apply to any pooled connections already open.
    eng.dispose()
