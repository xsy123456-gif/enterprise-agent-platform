"""Shared primitives for the Canonical Commerce Model.

``ExternalIdentity`` is the stable mapping between an external platform object
and its canonical id.  Repeated sync of the same external object must resolve
to the same ``canonical_id`` — never a new one.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ExternalIdentity:
    """Stable external -> canonical identity mapping.

    ``tenant + platform + store + resource_type + external_id`` uniquely
    identifies one external object; ``canonical_id`` is its platform-neutral
    internal id.
    """

    tenant_id: str
    platform: str
    store_id: str
    resource_type: str
    external_id: str
    canonical_id: str

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "platform": self.platform,
            "store_id": self.store_id,
            "resource_type": self.resource_type,
            "external_id": self.external_id,
            "canonical_id": self.canonical_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExternalIdentity":
        return cls(
            tenant_id=data["tenant_id"],
            platform=data["platform"],
            store_id=data["store_id"],
            resource_type=data["resource_type"],
            external_id=data["external_id"],
            canonical_id=data["canonical_id"],
        )
