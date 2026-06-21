"""Shared classification result type (Phase 2)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prediction:
    """A routing prediction with a *raw* (uncalibrated) confidence.

    `tier` records which cascade stage produced it (cheap-knn / groq / openai /
    prior); calibration (2.5) maps `confidence` → a calibrated probability.
    """

    agency: str | None
    confidence: float  # raw, in [0, 1]
    tier: str
    neighbors: int = 0
