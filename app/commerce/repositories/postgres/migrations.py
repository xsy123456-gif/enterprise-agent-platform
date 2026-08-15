"""Versioned schema migrations for the canonical commerce store.

Production schema evolution is versioned, not ad-hoc: each migration has a
version and is recorded in ``commerce_schema_migrations`` after it succeeds.
Migration 0001 is the initial canonical schema (``build_schema_sql``), which
also remains available as a development/test bootstrap helper.

This deliberately does not pull in a migration framework; it adapts the
project's existing PostgreSQL boundary (a single idempotent ``schema_migrations``
table + ordered migration list).
"""

from dataclasses import dataclass

from app.commerce.domain.base import utc_now
from app.commerce.repositories.errors import CommerceStorageError
from app.commerce.repositories.postgres.schema import build_schema_sql

# Bump this when a new migration is added; never edit a shipped migration.
SCHEMA_VERSION = 1

_MIGRATIONS_TABLE = "commerce_schema_migrations"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


MIGRATIONS = (
    Migration(version=1, name="initial_canonical_schema", sql=build_schema_sql()),
)


def apply_migrations(connection) -> int:
    """Apply all pending migrations on ``connection`` and return the new version.

    Runs inside the caller's transaction; a failed migration rolls back.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS {_MIGRATIONS_TABLE} (
            version integer PRIMARY KEY, name text NOT NULL, applied_at text NOT NULL)"""
        )
        cursor.execute(f"SELECT COALESCE(MAX(version), 0) FROM {_MIGRATIONS_TABLE}")
        current = int(cursor.fetchone()[0])
        if current > SCHEMA_VERSION:
            raise CommerceStorageError(
                f"database schema version {current} is newer than code "
                f"version {SCHEMA_VERSION}; downgrade is not supported"
            )
        for migration in MIGRATIONS:
            if migration.version <= current:
                continue
            cursor.execute(migration.sql)
            cursor.execute(
                f"INSERT INTO {_MIGRATIONS_TABLE} (version, name, applied_at) "
                "VALUES (%s, %s, %s)",
                (migration.version, migration.name, utc_now()),
            )
    return SCHEMA_VERSION


def current_schema_version(connection) -> int:
    """Return the highest applied migration version (0 if none)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass(%s)", (f"public.{_MIGRATIONS_TABLE}",)
        )
        if cursor.fetchone()[0] is None:
            return 0
        cursor.execute(f"SELECT COALESCE(MAX(version), 0) FROM {_MIGRATIONS_TABLE}")
        return int(cursor.fetchone()[0])


__all__ = [
    "SCHEMA_VERSION",
    "Migration",
    "MIGRATIONS",
    "apply_migrations",
    "current_schema_version",
]
