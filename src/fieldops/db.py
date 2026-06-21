"""Engine, session, and one-shot schema init.

`init_db()` enables the pgvector extension *before* create_all (the Vector
column DDL needs it) — ADR-010.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings
from .models import Base

_engine = create_engine(get_settings().database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


def engine():
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commit on success, roll back on error (NFR-3.2)."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db() -> None:
    """Create the pgvector extension, all tables, and the ANN index. Idempotent."""
    with _engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(_engine)
    # HNSW index for cosine ANN over embeddings (FR-2 dedup / find_similar_tickets).
    # create_all can't express it, so add it explicitly after the table exists.
    with _engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS embedding_vector_hnsw "
                "ON embedding USING hnsw (vector vector_cosine_ops)"
            )
        )
