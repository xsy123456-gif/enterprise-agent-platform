from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class MemoryReadGrant:
    allowed_types: frozenset[str] = field(default_factory=frozenset)

    def permits(self, requested_types):
        return not requested_types or set(requested_types).issubset(self.allowed_types)


class MemoryAuthorizationProvider(Protocol):
    def authorize_ingest(self, principal, scope, source) -> None:
        ...

    def authorize_read(self, principal, scope, requested_types) -> MemoryReadGrant:
        ...

    def authorize_write_candidate(self, principal, scope, candidate_type) -> None:
        ...


class AllowAllMemoryAuthorizationProvider:
    """Explicit test/development policy; never used as a production default."""

    def authorize_ingest(self, principal, scope, source):
        return None

    def authorize_read(self, principal, scope, requested_types):
        return MemoryReadGrant(frozenset(requested_types or ()))

    def authorize_write_candidate(self, principal, scope, candidate_type):
        return None


class DenyByDefaultMemoryAuthorizationProvider:
    def authorize_ingest(self, principal, scope, source):
        raise PermissionError("Memory ingest authorization is required")

    def authorize_read(self, principal, scope, requested_types):
        raise PermissionError("Memory read authorization is required")

    def authorize_write_candidate(self, principal, scope, candidate_type):
        raise PermissionError("Memory write authorization is required")
