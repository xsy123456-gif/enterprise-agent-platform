"""Agent intelligence optimization errors (Phase 17)."""

from app.core.errors import ApplicationError


class IntelligenceError(ApplicationError):
    """Base error for the intelligence optimization layer."""


class EvaluationError(IntelligenceError):
    """An evaluation failed or produced invalid data."""


class OptimizationError(IntelligenceError):
    """An optimization proposal is invalid or unsupported."""


class ImprovementError(IntelligenceError):
    """An improvement lifecycle transition is invalid."""


class ExperimentError(IntelligenceError):
    """An experiment is invalid or its decision is not allowed."""


class GovernanceDeniedError(IntelligenceError):
    """An optimization was denied by governance."""


class DeploymentDeniedError(IntelligenceError):
    """A version release/deployment was denied."""


__all__ = [
    "IntelligenceError",
    "EvaluationError",
    "OptimizationError",
    "ImprovementError",
    "ExperimentError",
    "GovernanceDeniedError",
    "DeploymentDeniedError",
]
