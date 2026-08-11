"""Contracts for Agent-to-Agent governance decisions and evidence."""

from dataclasses import dataclass, field
from enum import Enum
import uuid


class AuthorizationStatus(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class TrustLevel(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class AgentAuthorizationContext:
    user_id: str
    tenant_id: str
    authenticated: bool = True
    allowed_capabilities: frozenset[str] = frozenset()

    def __post_init__(self):
        if not self.user_id or not self.tenant_id:
            raise ValueError("user_id and tenant_id are required")
        if not isinstance(self.authenticated, bool):
            raise TypeError("authenticated must be bool")
        object.__setattr__(
            self, "allowed_capabilities", frozenset(self.allowed_capabilities)
        )


@dataclass(frozen=True)
class AgentInvocationPolicy:
    source_agent_id: str
    target_agent_id: str
    allowed_capabilities: frozenset[str]
    allowed_context_fields: frozenset[str] = frozenset()
    approval_required: bool = False
    risk_level: str = "low"
    policy_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        for name in ("policy_id", "source_agent_id", "target_agent_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "allowed_capabilities", frozenset(self.allowed_capabilities))
        object.__setattr__(self, "allowed_context_fields", frozenset(self.allowed_context_fields))
        if self.risk_level not in {"low", "medium", "high", "critical"}:
            raise ValueError(f"Unsupported risk level: {self.risk_level}")


@dataclass(frozen=True)
class AuthorizationDecision:
    status: AuthorizationStatus
    reason: str
    source_agent_id: str
    target_agent_id: str
    policy_id: str | None = None
    approval_id: str | None = None
    authorization_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        object.__setattr__(self, "status", AuthorizationStatus(self.status))
        for name in (
            "authorization_id", "reason", "source_agent_id", "target_agent_id",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")

    def to_dict(self):
        return {
            **self.__dict__,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class ContextGuardResult:
    envelope: object
    removed_fields: tuple[str, ...] = ()
    context_projection_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if not self.context_projection_id:
            raise ValueError("context_projection_id is required")
        object.__setattr__(self, "removed_fields", tuple(self.removed_fields))


@dataclass(frozen=True)
class ResultValidation:
    trust_level: TrustLevel
    issues: tuple[str, ...]
    agent_id: str
    artifact_hash: str
    validation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        object.__setattr__(self, "trust_level", TrustLevel(self.trust_level))
        object.__setattr__(self, "issues", tuple(self.issues))
        if not self.validation_id or not self.agent_id or not self.artifact_hash:
            raise ValueError("validation_id, agent_id and artifact_hash are required")

    def to_dict(self):
        return {
            "validation_id": self.validation_id,
            "trust_level": self.trust_level.value,
            "issues": list(self.issues),
            "agent_id": self.agent_id,
            "artifact_hash": self.artifact_hash,
        }
