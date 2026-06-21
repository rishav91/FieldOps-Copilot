"""Calibration tests (sub-phase 2.5)."""
from __future__ import annotations

import pytest

from fieldops.classify.calibration import IsotonicCalibrator
from fieldops.eval.calibration import expected_calibration_error, reliability_curve


def test_ece_zero_when_calibrated():
    # Confidence 0.5 with exactly 50% correct -> perfectly calibrated bin.
    conf = [0.5] * 10
    correct = [True] * 5 + [False] * 5
    assert expected_calibration_error(conf, correct) == pytest.approx(0.0)


def test_ece_positive_when_overconfident():
    conf = [0.9] * 10
    correct = [True] * 5 + [False] * 5  # 50% accurate but 90% confident
    assert expected_calibration_error(conf, correct) == pytest.approx(0.4)


def test_reliability_curve_bins():
    bins = reliability_curve([0.1, 0.15, 0.95], [False, False, True], n_bins=10)
    assert bins[0].count == 2 and bins[0].accuracy == 0.0
    assert bins[-1].count == 1 and bins[-1].accuracy == 1.0


def test_isotonic_is_monotonic_and_reduces_ece():
    # Overconfident, varied: higher confidence isn't matched by accuracy.
    conf = [0.6, 0.7, 0.8, 0.9, 0.6, 0.7, 0.8, 0.9]
    correct = [False, False, True, False, False, True, False, True]
    cal = IsotonicCalibrator().fit(conf, correct)
    preds = cal.predict(conf)
    # monotonic non-decreasing in the calibrated mapping
    pairs = sorted(zip(conf, preds))
    assert all(pairs[i][1] <= pairs[i + 1][1] + 1e-9 for i in range(len(pairs) - 1))
    # calibration should not worsen ECE
    before = expected_calibration_error(conf, correct)
    after = expected_calibration_error(preds, correct)
    assert after <= before + 1e-9


def test_unfitted_calibrator_is_identity():
    cal = IsotonicCalibrator()
    assert cal.predict_one(0.42) == 0.42
