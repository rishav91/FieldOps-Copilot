"""Ambiguous-request population profiling (FR-1 goal; feeds the Phase 2 gate).

The single largest risk ([PRD R2](../../../docs/PRD.md#7-risks)) is building the
triage agent with no genuine ambiguity to justify it. This profiles the backfill
for the signals the agent would actually face:

  - thin_text      : descriptor too short to route with confidence
  - multi_issue    : descriptor implies more than one distinct problem
                     (a proxy for the multi-agency case the agent resolves)

Heuristic and deliberately coarse — its job is a *count* for the gate decision,
not a precise classifier. The real multi-agency split needs the jurisdiction
lookup that arrives with the agent in Phase 3.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Ticket, TicketStatus

# Distinct issue categories; ≥2 hits in one descriptor suggests multiple problems.
_ISSUE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "water": ("leak", "water", "flood", "hydrant", "pipe"),
    "structural": ("crack", "buckl", "collaps", "structural", "ceiling", "wall"),
    "heat": ("heat", "hot water", "boiler", "radiator"),
    "sewer": ("sewage", "sewer", "drain", "backup", "back up"),
    "tree": ("tree", "branch", "limb", "root"),
    "noise": ("noise", "music", "loud", "party"),
    "street": ("pothole", "pavement", "sidewalk", "curb", "road"),
    "electrical": ("light", "wire", "electric", "spark", "outage"),
}
_CONNECTORS = (" and ", "; ", " also ", " plus ", " as well as ", "&")
_THIN_TEXT_MIN = 12


def _matches(keyword: str, low: str) -> bool:
    # Word-boundary match so "street" doesn't trip the "tree" category, while
    # still allowing intentional prefixes like "buckl" -> "buckling".
    return re.search(rf"\b{re.escape(keyword)}", low) is not None


def _issue_categories(text: str) -> set[str]:
    low = text.lower()
    return {cat for cat, kws in _ISSUE_KEYWORDS.items() if any(_matches(k, low) for k in kws)}


def is_thin_text(text: str | None, min_len: int = _THIN_TEXT_MIN) -> bool:
    return not text or len(text.strip()) < min_len


def is_multi_issue(text: str | None) -> bool:
    """True when the descriptor spans ≥2 issue categories (esp. with a connector)."""
    if not text:
        return False
    cats = _issue_categories(text)
    if len(cats) >= 2:
        return True
    # A connector plus two issue-ish noun phrases also counts.
    low = text.lower()
    has_connector = any(c in low for c in _CONNECTORS)
    return has_connector and len(cats) >= 1 and len(re.findall(r"\b\w+\b", low)) >= 6


@dataclass
class AmbiguityProfile:
    total: int = 0
    thin_text: int = 0
    multi_issue: int = 0
    ambiguous: int = 0  # union of the above
    examples: list[str] = field(default_factory=list)

    @property
    def ambiguous_fraction(self) -> float:
        return self.ambiguous / self.total if self.total else 0.0

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "thin_text": self.thin_text,
            "multi_issue": self.multi_issue,
            "ambiguous": self.ambiguous,
            "ambiguous_fraction": round(self.ambiguous_fraction, 4),
            "examples": self.examples,
        }


def classify_ticket_text(text: str | None) -> dict[str, bool]:
    thin = is_thin_text(text)
    multi = is_multi_issue(text)
    return {"thin_text": thin, "multi_issue": multi, "ambiguous": thin or multi}


def profile_ambiguity(session: Session, *, max_examples: int = 10) -> AmbiguityProfile:
    """Profile non-duplicate tickets for ambiguity signals."""
    prof = AmbiguityProfile()
    stmt = select(Ticket).where(Ticket.status != TicketStatus.DUPLICATE)
    for ticket in session.scalars(stmt):
        prof.total += 1
        flags = classify_ticket_text(ticket.descriptor)
        prof.thin_text += flags["thin_text"]
        prof.multi_issue += flags["multi_issue"]
        if flags["ambiguous"]:
            prof.ambiguous += 1
            if flags["multi_issue"] and len(prof.examples) < max_examples:
                prof.examples.append(ticket.descriptor or "")
    return prof
