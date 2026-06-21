"""PII redaction tests (sub-phase 1.3, FR-10.1)."""
from __future__ import annotations

from fieldops.guardrails import contains_pii, redact


def test_redacts_phone():
    out = redact("Call me at 718-555-0142 about the leak")
    assert "[REDACTED_PHONE]" in out
    assert "555" not in out


def test_redacts_email():
    out = redact("Reach reporter@example.com regarding the hydrant")
    assert "[REDACTED_EMAIL]" in out
    assert "@example.com" not in out


def test_redacts_street_address():
    out = redact("Flooding at 123 Flatbush Avenue near the corner")
    assert "[REDACTED_ADDRESS]" in out
    assert "Flatbush" not in out


def test_keeps_clean_text():
    text = "Hydrant leaking onto the street, water pooling"
    assert redact(text) == text
    assert not contains_pii(text)


def test_contains_pii_detects():
    assert contains_pii("ring 2125550199")
    assert not contains_pii("just a sidewalk crack")


def test_redact_handles_none_and_empty():
    assert redact(None) is None
    assert redact("") == ""
