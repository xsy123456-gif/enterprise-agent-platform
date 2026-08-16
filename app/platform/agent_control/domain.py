"""Agent control plane domain models (Phase 13).

An Agent is an enterprise asset.  The control plane manages its lifecycle,
versioning, deployment, governance and evaluation — it never runs the agent and
never changes a Runtime definition.
"""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now

# Agent lifecycle (§7)
AGENT_DRAFT = "DRAFT"
AGENT_VALIDATED = "VALIDATED"
AGENT_ACTIVE = "ACTIVE"
AGENT_DEPRECATED = "DEPRECATED"
AGENT_DISABLED = "DISABLED"
AGENT_STATUSES = frozenset({
    AGENT_DRAFT, AGENT_VALIDATED, AGENT_ACTIVE, AGENT_DEPRECATED, AGENT_DISABLED,
})

# Deployment environments (§9)
ENV_DEV = "DEV"
ENV_TEST = "TEST"
ENV_PRODUCTION = "PRODUCTION"
ENVIRONMENTS = frozenset({ENV_DEV, ENV_TEST, ENV_PRODUCTION})

# Deployment status
DEPLOYMENT_ACTIVE = "ACTIVE"
DEPLOYMENT_DISABLED = "DISABLED"
DEPLOYMENT_STATUSES = frozenset({DEPLOYMENT_ACTIVE, DEPLOYMENT_DISABLED})

# Agent permissions (§10)
PERM_EXECUTE = "agent.execute"
PERM_VIEW = "agent.view"
PERM_MANAGE = "agent.manage"
AGENT_PERMISSIONS = frozenset({PERM_EXECUTE, PERM_VIEW, PERM_MANAGE})

# Access-policy subject types (§10)
SUBJECT_USER = "user"
SUBJECT_ROLE = "role"
SUBJECT_DEPARTMENT = "department"
SUBJECT_TYPES = frozenset({SUBJECT_USER, SUBJECT_ROLE, SUBJECT_DEPARTMENT})


@dataclass(frozen=True)
class AgentArtifact:
    """A deployable agent: identity + version + manifest + content checksum."""

    agent_id: str
    version: str
    manifest: object
    skills: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    checksum: str = ""
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        object.__setattr__(self, "skills", tuple(self.skills or ()))
        object.__setattr__(self, "capabilities", tuple(self.capabilities or ()))
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if not self.version:
            raise ValueError("version is required")

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "manifest": self.manifest.to_dict() if hasattr(self.manifest, "to_dict") else self.manifest,
            "skills": list(self.skills),
            "capabilities": list(self.capabilities),
            "checksum": self.checksum,
            "created_at": self.created_at,
        }


__all__ = [
    "AgentArtifact",
    "AGENT_STATUSES",
    "AGENT_DRAFT",
    "AGENT_VALIDATED",
    "AGENT_ACTIVE",
    "AGENT_DEPRECATED",
    "AGENT_DISABLED",
    "ENVIRONMENTS",
    "ENV_DEV",
    "ENV_TEST",
    "ENV_PRODUCTION",
    "DEPLOYMENT_STATUSES",
    "DEPLOYMENT_ACTIVE",
    "DEPLOYMENT_DISABLED",
    "AGENT_PERMISSIONS",
    "PERM_EXECUTE",
    "PERM_VIEW",
    "PERM_MANAGE",
    "SUBJECT_TYPES",
    "SUBJECT_USER",
    "SUBJECT_ROLE",
    "SUBJECT_DEPARTMENT",
]
