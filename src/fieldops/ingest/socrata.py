"""Socrata SODA API client for NYC 311 (FR-1).

A thin, sync, testable client over the SODA endpoint. It does paging and lets
callers express SoQL filters (borough, complaint-type whitelist, date window);
it does **not** normalize — that's `pipeline.ingest` against the canonical model.

App-token auth (`X-App-Token`) lifts the anonymous rate limit. The client is
injectable with a custom httpx transport so tests run fully offline.
"""
from __future__ import annotations

from collections.abc import Iterator

import httpx

from ..config import get_settings
from ..tracing import span


def soql_where(
    *,
    borough: str | None = None,
    complaint_types: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str | None:
    """Build a SoQL `$where` clause from common 311 filters (AND-joined).

    Dates are ISO floating timestamps on `created_date`. Returns None when no
    filter is requested.
    """
    clauses: list[str] = []
    if borough:
        clauses.append(f"upper(borough)='{borough.upper()}'")
    if complaint_types:
        quoted = ",".join(f"'{c}'" for c in complaint_types)
        clauses.append(f"complaint_type in({quoted})")
    if start_date:
        clauses.append(f"created_date>='{start_date}'")
    if end_date:
        clauses.append(f"created_date<'{end_date}'")
    return " AND ".join(clauses) if clauses else None


class SodaClient:
    """Pages through a Socrata dataset's `.json` resource endpoint."""

    def __init__(
        self,
        *,
        domain: str | None = None,
        dataset_id: str | None = None,
        app_token: str | None = None,
        page_size: int | None = None,
        timeout_s: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        s = get_settings()
        self.domain = domain or s.socrata_domain
        self.dataset_id = dataset_id or s.socrata_dataset_id
        self.url = f"https://{self.domain}/resource/{self.dataset_id}.json"
        self.page_size = page_size or s.socrata_page_size
        self._headers = {}
        token = app_token if app_token is not None else s.socrata_app_token
        if token:
            self._headers["X-App-Token"] = token
        self._timeout = timeout_s if timeout_s is not None else s.socrata_timeout_s
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, transport=self._transport)

    def fetch_page(
        self,
        *,
        where: str | None = None,
        select: str | None = None,
        order: str = "created_date",
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        """Fetch one page of records. Raises on a non-2xx response."""
        params: dict[str, str | int] = {"$limit": limit or self.page_size, "$offset": offset}
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select
        if order:
            params["$order"] = order
        with span("ingest.socrata.fetch_page", offset=offset, limit=params["$limit"]) as sp:
            with self._client() as client:
                resp = client.get(self.url, params=params, headers=self._headers)
                resp.raise_for_status()
                rows = resp.json()
            sp["rows"] = len(rows)
            return rows

    def iter_records(
        self,
        *,
        where: str | None = None,
        order: str = "created_date",
        max_records: int | None = None,
    ) -> Iterator[dict]:
        """Yield records across pages until exhausted or `max_records` reached.

        Orders by a stable key so paging is consistent (Socrata paging without an
        order is not guaranteed stable).
        """
        offset = 0
        yielded = 0
        while True:
            page = self.fetch_page(where=where, order=order, limit=self.page_size, offset=offset)
            if not page:
                return
            for rec in page:
                yield rec
                yielded += 1
                if max_records is not None and yielded >= max_records:
                    return
            if len(page) < self.page_size:
                return
            offset += self.page_size
