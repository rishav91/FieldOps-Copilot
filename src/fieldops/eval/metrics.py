"""Discriminative metrics (EVAL-SPEC §3) — pure, unit-testable.

Used by the dedup eval (FR-8.1) and reused later for classification. Inter-
annotator agreement (Cohen's kappa) backs the labeled-set governance (FR-8.14).
"""
from __future__ import annotations

from collections.abc import Sequence


def precision_recall_f1(y_true: Sequence[bool], y_pred: Sequence[bool]) -> dict[str, float]:
    """Binary precision/recall/F1 for the positive (duplicate) class."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if (not t) and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and (not p))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def cohen_kappa(a: Sequence[object], b: Sequence[object]) -> float:
    """Cohen's kappa between two annotators' label sequences."""
    if len(a) != len(b):
        raise ValueError("annotator sequences must be the same length")
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    categories = set(a) | set(b)
    pe = sum((list(a).count(c) / n) * (list(b).count(c) / n) for c in categories)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)
