"""Offline smoke tests — no DB, no LLM keys required."""
from __future__ import annotations

from datetime import datetime

import pytest

from fieldops.config import get_settings
from fieldops.llm import Tier, get_llm
from fieldops.llm.base import ChatMessage, LLMClient
from fieldops.pipeline.draft import _draft_hash
from fieldops.pipeline.ingest import _parse_dt, _to_float, load_sample_record
from fieldops.tracing import span, trace


def test_settings_load():
    s = get_settings()
    assert s.embedding_dim == 1536
    assert s.target_borough == "BROOKLYN"


def test_sample_record_shape():
    raw = load_sample_record()
    assert raw["unique_key"] == "59812345"
    assert raw["agency"] == "DEP"
    assert raw["borough"] == "BROOKLYN"


def test_normalize_helpers():
    assert _to_float("40.67") == pytest.approx(40.67)
    assert _to_float("") is None
    assert _parse_dt(None) is None
    assert _parse_dt("2024-03-14T08:21:00.000") == datetime(2024, 3, 14, 8, 21)


def test_draft_hash_is_deterministic_and_content_sensitive():
    d1 = {"owner": "DEP", "next_action": "x"}
    assert _draft_hash("t1", d1) == _draft_hash("t1", d1)
    assert _draft_hash("t1", d1) != _draft_hash("t1", {"owner": "HPD", "next_action": "x"})


def test_factory_requires_keys_offline():
    # No keys in the test env -> constructing a client fails fast, no network call.
    with pytest.raises(ValueError):
        get_llm(Tier.AGENT)


def test_chatmessage_and_protocol():
    msg = ChatMessage("user", "hi")
    assert msg.role == "user"
    # Protocol is runtime-checkable; a bare object is not an LLMClient.
    assert not isinstance(object(), LLMClient)


def test_tracing_runs_without_backend():
    with trace(ticket_id="t-123") as tid:
        assert tid
        with span("unit.test", foo=1) as data:
            data["bar"] = 2
