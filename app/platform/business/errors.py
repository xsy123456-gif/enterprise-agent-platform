"""Enterprise business expansion errors (Phase 16)."""

from app.core.errors import ApplicationError


class BusinessError(ApplicationError):
    """Base error for the business expansion layer."""


class PackageValidationError(BusinessError):
    """A vertical agent package failed validation."""


class PackageNotPublishedError(BusinessError):
    """A package is not PUBLISHED and cannot be installed."""


class ApprovalRequiredError(BusinessError):
    """An action requires approval and has not been approved."""


class ActionExecutionError(BusinessError):
    """A business action execution failed."""


class WorkflowError(BusinessError):
    """A workflow failed or is invalid."""


class EntitlementError(BusinessError):
    """A tenant lacks the entitlement for an action/feature."""


__all__ = [
    "BusinessError",
    "PackageValidationError",
    "PackageNotPublishedError",
    "ApprovalRequiredError",
    "ActionExecutionError",
    "WorkflowError",
    "EntitlementError",
]
