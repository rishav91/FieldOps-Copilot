"""Socrata SODA client tests (sub-phase 1.1) — fully offline via MockTransport."""
from __future__ import annotations

import httpx
import pytest

from fieldops.ingest import SodaClient, soql_where


def test_soql_where_builds_and_joins():
    where = soql_where(
        borough="brooklyn",
        complaint_types=["Water System", "Sewer"],
        start_date="2024-01-01",
        end_date="2025-01-01",
    )
    assert where == (
        "upper(borough)='BROOKLYN' AND complaint_type in('Water System','Sewer') "
        "AND created_date>='2024-01-01' AND created_date<'2025-01-01'"
    )


def test_soql_where_empty_is_none():
    assert soql_where() is None


def test_fetch_page_sends_params_token_and_returns_rows():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["token"] = request.headers.get("X-App-Token")
        return httpx.Response(200, json=[{"unique_key": "1"}, {"unique_key": "2"}])

    client = SodaClient(app_token="secret", transport=httpx.MockTransport(handler))
    rows = client.fetch_page(where="upper(borough)='BROOKLYN'", limit=2, offset=0)

    assert [r["unique_key"] for r in rows] == ["1", "2"]
    assert seen["token"] == "secret"
    assert "%24limit=2" in seen["url"] or "$limit=2" in seen["url"]
    assert "erm2-nwe9.json" in seen["url"]


def test_fetch_page_raises_on_error():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    client = SodaClient(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_page()


def test_iter_records_pages_until_short_page():
    # Two full pages (size 2) then a short page of 1 → stops; 5 records total.
    pages = [
        [{"unique_key": "1"}, {"unique_key": "2"}],
        [{"unique_key": "3"}, {"unique_key": "4"}],
        [{"unique_key": "5"}],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(httpx.QueryParams(request.url.query).get("$offset", "0"))
        idx = offset // 2
        return httpx.Response(200, json=pages[idx] if idx < len(pages) else [])

    client = SodaClient(page_size=2, transport=httpx.MockTransport(handler))
    got = [r["unique_key"] for r in client.iter_records()]
    assert got == ["1", "2", "3", "4", "5"]


def test_iter_records_respects_max():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"unique_key": "1"}, {"unique_key": "2"}])

    client = SodaClient(page_size=2, transport=httpx.MockTransport(handler))
    got = [r["unique_key"] for r in client.iter_records(max_records=3)]
    assert got == ["1", "2", "1"]  # page1 (2) + first of page2 (1) = 3
