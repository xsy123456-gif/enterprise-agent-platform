"""Enterprise production platform errors (Phase 15)."""

from app.core.errors import ApplicationError


class ProductionError(ApplicationError):
    """Base error for the production operation layer."""


class QuotaExceededError(ProductionError):
    """A tenant quota limit was exceeded."""


class BudgetExceededError(ProductionError):
    """An agent cost budget was exceeded."""


class ExecutionTimeoutError(ProductionError):
    """An execution exceeded its configured timeout."""


class CircuitOpenError(ProductionError):
    """A dependency circuit breaker is open."""


class TenantIsolationViolationError(ProductionError):
    """A cross-tenant resource access was attempted."""


class KnowledgeAccessDeniedError(ProductionError):
    """Knowledge access was denied by governance."""


__all__ = [
    "ProductionError",
    "QuotaExceededError",
    "BudgetExceededError",
    "ExecutionTimeoutError",
    "CircuitOpenError",
    "TenantIsolationViolationError",
    "KnowledgeAccessDeniedError",
]
