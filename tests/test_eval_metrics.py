"""Eval metric + dedup-harness tests (sub-phase 1.6, FR-8.1/8.14)."""
from __future__ import annotations

import pytest

from fieldops.eval import cohen_kappa, precision_recall_f1
from fieldops.eval.dedup_eval import annotator_agreement, evaluate, load_pairs


def test_precision_recall_f1_basic():
    y_true = [True, True, False, False]
    y_pred = [True, False, False, False]
    m = precision_recall_f1(y_true, y_pred)
    assert m["precision"] == pytest.approx(1.0)  # 1 tp, 0 fp
    assert m["recall"] == pytest.approx(0.5)  # 1 tp, 1 fn
    assert m["f1"] == pytest.approx(2 / 3)


def test_precision_recall_length_mismatch():
    with pytest.raises(ValueError):
        precision_recall_f1([True], [True, False])


def test_cohen_kappa_perfect_and_chance():
    assert cohen_kappa([True, False, True], [True, False, True]) == pytest.approx(1.0)
    # all-agree-on-one-label => pe == 1 => defined as 1.0
    assert cohen_kappa([True, True], [True, True]) == pytest.approx(1.0)


def test_bundled_pairs_load_and_perfect_predictor():
    pairs = load_pairs()
    assert len(pairs) == 10
    # An oracle predictor (returns the label) must score precision/recall 1.0.
    m = evaluate(pairs, predict=lambda p: p.label)
    assert m["precision"] == pytest.approx(1.0)
    assert m["recall"] == pytest.approx(1.0)
    assert m["n"] == 10


def test_annotator_agreement_is_high_but_imperfect():
    # Two of ten pairs have annotator disagreement by construction.
    kappa = annotator_agreement(load_pairs())
    assert 0.5 < kappa < 1.0
