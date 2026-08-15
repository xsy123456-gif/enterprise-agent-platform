"""Commerce repository construction.

The repository boundary is decoupled from psycopg: pass ``url`` to get the
production PostgreSQL implementation, or omit it to get the in-memory
implementation for tests/development.
"""

from app.commerce.repositories.inmemory import (
    InMemoryCommerceRepository,
    InMemoryExternalIdentityMap,
)
from app.commerce.repositories.postgres.identity_map import PostgresExternalIdentityMap
from app.commerce.repositories.postgres.repository import PostgresCommerceRepository


def _connection_factory(url):
    def factory():
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("psycopg is required for PostgreSQL") from error
        return psycopg.connect(url)

    return factory


def build_repository(url=None, initialize=False):
    """Build a ``CommerceRepository`` (Postgres when ``url`` is set)."""
    if not url:
        return InMemoryCommerceRepository()
    repository = PostgresCommerceRepository(_connection_factory(url))
    repository.healthcheck()
    if initialize:
        repository.initialize()
    else:
        repository.validate_schema()
    return repository


def build_identity_map(url=None):
    """Build an ``ExternalIdentityMap`` (Postgres when ``url`` is set)."""
    if not url:
        return InMemoryExternalIdentityMap()
    return PostgresExternalIdentityMap(_connection_factory(url))


__all__ = ["build_repository", "build_identity_map"]
