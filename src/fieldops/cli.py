"""`fieldops` CLI — the console entrypoint for the Phase-0 skeleton.

    fieldops init-db       create the pgvector extension + tables
    fieldops demo          flow one sample ticket through the spine -> console
    fieldops llm-health     probe the configured LLM providers (needs keys)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fieldops", description="FieldOps Copilot (Phase 0)")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init-db", help="create pgvector extension + tables")
    p_init.set_defaults(fn=_cmd_init_db)
    p_demo = sub.add_parser("demo", help="run one sample ticket through the spine")
    p_demo.set_defaults(fn=_cmd_demo)
    p_health = sub.add_parser("llm-health", help="probe configured LLM providers")
    p_health.set_defaults(fn=_cmd_llm_health)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
