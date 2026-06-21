"""Multi-label / multi-agency detection (sub-phase 2.4).

A ticket whose descriptor spans ≥2 issue categories owned by different agencies
is a genuine multi-agency case (PRD UC3: "water from the ceiling AND the floor is
buckling" → DEP + DOB). The confidence gate (2.6) routes these to the agent
regardless of the classifier's single-label confidence — they're exactly the tail
the agent exists for.

Reuses the issue-category heuristic from profiling (1.7), mapped to agencies.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..profiling.ambiguity import issue_categories

# Issue category -> the agency that typically owns it.
ISSUE_CATEGORY_TO_AGENCY: dict[str, str] = {
    "water": "DEP",
    "sewer": "DEP",
    "structural": "DOB",
    "heat": "HPD",
    "tree": "DPR",
    "noise": "NYPD",
    "street": "DOT",
    "electrical": "DOT",
}


@dataclass(frozen=True)
class MultiAgency:
    agencies: frozenset[str]
    is_multi: bool


def candidate_agencies(complaint_type: str | None, descriptor: str | None) -> frozenset[str]:
    """Agencies implied by the issue categories in the text."""
    text = f"{complaint_type or ''} {descriptor or ''}"
    cats = issue_categories(text)
    return frozenset(ISSUE_CATEGORY_TO_AGENCY[c] for c in cats if c in ISSUE_CATEGORY_TO_AGENCY)


def detect_multi_agency(complaint_type: str | None, descriptor: str | None) -> MultiAgency:
    agencies = candidate_agencies(complaint_type, descriptor)
    return MultiAgency(agencies=agencies, is_multi=len(agencies) >= 2)
