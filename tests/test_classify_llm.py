"""LLM classify-step tests (sub-phase 2.3) — offline with a fake client."""
from __future__ import annotations

from types import SimpleNamespace

from fieldops.classify import classify_llm
from fieldops.llm.base import CompletionResult


class _FakeLLM:
    provider = "fake"
    model = "fake"

    def __init__(self, text: str = "", raise_exc: bool = False) -> None:
        self.text = text
        self.raise_exc = raise_exc
        self.calls: list = []

    def complete(self, messages, **_kw) -> CompletionResult:
        self.calls.append(messages)
        if self.raise_exc:
            raise RuntimeError("provider down")
        return CompletionResult(text=self.text, model=self.model, provider=self.provider)

    def embed(self, texts):  # pragma: no cover
        raise NotImplementedError


_TICKET = SimpleNamespace(complaint_type="Water System", descriptor="hydrant leaking")


def test_valid_json_yields_prediction():
    pred = classify_llm(_TICKET, _FakeLLM('{"agency": "DEP", "confidence": 0.9}'), tier_name="groq")
    assert pred.agency == "DEP"
    assert pred.confidence == 0.9
    assert pred.tier == "groq"


def test_out_of_enum_agency_is_malformed_low_confidence():
    fake = _FakeLLM('{"agency": "FBI", "confidence": 0.99}')
    pred = classify_llm(_TICKET, fake, tier_name="groq")
    assert pred.agency is None
    assert pred.confidence == 0.0
    assert pred.tier == "groq-malformed"


def test_unparseable_output_is_safe():
    pred = classify_llm(_TICKET, _FakeLLM("I think it's the water department"), tier_name="openai")
    assert pred.agency is None and pred.tier == "openai-malformed"


def test_provider_exception_is_caught():
    pred = classify_llm(_TICKET, _FakeLLM(raise_exc=True), tier_name="groq")
    assert pred.agency is None and pred.tier == "groq-error"


def test_pii_is_redacted_before_send():
    fake = _FakeLLM('{"agency": "HPD", "confidence": 0.8}')
    ticket = SimpleNamespace(
        complaint_type="Plumbing", descriptor="call 718-555-0142 at 50 Main Street"
    )
    classify_llm(ticket, fake, tier_name="groq")
    sent = fake.calls[0][1].content  # user message
    assert "718-555-0142" not in sent and "[REDACTED_PHONE]" in sent
    assert "Main Street" not in sent and "[REDACTED_ADDRESS]" in sent
