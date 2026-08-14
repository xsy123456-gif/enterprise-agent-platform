"""Trusted principal — an upstream-authenticated subject reference."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TrustedPrincipal:
    principal_id: str
    source: str = "local"
    assertion_id: str | None = None
    issued_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.principal_id:
            raise ValueError("principal_id is required")
