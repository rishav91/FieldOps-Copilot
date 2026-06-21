"""Classification discriminative eval (sub-phase 2.7, FR-8.1 + FR-8.11).

Runs the cascade over labeled tickets, fits the calibrator on a **temporal**
held-out split (earlier half calibrates, later half tests — ADR-011 / DR-08, no
future label leaks into calibration), and reports on the test split: macro-F1
(NFR-4.2), ECE (NFR-4.1), accuracy, the cheap-tier false-confidence rate
(FR-8.11), and the fast/agent gate split. Ground truth is the 311 `agency`
(ADR-006).
"""
from __future__ import annotations

from collections import namedtuple
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


_Row = namedtuple("_Row", "truth pred raw_conf cheap_tier cheap_conf multi")


def run_classification_eval(session: Session, *, sample: int | None = None) -> ClassificationReport:
    s = get_settings()
    stmt = (
        select(Ticket, Raw311Record.payload)
        .join(Raw311Record, Raw311Record.unique_key == Ticket.unique_key)
        .join(Embedding, Embedding.ticket_id == Ticket.id)
        .where(Ticket.status != TicketStatus.DUPLICATE)
        .order_by(Ticket.created_date)  # time order for an as-of split (ADR-011, DR-08)
    )
    if sample:
        stmt = stmt.limit(sample)

    rows: list[_Row] = []
    for ticket, payload in session.execute(stmt).all():
        truth = (payload.get("agency") or "").strip().upper() or None
        if truth is None:
            continue
        cheap = classify_cheap(session, ticket)
        final = classify_cascade(session, ticket)
        multi = detect_multi_agency(ticket.complaint_type, ticket.descriptor).is_multi
        rows.append(
            _Row(truth, final.agency, final.confidence, cheap.tier, cheap.confidence, multi)
        )

    # Temporal split (ADR-011): calibrate on the earlier half, test on the later
    # half — no future label leaks into calibration.
    cutoff = len(rows) // 2
    calib, test = rows[:cutoff], rows[cutoff:]
    report = ClassificationReport(n_test=len(test), n_calib=len(calib))
    if not test:
        report.notes.append("no test rows (need embedded, labeled tickets)")
        return report

    calibrator = IsotonicCalibrator()
    if calib:
        calibrator.fit([r.raw_conf for r in calib], [r.truth == r.pred for r in calib])

    truths = [r.truth for r in test]
    preds = [r.pred for r in test]
    correct = [t == p for t, p in zip(truths, preds)]
    calibrated = calibrator.predict([r.raw_conf for r in test])

    report.macro_f1 = macro_f1(truths, preds)
    report.accuracy = sum(correct) / len(test)
    report.ece = expected_calibration_error(calibrated, correct)
    fc_records = [(r.cheap_tier, r.cheap_conf, r.truth == r.pred) for r in test]
    report.cheap_false_confidence, report.n_cheap_high_conf = cheap_tier_false_confidence(
        fc_records, s.cascade_cheap_min_confidence
    )

    n_agent = sum(
        decide_gate(_pred(r.pred, r.raw_conf), cal, multi_agency=r.multi).path.value == "agent"
        for r, cal in zip(test, calibrated)
    )
    report.agent_fraction = n_agent / len(test)
    report.fast_fraction = 1.0 - report.agent_fraction
    report.notes.append("temporal split (ADR-011): calibrate earlier half, test later half")
    return report


def _pred(agency, confidence):
    from ..classify import Prediction

    return Prediction(agency=agency, confidence=confidence, tier="final")
