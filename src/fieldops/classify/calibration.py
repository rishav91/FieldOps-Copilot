"""Confidence calibration (sub-phase 2.5, FR-3.4, ADR-007).

Isotonic regression (pool-adjacent-violators) maps a raw classifier confidence to
a calibrated probability — non-parametric, monotonic, and dependency-free
(Platt's logistic fit is the parametric alternative; isotonic is more flexible
and the right default when the reliability curve isn't sigmoidal).

Fit on a held-out split; evaluate ECE on the test split (EVAL-SPEC §2).
"""
from __future__ import annotations

import bisect
from collections.abc import Sequence


def _pava(values: list[float]) -> list[float]:
    """Pool-adjacent-violators: nearest non-decreasing fit (L2) to `values`."""
    # Each block: [sum, count]; merge while the previous mean exceeds the next.
    blocks: list[list[float]] = []
    for v in values:
        blocks.append([v, 1])
        while len(blocks) >= 2 and blocks[-2][0] / blocks[-2][1] >= blocks[-1][0] / blocks[-1][1]:
            s2, c2 = blocks.pop()
            s1, c1 = blocks.pop()
            blocks.append([s1 + s2, c1 + c2])
    fitted: list[float] = []
    for s, c in blocks:
        fitted.extend([s / c] * int(c))
    return fitted


class IsotonicCalibrator:
    """Monotonic raw-confidence → calibrated-probability mapping."""

    def __init__(self) -> None:
        self._x: list[float] = []
        self._y: list[float] = []

    def fit(self, confidences: Sequence[float], correct: Sequence[bool]) -> IsotonicCalibrator:
        if len(confidences) != len(correct):
            raise ValueError("confidences and correct must be the same length")
        if not confidences:
            return self
        order = sorted(range(len(confidences)), key=lambda i: confidences[i])
        xs = [float(confidences[i]) for i in order]
        ys = [1.0 if correct[i] else 0.0 for i in order]
        self._x, self._y = xs, _pava(ys)
        return self

    def predict_one(self, confidence: float) -> float:
        if not self._x:
            return confidence  # unfitted → identity
        if confidence <= self._x[0]:
            return self._y[0]
        if confidence >= self._x[-1]:
            return self._y[-1]
        i = bisect.bisect_right(self._x, confidence) - 1
        return self._y[i]

    def predict(self, confidences: Sequence[float]) -> list[float]:
        return [self.predict_one(c) for c in confidences]
