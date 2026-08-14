"""Permission subsystem errors.

Internal domain errors; authorization outcomes are expressed via
``ReasonCode`` in ``PermissionDecision``, never via exceptions leaking out of
``PermissionService.evaluate``.
"""


class PermissionDomainError(Exception):
    """Base class for all Permission subsystem errors."""


class PermissionValidationError(PermissionDomainError):
    """A request or policy failed validation."""


class PermissionPolicyError(PermissionDomainError):
    """A policy is malformed or the policy set is invalid."""


class PermissionEvaluationError(PermissionDomainError):
    """The evaluator could not safely interpret a condition."""


class PermissionUnavailableError(PermissionDomainError):
    """No valid policy snapshot is available."""
