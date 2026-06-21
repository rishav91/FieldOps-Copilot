"""PII redaction (FR-10.1, NFR-8.4).

311 free text carries addresses, phone numbers, and emails. We redact them
**before** any text leaves the boundary to an external LLM (embeddings, agent,
drafting) or telemetry. Regex-based for the skeleton: high-precision on phone /
email / street address.

Known limitation: personal *names* need NER, not regex — out of scope here and
flagged for a later pass. The redaction is intentionally conservative (favors a
false redaction over leaking PII).
"""
from __future__ import annotations

import re

# Order matters: emails before phones (an email can contain digit runs).
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"
)
_STREET_SUFFIX = (
    r"street|st|avenue|ave|boulevard|blvd|road|rd|lane|ln|drive|dr|court|ct|"
    r"place|pl|way|terrace|ter|parkway|pkwy|plaza|sq|square"
)
_ADDRESS = re.compile(
    rf"\b\d{{1,5}}\s+(?:[A-Za-z0-9.'-]+\s){{0,4}}(?:{_STREET_SUFFIX})\b\.?",
    re.IGNORECASE,
)

_REPLACEMENTS = (
    (_EMAIL, "[REDACTED_EMAIL]"),
    (_PHONE, "[REDACTED_PHONE]"),
    (_ADDRESS, "[REDACTED_ADDRESS]"),
)


def redact(text: str | None) -> str | None:
    """Return `text` with emails, phones, and street addresses masked."""
    if not text:
        return text
    for pattern, token in _REPLACEMENTS:
        text = pattern.sub(token, text)
    return text


def contains_pii(text: str | None) -> bool:
    """True if any redactable PII pattern is present."""
    if not text:
        return False
    return any(pattern.search(text) for pattern, _ in _REPLACEMENTS)
