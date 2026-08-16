"""Product API error contract (Phase 18.12).

A single, stable public error envelope.  The HTTP adapter maps existing Domain
errors (and its own validation errors) into ``ApiError``; it never re-decides
business failure and never leaks secrets / stack traces.
"""

from dataclasses import dataclass, field


class ApiErrorCode:
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_CREDENTIAL = "INVALID_CREDENTIAL"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    INVALID_STATE = "INVALID_STATE"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    INVALID_RESUME_SIGNAL = "INVALID_RESUME_SIGNAL"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    BUSINESS_VALIDATION_FAILED = "BUSINESS_VALIDATION_FAILED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


@dataclass
class ApiError(Exception):
    code: str
    message: str
    http_status: int = 400
    details: dict = field(default_factory=dict)

    def envelope(self, request_id="", trace_id=None):
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": request_id,
                "trace_id": trace_id,
                "details": dict(self.details),
            }
        }


def not_found(resource: str) -> ApiError:
    return ApiError(
        ApiErrorCode.RESOURCE_NOT_FOUND,
        f"{resource} not found.", http_status=404,
    )


def permission_denied() -> ApiError:
    return ApiError(
        ApiErrorCode.PERMISSION_DENIED,
        "You do not have permission to access this resource.", http_status=403,
    )


def invalid_state(message: str) -> ApiError:
    return ApiError(ApiErrorCode.INVALID_STATE, message, http_status=409)


__all__ = [
    "ApiError",
    "ApiErrorCode",
    "not_found",
    "permission_denied",
    "invalid_state",
]
