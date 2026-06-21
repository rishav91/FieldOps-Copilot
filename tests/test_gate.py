"""Confidence gate tests (sub-phase 2.6) — pure, offline."""
from __future__ import annotations

from fieldops.classify import Prediction, decide_gate
from fieldops.models import RoutingPath


def _pred(agency: str | None) -> Prediction:
    return Prediction(agency=agency, confidence=0.0, tier="cheap-knn")


def test_high_confidence_single_agency_goes_fast():
    d = decide_gate(_pred("DEP"), calibrated_confidence=0.9, threshold=0.75)
    assert d.path == RoutingPath.FAST and d.reason == "high-confidence"


def test_low_confidence_goes_agent():
    d = decide_gate(_pred("DEP"), calibrated_confidence=0.5, threshold=0.75)
    assert d.path == RoutingPath.AGENT and d.reason == "low-confidence"


def test_multi_agency_overrides_high_confidence():
    d = decide_gate(_pred("DEP"), calibrated_confidence=0.99, multi_agency=True, threshold=0.75)
    assert d.path == RoutingPath.AGENT and d.reason == "multi-agency"


def test_missing_agency_goes_agent():
    d = decide_gate(_pred(None), calibrated_confidence=0.99, threshold=0.75)
    assert d.path == RoutingPath.AGENT and d.reason == "no-agency"


def test_gate_version_stamped():
    d = decide_gate(_pred("DEP"), calibrated_confidence=0.9, threshold=0.75)
    assert d.gate_version == "gate-v1"
