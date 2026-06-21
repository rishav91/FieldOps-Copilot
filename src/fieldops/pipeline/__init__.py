"""The deterministic pipeline spine (ARCHITECTURE §2).

Phase 0 wires: ingest -> store -> (stub) classify -> (stub) draft. Classify and
draft are stubs that run offline; later phases replace their bodies without
changing the spine.
"""
