"""Classification + routing (FR-3, FR-4).

Phase 2 builds the cascade (cheap → Grok → OpenAI) with calibrated confidence
and the confidence gate. Sub-phase 2.1 lands the agency taxonomy.
"""
from .taxonomy import (
    AGENCIES,
    COMPLAINT_TYPE_TO_AGENCY,
    ground_truth_agency,
    is_valid_agency,
    normalize_agency,
)

__all__ = [
    "AGENCIES",
    "COMPLAINT_TYPE_TO_AGENCY",
    "ground_truth_agency",
    "is_valid_agency",
    "normalize_agency",
]
