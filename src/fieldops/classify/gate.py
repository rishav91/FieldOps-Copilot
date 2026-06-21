"""Confidence gate (sub-phase 2.6, FR-4) — the deterministic/agentic fork.

A pure decision over the *calibrated* confidence plus the multi-agency flag:
route the easy majority on the fast path; send the low-confidence / multi-agency
tail to the agent. This is the single architectural fork (ARCHITECTURE §2); the
threshold is config-tunable without redeploy and stamped with `gate_version`.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import get_settings
from ..models import RoutingPath
from .types import Prediction

GATE_VERSION = "gate-v1"


@dataclass(frozen=True)
class GateDecision:
    path: RoutingPath
    calibrated_confidence: float | None
    reason: str
    gate_version: str = GATE_VERSION


def decide_gate(
    prediction: Prediction,
    calibrated_confidence: float | None,
    *,
    multi_agency: bool = False,
    threshold: float | None = None,
) -> GateDecision:
    """Fast vs. agent. Multi-agency and missing-agency always go to the agent."""
    threshold = get_settings().gate_threshold if threshold is None else threshold

    if multi_agency:
        return GateDecision(RoutingPath.AGENT, calibrated_confidence, "multi-agency")
    if prediction.agency is None:
        return GateDecision(RoutingPath.AGENT, calibrated_confidence, "no-agency")
    if calibrated_confidence is not None and calibrated_confidence >= threshold:
        return GateDecision(RoutingPath.FAST, calibrated_confidence, "high-confidence")
    return GateDecision(RoutingPath.AGENT, calibrated_confidence, "low-confidence")
