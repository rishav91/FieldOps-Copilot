"""Cascade escalation tests (sub-phase 2.3) — DB-gated, injected fake LLMs."""
from __future__ import annotations

import random
import uuid

import pytest
from sqlalchemy.exc import OperationalError

from fieldops.config import get_settings
from fieldops.llm.base import CompletionResult


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


class _FakeLLM:
    provider = "fake"
    model = "fake"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list = []

    def complete(self, messages, **_kw) -> CompletionResult:
        self.calls.append(messages)
        return CompletionResult(text=self.text, model=self.model, provider=self.provider)

    def embed(self, texts):  # pragma: no cover
        raise NotImplementedError


@pytest.fixture(scope="module")
def db_ready():
    from fieldops.db import init_db

    try:
        init_db()
    except OperationalError as exc:
        pytest.skip(f"Postgres not reachable: {exc}")


def _raw(uk: str, text: str, agency: str) -> dict:
    return {
        "unique_key": uk,
        "created_date": "2024-08-01T09:00:00.000",
        "complaint_type": "Water System",
        "descriptor": text,
        "agency": agency,
        "borough": "BROOKLYN",
        "latitude": "40.6782",
        "longitude": "-73.9442",
    }


def _seed(session, texts_agencies: list[tuple[str, str]], fake_embed):
    from fieldops.dedup import embed_ticket
    from fieldops.pipeline.ingest import ingest_record

    last = None
    for i, (text, agency) in enumerate(texts_agencies):
        t = ingest_record(session, _raw(f"{text}-{i}", text, agency))
        embed_ticket(session, t, fake_embed)
        last = t
    return last


def test_cheap_confident_does_not_call_llm(db_ready):  # noqa: ARG001
    from fieldops.classify import classify_cascade
    from fieldops.db import session_scope
    from fieldops.models import Ticket

    fake_embed = _FakeEmbedder(get_settings().embedding_dim)
    run = uuid.uuid4().hex[:8]
    groq = _FakeLLM('{"agency": "DOT", "confidence": 0.99}')

    with session_scope() as session:
        text = f"water main break {run}"
        _seed(session, [(text, "DEP"), (text, "DEP"), (text, "DEP")], fake_embed)
        query = _seed(session, [(text, "DEP")], fake_embed)

        pred = classify_cascade(session, session.get(Ticket, query.id), groq=groq, openai=None)
        assert pred.agency == "DEP" and pred.tier == "cheap-knn"
        assert groq.calls == []  # cheap was confident -> LLM never called


def test_low_confidence_escalates_to_groq(db_ready):  # noqa: ARG001
    from fieldops.classify import classify_cascade
    from fieldops.db import session_scope
    from fieldops.models import Ticket

    fake_embed = _FakeEmbedder(get_settings().embedding_dim)
    run = uuid.uuid4().hex[:8]
    groq = _FakeLLM('{"agency": "DEP", "confidence": 0.95}')

    with session_scope() as session:
        # Same text, three different agencies -> a 1/3 vote tie -> escalate.
        text = f"ambiguous overflow {run}"
        _seed(session, [(text, "DEP"), (text, "DOT"), (text, "DPR")], fake_embed)
        query = _seed(session, [(text, "DEP")], fake_embed)

        pred = classify_cascade(session, session.get(Ticket, query.id), groq=groq, openai=None)
        assert pred.tier == "groq" and pred.agency == "DEP"
        assert len(groq.calls) == 1
