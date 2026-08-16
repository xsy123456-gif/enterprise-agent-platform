"""Adapter base (Phase 12.9.1).

Reuses the frozen Phase 7 mapping contract (``AdapterPort`` /
``CanonicalMutation``).  A ``BaseAdapter`` provides the shared helper for
building a canonical mutation with an ExternalIdentity bridge — never computes
metrics, never detects anomalies, never creates Cause / Impact.
"""

from app.commerce.ingestion.envelope import (
    MUTATION_APPEND,
    MUTATION_TOMBSTONE,
    MUTATION_UPSERT,
    CanonicalMutation,
)
from app.commerce.ingestion.ports import AdapterPort


class BaseAdapter(AdapterPort):
    adapter_id = ""

    def __init__(self, version="1.0", tenant_id="", store_id=""):
        self.version = version
        self.tenant_id = tenant_id
        self.store_id = store_id

    def adapt(self, envelope):
        raise NotImplementedError

    def _mutation(self, mutation_type, resource, entity, envelope,
                  external_id=None, resource_type=None, canonical_id="",
                  critical=False):
        external = None
        if external_id is not None:
            external = {
                "platform": envelope.source,
                "store_id": self.store_id,
                "resource_type": resource_type or resource,
                "external_id": external_id,
                "canonical_id": canonical_id,
            }
        return CanonicalMutation(
            mutation_type=mutation_type,
            resource=resource,
            tenant_id=self.tenant_id,
            entity=entity,
            external_identity=external,
            source_record_id=envelope.source_record_id,
            critical=critical,
            adapter_id=self.adapter_id,
            adapter_version=self.version,
            source_external_id=envelope.source_external_id,
            source_updated_at=envelope.source_updated_at,
        )


__all__ = ["BaseAdapter", "MUTATION_UPSERT", "MUTATION_APPEND", "MUTATION_TOMBSTONE"]
