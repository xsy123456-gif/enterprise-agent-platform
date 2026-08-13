from .base import ApplicationContainer
import os

from app.infrastructure import PostgresProvider, RedisProvider, VectorStoreProvider
from app.runtime.backends.langgraph.checkpoint.postgres import PostgresCheckpointAdapter


def build_production(**components):
    """Build production providers lazily; health() performs the checks."""
    database_url = (
        os.getenv("MEMORY_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or "postgresql://user:password@localhost:5433/agentdb"
    )
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    vector_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    infrastructure = dict(components.pop("infrastructure", {}) or {})
    if database_url:
        infrastructure.setdefault("database", PostgresProvider(database_url))
        # Checkpointer construction is intentionally opt-in because the
        # optional package may not be installed in development environments.
        if os.getenv("LANGGRAPH_CHECKPOINT_DATABASE_URL"):
            try:
                components.setdefault(
                    "checkpoint",
                    PostgresCheckpointAdapter(
                        os.environ["LANGGRAPH_CHECKPOINT_DATABASE_URL"]
                    ),
                )
            except RuntimeError:
                components.setdefault("checkpoint", None)
    infrastructure.setdefault("redis", RedisProvider(redis_url))
    infrastructure.setdefault("vector", VectorStoreProvider(vector_url))
    return ApplicationContainer(
        environment="production", infrastructure=infrastructure, **components
    )
