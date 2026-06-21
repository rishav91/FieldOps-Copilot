"""FastAPI app (Phase 0).

Minimal surface that proves the spine over HTTP:
  GET  /health        liveness
  POST /tickets/demo  run the bundled sample ticket through the pipeline
"""
from __future__ import annotations

from fastapi import FastAPI

from ..db import session_scope
from ..pipeline.runner import run_ticket

app = FastAPI(title="FieldOps Copilot", version="0.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "phase": 0}


@app.post("/tickets/demo")
def run_demo_ticket() -> dict:
    """Ingest -> store -> (stub) classify -> (stub) draft for the sample record."""
    with session_scope() as session:
        return run_ticket(session).as_dict()
