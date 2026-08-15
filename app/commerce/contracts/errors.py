"""Commerce error contracts.

``ToolError`` is the structured, typed error surface returned by Read Tools.
External platform raw errors never enter the LLM context; they are mapped to a
canonical code + category with safe details.  ``CommerceError`` /
``CommerceValidationError`` are the Python exceptions used internally.
"""

from dataclasses import dataclass, field

# Canonical error codes (v1)
INVALID_REQUEST = "INVALID_REQUEST"
SUBJECT_NOT_FOUND = "SUBJECT_NOT_FOUND"
AMBIGUOUS_REFERENCE = "AMBIGUOUS_REFERENCE"
PERMISSION_DENIED = "PERMISSION_DENIED"
DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
DATA_STALE = "DATA_STALE"
UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
RATE_LIMITED = "RATE_LIMITED"
TIMEOUT = "TIMEOUT"
INTERNAL_ERROR = "INTERNAL_ERROR"

ERROR_CODES = frozenset({
    INVALID_REQUEST,
    SUBJECT_NOT_FOUND,
    AMBIGUOUS_REFERENCE,
    PERMISSION_DENIED,
    DATA_UNAVAILABLE,
    DATA_INSUFFICIENT,
    DATA_STALE,
    UPSTREAM_UNAVAILABLE,
    RATE_LIMITED,
    TIMEOUT,
    INTERNAL_ERROR,
})

CATEGORY_REQUEST = "REQUEST"
CATEGORY_AUTHORIZATION = "AUTHORIZATION"
CATEGORY_DATA = "DATA"
CATEGORY_UPSTREAM = "UPSTREAM"
CATEGORY_INTERNAL = "INTERNAL"

ERROR_CATEGORIES = frozenset({
    CATEGORY_REQUEST,
    CATEGORY_AUTHORIZATION,
    CATEGORY_DATA,
    CATEGORY_UPSTREAM,
    CATEGORY_INTERNAL,
})

# code -> (category, retryable)
_ERROR_METADATA = {
    INVALID_REQUEST: (CATEGORY_REQUEST, False),
    SUBJECT_NOT_FOUND: (CATEGORY_DATA, False),
    AMBIGUOUS_REFERENCE: (CATEGORY_REQUEST, False),
    PERMISSION_DENIED: (CATEGORY_AUTHORIZATION, False),
    DATA_UNAVAILABLE: (CATEGORY_DATA, True),
    DATA_INSUFFICIENT: (CATEGORY_DATA, False),
    DATA_STALE: (CATEGORY_DATA, False),
    UPSTREAM_UNAVAILABLE: (CATEGORY_UPSTREAM, True),
    RATE_LIMITED: (CATEGORY_UPSTREAM, True),
    TIMEOUT: (CATEGORY_UPSTREAM, True),
    INTERNAL_ERROR: (CATEGORY_INTERNAL, True),
}


class CommerceError(Exception):
    """Base exception for the Commerce Employee Layer."""


class CommerceValidationError(CommerceError):
    """A contract or request failed validation (fail-closed)."""


@dataclass(frozen=True)
class ToolError:
    """Structured tool error contract.

    ``details_safe`` is what may be shown to a caller; raw upstream errors must
    be kept out of it (they go to logs/audit, not the LLM context).
    """

    code: str
    category: str
    retryable: bool
    message_key: str
    details_safe: dict = field(default_factory=dict)
    trace_id: str | None = None
    upstream_error_ref: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "details_safe", dict(self.details_safe or {}))
        if self.code not in ERROR_CODES:
            raise CommerceValidationError(f"unknown tool error code: {self.code}")

    @classmethod
    def from_code(
        cls,
        code: str,
        message_key: str = "",
        details_safe: dict | None = None,
        trace_id: str | None = None,
        upstream_error_ref: str | None = None,
    ) -> "ToolError":
        category, retryable = _ERROR_METADATA[code]
        return cls(
            code=code,
            category=category,
            retryable=retryable,
            message_key=message_key or code.lower(),
            details_safe=details_safe or {},
            trace_id=trace_id,
            upstream_error_ref=upstream_error_ref,
        )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "category": self.category,
            "retryable": self.retryable,
            "message_key": self.message_key,
            "details_safe": dict(self.details_safe),
            "trace_id": self.trace_id,
            "upstream_error_ref": self.upstream_error_ref,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ToolError":
        return cls(
            code=data["code"],
            category=data["category"],
            retryable=data["retryable"],
            message_key=data.get("message_key", ""),
            details_safe=data.get("details_safe", {}),
            trace_id=data.get("trace_id"),
            upstream_error_ref=data.get("upstream_error_ref"),
        )


__all__ = [
    "CommerceError",
    "CommerceValidationError",
    "ToolError",
    "ERROR_CODES",
    "ERROR_CATEGORIES",
    "CATEGORY_REQUEST",
    "CATEGORY_AUTHORIZATION",
    "CATEGORY_DATA",
    "CATEGORY_UPSTREAM",
    "CATEGORY_INTERNAL",
]
