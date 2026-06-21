"""`fieldops` CLI — the console entrypoint.

    fieldops init-db                 create the pgvector extension + tables + index
    fieldops demo                    flow one sample ticket through the spine
    fieldops llm-health              probe the configured LLM providers (needs keys)
    fieldops ingest --backfill       12-month Brooklyn backfill (FR-1)
    fieldops ingest --delta          incremental pull since the watermark
    fieldops embed                   embed tickets missing a vector (FR-2)
    fieldops dedup                   link duplicates over embedded tickets (FR-2)
    fieldops profile-ambiguity       profile the ambiguous population (Phase 2 gate)
"""
from __future__ import annotations

import argparse
import sys

from .config import get_settings


def _cmd_init_db(_: argparse.Namespace) -> int:
    from .db import init_db

    init_db()
    print("init-db: pgvector extension + tables ready.")
    return 0


def _cmd_demo(_: argparse.Namespace) -> int:
    from .db import session_scope
    from .pipeline.runner import run_ticket

    with session_scope() as session:
        result = run_ticket(session)

    print("\n── pipeline result ─────────────────────────────")
    for k, v in result.as_dict().items():
        print(f"  {k:16} {v}")
    print("────────────────────────────────────────────────")
    print("ingest → store → (stub) classify → (stub) draft  ✓")
    return 0


def _cmd_llm_health(_: argparse.Namespace) -> int:
    from .llm import Tier, get_llm
    from .llm.base import ChatMessage

    s = get_settings()
    checks = [
        ("OpenAI (agent)", Tier.AGENT, bool(s.openai_api_key)),
        ("Grok (cheap)", Tier.CHEAP, bool(s.xai_api_key)),
    ]
    rc = 0
    for label, tier, has_key in checks:
        if not has_key:
            print(f"  {label:18} skipped (no key set)")
            continue
        try:
            client = get_llm(tier)
            out = client.complete([ChatMessage("user", "reply with: ok")], max_tokens=5)
            print(f"  {label:18} ok  model={out.model} reply={out.text!r}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {label:18} FAIL {exc}")
            rc = 1
    return rc


def _cmd_ingest(args: argparse.Namespace) -> int:
    from .ingest.backfill import run_backfill, run_delta

    if args.delta:
        n = run_delta(max_records=args.max)
        print(f"ingest --delta: {n} records ingested")
    else:
        n = run_backfill(months=args.months, max_records=args.max)
        print(f"ingest --backfill ({args.months}mo): {n} records ingested")
    return 0


def _cmd_embed(args: argparse.Namespace) -> int:
    from .db import session_scope
    from .dedup import embed_missing

    with session_scope() as session:
        n = embed_missing(session, limit=args.max)
    print(f"embed: {n} tickets embedded")
    return 0


def _cmd_dedup(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from .db import session_scope
    from .dedup import dedup_ticket
    from .models import Ticket, TicketStatus

    linked = 0
    with session_scope() as session:
        stmt = select(Ticket).where(Ticket.status != TicketStatus.DUPLICATE)
        if args.max:
            stmt = stmt.limit(args.max)
        for ticket in session.scalars(stmt).all():
            if dedup_ticket(session, ticket) is not None:
                linked += 1
    print(f"dedup: {linked} tickets linked as duplicates")
    return 0


def _cmd_classify_eval(args: argparse.Namespace) -> int:
    import json

    from .db import session_scope
    from .eval.classify_eval import run_classification_eval

    with session_scope() as session:
        report = run_classification_eval(session, sample=args.max)
    print(json.dumps(report.as_dict(), indent=2))
    return 0


def _cmd_profile_ambiguity(_: argparse.Namespace) -> int:
    import json

    from .db import session_scope
    from .profiling import profile_ambiguity

    with session_scope() as session:
        prof = profile_ambiguity(session)
    print(json.dumps(prof.as_dict(), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fieldops", description="FieldOps Copilot")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init-db", help="create pgvector extension + tables + index")
    p_init.set_defaults(fn=_cmd_init_db)
    p_demo = sub.add_parser("demo", help="run one sample ticket through the spine")
    p_demo.set_defaults(fn=_cmd_demo)
    p_health = sub.add_parser("llm-health", help="probe configured LLM providers")
    p_health.set_defaults(fn=_cmd_llm_health)

    p_ingest = sub.add_parser("ingest", help="pull 311 records (backfill or delta)")
    mode = p_ingest.add_mutually_exclusive_group()
    mode.add_argument("--backfill", action="store_true", help="trailing-window backfill (default)")
    mode.add_argument("--delta", action="store_true", help="incremental pull since the watermark")
    p_ingest.add_argument("--months", type=int, default=12, help="backfill window (default 12)")
    p_ingest.add_argument("--max", type=int, default=None, help="cap records (for a quick run)")
    p_ingest.set_defaults(fn=_cmd_ingest)

    p_embed = sub.add_parser("embed", help="embed tickets missing a vector")
    p_embed.add_argument("--max", type=int, default=None)
    p_embed.set_defaults(fn=_cmd_embed)

    p_dedup = sub.add_parser("dedup", help="link duplicates over embedded tickets")
    p_dedup.add_argument("--max", type=int, default=None)
    p_dedup.set_defaults(fn=_cmd_dedup)

    p_ceval = sub.add_parser("classify-eval", help="discriminative eval: F1, ECE, gate split")
    p_ceval.add_argument("--max", type=int, default=None)
    p_ceval.set_defaults(fn=_cmd_classify_eval)

    p_prof = sub.add_parser("profile-ambiguity", help="profile the ambiguous population")
    p_prof.set_defaults(fn=_cmd_profile_ambiguity)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
