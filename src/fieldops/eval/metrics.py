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


def macro_f1(y_true: Sequence[object], y_pred: Sequence[object]) -> float:
    """Unweighted mean of per-class one-vs-rest F1 (multiclass routing, NFR-4.2)."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")
    classes = sorted({c for c in (*y_true, *y_pred) if c is not None}, key=str)
    if not classes:
        return 0.0
    f1s = []
    for c in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    return sum(f1s) / len(f1s)


def confusion_matrix(
    y_true: Sequence[object], y_pred: Sequence[object]
) -> dict[object, dict[object, int]]:
    """Nested dict: matrix[true][pred] = count."""
    matrix: dict[object, dict[object, int]] = {}
    for t, p in zip(y_true, y_pred):
        matrix.setdefault(t, {})
        matrix[t][p] = matrix[t].get(p, 0) + 1
    return matrix


def cheap_tier_false_confidence(
    records: Sequence[tuple[str, float, bool]], min_confidence: float
) -> tuple[float, int]:
    """Among high-confidence cheap-tier calls that *skip the gate*, the wrong rate.

    `records` are (tier, raw_confidence, correct). This bounds the silent
    mis-route rate the gate can't catch (FR-8.11) — the safety-critical metric.
    Returns (false_confidence_rate, n_high_confidence_cheap).
    """
    hot = [
        ok for tier, conf, ok in records if tier.startswith("cheap") and conf >= min_confidence
    ]
    if not hot:
        return 0.0, 0
    wrong = sum(1 for ok in hot if not ok)
    return wrong / len(hot), len(hot)


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
