"""Classification eval tests (sub-phase 2.7)."""
from __future__ import annotations

import pytest

from fieldops.eval import cheap_tier_false_confidence, confusion_matrix, macro_f1


def test_macro_f1_perfect():
    assert macro_f1(["DEP", "DOT", "HPD"], ["DEP", "DOT", "HPD"]) == pytest.approx(1.0)


def test_macro_f1_penalizes_errors():
    # One of two DEP predicted as DOT.
    f1 = macro_f1(["DEP", "DEP", "DOT"], ["DEP", "DOT", "DOT"])
    assert 0.0 < f1 < 1.0


def test_confusion_matrix_counts():
    cm = confusion_matrix(["DEP", "DEP", "DOT"], ["DEP", "DOT", "DOT"])
    assert cm["DEP"] == {"DEP": 1, "DOT": 1}
    assert cm["DOT"] == {"DOT": 1}


def test_cheap_false_confidence_flags_wrong_high_conf():
    records = [
        ("cheap-knn", 0.9, True),   # high-conf, correct
        ("cheap-knn", 0.9, False),  # high-conf, WRONG -> counts
        ("cheap-knn", 0.4, False),  # low-conf -> ignored (would hit the gate)
        ("groq", 0.9, False),       # not cheap tier -> ignored
    ]
    rate, n = cheap_tier_false_confidence(records, min_confidence=0.7)
    assert n == 2 and rate == pytest.approx(0.5)


def test_cheap_false_confidence_none_qualifying():
    rate, n = cheap_tier_false_confidence([("cheap-knn", 0.3, False)], min_confidence=0.7)
    assert n == 0 and rate == 0.0
