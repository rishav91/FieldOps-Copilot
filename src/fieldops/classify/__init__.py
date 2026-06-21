"""Classification + routing (FR-3, FR-4).

Phase 2 builds the cascade (cheap → Grok → OpenAI) with calibrated confidence
and the confidence gate. Sub-phase 2.1 lands the agency taxonomy.
"""
from .cascade import classify_cascade
from .cheap import classify_cheap, vote
from .llm_classify import classify_llm
from .taxonomy import (
    AGENCIES,
    COMPLAINT_TYPE_TO_AGENCY,
    ground_truth_agency,
    is_valid_agency,
    normalize_agency,
)
from .types import Prediction

__all__ = [
    "AGENCIES",
    "COMPLAINT_TYPE_TO_AGENCY",
    "ground_truth_agency",
    "is_valid_agency",
    "normalize_agency",
    "Prediction",
    "classify_cheap",
    "vote",
    "classify_llm",
    "classify_cascade",
]
