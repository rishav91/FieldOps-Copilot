"""Tracing skeleton (OBSERVABILITY §2).

A dependency-light stand-in for LangSmith/OpenTelemetry: one trace per ticket,
correlation IDs (`trace_id`, `ticket_id`) propagated via contextvars, and a
`span()` context manager that records name, attributes, latency, and status.

Phase 0 emits spans as structured logs. The interface (`span(...)`) is the
upgrade seam: later phases swap the body for OTel/LangSmith exporters without
touching call sites. Everything is traced (ARCHITECTURE tenet 5).
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from .config import get_settings

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_ticket_id: ContextVar[str | None] = ContextVar("ticket_id", default=None)

logger = logging.getLogger("fieldops.trace")


def _configure_once() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(get_settings().log_level.upper())
    logger.propagate = False


def current_trace_id() -> str | None:
    return _trace_id.get()


def current_ticket_id() -> str | None:
    return _ticket_id.get()


@contextmanager
def trace(ticket_id: str | None = None, trace_id: str | None = None) -> Iterator[str]:
    """Open a root trace for one ticket; everything inside shares its IDs."""
    _configure_once()
    tid = trace_id or uuid.uuid4().hex
    t_tok = _trace_id.set(tid)
    k_tok = _ticket_id.set(ticket_id)
    try:
        yield tid
    finally:
        _trace_id.reset(t_tok)
        _ticket_id.reset(k_tok)


@contextmanager
def span(name: str, **attrs: object) -> Iterator[dict[str, object]]:
    """Record one unit of work. Mutate the yielded dict to attach result attrs."""
    _configure_once()
    started = time.perf_counter()
    data: dict[str, object] = dict(attrs)
    status = "ok"
    try:
        yield data
    except Exception as exc:  # noqa: BLE001 — trace then re-raise
        status = "error"
        data["error"] = repr(exc)
        raise
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        fields = " ".join(f"{k}={v!r}" for k, v in data.items())
        logger.info(
            "span name=%s status=%s latency_ms=%s trace_id=%s ticket_id=%s %s",
            name, status, latency_ms, _trace_id.get(), _ticket_id.get(), fields,
        )
