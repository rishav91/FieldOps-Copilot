"""Agency taxonomy + 311 label mapping (sub-phase 2.1).

Two roles:
  1. The **valid agency enum** — the closed set LLM output must be a member of
     (FR-10.3); anything else is rejected.
  2. A `complaint_type → agency` reference map — a deterministic prior the cheap
     tier can fall back on, and the expected routing for multi-agency detection.

Ground truth is always the 311 `agency` field on the raw payload (ADR-006); this
module never invents it.
"""
from __future__ import annotations

# NYC agencies relevant to the MVP's top-10 complaint types (PRD §5). The closed
# set the classifier/agent may output (FR-10.3).
AGENCIES: frozenset[str] = frozenset(
    {
        "DEP",   # Environmental Protection — water, sewer, hydrants
        "DOT",   # Transportation — street, sidewalk, street lights
        "DPR",   # Parks & Recreation — trees
        "HPD",   # Housing Preservation & Development — heat/hot water, plumbing
        "DOB",   # Buildings — construction
        "NYPD",  # Police — residential noise
        "DSNY",  # Sanitation
    }
)

# Deterministic prior: the agency that *usually* owns each complaint type.
COMPLAINT_TYPE_TO_AGENCY: dict[str, str] = {
    "Water System": "DEP",
    "Sewer": "DEP",
    "Street Condition": "DOT",
    "Street Light Condition": "DOT",
    "Sidewalk Condition": "DOT",
    "Damaged Tree": "DPR",
    "Noise - Residential": "NYPD",
    "HEAT/HOT WATER": "HPD",
    "Plumbing": "HPD",
    "General Construction": "DOB",
}


def normalize_agency(code: str | None) -> str | None:
    """Upper/trim an agency code; None stays None."""
    if code is None:
        return None
    code = code.strip().upper()
    return code or None


def is_valid_agency(code: str | None) -> bool:
    """True if `code` is in the recognized agency enum."""
    return normalize_agency(code) in AGENCIES


def ground_truth_agency(payload: dict) -> str | None:
    """The 311 ground-truth agency from a raw record payload (ADR-006)."""
    return normalize_agency(payload.get("agency"))


def agency_for_complaint_type(complaint_type: str | None) -> str | None:
    """Deterministic prior agency for a complaint type, or None if unmapped."""
    if not complaint_type:
        return None
    return COMPLAINT_TYPE_TO_AGENCY.get(complaint_type)
