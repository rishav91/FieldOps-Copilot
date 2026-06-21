"""Configuration — all pipeline knobs are config-driven (ARCHITECTURE §8).

Loaded from environment / .env. Nothing here requires LLM keys for the Phase-0
skeleton; classify and draft are stubs that run offline.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Datastore (ADR-010)
    database_url: str = "postgresql+psycopg://fieldops:fieldops@localhost:5432/fieldops"

    # 311 ingest (FR-1) — NYC Open Data Socrata SODA API
    socrata_domain: str = "data.cityofnewyork.us"
    socrata_dataset_id: str = "erm2-nwe9"  # 311 Service Requests
    socrata_app_token: str | None = None  # raises the anonymous rate limit
    socrata_page_size: int = 1000
    socrata_timeout_s: float = 30.0

    # LLM providers (ADR-003): OpenAI primary, Groq cheap tier
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    openai_agent_model: str = "gpt-4o"
    openai_embed_model: str = "text-embedding-3-small"
    groq_cheap_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    embedding_dim: int = 1536

    # Dedup knobs (FR-2) — geo/time window + cosine threshold
    dedup_cosine_threshold: float = 0.15  # max cosine distance to call a duplicate
    dedup_geo_meters: float = 150.0
    dedup_time_days: int = 7

    # Classifier knobs (FR-3)
    cheap_knn_k: int = 10  # neighbors for the cheap kNN tier
    cheap_knn_max_distance: float = 0.30  # only count neighbors within this cosine distance
    cascade_cheap_min_confidence: float = 0.7  # below this, escalate to an LLM tier

    # Pipeline knobs (gate / agent / spend) — see REQUIREMENTS FR-4, FR-5, FR-10
    gate_threshold: float = 0.75
    agent_turn_cap: int = 6
    agent_split_cap: int = 3
    daily_spend_ceiling_usd: float = 5.00

    # Demo scope (PRD §5)
    target_borough: str = "BROOKLYN"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Process-wide singleton so config is read once."""
    return Settings()
