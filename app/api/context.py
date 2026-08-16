"""API request context (Phase 18.12).

Carries the HTTP correlation identity + the authenticated principal + the
trusted execution context.  ``client_metadata`` holds only safe protocol data
(user-agent, locale) — never permissions / roles / scope.
"""

from dataclasses import dataclass, field

from app.core.time import utc_now


@dataclass
class ApiRequestContext:
    request_id: str
    authenticated_principal: object
    trusted_context: object
    received_at: str = field(default_factory=utc_now)
    client_metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "client_metadata",
                           dict(self.client_metadata or {}))


__all__ = ["ApiRequestContext"]
