"""Deduplication (FR-2): embeddings + geo/time + cosine linking."""
from .embed import embed_missing, embed_ticket, ticket_text
from .link import dedup_ticket, find_canonical, link_duplicate

__all__ = [
    "ticket_text",
    "embed_ticket",
    "embed_missing",
    "find_canonical",
    "link_duplicate",
    "dedup_ticket",
]
