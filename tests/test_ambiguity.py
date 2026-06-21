"""Ambiguity heuristic tests (sub-phase 1.7)."""
from __future__ import annotations

from fieldops.profiling import classify_ticket_text
from fieldops.profiling.ambiguity import is_multi_issue, is_thin_text


def test_thin_text():
    assert is_thin_text("leak")
    assert is_thin_text("")
    assert is_thin_text(None)
    assert not is_thin_text("Water pouring from the ceiling onto the floor")


def test_multi_issue_two_categories():
    # water + structural => multi-issue (the canonical ambiguous case, PRD UC3)
    assert is_multi_issue("Water leak from ceiling and the floor is buckling")


def test_single_issue_not_multi():
    assert not is_multi_issue("Hydrant leaking water onto the street")


def test_classify_combines_flags():
    flags = classify_ticket_text("leak")
    assert flags["thin_text"] and flags["ambiguous"]
    clean = classify_ticket_text("Loud music from the upstairs apartment late at night")
    assert not clean["ambiguous"]
