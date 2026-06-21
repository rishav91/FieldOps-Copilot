"""Classification discriminative eval (sub-phase 2.7, FR-8.1 + FR-8.11).

Runs the cascade over labeled tickets, fits the calibrator on a held-out split
(EVAL-SPEC §2), and reports on the **test** split: macro-F1 (NFR-4.2), ECE
(NFR-4.1), accuracy, the cheap-tier false-confidence rate (FR-8.11), and the
fast/agent gate split. Ground truth is the 311 `agency` (ADR-006).
"""
from __future__ import annotations

import zlib
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..classify import classify_cascade, classify_cheap, decide_gate, detect_multi_agency
from ..classify.calibration import IsotonicCalibrator
from ..config import get_settings
from ..models import Embedding, Raw311Record, Ticket, TicketStatus
from .calibration import expected_calibration_error
from .metrics import cheap_tier_false_confidence, macro_f1


@dataclass
class ClassificationReport:
    n_test: int = 0
    n_calib: int = 0
    macro_f1: float = 0.0
    accuracy: float = 0.0
    ece: float = 0.0
    cheap_false_confidence: float = 0.0
    n_cheap_high_conf: int = 0
    fast_fraction: float = 0.0
    agent_fraction: float = 0.0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _split(ticket_id: str) -> str:
    """Deterministic calib/test split by a hash of the ticket id."""
    return "test" if zlib.crc32(ticket_id.encode()) % 2 else "calib"


def run_classification_eval(session: Session, *, sample: int | None = None) -> ClassificationReport:
    s = get_settings()
    stmt = (
        select(Ticket, Raw311Record.payload)
        .join(Raw311Record, Raw311Record.unique_key == Ticket.unique_key)
        .join(Embedding, Embedding.ticket_id == Ticket.id)
        .where(Ticket.status != TicketStatus.DUPLICATE)
    )
    if sample:
        stmt = stmt.limit(sample)

    rows = []  # (split, truth, final_agency, raw_conf, cheap_tier, cheap_conf, multi)
    for ticket, payload in session.execute(stmt).all():
        truth = (payload.get("agency") or "").strip().upper() or None
        if truth is None:
            continue
        cheap = classify_cheap(session, ticket)
        final = classify_cascade(session, ticket)
        multi = detect_multi_agency(ticket.complaint_type, ticket.descriptor).is_multi
        rows.append(
            (
                _split(ticket.id),
                truth,
                final.agency,
                final.confidence,
                cheap.tier,
                cheap.confidence,
                multi,
            )
        )

    calib = [r for r in rows if r[0] == "calib"]
    test = [r for r in rows if r[0] == "test"]
    report = ClassificationReport(n_test=len(test), n_calib=len(calib))
    if not test:
        report.notes.append("no test rows (need embedded, labeled tickets)")
        return report

    # Fit calibration on calib split: raw final-confidence -> correctness.
    calibrator = IsotonicCalibrator()
    if calib:
        calibrator.fit([r[3] for r in calib], [r[1] == r[2] for r in calib])

    truths = [r[1] for r in test]
    preds = [r[2] for r in test]
    correct = [t == p for t, p in zip(truths, preds)]
    calibrated = calibrator.predict([r[3] for r in test])

    report.macro_f1 = macro_f1(truths, preds)
    report.accuracy = sum(correct) / len(test)
    report.ece = expected_calibration_error(calibrated, correct)
    report.cheap_false_confidence, report.n_cheap_high_conf = cheap_tier_false_confidence(
        [(r[4], r[5], r[1] == r[2]) for r in test], s.cascade_cheap_min_confidence
    )

    n_agent = sum(
        decide_gate(
            _pred(r[2], r[3]), cal, multi_agency=r[6]
        ).path.value == "agent"
        for r, cal in zip(test, calibrated)
    )
    report.agent_fraction = n_agent / len(test)
    report.fast_fraction = 1.0 - report.agent_fraction
    return report


def _pred(agency, confidence):
    from ..classify import Prediction

    return Prediction(agency=agency, confidence=confidence, tier="final")
