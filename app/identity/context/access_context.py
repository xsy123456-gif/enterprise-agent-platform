"""AccessContext — the Identity subsystem's final product.

A trusted, validated snapshot of enterprise identity facts for one platform
call.  ``identity_version`` is a deterministic SHA-256 over the canonical
serialization of identity facts, with all unordered sets sorted and runtime
fields (``issued_at``) excluded.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from app.identity.models.scope import BusinessScope


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AccessContext:
    user_id: str
    tenant_id: str
    organization_id: str
    department_id: str
    position_id: str
    professional_level: str
    roles: tuple[str, ...]
    business_scope: BusinessScope
    security_clearance: str
    attributes: dict[str, Any] = field(default_factory=dict)
    identity_version: str = ""
    issued_at: str = field(default_factory=utc_now)

    def canonical_payload(self) -> dict:
        """Deterministic identity facts with all unordered sets sorted."""
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "organization_id": self.organization_id,
            "department_id": self.department_id,
            "position_id": self.position_id,
            "professional_level": self.professional_level,
            "roles": sorted(self.roles),
            "business_scope": self.business_scope.to_dict(),
            "security_clearance": self.security_clearance,
            "attributes": dict(sorted((self.attributes or {}).items())),
        }

    def stable_identity_version(self) -> str:
        serialized = json.dumps(
            self.canonical_payload(), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "organization_id": self.organization_id,
            "department_id": self.department_id,
            "position_id": self.position_id,
            "professional_level": self.professional_level,
            "roles": list(self.roles),
            "business_scope": self.business_scope.to_dict(),
            "security_clearance": self.security_clearance,
            "attributes": dict(self.attributes),
            "identity_version": self.identity_version,
            "issued_at": self.issued_at,
        }
