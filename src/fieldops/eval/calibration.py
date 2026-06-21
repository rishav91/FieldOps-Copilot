"""Calibration metrics (sub-phase 2.5, EVAL-SPEC §3).

Expected Calibration Error (ECE) and the reliability curve — how well a
confidence score matches observed accuracy. The whole deterministic/agentic gate
rests on a calibrated score (ADR-007), so ECE ≤ 0.05 is a first-class target
(NFR-4.1).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ReliabilityBin:
    lo: float
    hi: float
    confidence: float  # mean predicted confidence in the bin
    accuracy: float    # observed fraction correct
    count: int


def reliability_curve(
    confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 10
) -> list[ReliabilityBin]:
    """Bin predictions into equal-width confidence bins → (conf, accuracy, n)."""
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must be the same length")
    sums = [[0.0, 0, 0] for _ in range(n_bins)]  # sum_conf, n_correct, count
    for conf, ok in zip(confidences, correct):
        b = min(int(conf * n_bins), n_bins - 1)
        sums[b][0] += conf
        sums[b][1] += 1 if ok else 0
        sums[b][2] += 1
    out = []
    for b, (sconf, ncorr, cnt) in enumerate(sums):
        if cnt == 0:
            continue
        out.append(
            ReliabilityBin(
                lo=b / n_bins,
                hi=(b + 1) / n_bins,
                confidence=sconf / cnt,
                accuracy=ncorr / cnt,
                count=cnt,
            )
        )
    return out


def expected_calibration_error(
    confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 10
) -> float:
    """Weighted average gap between confidence and accuracy across bins."""
    n = len(confidences)
    if n == 0:
        return 0.0
    ece = 0.0
    for b in reliability_curve(confidences, correct, n_bins):
        ece += (b.count / n) * abs(b.accuracy - b.confidence)
    return ece
