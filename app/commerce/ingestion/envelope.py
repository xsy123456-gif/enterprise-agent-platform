"""Sync envelope + canonical mutation contracts.

A Connector wraps raw source DTOs in ``SourceRecordEnvelope`` (with a payload
checksum); an Adapter maps envelopes into platform-neutral ``CanonicalMutation``
records.  Canonical writes are at-least-once + idempotent.
"""

import hashlib
import json
from dataclasses import dataclass, field

MUTATION_UPSERT = "UPSERT"
MUTATION_APPEND = "APPEND"
MUTATION_TOMBSTONE = "TOMBSTONE"
MUTATION_TYPES = frozenset({MUTATION_UPSERT, MUTATION_APPEND, MUTATION_TOMBSTONE})


def _canonical(value):
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def payload_checksum(payload) -> str:
    serialized = json.dumps(_canonical(payload or {}), ensure_ascii=False,
                            sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceRecordEnvelope:
    """A raw source record wrapped at the Connector boundary."""

    source_record_id: str
    resource: str
    source: str
    payload: dict = field(default_factory=dict)
    source_payload_checksum: str = ""
    sequence: str | None = None
    deleted: bool = False

    def __post_init__(self):
        object.__setattr__(self, "payload", dict(self.payload or {}))
        if not self.source_payload_checksum:
            object.__setattr__(self, "source_payload_checksum",
                               payload_checksum(self.payload))

    def to_dict(self) -> dict:
        return {
            "source_record_id": self.source_record_id,
            "resource": self.resource,
            "source": self.source,
            "payload": dict(self.payload),
            "source_payload_checksum": self.source_payload_checksum,
            "sequence": self.sequence,
            "deleted": self.deleted,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SourceRecordEnvelope":
        return cls(
            source_record_id=data["source_record_id"],
            resource=data["resource"],
            source=data["source"],
            payload=data.get("payload", {}),
            source_payload_checksum=data.get("source_payload_checksum", ""),
            sequence=data.get("sequence"),
            deleted=data.get("deleted", False),
        )


@dataclass(frozen=True)
class CanonicalMutation:
    """A platform-neutral canonical write produced by an Adapter."""

    mutation_type: str
    resource: str
    tenant_id: str
    entity: dict | None = None
    external_identity: dict | None = None
    source_record_id: str = ""
    subject_id: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "entity", dict(self.entity or {}))
        object.__setattr__(self, "external_identity",
                           dict(self.external_identity or {}) or None)

    def to_dict(self) -> dict:
        return {
            "mutation_type": self.mutation_type,
            "resource": self.resource,
            "tenant_id": self.tenant_id,
            "entity": dict(self.entity or {}),
            "external_identity": dict(self.external_identity or {}),
            "source_record_id": self.source_record_id,
            "subject_id": self.subject_id,
        }


__all__ = [
    "SourceRecordEnvelope",
    "CanonicalMutation",
    "MUTATION_UPSERT",
    "MUTATION_APPEND",
    "MUTATION_TOMBSTONE",
    "MUTATION_TYPES",
    "payload_checksum",
]
