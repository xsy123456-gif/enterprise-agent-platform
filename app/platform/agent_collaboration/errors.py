"""Multi-agent collaboration errors (Phase 14)."""

from app.core.errors import ApplicationError


class CollaborationError(ApplicationError):
    """Base error for the multi-agent collaboration runtime."""


class CycleDetectedError(CollaborationError):
    """The agent task graph contains a cycle (must be a DAG)."""


class MaxDepthExceededError(CollaborationError):
    """The agent task graph exceeds the configured max depth."""


class DelegationDeniedError(CollaborationError):
    """A delegation was denied by collaboration governance."""


class ContextAccessDeniedError(CollaborationError):
    """A context envelope access was denied."""


class AgentUnavailableError(CollaborationError):
    """A target agent is not ACTIVE / not runnable."""


class CollaborationConflictError(CollaborationError):
    """A conflict could not be resolved deterministically."""


__all__ = [
    "CollaborationError",
    "CycleDetectedError",
    "MaxDepthExceededError",
    "DelegationDeniedError",
    "ContextAccessDeniedError",
    "AgentUnavailableError",
    "CollaborationConflictError",
]
