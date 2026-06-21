"""311 ingestion (FR-1).

Sub-phase 1.1 adds the Socrata SODA client (paging + SoQL filters). Normalization
to the canonical ticket lives in `pipeline.ingest`.
"""
from .socrata import SodaClient, soql_where

__all__ = ["SodaClient", "soql_where"]
