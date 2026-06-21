"""Agency taxonomy tests (sub-phase 2.1)."""
from __future__ import annotations

from fieldops.classify import (
    AGENCIES,
    COMPLAINT_TYPE_TO_AGENCY,
    ground_truth_agency,
    is_valid_agency,
    normalize_agency,
)
from fieldops.classify.taxonomy import agency_for_complaint_type


def test_normalize_agency():
    assert normalize_agency("  dep ") == "DEP"
    assert normalize_agency("") is None
    assert normalize_agency(None) is None


def test_is_valid_agency():
    assert is_valid_agency("DEP")
    assert is_valid_agency("hpd")  # normalized
    assert not is_valid_agency("FBI")
    assert not is_valid_agency(None)


def test_ground_truth_agency_from_payload():
    assert ground_truth_agency({"agency": "dep"}) == "DEP"
    assert ground_truth_agency({}) is None


def test_complaint_type_mapping_targets_valid_agencies():
    # Every mapped agency must be in the enum (keeps the prior consistent).
    for agency in COMPLAINT_TYPE_TO_AGENCY.values():
        assert agency in AGENCIES


def test_agency_for_complaint_type():
    assert agency_for_complaint_type("Water System") == "DEP"
    assert agency_for_complaint_type("Damaged Tree") == "DPR"
    assert agency_for_complaint_type("Unknown Type") is None
    assert agency_for_complaint_type(None) is None
