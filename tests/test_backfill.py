"""Backfill query-construction tests (sub-phase 1.2) — offline, no DB."""
from __future__ import annotations

from collections.abc import Iterator

from fieldops.ingest.backfill import TOP_COMPLAINT_TYPES, backfill_window, run_backfill


class _FakeClient:
    """Records the args it's called with; yields a canned record stream."""

    def __init__(self, records: list[dict] | None = None) -> None:
        self.records = records or []
        self.calls: list[dict] = []

    def iter_records(self, *, where=None, order=None, max_records=None) -> Iterator[dict]:
        self.calls.append({"where": where, "order": order, "max_records": max_records})
        yield from self.records


def test_backfill_window_spans_months():
    start, end = backfill_window(months=12)
    assert start < end


def test_run_backfill_builds_filtered_where():
    client = _FakeClient(records=[])  # empty stream => no DB writes
    n = run_backfill(client, months=12)
    assert n == 0
    where = client.calls[0]["where"]
    assert "upper(borough)='BROOKLYN'" in where
    assert "complaint_type in(" in where
    assert TOP_COMPLAINT_TYPES[0] in where
    assert "created_date>=" in where and "created_date<" in where


def test_run_backfill_forwards_max_records():
    client = _FakeClient(records=[])
    run_backfill(client, max_records=250)
    assert client.calls[0]["max_records"] == 250
