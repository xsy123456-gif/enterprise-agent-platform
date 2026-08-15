"""PostgreSQL implementation of the external-id -> canonical-id map."""

from app.commerce.domain import ExternalIdentity
from app.commerce.repositories.ports import ExternalIdentityMap


class PostgresExternalIdentityMap(ExternalIdentityMap):

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def resolve(self, tenant_id, platform, store_id, resource_type, external_id):
        with self.connection_factory() as conn:
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
        with self.connection_factory() as conn:
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
        # First-write-wins: return the canonical id actually stored, so repeated
        # sync of the same external object never produces a new canonical id.
        return self.resolve(
            identity.tenant_id, identity.platform, identity.store_id,
            identity.resource_type, identity.external_id,
        )

    def list(self, tenant_id):
        with self.connection_factory() as conn:
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
