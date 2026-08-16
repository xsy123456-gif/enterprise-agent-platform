"""Enterprise Agent Control Plane errors (Phase 13)."""

from app.core.errors import ApplicationError


class AgentControlError(ApplicationError):
    """Base error for the enterprise agent control plane."""


class AgentValidationError(AgentControlError):
    """An agent manifest / artifact failed validation."""


class AgentNotActiveError(AgentControlError):
    """The requested agent has no ACTIVE version."""


class ManifestError(AgentControlError):
    """An enterprise agent manifest is structurally invalid or unparsable."""


class DeploymentError(AgentControlError):
    """An agent deployment failed (unknown version / environment / not active)."""


class AgentAccessDeniedError(AgentControlError):
    """A subject is not authorized to access an agent."""


class DeploymentVersionMismatchError(AgentControlError):
    """A runtime projection version/checksum does not match the control plane."""


__all__ = [
    "AgentControlError",
    "AgentValidationError",
    "AgentNotActiveError",
    "ManifestError",
    "DeploymentError",
    "AgentAccessDeniedError",
    "DeploymentVersionMismatchError",
]
