"""Backfill + incremental delta over the 311 stream (FR-1).

`run_backfill` loads a trailing window (default 12 months) for the target
borough; `run_delta` pulls only what's newer than the highest `created_date`
already stored (the watermark). Both normalize via `pipeline.ingest.ingest_record`,
so re-runs are idempotent (upsert by `unique_key`, NFR-3.2).
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta, timezone
from itertools import islice

from sqlalchemy import func, select

from ..config import get_settings
from ..db import session_scope
from ..models import Ticket
from ..pipeline.ingest import ingest_record
from ..tracing import span, trace
from .socrata import SodaClient, soql_where

# Curated top-10 complaint types with genuine free-text descriptors (PRD §5).
# Starting set — refine against the live distribution during profiling (1.7).
TOP_COMPLAINT_TYPES = [
    "Water System",
    "Sewer",
    "Street Condition",
    "Street Light Condition",
    "Sidewalk Condition",
    "Damaged Tree",
    "Noise - Residential",
    "HEAT/HOT WATER",
    "Plumbing",
    "General Construction",
]


def socrata_ts(dt: datetime) -> str:
    """Format a datetime as a Socrata floating timestamp (no tz, ms precision).

    SoQL rejects a timezone offset / microseconds on `created_date` comparisons,
    so '2025-06-21T10:39:47.066' is the accepted shape.
    """
    return dt.replace(tzinfo=None).isoformat(timespec="milliseconds")


def backfill_window(months: int = 12, now: datetime | None = None) -> tuple[str, str]:
    """Return (start, end) as Socrata floating timestamps for a trailing window."""
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=round(months * 30.4375))
    return socrata_ts(start), socrata_ts(now)


def watermark() -> datetime | None:
    """Highest `created_date` already ingested — the delta cursor."""
    with session_scope() as session:
        return session.scalar(select(func.max(Ticket.created_date)))


def _ingest_stream(records: Iterable[dict], batch_size: int) -> int:
    """Ingest records in batches, one transaction per batch. Returns the count."""
    count = 0
    it: Iterator[dict] = iter(records)
    while True:
        batch = list(islice(it, batch_size))
        if not batch:
            return count
        with session_scope() as session:
            for raw in batch:
                ingest_record(session, raw)
                count += 1


def run_backfill(
    client: SodaClient | None = None,
    *,
    months: int = 12,
    batch_size: int = 500,
    max_records: int | None = None,
) -> int:
    client = client or SodaClient()
    s = get_settings()
    start, end = backfill_window(months)
    where = soql_where(
        borough=s.target_borough,
        complaint_types=TOP_COMPLAINT_TYPES,
        start_date=start,
        end_date=end,
    )
    with trace(), span("ingest.backfill", borough=s.target_borough, months=months) as sp:
        n = _ingest_stream(
            client.iter_records(where=where, order="created_date", max_records=max_records),
            batch_size,
        )
        sp["ingested"] = n
        return n


def run_delta(
    client: SodaClient | None = None,
    *,
    batch_size: int = 500,
    max_records: int | None = None,
) -> int:
    client = client or SodaClient()
    s = get_settings()
    wm = watermark()
    where = soql_where(
        borough=s.target_borough,
        complaint_types=TOP_COMPLAINT_TYPES,
        start_date=socrata_ts(wm) if wm else None,
    )
    with trace(), span("ingest.delta", since=wm.isoformat() if wm else None) as sp:
        n = _ingest_stream(
            client.iter_records(where=where, order="created_date", max_records=max_records),
            batch_size,
        )
        sp["ingested"] = n
        return n
