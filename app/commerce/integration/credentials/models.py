"""Credential contract (Phase 12.9.1).

A ``Credential`` never stores a plain token / secret — only an opaque
``SecretReference``.  The plain secret is resolved by a ``SecretProvider``
inside the Connector Runtime; an Agent (or any layer above the Connector) can
never see it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now


@dataclass(frozen=True)
class SecretReference:
    """Opaque reference to a secret in an external secret store."""

    reference_id: str
    provider: str = "vault"

    def __post_init__(self):
        if not self.reference_id:
            raise ValueError("reference_id is required")


@dataclass(frozen=True)
class Credential:
    """A tenant x provider credential (token reference only, never the token)."""

    credential_id: str
    tenant_id: str
    provider: str
    type: str = "oauth2"
    status: str = "ACTIVE"
    secret_ref: SecretReference | None = None
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.credential_id:
            raise ValueError("credential_id is required")
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.provider:
            raise ValueError("provider is required")
        if self.secret_ref is not None and not isinstance(self.secret_ref, SecretReference):
            raise ValueError("secret_ref must be a SecretReference")

    def to_dict(self) -> dict:
        return {
            "credential_id": self.credential_id,
            "tenant_id": self.tenant_id,
            "provider": self.provider,
            "type": self.type,
            "status": self.status,
            "secret_ref": {
                "reference_id": self.secret_ref.reference_id,
                "provider": self.secret_ref.provider,
            } if self.secret_ref else None,
            "created_at": self.created_at,
        }


class CredentialProvider(ABC):
    """Resolves a tenant x provider credential (reference only, no token)."""

    @abstractmethod
    def resolve(self, tenant_id, provider) -> Credential:
        pass


class SecretProvider(ABC):
    """Resolves a SecretReference into the actual secret (Connector Runtime only)."""

    @abstractmethod
    def get_secret(self, secret_ref: SecretReference) -> str:
        pass


__all__ = [
    "SecretReference",
    "Credential",
    "CredentialProvider",
    "SecretProvider",
]
