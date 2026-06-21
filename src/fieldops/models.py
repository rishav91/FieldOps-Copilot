"""Canonical data model (ARCHITECTURE §5).

Single store: Postgres + pgvector (ADR-010). These tables are the spine every
later phase plugs into. Phase 0 exercises raw_311_record, ticket,
routing_decision, and work_order; the embedding table is created so pgvector is
proven up, and is populated starting Phase 1 (dedup).

Idempotency keys (NFR-3.2): ticket upsert by `unique_key`, agent by
`routing_decision_id`, submission by `draft_hash`.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .config import get_settings


class Base(DeclarativeBase):
    pass


class TicketStatus(str, enum.Enum):
    """Lifecycle states (ARCHITECTURE §6)."""

    INGESTED = "INGESTED"
    DUPLICATE = "DUPLICATE"
    CLASSIFIED = "CLASSIFIED"
    IN_TRIAGE = "IN_TRIAGE"
    ESCALATED = "ESCALATED"
    ROUTED = "ROUTED"
    DRAFTED = "DRAFTED"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"


class RoutingPath(str, enum.Enum):
    FAST = "fast"
    AGENT = "agent"


def _uuid() -> str:
    return uuid.uuid4().hex


class Raw311Record(Base):
    """Immutable landing copy of the source payload — enables replay."""

    __tablename__ = "raw_311_record"

    unique_key: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Ticket(Base):
    """The canonical unit everything downstream operates on."""

    __tablename__ = "ticket"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    unique_key: Mapped[str] = mapped_column(
        ForeignKey("raw_311_record.unique_key"), unique=True, index=True
    )
    complaint_type: Mapped[str | None] = mapped_column(String)
    descriptor: Mapped[str | None] = mapped_column(String)
    borough: Mapped[str | None] = mapped_column(String, index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    created_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    closed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report_count: Mapped[int] = mapped_column(Integer, default=1)
    duplicate_of: Mapped[str | None] = mapped_column(ForeignKey("ticket.id"), nullable=True)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, native_enum=False, length=20), default=TicketStatus.INGESTED
    )

    routing_decisions: Mapped[list[RoutingDecision]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    work_orders: Mapped[list[WorkOrder]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class Embedding(Base):
    """pgvector store for dedup + retrieval (populated from Phase 1)."""

    __tablename__ = "embedding"

    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"), primary_key=True)
    vector: Mapped[list[float]] = mapped_column(Vector(get_settings().embedding_dim))
    model: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoutingDecision(Base):
    """Audit of every routing call; `path` powers cost/quality dashboards."""

    __tablename__ = "routing_decision"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"), index=True)
    predicted_agency: Mapped[str | None] = mapped_column(String)
    predicted_type: Mapped[str | None] = mapped_column(String)
    confidence_calibrated: Mapped[float | None] = mapped_column(Float)
    path: Mapped[RoutingPath] = mapped_column(Enum(RoutingPath, native_enum=False, length=10))
    gate_version: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped[Ticket] = relationship(back_populates="routing_decisions")


class WorkOrder(Base):
    """Drafted order; `draft_hash` is the idempotency key for submission."""

    __tablename__ = "work_order"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"), index=True)
    draft: Mapped[dict] = mapped_column(JSONB)
    validator_status: Mapped[str | None] = mapped_column(String)
    repair_count: Mapped[int] = mapped_column(Integer, default=0)
    review_status: Mapped[str | None] = mapped_column(String)
    draft_hash: Mapped[str] = mapped_column(String, index=True)

    ticket: Mapped[Ticket] = relationship(back_populates="work_orders")
