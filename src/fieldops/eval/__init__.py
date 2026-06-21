"""Offline evaluation harnesses (EVAL-SPEC). Dedup (P1) + classification (P2)."""
from .metrics import (
    cheap_tier_false_confidence,
    cohen_kappa,
    confusion_matrix,
    macro_f1,
    precision_recall_f1,
)

__all__ = [
    "precision_recall_f1",
    "cohen_kappa",
    "macro_f1",
    "confusion_matrix",
    "cheap_tier_false_confidence",
]
