import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryDatabaseConfig:
    url: str
    embedding_dimension: int
    initialize: bool = False

    @classmethod
    def from_environment(cls):
        url = os.getenv("MEMORY_DATABASE_URL")
        if not url:
            raise RuntimeError("MEMORY_DATABASE_URL is required for production Memory storage")
        raw_dimension = os.getenv("MEMORY_EMBEDDING_DIMENSION")
        if not raw_dimension:
            raise RuntimeError(
                "MEMORY_EMBEDDING_DIMENSION must match the configured embedding provider"
            )
        try:
            dimension = int(raw_dimension)
        except ValueError as error:
            raise RuntimeError("MEMORY_EMBEDDING_DIMENSION must be an integer") from error
        initialize = os.getenv("MEMORY_DATABASE_INITIALIZE", "").lower() in {
            "1", "true", "yes",
        }
        return cls(url=url, embedding_dimension=dimension, initialize=initialize)
