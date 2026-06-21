"""Multi-agency detection tests (sub-phase 2.4)."""
from __future__ import annotations

from fieldops.classify.multilabel import candidate_agencies, detect_multi_agency


def test_ceiling_and_floor_is_multi_agency():
    # water (DEP) + structural (DOB) -> the canonical multi-agency case (PRD UC3).
    m = detect_multi_agency("Water System", "Water from the ceiling and the floor is buckling")
    assert m.is_multi
    assert m.agencies == frozenset({"DEP", "DOB"})


def test_single_issue_is_not_multi():
    m = detect_multi_agency("Water System", "Hydrant leaking onto the street")
    assert not m.is_multi
    assert m.agencies == frozenset({"DEP"})


def test_candidate_agencies_empty_for_unmatched_text():
    assert candidate_agencies("Other", "something unclassifiable") == frozenset()


def test_handles_missing_text():
    assert not detect_multi_agency(None, None).is_multi
