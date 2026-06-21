"""Dedup eval harness (FR-2, FR-8.1/8.9/8.14).

Loads labeled pairs, scores a prediction function against the ground-truth
`label`, and reports precision/recall/F1 ([NFR-4.2](dedup precision ≥ 0.90))
plus inter-annotator agreement (Cohen's kappa) over the two annotator columns.

The dataset is versioned with a card (`dedup_pairs.CARD.md`); the labeled file is
the frozen eval split (FR-8.9). Phase-1 pairs are synthetic and tagged as such.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import resources

from .metrics import cohen_kappa, precision_recall_f1


@dataclass(frozen=True)
class DedupPair:
    text_a: str
    text_b: str
    label: bool  # ground truth: are these the same underlying report?
    ann1: bool
    ann2: bool


def load_pairs(text: str | None = None) -> list[DedupPair]:
    """Load labeled pairs from JSONL (bundled `data/dedup_pairs.jsonl` by default)."""
    if text is None:
        text = resources.files("fieldops.data").joinpath("dedup_pairs.jsonl").read_text()
    pairs = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        pairs.append(
            DedupPair(d["text_a"], d["text_b"], bool(d["label"]), bool(d["ann1"]), bool(d["ann2"]))
        )
    return pairs


def annotator_agreement(pairs: Iterable[DedupPair]) -> float:
    pairs = list(pairs)
    return cohen_kappa([p.ann1 for p in pairs], [p.ann2 for p in pairs])


def evaluate(pairs: Iterable[DedupPair], predict: Callable[[DedupPair], bool]) -> dict:
    """Run `predict` over the pairs; return metrics + annotator kappa."""
    pairs = list(pairs)
    y_true = [p.label for p in pairs]
    y_pred = [bool(predict(p)) for p in pairs]
    metrics = precision_recall_f1(y_true, y_pred)
    metrics["n"] = len(pairs)
    metrics["annotator_kappa"] = annotator_agreement(pairs)
    return metrics
