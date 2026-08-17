"""Employee Agent errors (Phase 12)."""

from app.commerce.contracts.errors import CommerceError


class AgentError(CommerceError):
    """Base error for the Employee Agent layer."""


class AgentValidationError(AgentError):
    """An agent definition / manifest failed lifecycle or capability validation."""


class AgentNotActiveError(AgentError):
    """The requested agent has no ACTIVE version."""


class AgentManifestError(AgentError):
    """An agent manifest is structurally invalid or unparsable."""


class UnknownSkillForAgent(AgentError):
    """A skill referenced by an agent is unknown or has no such version."""


class ResourceOwnershipError(AgentError):
    """A message referenced a business resource not owned by the trusted tenant.

    Raised before any diagnostic execution.  The caller must map it to a safe
    deny (404 / NOT_FOUND) and must not reveal whether the resource exists.
    """


__all__ = [
    "AgentError",
    "AgentValidationError",
    "AgentNotActiveError",
    "AgentManifestError",
    "UnknownSkillForAgent",
    "ResourceOwnershipError",
]
