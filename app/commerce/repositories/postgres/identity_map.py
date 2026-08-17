"""PostgreSQL implementation of the external-id -> canonical-id map."""

from contextlib import contextmanager

from app.commerce.domain import ExternalIdentity
from app.commerce.repositories.errors import ExternalIdentityConflict
from app.commerce.repositories.ports import ExternalIdentityMap
from app.commerce.repositories.postgres.tx import current_tx_connection


class PostgresExternalIdentityMap(ExternalIdentityMap):

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @contextmanager
    def _connection(self):
        shared = current_tx_connection()
        if shared is not None:
            yield shared
            return
        with self.connection_factory() as conn:
            yield conn

    def resolve(self, tenant_id, platform, store_id, resource_type, external_id):
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT canonical_id FROM commerce_external_identities "
                    "WHERE tenant_id=%s AND platform=%s AND store_id=%s "
                    "AND resource_type=%s AND external_id=%s",
                    (tenant_id, platform, store_id, resource_type, external_id),
                )
                row = cursor.fetchone()
        return row[0] if row else None

    def register(self, tenant_id, identity):
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO commerce_external_identities
                    (tenant_id, platform, store_id, resource_type, external_id, canonical_id)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (tenant_id, platform, store_id, resource_type, external_id)
                    DO NOTHING""",
                    (identity.tenant_id, identity.platform, identity.store_id,
                     identity.resource_type, identity.external_id, identity.canonical_id),
                )
                inserted = cursor.rowcount == 1
        if inserted:
            return identity.canonical_id
        # Idempotent success: same external key + same canonical id.
        # Conflict: same external key + different canonical id -> fail closed,
        # the original mapping is left unchanged.
        existing = self.resolve(
            identity.tenant_id, identity.platform, identity.store_id,
            identity.resource_type, identity.external_id,
        )
        if existing != identity.canonical_id:
            raise ExternalIdentityConflict(
                f"external identity conflict for "
                f"{identity.resource_type}:{identity.external_id}: "
                f"canonical_id {existing!r} already mapped, "
                f"cannot remap to {identity.canonical_id!r}"
            )
        return existing

    def list(self, tenant_id):
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT tenant_id, platform, store_id, resource_type, "
                    "external_id, canonical_id FROM commerce_external_identities "
                    "WHERE tenant_id=%s ORDER BY resource_type, external_id",
                    (tenant_id,),
                )
                columns = [description.name for description in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return [ExternalIdentity.from_dict(row) for row in rows]
